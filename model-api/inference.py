"""
inference.py -- Preprocessing, calibration loading, and the full
calibrated inference pipeline for FracNet.

MAIN MODEL: stop-gradient encoder + standard CrossEntropyLoss
(Dice 0.6402, IoU 0.5235, AUROC 0.9665), deployment threshold 0.5
(chosen for a balanced false-positive/false-negative rate).

Clinician-facing output:
  - prediction               : "Fractured" / "Healthy"
  - confidence_display        : e.g. "89.4% (High)"
  - ood_score / ood_threshold : raw Mahalanobis score + calibrated p95
                                 threshold (26.883) -- NO label banding,
                                 the frontend (Astro) computes its own
                                 Low/Moderate/High display from these
  - is_novel                  : bool, ood_score > ood_threshold
  - cross_head_disagreement   : bool, flags cases where segmentation
                                 finds a substantial, coherent region
                                 despite a "Healthy" classification
                                 (calibrated p97 threshold on
                                 confidence-weighted mass within the
                                 largest connected component -- 776.56
                                 for THIS checkpoint, distinct from the
                                 Focal Loss checkpoint's 1667.60)

Expects three artifact files on disk (paths via env vars or passed
explicitly):
  - MODEL_BUNDLE_PATH            : fracnet_main_bundle.pth
  - ISOTONIC_CALIBRATOR_PATH     : isotonic_calibrator.pkl
  - UNCERTAINTY_THRESHOLDS_PATH  : uncertainty_thresholds.json
      (must include: ood_threshold_global, seg_aleatoric_threshold,
       cls_disagreement_threshold, cls_decision_threshold (0.5),
       seg_mask_threshold, cross_head_mass_threshold)

Usage (from main.py):
    from inference import InferenceEngine
    engine = InferenceEngine()
    result = engine.predict(pil_image)
"""

import os
import io
import json
import base64

import numpy as np
import cv2
from PIL import Image
from skimage import exposure

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms

import joblib

from model import build_model, IMAGE_SIZE

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


# ============================================================
# Preprocessing -- CLAHE removed, matches this checkpoint's
# actual training pipeline (percentile clipping + normalization only).
# ============================================================
def apply_clahe(image):
    p1, p99 = np.percentile(image, (1, 99))
    img_clipped = np.clip(image, p1, p99).astype(np.float32)
    img_min, img_max = np.min(img_clipped), np.max(img_clipped)
    img_norm = (img_clipped - img_min) / (img_max - img_min) if img_max > img_min else img_clipped
    return (img_norm * 255).astype(np.uint8)


def resize_with_padding(image, target_size=IMAGE_SIZE, interpolation=cv2.INTER_LINEAR):
    h, w = image.shape[:2]
    scale = target_size / max(h, w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=interpolation)
    pad_top = (target_size - new_h) // 2
    pad_left = (target_size - new_w) // 2
    return cv2.copyMakeBorder(
        resized, pad_top, target_size - new_h - pad_top,
        pad_left, target_size - new_w - pad_left, cv2.BORDER_CONSTANT, value=0
    )


def preprocess_pil_image(pil_image):
    gray = np.array(pil_image.convert("L"))
    clahe_img = apply_clahe(gray)
    padded = resize_with_padding(clahe_img, IMAGE_SIZE, cv2.INTER_LINEAR)
    img_array = np.stack([padded] * 3, axis=0).astype(np.float32) / 255.0
    tensor = torch.from_numpy(img_array).float()
    normalize = transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    return normalize(tensor)


# ============================================================
# Checkpoint bundle loading
# ============================================================
def load_fracnet_bundle(model, filepath, device):
    checkpoint = torch.load(filepath, map_location=device, weights_only=False)
    assert checkpoint['config_hash']['bottleneck_dim'] == 512, "Architecture mismatch: bottleneck dim changed!"
    model.load_state_dict(checkpoint['model_state'])
    model.eval()
    return model, checkpoint['gaussians']


# ============================================================
# Epistemic uncertainty (Mahalanobis distance)
# ============================================================
def mahalanobis_distance(feature, mean, precision):
    diff = feature - mean
    return float(np.sqrt(diff @ precision @ diff))


def compute_ood_score(feature, gaussians):
    distances = {cls: mahalanobis_distance(feature, g["mean"], g["precision"]) for cls, g in gaussians.items()}
    return {
        "ood_score": min(distances.values()),
        "predicted_class": min(distances, key=distances.get),
        "distances": distances,
    }


def enable_mc_dropout(model):
    """Puts only Dropout / Dropout2d layers into train mode.
    BatchNorm and everything else stays in eval mode."""
    for module in model.modules():
        if isinstance(module, (nn.Dropout, nn.Dropout2d)):
            module.train()


# ============================================================
# Cross-head consistency check -- confidence-weighted mass within
# the largest connected segmentation component. Calibrated FRESH for
# this checkpoint at p97 of healthy validation images
# (threshold=776.56, 3.1% false-alarm rate). NOT gated on classifier
# confidence, so it also catches confidently-wrong classifications --
# the highest-stakes case.
# ============================================================
def compute_largest_component_mass(prob_map, mask_binary):
    pred_binary_uint8 = mask_binary.astype(np.uint8)
    n_components, labels_img, stats, _ = cv2.connectedComponentsWithStats(pred_binary_uint8)
    if n_components > 1:
        largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        largest_component_mask = (labels_img == largest_label)
        return float(prob_map[largest_component_mask].sum())
    return 0.0


# ============================================================
# Classification confidence: isotonic-calibrated probability,
# decided at the deployment threshold (0.5 for this checkpoint)
# ============================================================
def calibrated_classification_confidence_isotonic(class_logits, iso_model, deploy_threshold):
    raw_prob = F.softmax(class_logits.cpu(), dim=1)[:, 1].item()
    calibrated_prob_fracture = float(iso_model.predict([raw_prob])[0])
    predicted_class = 1 if calibrated_prob_fracture >= deploy_threshold else 0
    confidence = calibrated_prob_fracture if predicted_class == 1 else (1 - calibrated_prob_fracture)
    return confidence, predicted_class


def _reliability_label(score_0_100):
    if score_0_100 >= 80:
        return "High"
    elif score_0_100 >= 55:
        return "Moderate"
    else:
        return "Low"


def _classification_confidence_score(iso_calibrated_confidence, cls_pred_disagreement, cls_disagreement_threshold):
    """Disagreement-only formula -- validated significant on this
    checkpoint (Mann-Whitney p<0.0001, ~15x higher disagreement on
    wrong predictions than correct ones)."""
    base_score = iso_calibrated_confidence * 100
    if cls_pred_disagreement > cls_disagreement_threshold:
        excess = (cls_pred_disagreement - cls_disagreement_threshold) / max(1 - cls_disagreement_threshold, 1e-6)
        penalty = min(excess * 30, 30)
        base_score -= penalty
    final_score = max(0, min(100, base_score))
    return {
        "score": round(final_score, 1),
        "label": _reliability_label(final_score),
        "calibrated_probability": round(iso_calibrated_confidence * 100, 1),
        "mc_disagreement_penalty_applied": cls_pred_disagreement > cls_disagreement_threshold,
    }


def _segmentation_reliability_score(aleatoric_var, seg_aleatoric_threshold):
    """INTERNAL ONLY. NOTE: subgroup analysis on this checkpoint found
    this signal catches confident-imprecise segmentation failures
    (p=0.035) but NOT confident-silence failures (p=1.000) -- a known,
    documented blind spot for roughly half this checkpoint's
    catastrophic segmentation cases."""
    ratio = aleatoric_var / max(seg_aleatoric_threshold, 1e-12)
    score = max(0, min(100, 100 * (1 - ratio)))
    return {
        "score": round(score, 1),
        "label": _reliability_label(score),
        "raw_aleatoric_variance": aleatoric_var,
    }


# ============================================================
# Heatmap rendering -- outline only, transparent interior
# ============================================================
def render_fracture_heatmap(prob_map, image_display, outline_threshold=0.5,
                             outline_color=(255, 0, 0), outline_thickness=2):
    pred_binary = (prob_map > outline_threshold).astype(np.uint8)
    overlay_uint8 = (np.clip(image_display, 0, 1) * 255).astype(np.uint8).copy()
    if pred_binary.sum() > 0:
        contours, _ = cv2.findContours(pred_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay_uint8, contours, -1, outline_color, outline_thickness)
    return overlay_uint8.astype(np.float32) / 255.0


def image_array_to_base64_png(image_array_0_1):
    img_uint8 = (np.clip(image_array_0_1, 0, 1) * 255).astype(np.uint8)
    pil_img = Image.fromarray(img_uint8)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ============================================================
# InferenceEngine -- loads everything once at startup
# ============================================================
class InferenceEngine:
    def __init__(self,
                 model_bundle_path=None,
                 isotonic_calibrator_path=None,
                 uncertainty_thresholds_path=None,
                  mc_passes=3):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        model_bundle_path = model_bundle_path or os.environ.get(
            "MODEL_BUNDLE_PATH", "artifacts/fracnet_main_bundle.pth")
        isotonic_calibrator_path = isotonic_calibrator_path or os.environ.get(
            "ISOTONIC_CALIBRATOR_PATH", "artifacts/isotonic_calibrator.pkl")
        uncertainty_thresholds_path = uncertainty_thresholds_path or os.environ.get(
            "UNCERTAINTY_THRESHOLDS_PATH", "artifacts/uncertainty_thresholds.json")

        self.mc_passes = mc_passes

        self.model = build_model(self.device)
        self.model, self.gaussians = load_fracnet_bundle(self.model, model_bundle_path, self.device)
        self.model.eval()

        self.iso_reg = joblib.load(isotonic_calibrator_path)

        with open(uncertainty_thresholds_path, "r") as f:
            thresholds = json.load(f)
        self.ood_threshold = thresholds["ood_threshold_global"]
        self.seg_aleatoric_threshold = thresholds["seg_aleatoric_threshold"]
        self.cls_disagreement_threshold = thresholds["cls_disagreement_threshold"]
        self.deploy_threshold = thresholds["cls_decision_threshold"]  # 0.5 for this checkpoint
        self.cross_head_mass_threshold = thresholds["cross_head_mass_threshold"]

        print(f"[InferenceEngine] Ready on {self.device}. "
              f"deploy_threshold={self.deploy_threshold}, "
              f"OOD threshold={self.ood_threshold:.3f}, "
              f"seg aleatoric threshold={self.seg_aleatoric_threshold:.6f}, "
              f"cls disagreement threshold={self.cls_disagreement_threshold:.3f}, "
              f"cross_head_mass_threshold={self.cross_head_mass_threshold:.2f}")

    def predict(self, pil_image, include_heatmap=True, include_original=True):
        """
        Runs the complete calibrated inference pipeline on a single
        uploaded PIL image. Returns clinician-facing fields (prediction,
        confidence_display, ood_score, ood_threshold, is_novel,
        cross_head_disagreement) plus internal_* fields for logging --
        filter internal_* before returning JSON to the frontend.
        """
        image_tensor = preprocess_pil_image(pil_image)
        image_batch = image_tensor.unsqueeze(0).to(self.device)

        # --- PASS 1: standard eval ---
        self.model.eval()
        with torch.no_grad():
            mask_logits, class_logits = self.model(image_batch)
            feature = self.model.gap(self.model.last_features).squeeze().cpu().numpy()
            prob_map = torch.sigmoid(mask_logits).squeeze().cpu().numpy()

        calibrated_confidence, predicted_class = calibrated_classification_confidence_isotonic(
            class_logits, self.iso_reg, self.deploy_threshold
        )

        ood_result = compute_ood_score(feature, self.gaussians)
        ood_score = ood_result["ood_score"]
        is_novel = ood_score > self.ood_threshold

        # --- PASS 2: MC-Dropout, both heads ---
        self.model.eval()
        enable_mc_dropout(self.model)
        mc_masks, mc_class_probs = [], []
        with torch.no_grad():
            for _ in range(self.mc_passes):
                m_logits, c_logits = self.model(image_batch)
                mc_masks.append(torch.sigmoid(m_logits).cpu().numpy())
                mc_class_probs.append(F.softmax(c_logits, dim=1).cpu().numpy())
        self.model.eval()

        mc_stack = np.stack(mc_masks)
        aleatoric_map = np.var(mc_stack, axis=0)[0, 0]
        aleatoric_mean = float(aleatoric_map.mean())

        mc_class_stack = np.stack(mc_class_probs).squeeze(1)
        mc_pred_classes = []
        for p in mc_class_stack[:, 1]:
            cal_p = float(self.iso_reg.predict([p])[0])
            mc_pred_classes.append(1 if cal_p >= self.deploy_threshold else 0)
        mc_pred_classes = np.array(mc_pred_classes)
        cls_pred_disagreement = float((mc_pred_classes != predicted_class).mean())

        classification_confidence = _classification_confidence_score(
            calibrated_confidence, cls_pred_disagreement, self.cls_disagreement_threshold
        )
        segmentation_reliability = _segmentation_reliability_score(
            aleatoric_mean, self.seg_aleatoric_threshold
        )

        mask_binary = (prob_map > 0.5).astype(np.float32)
        predicted_class_label = "Fractured" if predicted_class == 1 else "Healthy"

        # --- Cross-head consistency check ---
        largest_component_mass = compute_largest_component_mass(prob_map, mask_binary)
        cross_head_disagreement = (predicted_class == 0) and (largest_component_mass > self.cross_head_mass_threshold)

        result = {
            # ---------- Clinician-facing ----------
            "prediction": predicted_class_label,
            "confidence_display": f"{classification_confidence['score']}% ({classification_confidence['label']})",
            "ood_score": round(ood_score, 3),
            "ood_threshold": round(self.ood_threshold, 3),
            "is_novel": is_novel,
            "cross_head_disagreement": cross_head_disagreement,

            # ---------- Internal only -- filter out before returning to clinician ----------
            "internal_confidence_score": classification_confidence["score"],
            "internal_confidence_label": classification_confidence["label"],
            "internal_confidence_calibrated_probability": classification_confidence["calibrated_probability"],
            "internal_confidence_mc_disagreement": round(cls_pred_disagreement, 3),
            "internal_mask_area_pixels": int(mask_binary.sum()),
            "internal_largest_component_mass": round(largest_component_mass, 2),
            "internal_segmentation_reliability_score": segmentation_reliability["score"],
            "internal_segmentation_reliability_label": segmentation_reliability["label"],
        }

        # --- Image outputs, base64-encoded for JSON transport ---
        img_disp = image_tensor[0].numpy() * IMAGENET_STD[0] + IMAGENET_MEAN[0]
        img_disp = np.clip(img_disp, 0, 1)
        img_gray_rgb = np.stack([img_disp] * 3, axis=-1)

        if include_original:
            result["original_image_base64"] = image_array_to_base64_png(img_gray_rgb)

        if include_heatmap:
            heatmap_overlay = render_fracture_heatmap(prob_map, img_gray_rgb)
            result["heatmap_png_base64"] = image_array_to_base64_png(heatmap_overlay)

        return result
