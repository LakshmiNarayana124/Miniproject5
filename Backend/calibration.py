"""
INTELLIWATCH - CALIBRATION SERVICE
Collects a baseline window of readings at startup (or on demand),
derives equipment-specific warning/critical thresholds from the
observed statistics, pushes them into the engine, and provides a
validation check that gives confidence the sensor values are
physically plausible.

Three phases:
  1. baseline_sample(n, reader)   — collect n normal readings
  2. derive_thresholds(samples)   — mean±k·std → warning/critical
  3. validate(engine, readings)   — spot-check each sensor is
                                   within plausible physical range
"""

import math
import statistics
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import database

logger = logging.getLogger(__name__)

# ── Multipliers for threshold derivation ─────────────────────
# warning  = mean + WARN_K  × std
# critical = mean + CRIT_K  × std
# These are conservative: flag only clear deviations from baseline.
WARN_K = 2.5
CRIT_K = 4.0

# Minimum samples for a statistically meaningful baseline.
MIN_BASELINE_SAMPLES = 30

# Physical plausibility ranges (sanity bounds, not operating limits).
PLAUSIBILITY = {
    "vibration": {"min": 0.0,    "max": 50.0,  "unit": "g"},
    "temperature": {"min": -40.0, "max": 200.0, "unit": "°C"},
    "current":    {"min": 0.0,    "max": 100.0, "unit": "A"},
}


# ═══════════════════════════════════════════════════════════════
# 1. BASELINE SAMPLING
# ═══════════════════════════════════════════════════════════════

def baseline_sample(n: int = MIN_BASELINE_SAMPLES, reader=None) -> Dict[str, List[float]]:
    """
    Collect n sensor readings that represent normal operation.

    reader  — callable returning read_all_sensors() dict.
              Defaults to importing sensor_reader.read_all_sensors.
    Returns  dict  {sensor_type: [float, ...]}
    """
    if reader is None:
        from sensor_reader import read_all_sensors as reader  # type: ignore

    n = max(MIN_BASELINE_SAMPLES, int(n))
    buckets: Dict[str, List[float]] = {
        "vibration": [], "temperature": [], "current": []
    }

    for i in range(n):
        try:
            readings = reader()
        except Exception as exc:
            logger.warning("Baseline read %d failed: %s", i, exc)
            continue
        for sensor, reading in readings.items():
            v = reading.get("value")
            if v is not None:
                try:
                    buckets.setdefault(sensor, []).append(float(v))
                except (TypeError, ValueError):
                    pass

    return buckets


# ═══════════════════════════════════════════════════════════════
# 2. THRESHOLD DERIVATION
# ═══════════════════════════════════════════════════════════════

def derive_thresholds(samples: Dict[str, List[float]]) -> Dict[str, Dict[str, Any]]:
    """
    Derive warning and critical thresholds from baseline samples.

    Strategy: statistical upper-bound approach.
      warning  = mean + WARN_K × std   (flags unusual elevation)
      critical = mean + CRIT_K × std   (flags clearly abnormal)

    Returns a dict keyed by sensor type, each with:
      mean, std, warning_max, critical_max, sample_count, derived_at
    """
    result = {}
    for sensor, values in samples.items():
        valid = [v for v in values if v is not None and math.isfinite(v)]
        if len(valid) < 3:
            logger.warning("Not enough valid samples for %s (%d)", sensor, len(valid))
            continue

        mean = statistics.mean(valid)
        std = statistics.pstdev(valid)

        # Never let std be zero (constant signal → use a small fraction of mean)
        if std == 0:
            std = max(abs(mean) * 0.05, 0.01)

        warning_max = mean + WARN_K * std
        critical_max = mean + CRIT_K * std

        # Clamp to physical plausibility
        plaus = PLAUSIBILITY.get(sensor, {})
        if plaus.get("max") is not None:
            critical_max = min(critical_max, plaus["max"])
            warning_max = min(warning_max, critical_max * 0.9)

        # Ensure warning < critical
        if warning_max >= critical_max:
            warning_max = critical_max * 0.75

        result[sensor] = {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "warning_max": round(warning_max, 4),
            "critical_max": round(critical_max, 4),
            "sample_count": len(valid),
            "derived_at": datetime.now(timezone.utc).isoformat(),
        }

    return result


# ═══════════════════════════════════════════════════════════════
# 3. APPLY THRESHOLDS TO ENGINE
# ═══════════════════════════════════════════════════════════════

def apply_thresholds(engine, thresholds: Dict[str, Dict[str, Any]]) -> None:
    """
    Push derived thresholds into the Welford engine's operating_limits
    so analyse_sensor() enforces them immediately.

    The engine uses keys: warning_minimum/warning_maximum/
                          critical_minimum/critical_maximum
    per feature name (e.g. "vibration", "temperature", "current").
    """
    limits: Dict[str, Dict[str, float]] = {}

    for sensor, t in thresholds.items():
        w = t.get("warning_max")
        c = t.get("critical_max")
        if w is None or c is None:
            continue
        limits[sensor] = {
            "warning_maximum":  w,
            "critical_maximum": c,
            # No lower-bound limits by default (sensors can't go too low
            # except temperature, handled by plausibility check).
        }

    if limits:
        engine.set_operating_limits(limits)
        logger.info("Calibration: applied limits to engine: %s", limits)


# ═══════════════════════════════════════════════════════════════
# 4. PERSIST / LOAD
# ═══════════════════════════════════════════════════════════════

def save_calibration(thresholds: Dict[str, Dict[str, Any]]) -> None:
    """Persist calibration result to threshold_definitions table."""
    _MAP = {
        "vibration":   ("warning_max", "critical_max"),
        "temperature": ("warning_max", "critical_max"),
        "current":     ("warning_max", "critical_max"),
    }
    from iso_standards import save_threshold_to_db
    for sensor, t in thresholds.items():
        if sensor not in _MAP:
            continue
        w_key, c_key = _MAP[sensor]
        try:
            save_threshold_to_db(
                parameter_name=f"{sensor}_calibrated",
                normal_max=t.get("mean", 0.0),
                warning_max=t.get("warning_max", 1.0),
                source_standard=None,
                equipment_specific=1,
            )
        except Exception as exc:
            logger.warning("Could not persist calibration for %s: %s", sensor, exc)

    # Also record in audit log
    database.record_audit_entry(
        category="calibration",
        detail_json=json.dumps(thresholds, default=str),
    )


def load_calibration() -> Optional[Dict[str, Any]]:
    """Load most recent calibration from audit log, or None."""
    conn = database.get_connection()
    try:
        row = conn.execute("""
            SELECT detail_json, timestamp FROM audit_entries
            WHERE category = 'calibration'
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
        if row:
            return {"thresholds": json.loads(row["detail_json"]), "calibrated_at": row["timestamp"]}
        return None
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 5. VALIDATION CHECK
# ═══════════════════════════════════════════════════════════════

def validate_readings(readings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Quick plausibility check on a readings dict from read_all_sensors().

    For each sensor it checks:
      - value is not None / non-finite
      - value is within physical plausibility bounds
      - quality is GOOD

    Returns:
      {
        "passed": bool,
        "sensors": {sensor: {"ok": bool, "reason": str, "value": float}}
      }
    An overall pass means every present sensor is plausible.
    Does NOT make anomaly claims — it only assures the readings
    look physically possible.
    """
    result = {"passed": True, "sensors": {}}

    for sensor, reading in readings.items():
        v = reading.get("value")
        quality = reading.get("quality", "GOOD")

        if quality in ("ERROR", "BAD", "INVALID") or v is None:
            result["sensors"][sensor] = {
                "ok": False,
                "reason": f"quality={quality}, value={v}",
                "value": v,
            }
            result["passed"] = False
            continue

        try:
            fv = float(v)
        except (TypeError, ValueError):
            result["sensors"][sensor] = {"ok": False, "reason": "non-numeric", "value": v}
            result["passed"] = False
            continue

        if not math.isfinite(fv):
            result["sensors"][sensor] = {"ok": False, "reason": "non-finite", "value": fv}
            result["passed"] = False
            continue

        plaus = PLAUSIBILITY.get(sensor, {})
        lo, hi = plaus.get("min"), plaus.get("max")

        if lo is not None and fv < lo:
            result["sensors"][sensor] = {
                "ok": False, "reason": f"below physical min {lo}", "value": fv
            }
            result["passed"] = False
        elif hi is not None and fv > hi:
            result["sensors"][sensor] = {
                "ok": False, "reason": f"above physical max {hi}", "value": fv
            }
            result["passed"] = False
        else:
            result["sensors"][sensor] = {"ok": True, "reason": "plausible", "value": fv}

    return result


# ═══════════════════════════════════════════════════════════════
# 6. FULL CALIBRATION RUN (convenience)
# ═══════════════════════════════════════════════════════════════

def run_calibration(engine, n: int = MIN_BASELINE_SAMPLES, reader=None) -> Dict[str, Any]:
    """
    Full pipeline: sample → derive → apply → persist.
    Returns the derived thresholds dict.
    """
    logger.info("Starting calibration with %d samples…", n)
    samples = baseline_sample(n=n, reader=reader)
    thresholds = derive_thresholds(samples)

    if not thresholds:
        logger.warning("Calibration produced no thresholds.")
        return {"success": False, "reason": "no valid samples", "thresholds": {}}

    apply_thresholds(engine, thresholds)
    save_calibration(thresholds)

    logger.info("Calibration complete: %s", list(thresholds.keys()))
    return {"success": True, "thresholds": thresholds}
