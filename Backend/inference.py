"""
INTELLIWATCH - INFERENCE MODULE
Version: 1.0

Purpose:
- Per-window inference that determines the System_Status from a feature
  vector using the active trained model from the registry (Requirement 11.1).
- Cold-start fallback to the existing Welford engine
  (``intelliwatch_engine.py``) when no trained model is active, so the system
  degrades gracefully rather than failing (design §12).
- ``status_from_probs`` combines the model output with ISO band rules and
  takes the most severe of model + threshold outputs (Requirement 7.1).
- ``DetectionTrace`` references the originating Monitoring_Parameter values,
  the model version, and the resulting System_Status so every decision is
  traceable (Requirement 2.6, Property 10).

Dependencies:
- ``model_registry`` (``registry.active_model``).
- ``intelliwatch_engine`` (``IntelliWatchEngine``) for the cold-start fallback.
- ``iso_standards`` for ISO band classification.
- ``feature_extractor`` for ``MonitoringParameter`` and ``build_feature_vector``.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from model_registry import registry
from iso_standards import (
    classify_vibration_severity,
    classify_vibration_severity_acceleration,
)

logger = logging.getLogger(__name__)


# ============================================================
# DETECTION TRACE  (Requirement 2.6, Property 10)
# ============================================================

@dataclass
class DetectionTrace:
    """Trace record linking a detection decision to its inputs and outcome.

    Every inference call produces a DetectionTrace that references the
    originating Monitoring_Parameter values, the model version that produced
    the decision, and the resulting System_Status so the decision is
    traceable to its inputs and its Control_Signal (Requirement 2.6,
    Property 10).

    Fields
    ------
    inputs : dict
        The Monitoring_Parameter values (or their dict representations) that
        were fed to the model.
    status : str
        The resulting System_Status: ``"NORMAL"``, ``"WARNING"``, or
        ``"CRITICAL"``.
    model_version : str
        Version identifier of the model that produced the decision, or
        ``"cold_start"`` when the Welford fallback was used.
    timestamp : str
        ISO-8601 timestamp of the decision.
    method : str
        How the status was determined: ``"model"``, ``"threshold"``, or
        ``"cold_start"``.
    probabilities : dict
        Class probabilities from the model (when available).
    threshold_status : str
        The status from ISO threshold rules (when thresholds were applied).
    """

    inputs: Dict[str, Any]
    status: str
    model_version: str
    timestamp: str
    method: str = "model"
    probabilities: Dict[str, float] = field(default_factory=dict)
    threshold_status: Optional[str] = None
    fault_hint: Optional[Dict[str, Any]] = None   # populated by classify_fault_hint()


# ============================================================
# FAULT SIGNATURE CLASSIFICATION  (server-side mirror of
# frontend faultSignatures.js — same rule logic, Python port)
#
# References: ISO 10816-3, IEC 60034-1, IEC 60947-4-1,
#             ISO 13373-1 condition monitoring practices.
# ============================================================

_FAULT_CATALOGUE = [
    {
        "id": "bearing_wear",
        "label": "Bearing Wear",
        "severity": "high",
        "standard": "ISO 10816-3 / ISO 13373-1",
        "description": "Progressive rolling-element bearing degradation.",
    },
    {
        "id": "mechanical_imbalance",
        "label": "Mechanical Imbalance",
        "severity": "medium",
        "standard": "ISO 10816-3",
        "description": "Rotating mass imbalance causing 1× running-frequency vibration.",
    },
    {
        "id": "thermal_overload",
        "label": "Thermal Overload",
        "severity": "high",
        "standard": "IEC 60034-1 Class F",
        "description": "Winding or bearing temperature exceeds safe operating limit.",
    },
    {
        "id": "electrical_overload",
        "label": "Electrical Overload",
        "severity": "high",
        "standard": "IEC 60947-4-1 / NEMA MG-1",
        "description": "Motor drawing current above service factor limit.",
    },
    {
        "id": "compound_fault",
        "label": "Compound Fault",
        "severity": "high",
        "standard": "ISO 10816-3 / IEC 60034-1",
        "description": "Multiple sensors simultaneously in abnormal zones.",
    },
]

_MIN_CONFIDENCE = 32


def _score_bearing_wear(v, t, c):
    if v is None:
        return 0
    score = 55 if v > 7.1 else 40 if v > 4.5 else 20 if v > 3.5 else 0
    if score == 0:
        return 0
    if t is not None and t > 80:
        score += 8
    if c is not None and c < 16.5:
        score += 7
    return min(score, 95)


def _score_imbalance(v, t, c):
    if v is None:
        return 0
    score = 45 if 4.5 < v <= 10 else 25 if 2.8 < v <= 4.5 else 0
    if score == 0:
        return 0
    if t is not None and t < 80:
        score += 10
    if c is not None and 12 < c < 16.5:
        score += 10
    return min(score, 90)


def _score_thermal(v, t, c):
    if t is None:
        return 0
    score = 60 if t > 100 else 40 if t > 85 else 20 if t > 80 else 0
    if score == 0:
        return 0
    if c is not None and c > 16.5:
        score += 12
    if v is not None and v < 4.5:
        score += 5
    return min(score, 95)


def _score_electrical(v, t, c):
    if c is None:
        return 0
    score = 60 if c > 18.75 else 40 if c > 16.5 else 15 if c > 15 else 0
    if score == 0:
        return 0
    if t is not None and t > 80:
        score += 12
    if v is not None and v > 4.5:
        score += 8
    return min(score, 95)


def _score_compound(v, t, c):
    zones = sum([
        v is not None and v > 4.5,
        t is not None and t > 80,
        c is not None and c > 16.5,
    ])
    if zones < 2:
        return 0
    score = 85 if zones == 3 else 60
    if v is not None and v > 7.1:
        score += 8
    if t is not None and t > 100:
        score += 8
    if c is not None and c > 18.75:
        score += 8
    return min(score, 98)


_SCORERS = [
    ("bearing_wear",        _score_bearing_wear),
    ("mechanical_imbalance", _score_imbalance),
    ("thermal_overload",    _score_thermal),
    ("electrical_overload", _score_electrical),
    ("compound_fault",      _score_compound),
]


def classify_fault_hint(
    vibration_mm_s: Optional[float] = None,
    temperature_c: Optional[float] = None,
    current_a: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Return the best-matching fault signature dict or None.

    Mirrors the browser-side faultSignatures.js logic so the backend
    DetectionTrace carries the same fault_hint field.

    Parameters
    ----------
    vibration_mm_s : float | None
        Vibration RMS in mm/s (ISO 10816-3 scale).
    temperature_c  : float | None
        Temperature in °C.
    current_a      : float | None
        Motor current in Amperes.

    Returns
    -------
    dict with keys id, label, severity, standard, description, confidence
    or None when no pattern exceeds the minimum confidence threshold.
    """
    v, t, c = vibration_mm_s, temperature_c, current_a
    best_id, best_score = None, _MIN_CONFIDENCE - 1

    for fault_id, scorer in _SCORERS:
        score = scorer(v, t, c)
        if score > best_score:
            best_score = score
            best_id    = fault_id

    if best_id is None:
        return None

    meta = next(f for f in _FAULT_CATALOGUE if f["id"] == best_id)
    return {**meta, "confidence": best_score}


# ============================================================
# STATUS SEVERITY ORDERING
# ============================================================

_STATUS_RANK = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}


def _normalize_status(status: str) -> str:
    """Normalize a status string to uppercase NORMAL/WARNING/CRITICAL."""
    if not status:
        return "NORMAL"
    s = str(status).strip().upper()
    if s in ("NORMAL", "WARNING", "CRITICAL"):
        return s
    # Map engine-specific statuses.
    if s in ("UNDER_OBSERVATION", "UNKNOWN"):
        return "WARNING"
    if s in ("UNAVAILABLE",):
        return "WARNING"
    return "NORMAL"


def _most_severe(*statuses: str) -> str:
    """Return the most severe status from the given candidates (Req 7.1)."""
    ranked = [(_STATUS_RANK.get(_normalize_status(s), 0), s) for s in statuses if s]
    if not ranked:
        return "NORMAL"
    ranked.sort(key=lambda x: x[0], reverse=True)
    return _normalize_status(ranked[0][1])


# ============================================================
# STATUS FROM PROBABILITIES
# ============================================================

def status_from_probs(
    probabilities: Any,
    classes: Optional[List[str]] = None,
    threshold_inputs: Optional[Dict[str, float]] = None,
) -> Tuple[str, Dict[str, float]]:
    """Combine model probabilities with ISO band rules (Requirement 7.1).

    Takes the most severe of the model's predicted status and any ISO
    threshold-based status derived from ``threshold_inputs`` (Req 7.1,
    matching existing ``calculate_overall_status`` semantics).

    Parameters
    ----------
    probabilities : array-like | dict
        Model probability output.  When a list/array, ``classes`` provides the
        label alignment.  When a dict, keys are labels.
    classes : list[str], optional
        Class labels aligned to the probability array.
    threshold_inputs : dict, optional
        Mapping of parameter name -> numeric value used for ISO threshold
        classification (e.g. ``{"vibration_rms_mm_s": 3.5}``).

    Returns
    -------
    (status, prob_dict) : (str, dict)
        The combined System_Status and a dict of class -> probability.
    """
    # --- Model-derived status ---
    prob_dict: Dict[str, float] = {}
    model_status = "NORMAL"

    if probabilities is not None:
        if isinstance(probabilities, dict):
            prob_dict = {str(k): float(v) for k, v in probabilities.items()}
        elif isinstance(probabilities, (list, tuple)) and classes:
            prob_dict = {str(c): float(p) for c, p in zip(classes, probabilities)}
        elif isinstance(probabilities, (list, tuple)):
            # Single sample with positional probabilities
            prob_dict = {f"class_{i}": float(p) for i, p in enumerate(probabilities)}

        if prob_dict:
            # The model's status is the class with the highest probability,
            # mapped to a system status.
            best_label = max(prob_dict, key=prob_dict.get)
            model_status = _label_to_status(best_label)

    # --- ISO threshold-derived status ---
    threshold_status = "NORMAL"
    if threshold_inputs:
        for param_name, value in threshold_inputs.items():
            if value is None or not math.isfinite(value):
                continue
            try:
                if "velocity" in param_name or "rms_mm_s" in param_name:
                    iso = classify_vibration_severity(float(value))
                    threshold_status = _most_severe(
                        threshold_status, iso.upper()
                    )
                elif "acceleration" in param_name or "rms_g" in param_name:
                    iso = classify_vibration_severity_acceleration(float(value))
                    threshold_status = _most_severe(
                        threshold_status, iso.upper()
                    )
            except (ValueError, TypeError):
                pass

    # Combine: most severe of model + threshold (Req 7.1).
    combined = _most_severe(model_status, threshold_status)
    return combined, prob_dict


def _label_to_status(label: str) -> str:
    """Map a model class label to a System_Status."""
    s = str(label).strip().lower()
    if s in ("critical", "shutdown", "anomaly", "abnormal"):
        return "CRITICAL"
    if s in ("warning", "de_rate", "caution"):
        return "WARNING"
    return "NORMAL"


# ============================================================
# COLD-START FALLBACK
# ============================================================

_cold_start_engine: Optional[Any] = None


def get_cold_start_engine() -> Any:
    """Return (and lazily create) the shared Welford cold-start engine."""
    global _cold_start_engine
    if _cold_start_engine is None:
        try:
            from intelliwatch_engine import IntelliWatchEngine
            _cold_start_engine = IntelliWatchEngine()
            logger.info("Cold-start Welford engine initialised for inference fallback.")
        except Exception as exc:
            logger.warning("Could not initialise cold-start engine: %s", exc)
    return _cold_start_engine


def _cold_start_status(feature_vector: List[float], names: List[str]) -> Tuple[str, Dict]:
    """Use the Welford engine to produce a cold-start status.

    Builds a readings list from the feature vector and calls
    ``process_readings`` to get a status, then maps it to NORMAL/WARNING/
    CRITICAL.
    """
    engine = get_cold_start_engine()
    if engine is None:
        return "NORMAL", {}

    try:
        readings = []
        for name, value in zip(names, feature_vector):
            group = "vibration" if "vibration" in name or name.startswith("rms") else \
                    "temperature" if "temperature" in name else \
                    "current" if "current" in name else "other"
            readings.append({
                "sensor_type": group,
                "parameter": name,
                "value": value,
                "quality": "GOOD",
            })
        result = engine.process_readings(readings, mode="automatic")
        raw_status = result.get("overall_system_status", {}).get("status", "NORMAL")
        return _normalize_status(raw_status), {}
    except Exception as exc:
        logger.warning("Cold-start inference failed: %s", exc)
        return "NORMAL", {}


# ============================================================
# DETERMINE STATUS  (Requirements 9.3, 11.1, 2.6)
# ============================================================

def determine_status(
    feature_vector: Any,
    ts: str,
    parameter_names: Optional[List[str]] = None,
    parameters: Optional[Dict[str, Any]] = None,
    threshold_inputs: Optional[Dict[str, float]] = None,
    family: str = "ensemble",
) -> Tuple[str, DetectionTrace]:
    """Determine the System_Status from a feature vector.

    Uses ``model_registry.active_model(family)`` when a trained model is
    active (Requirement 11.1).  When no model is active, falls back to the
    Welford cold-start engine so the system still produces a status
    (design §12, graceful degradation).

    Parameters
    ----------
    feature_vector : list[float] | dict[str, MonitoringParameter] | array-like
        The numeric model input, or a dict of MonitoringParameters (in which
        case ``build_feature_vector`` extracts available values).
    ts : str
        ISO-8601 timestamp of the decision.
    parameter_names : list[str], optional
        Names aligned to the feature vector (used for cold-start and tracing).
    parameters : dict, optional
        Original MonitoringParameter objects for the trace record.
    threshold_inputs : dict, optional
        Parameter name -> value for ISO threshold classification.
    family : str
        Model family to query from the registry (default ``"ensemble"``).

    Returns
    -------
    (status, trace) : (str, DetectionTrace)
        The System_Status and a DetectionTrace linking the inputs, model
        version, and resulting status (Requirement 2.6, Property 10).
    """
    # --- Build the numeric feature vector ---
    if parameters is not None and not isinstance(feature_vector, (list, tuple)):
        from feature_extractor import build_feature_vector
        names, values = build_feature_vector(parameters)
        feature_vector = values
        if parameter_names is None:
            parameter_names = names
    elif isinstance(feature_vector, dict):
        from feature_extractor import build_feature_vector
        names, values = build_feature_vector(feature_vector)
        feature_vector = values
        if parameter_names is None:
            parameter_names = names

    if parameter_names is None:
        parameter_names = [f"feature_{i}" for i in range(len(feature_vector))]

    # Record inputs for the trace.
    trace_inputs = parameters or {
        name: value for name, value in zip(parameter_names, feature_vector)
    }

    # --- Try the active model first ---
    model = None
    try:
        model = registry.active_model(family)
    except Exception as exc:
        logger.debug("Registry lookup failed for family '%s': %s", family, exc)

    if model is not None:
        try:
            proba = model.predict_proba(feature_vector)
            classes = getattr(model, "classes_", None)
            status, prob_dict = status_from_probs(
                proba, classes=classes, threshold_inputs=threshold_inputs,
            )
            model_version = getattr(model, "version", "unknown")
            trace = DetectionTrace(
                inputs=trace_inputs,
                status=status,
                model_version=model_version,
                timestamp=ts,
                method="model",
                probabilities=prob_dict,
                threshold_status=_threshold_only_status(threshold_inputs),
                fault_hint=classify_fault_hint(
                    vibration_mm_s=_extract_param(threshold_inputs, ("velocity", "rms_mm_s", "vibration")),
                    temperature_c =_extract_param(threshold_inputs, ("temperature", "temp_c")),
                    current_a     =_extract_param(threshold_inputs, ("current", "current_a")),
                ),
            )
            return status, trace
        except Exception as exc:
            logger.warning("Model inference failed, falling back to cold-start: %s", exc)

    # --- Cold-start fallback ---
    cold_status, _ = _cold_start_status(feature_vector, parameter_names)
    # Still apply ISO thresholds in cold-start mode.
    combined = _most_severe(cold_status, _threshold_only_status(threshold_inputs))

    trace = DetectionTrace(
        inputs=trace_inputs,
        status=combined,
        model_version="cold_start",
        timestamp=ts,
        method="cold_start",
        threshold_status=_threshold_only_status(threshold_inputs),
        fault_hint=classify_fault_hint(
            vibration_mm_s=_extract_param(threshold_inputs, ("velocity", "rms_mm_s", "vibration")),
            temperature_c =_extract_param(threshold_inputs, ("temperature", "temp_c")),
            current_a     =_extract_param(threshold_inputs, ("current", "current_a")),
        ),
    )
    return combined, trace


def _extract_param(
    threshold_inputs: Optional[Dict[str, float]],
    keywords: tuple,
) -> Optional[float]:
    """Return the first value whose key contains any of the keywords."""
    if not threshold_inputs:
        return None
    for key, val in threshold_inputs.items():
        if any(kw in key.lower() for kw in keywords):
            if val is not None and math.isfinite(float(val)):
                return float(val)
    return None


def _threshold_only_status(threshold_inputs: Optional[Dict[str, float]]) -> Optional[str]:
    """Return the ISO threshold status, or None when no thresholds apply."""
    if not threshold_inputs:
        return None
    result = "NORMAL"
    for param_name, value in threshold_inputs.items():
        if value is None or not math.isfinite(value):
            continue
        try:
            if "velocity" in param_name or "rms_mm_s" in param_name:
                iso = classify_vibration_severity(float(value))
                result = _most_severe(result, iso.upper())
            elif "acceleration" in param_name or "rms_g" in param_name:
                iso = classify_vibration_severity_acceleration(float(value))
                result = _most_severe(result, iso.upper())
        except (ValueError, TypeError):
            pass
    return result if result != "NORMAL" else None
