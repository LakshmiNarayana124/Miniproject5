"""
INTELLIWATCH - OBSERVABILITY SERVICE
Model/system status responses and degradation alerting.
Requirements: 14.1-14.4
"""

import json
import logging
from datetime import datetime, timezone

import database
import model_registry as _mr

logger = logging.getLogger(__name__)

# Degradation threshold (Req 14.4): alert when metric drops >0.05 below target
DEGRADATION_MARGIN = 0.05
TABULAR_ACCURACY_TARGET = 0.92
UNSUPERVISED_F1_TARGET = 0.90

# Module-level current state (set by EquipmentController / IntelliWatchBrain)
_current_status = {"status": "NORMAL", "intent": "RUN", "timestamp": None}
_degradation_alerts = []


def set_current_status(status: str, intent: str):
    """Update the live system status (called by brain/controller)."""
    _current_status["status"] = status
    _current_status["intent"] = intent
    _current_status["timestamp"] = datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------
# 11.1 — Model status response (Req 14.1)
# --------------------------------------------------------
def get_model_status(family: str = "ensemble"):
    """Return active model version, last training timestamp, metrics (Req 14.1)."""
    registry = _mr.registry
    model = registry.active_model(family)
    if model is None:
        return {"family": family, "active": False, "version": None, "metrics": {}}
    version = getattr(model, "version", "unknown")
    manifest = registry.get_manifest(family, version) or {}
    return {
        "family": family,
        "active": True,
        "version": version,
        "training_timestamp": manifest.get("training_timestamp"),
        "dataset_hash": manifest.get("dataset_hash"),
        "metrics": manifest.get("metrics", {}),
    }


def get_all_model_statuses():
    """Return status for all families."""
    families = ["tabular", "unsupervised", "sequence", "ensemble", "explorer"]
    return {f: get_model_status(f) for f in families}


# --------------------------------------------------------
# 11.1 — System status response (Req 14.2)
# --------------------------------------------------------
def get_system_status(iot_layer=None):
    """Return current system status, control intent, and device status (Req 14.2)."""
    devices = []
    if iot_layer is not None:
        try:
            devices = iot_layer.list_devices()
        except Exception:
            pass
    return {
        "system_status": _current_status.get("status", "NORMAL"),
        "control_intent": _current_status.get("intent", "RUN"),
        "timestamp": _current_status.get("timestamp"),
        "edge_devices": devices,
    }


# --------------------------------------------------------
# 11.2 — Degradation alerting (Req 14.4)
# --------------------------------------------------------
def check_model_degradation():
    """Raise alerts when deployed metrics fall >0.05 below target (Req 14.4)."""
    alerts = []
    for family in ["tabular", "unsupervised", "ensemble"]:
        info = get_model_status(family)
        if not info.get("active"):
            continue
        metrics = info.get("metrics", {})
        if family == "unsupervised":
            f1 = metrics.get("f1", 1.0)
            if f1 < UNSUPERVISED_F1_TARGET - DEGRADATION_MARGIN:
                alerts.append({
                    "family": family,
                    "metric": "f1",
                    "value": f1,
                    "target": UNSUPERVISED_F1_TARGET,
                    "shortfall": round(UNSUPERVISED_F1_TARGET - f1, 4),
                })
        else:
            acc = metrics.get("accuracy", 1.0)
            if acc < TABULAR_ACCURACY_TARGET - DEGRADATION_MARGIN:
                alerts.append({
                    "family": family,
                    "metric": "accuracy",
                    "value": acc,
                    "target": TABULAR_ACCURACY_TARGET,
                    "shortfall": round(TABULAR_ACCURACY_TARGET - acc, 4),
                })
    global _degradation_alerts
    _degradation_alerts = alerts
    return alerts


def get_degradation_alerts():
    return _degradation_alerts


# --------------------------------------------------------
# 11.2 — Event log (Req 14.3)
# --------------------------------------------------------
def log_event(event_type: str, outcome: str, detail: dict = None):
    """Log a training/recalibration/feedback event (Req 14.3)."""
    database.record_audit_entry(
        category=event_type,
        detail_json=json.dumps({"outcome": outcome, **(detail or {})}),
    )


# --------------------------------------------------------
# Accuracy trend
# --------------------------------------------------------
def get_accuracy_trend(family: str):
    """Return accuracy trend rows for a model family (Req 8.5)."""
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT at.f1_score, at.measured_at
            FROM accuracy_trend at
            JOIN ml_models m ON at.model_id = m.id
            WHERE m.family = ?
            ORDER BY at.measured_at ASC
        """, (family,)).fetchall()
        return [{"f1_score": r["f1_score"], "measured_at": r["measured_at"]} for r in rows]
    finally:
        conn.close()
