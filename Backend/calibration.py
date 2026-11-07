
"""
INTELLIWATCH - CALIBRATION SERVICE

Collects a baseline window of readings at startup (or on demand),
derives equipment-specific warning/critical thresholds from the
observed statistics, pushes them into the engine, and provides
validation checks for physical plausibility.

Three phases:
  1. baseline_sample(n, reader)   — collect normal readings
  2. derive_thresholds(samples)   — mean + k * std -> warning/critical
  3. validate_readings(readings)  — check physical plausibility
"""

import math
import statistics
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import database

logger = logging.getLogger(__name__)

# Multipliers for threshold derivation
WARN_K = 2.5
CRIT_K = 4.0

# Minimum samples for a statistically meaningful baseline
MIN_BASELINE_SAMPLES = 30

# Physical plausibility ranges (not equipment operating limits)
PLAUSIBILITY = {
    "vibration": {
        "min": 0.0,
        "max": 50.0,
        "unit": "g",
    },
    "temperature": {
        "min": -40.0,
        "max": 200.0,
        "unit": "°C",
    },
    "current": {
        "min": 0.0,
        "max": 100.0,
        "unit": "A",
    },
}


# ============================================================
# 1. BASELINE SAMPLING
# ============================================================

def baseline_sample(
    n: int = MIN_BASELINE_SAMPLES,
    reader=None
) -> Dict[str, List[float]]:
    """
    Collect sensor readings representing normal operation.

    reader:
        Callable returning read_all_sensors() dictionary.

    Returns:
        {sensor_type: [float, ...]}
    """

    if reader is None:
        from sensor_reader import read_all_sensors as reader

    n = max(MIN_BASELINE_SAMPLES, int(n))

    buckets: Dict[str, List[float]] = {
        "vibration": [],
        "temperature": [],
        "current": [],
    }

    for i in range(n):
        try:
            readings = reader()
        except Exception as exc:
            logger.warning(
                "Baseline read %d failed: %s",
                i,
                exc
            )
            continue

        for sensor, reading in readings.items():
            value = reading.get("value")

            if value is not None:
                try:
                    buckets.setdefault(sensor, []).append(
                        float(value)
                    )
                except (TypeError, ValueError):
                    pass

    return buckets


# ============================================================
# 2. THRESHOLD DERIVATION
# ============================================================

def derive_thresholds(
    samples: Dict[str, List[float]]
) -> Dict[str, Dict[str, Any]]:
    """
    Derive warning and critical thresholds from baseline samples.

    Strategy:
        warning  = mean + WARN_K * std
        critical = mean + CRIT_K * std

    Physical plausibility maximum is used as a safety clamp.

    Returns:
        {
            sensor: {
                mean,
                std,
                warning_max,
                critical_max,
                sample_count,
                derived_at
            }
        }
    """

    result = {}

    for sensor, values in samples.items():

        valid = [
            v for v in values
            if v is not None and math.isfinite(v)
        ]

        if len(valid) < 3:
            logger.warning(
                "Not enough valid samples for %s (%d)",
                sensor,
                len(valid)
            )
            continue

        mean = statistics.mean(valid)
        std = statistics.pstdev(valid)

        # Constant signal: use a small minimum variation
        if std == 0:
            std = max(abs(mean) * 0.05, 0.01)

        warning_max = mean + WARN_K * std
        critical_max = mean + CRIT_K * std

        # Clamp critical threshold to physical plausibility
        plaus = PLAUSIBILITY.get(sensor, {})

        physical_max = plaus.get("max")

        if physical_max is not None:
            critical_max = min(
                critical_max,
                physical_max
            )

            # IMPORTANT:
            # Clamp warning relative to the baseline mean,
            # not relative to the absolute critical value.
            #
            # This preserves:
            # mean < warning_max < critical_max

            warning_cap = mean + (
                0.9 * (critical_max - mean)
            )

            warning_max = min(
                warning_max,
                warning_cap
            )

        # Final threshold ordering validation
        if not (
            mean < warning_max < critical_max
        ):
            logger.warning(
                "Invalid derived thresholds for %s: "
                "mean=%.4f, warning=%.4f, critical=%.4f",
                sensor,
                mean,
                warning_max,
                critical_max
            )
            continue

        result[sensor] = {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "warning_max": round(warning_max, 4),
            "critical_max": round(critical_max, 4),
            "sample_count": len(valid),
            "derived_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    return result


# ============================================================
# 3. APPLY THRESHOLDS TO ENGINE
# ============================================================

def apply_thresholds(
    engine,
    thresholds: Dict[str, Dict[str, Any]]
) -> None:
    """
    Push derived thresholds into the engine's operating_limits.

    Engine keys:
        warning_minimum
        warning_maximum
        critical_minimum
        critical_maximum
    """

    limits: Dict[str, Dict[str, float]] = {}

    for sensor, threshold in thresholds.items():

        warning = threshold.get("warning_max")
        critical = threshold.get("critical_max")

        if warning is None or critical is None:
            continue

        limits[sensor] = {
            "warning_maximum": warning,
            "critical_maximum": critical,
        }

    if limits:
        engine.set_operating_limits(limits)

        logger.info(
            "Calibration: applied limits to engine: %s",
            limits
        )


# ============================================================
# 4. PERSIST / LOAD
# ============================================================

def save_calibration(
    thresholds: Dict[str, Dict[str, Any]]
) -> None:
    """
    Persist calibration results to threshold_definitions.
    """

    _MAP = {
        "vibration": ("warning_max", "critical_max"),
        "temperature": ("warning_max", "critical_max"),
        "current": ("warning_max", "critical_max"),
    }

    from iso_standards import save_threshold_to_db

    for sensor, threshold in thresholds.items():

        if sensor not in _MAP:
            continue

        w_key, c_key = _MAP[sensor]

        try:
            save_threshold_to_db(
                parameter_name=f"{sensor}_calibrated",
                normal_max=threshold.get("mean", 0.0),
                warning_max=threshold.get("warning_max", 1.0),
                source_standard=None,
                equipment_specific=1,
            )

        except Exception as exc:
            logger.warning(
                "Could not persist calibration for %s: %s",
                sensor,
                exc
            )

    # Record calibration in audit log
    database.record_audit_entry(
        category="calibration",
        detail_json=json.dumps(
            thresholds,
            default=str
        ),
    )


def load_calibration() -> Optional[Dict[str, Any]]:
    """
    Load most recent calibration from audit log.
    """

    conn = database.get_connection()

    try:
        row = conn.execute("""
            SELECT detail_json, timestamp
            FROM audit_entries
            WHERE category = 'calibration'
            ORDER BY timestamp DESC
            LIMIT 1
        """).fetchone()

        if row:
            return {
                "thresholds": json.loads(row["detail_json"]),
                "calibrated_at": row["timestamp"],
            }

        return None

    finally:
        conn.close()


# ============================================================
# 5. VALIDATION CHECK
# ============================================================

def validate_readings(
    readings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check whether sensor readings are physically plausible.

    Checks:
        - Value is not None
        - Value is numeric and finite
        - Value is within physical plausibility limits
        - Reading quality is GOOD

    This function does not make anomaly claims.
    """

    result = {
        "passed": True,
        "sensors": {},
    }

    for sensor, reading in readings.items():

        value = reading.get("value")
        quality = reading.get("quality", "GOOD")

        if quality in (
            "ERROR",
            "BAD",
            "INVALID"
        ) or value is None:

            result["sensors"][sensor] = {
                "ok": False,
                "reason": f"quality={quality}, value={value}",
                "value": value,
            }

            result["passed"] = False
            continue

        try:
            numeric_value = float(value)

        except (TypeError, ValueError):

            result["sensors"][sensor] = {
                "ok": False,
                "reason": "non-numeric",
                "value": value,
            }

            result["passed"] = False
            continue

        if not math.isfinite(numeric_value):

            result["sensors"][sensor] = {
                "ok": False,
                "reason": "non-finite",
                "value": numeric_value,
            }

            result["passed"] = False
            continue

        plausibility = PLAUSIBILITY.get(sensor, {})

        lower = plausibility.get("min")
        upper = plausibility.get("max")

        if lower is not None and numeric_value < lower:

            result["sensors"][sensor] = {
                "ok": False,
                "reason": f"below physical min {lower}",
                "value": numeric_value,
            }

            result["passed"] = False

        elif upper is not None and numeric_value > upper:

            result["sensors"][sensor] = {
                "ok": False,
                "reason": f"above physical max {upper}",
                "value": numeric_value,
            }

            result["passed"] = False

        else:

            result["sensors"][sensor] = {
                "ok": True,
                "reason": "plausible",
                "value": numeric_value,
            }

    return result


# ============================================================
# 6. FULL CALIBRATION RUN
# ============================================================

def run_calibration(
    engine,
    n: int = MIN_BASELINE_SAMPLES,
    reader=None
) -> Dict[str, Any]:
    """
    Full pipeline:
        sample -> derive -> apply -> persist

    Returns the derived thresholds.
    """

    logger.info(
        "Starting calibration with %d samples...",
        n
    )

    samples = baseline_sample(
        n=n,
        reader=reader
    )

    thresholds = derive_thresholds(samples)

    if not thresholds:

        logger.warning(
            "Calibration produced no thresholds."
        )

        return {
            "success": False,
            "reason": "no valid samples",
            "thresholds": {},
        }

    apply_thresholds(
        engine,
        thresholds
    )

    save_calibration(thresholds)

    logger.info(
        "Calibration complete: %s",
        list(thresholds.keys())
    )

    return {
        "success": True,
        "thresholds": thresholds,
    }
