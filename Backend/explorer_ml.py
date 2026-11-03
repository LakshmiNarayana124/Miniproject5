"""
INTELLIWATCH - EXPLORER ML MODEL
Dedicated ML model for the 3D Sensor Explorer.
Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import json
import logging
import os
from datetime import datetime, timezone

import model_registry as _mr

logger = logging.getLogger(__name__)

EXPLORER_FAMILY = "explorer"


def _feature_vector(arrangement, readings):
    """Extract a numeric feature vector from arrangement + per-component readings (Req 5.3)."""
    features = {}
    # Arrangement: count of placed components per type
    if isinstance(arrangement, list):
        for comp in arrangement:
            ctype = comp.get("type", "unknown") if isinstance(comp, dict) else str(comp)
            features[f"count_{ctype}"] = features.get(f"count_{ctype}", 0) + 1
        features["total_components"] = len(arrangement)
    # Per-component sensor readings
    if isinstance(readings, dict):
        for comp_id, sensor_vals in readings.items():
            if isinstance(sensor_vals, dict):
                for k, v in sensor_vals.items():
                    try:
                        features[f"{comp_id}_{k}"] = float(v)
                    except (TypeError, ValueError):
                        pass
    return features


def classify(arrangement, readings):
    """Classify an explorer workspace state (Req 5.2, Property 19).

    Returns {"label": str, "confidence": float, "model_version": str}.
    """
    fv = _feature_vector(arrangement, readings)
    if not fv:
        return {"label": "normal", "confidence": 0.5, "model_version": "none"}

    model = _mr.registry.active_model(EXPLORER_FAMILY)
    if model is not None:
        try:
            fv_list = list(fv.values())
            proba = model.predict_proba([fv_list])
            classes = getattr(model, "classes_", ["normal", "anomaly"])
            if hasattr(proba, "tolist"):
                proba = proba.tolist()
            row = proba[0] if proba else [0.5, 0.5]
            best_idx = max(range(len(row)), key=lambda i: row[i])
            label = classes[best_idx] if best_idx < len(classes) else "normal"
            confidence = float(row[best_idx]) if row else 0.5
            confidence = max(0.0, min(1.0, confidence))
            return {
                "label": label,
                "confidence": confidence,
                "model_version": getattr(model, "version", "unknown"),
            }
        except Exception as exc:
            logger.warning("Explorer model inference failed: %s", exc)

    # Heuristic fallback: anomaly if any reading is extreme
    vals = [v for v in fv.values() if isinstance(v, (int, float))]
    is_anomaly = any(abs(v) > 5.0 for v in vals)
    return {
        "label": "anomaly" if is_anomaly else "normal",
        "confidence": 0.6,
        "model_version": "heuristic",
    }


def train_explorer_model(arrangements_labels=None):
    """Train and register the explorer ML model (Req 5.1, 5.3).

    ``arrangements_labels`` is a list of (arrangement, readings, label) tuples.
    When None, a minimal synthetic dataset is used so the model registers.
    """
    from training_pipeline import EnsembleModel, UnsupervisedModel, persist_model

    version = datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S")

    if arrangements_labels:
        X, y = [], []
        for arr, rdg, lbl in arrangements_labels:
            fv = _feature_vector(arr, rdg)
            X.append(list(fv.values()))
            y.append(lbl)
    else:
        # Minimal synthetic data so the model exists
        X = [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [0.1, 0.2, 0.3], [6.0, 7.0, 8.0]]
        y = ["normal", "anomaly", "normal", "anomaly"]

    try:
        from sklearn.ensemble import IsolationForest
        from training_pipeline import UnsupervisedModel
        import numpy as np
        estimator = IsolationForest(n_estimators=50, contamination="auto", random_state=42)
        estimator.fit(np.array(X))
        feature_names = [f"f{i}" for i in range(len(X[0]))]
        model = UnsupervisedModel(estimator, feature_names, version)
        model.classes_ = ["normal", "anomaly"]
    except Exception as exc:
        logger.warning("Explorer model training error: %s", exc)
        return None

    out_dir = os.path.join(os.path.dirname(__file__), "models")
    try:
        persist_model(model, EXPLORER_FAMILY, out_dir, dataset_hash="explorer", version=version)
        _mr.registry.register(model, family=EXPLORER_FAMILY, version=version)
        _mr.registry.set_active(EXPLORER_FAMILY, version)
        logger.info("Explorer model %s registered and activated.", version)
    except Exception as exc:
        logger.warning("Explorer model registration failed: %s", exc)

    return model
