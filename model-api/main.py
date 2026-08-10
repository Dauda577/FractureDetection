"""
main.py -- FastAPI service exposing FracNet inference as a REST API.

MAIN MODEL: stop-gradient encoder + standard CrossEntropyLoss
(Dice 0.6402), deployment threshold 0.5.

Endpoints:
  GET  /health   -- basic liveness check
  POST /predict  -- accepts an uploaded X-ray image, returns the
                     clinician-facing output: prediction, confidence_display,
                     ood_score, ood_threshold, is_novel,
                     cross_head_disagreement, original_image_base64,
                     heatmap_png_base64.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import io
import logging
import time

import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from inference import InferenceEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fracnet-api")

app = FastAPI(
    title="FracNet Inference API",
    description="Fracture detection with calibrated confidence, OOD scoring, "
                "cross-head consistency checking, and heatmap localization.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: replace with your Astro app's domain(s) in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = None


@app.on_event("startup")
def load_engine():
    global engine
    logger.info("Loading FracNet inference engine...")
    start = time.time()
    engine = InferenceEngine()
    logger.info(f"Engine loaded in {time.time() - start:.1f}s")


@app.get("/health")
def health():
    return {
        "status": "ok" if engine is not None else "loading",
        "device": str(engine.device) if engine is not None else None,
    }


ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    if engine is None:
        raise HTTPException(status_code=503, detail="Model is still loading, try again shortly.")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: PNG, JPG, JPEG."
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit.")

    try:
        pil_image = Image.open(io.BytesIO(raw_bytes))
        pil_image.verify()
        pil_image = Image.open(io.BytesIO(raw_bytes))
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

    original = np.array(pil_image)
    if original.ndim == 3 and original.shape[2] >= 3:
        ch = [original[:, :, c].ravel().astype(np.float64) for c in range(3)]
        min_corr = min(
            np.corrcoef(ch[0], ch[1])[0, 1],
            np.corrcoef(ch[0], ch[2])[0, 1],
            np.corrcoef(ch[1], ch[2])[0, 1],
        )
        if min_corr < 0.92:
            raise HTTPException(
                status_code=400,
                detail="This does not appear to be an X-ray image. Please upload a medical X-ray."
            )

    # Input guards — validate image quality before inference
    w, h = pil_image.size
    if w < 64 or h < 64:
        raise HTTPException(status_code=400, detail=f"Image too small ({w}×{h}px). Minimum: 64×64 pixels.")

    img_array = np.array(pil_image.convert("L"), dtype=np.float64)
    if np.std(img_array) < 5.0:
        raise HTTPException(status_code=400, detail="Image appears to be a solid color. Please upload a valid X-ray.")

    p1, p99 = np.percentile(img_array, (1, 99))
    if p99 - p1 < 10:
        raise HTTPException(status_code=400, detail="Image has insufficient dynamic range. Please upload a valid X-ray.")

    start = time.time()
    try:
        result = engine.predict(pil_image)
    except Exception as e:
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
    inference_time = time.time() - start

    # Filter out internal-only diagnostic fields before returning to the
    # clinician-facing frontend -- log them server-side instead.
    clinician_response = {k: v for k, v in result.items() if not k.startswith("internal_")}
    clinician_response["inference_time_sec"] = round(inference_time, 3)

    logger.info(
        f"Prediction: {result['prediction']} "
        f"(confidence={result['confidence_display']}, "
        f"ood={result['ood_score']}/{result['ood_threshold']} [{'NOVEL' if result['is_novel'] else 'known'}], "
        f"cross_head_disagreement={result['cross_head_disagreement']}, "
        f"seg_reliability={result['internal_segmentation_reliability_label']}) "
        f"in {inference_time:.2f}s"
    )

    if result["cross_head_disagreement"]:
        logger.warning(
            f"Cross-head disagreement flagged: segmentation found a substantial region "
            f"(mass={result['internal_largest_component_mass']}) despite 'Healthy' classification."
        )

    return clinician_response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)