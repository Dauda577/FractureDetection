FROM python:3.11-slim

WORKDIR /app

# System dependencies for opencv / scikit-image + wget for model download
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model.py inference.py main.py ./

# Download model artifacts from Hugging Face Hub at build time
RUN mkdir -p artifacts && \
    wget -q https://huggingface.co/immortal577/fracnet-model/resolve/main/fracnet_main_bundle.pth -O artifacts/fracnet_main_bundle.pth && \
    wget -q https://huggingface.co/immortal577/fracnet-model/resolve/main/isotonic_calibrator.pkl -O artifacts/isotonic_calibrator.pkl && \
    wget -q https://huggingface.co/immortal577/fracnet-model/resolve/main/uncertainty_thresholds.json -O artifacts/uncertainty_thresholds.json

ENV MODEL_BUNDLE_PATH=/app/artifacts/fracnet_main_bundle.pth
ENV ISOTONIC_CALIBRATOR_PATH=/app/artifacts/isotonic_calibrator.pkl
ENV UNCERTAINTY_THRESHOLDS_PATH=/app/artifacts/uncertainty_thresholds.json

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
