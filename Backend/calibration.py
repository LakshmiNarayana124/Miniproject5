"""
INTELLIWATCH - CALIBRATION SERVICE

Collects baseline sensor readings, derives equipment-specific
thresholds, applies them to the engine, and validates readings.

Calibration sources:
    hardware    - Actual IoT sensor readings only.
    simulation  - Explicitly supplied synthetic readings.

Hardware and simulation calibration records are isolated.
Legacy calibration records without source metadata are not
automatically restored into hardware mode.
"""

import math
import statistics
import json
import logging

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import database


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

WARN_K = 2.5
CRIT_K = 4.0

MIN_BASELINE_SAMPLES = 30

CALIBRATION_SOURCES = ("hardware", "simulation")

EXPECTED_SENSORS = (
    "vibration",
    "temperature",
    "current",
)


# Physical plausibility ranges.
# These are not equipment operating limits.

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
# SOURCE VALIDATION
# ============================================================

def _validate_source(source):

    if source not in CALIBRATION_SOURCES:
        raise ValueError(
            "Calibration source must be 'hardware' or 'simulation'."
        )

    return source


# ============================================================
# 1. BASELINE SAMPLING
# ============================================================

def baseline_sample(
    n: int = MIN_BASELINE_SAMPLES,
    reader=None,
    source: str = "hardware"
) -> Dict[str, List[float]]:
    """
    Collect baseline sensor readings.

    Hardware calibration:
        - Accepts valid hardware readings only.
        - Rejects readings marked as simulated.
        - Requires GOOD or VALID quality.

    Simulation calibration:
        - Accepts explicitly supplied simulation readings.

    Returns:
        {
            sensor_type: [float, ...]
        }
    """

    source = _validate_source(source)

    if reader is None:
        from sensor_reader import read_all_sensors
        reader = read_all_sensors

    n = max(MIN_BASELINE_SAMPLES, int(n))

    buckets: Dict[str, List[float]] = {
        sensor: []
        for sensor in EXPECTED_SENSORS
    }

    for index in range(n):

        try:
            readings = reader()

        except Exception as exc:
            logger.warning(
                "Baseline read %d failed: %s",
                index + 1,
                exc
            )
            continue

        if not isinstance(readings, dict):
            continue

        for sensor in EXPECTED_SENSORS:

            reading = readings.get(sensor)

            if not isinstance(reading, dict):
                continue

            value = reading.get("value")

            if value is None:
                continue

            quality = str(
                reading.get("quality", "")
            ).upper()

            if quality not in ("GOOD", "VALID"):
                continue

            metadata = reading.get("metadata") or {}

            if not isinstance(metadata, dict):
                metadata = {}

            measurement_type = str(
                metadata.get("measurement_type", "")
            ).lower()

            metadata_source = str(
                metadata.get("source", "")
            ).lower()

            # Never allow synthetic readings into hardware
            # calibration, even if they are marked GOOD.
            if source == "hardware":

                if (
                    "simulated" in measurement_type
                    or metadata_source == "simulation"
                ):
                    continue

            try:
                numeric_value = float(value)

            except (TypeError, ValueError):
                continue

            if not math.isfinite(numeric_value):
                continue

            buckets[sensor].append(numeric_value)

    return buckets


# ============================================================
# 2. THRESHOLD DERIVATION
# ============================================================

def derive_thresholds(
    samples: Dict[str, List[float]]
) -> Dict[str, Dict[str, Any]]:
    """
    Derive warning and critical thresholds from baseline samples.

    warning  = mean + WARN_K * std
    critical = mean + CRIT_K * std

    Each sensor requires at least MIN_BASELINE_SAMPLES
    valid observations.
    """

    result = {}

    if not isinstance(samples, dict):
        return result

    for sensor in EXPECTED_SENSORS:

        values = samples.get(sensor, [])

        if not isinstance(values, (list, tuple)):
            continue

        valid = []

        for value in values:

            try:
                numeric_value = float(value)

            except (TypeError, ValueError):
                continue

            if math.isfinite(numeric_value):
                valid.append(numeric_value)

        if len(valid) < MIN_BASELINE_SAMPLES:

            logger.warning(
                "Insufficient calibration samples for %s: %d/%d",
                sensor,
                len(valid),
                MIN_BASELINE_SAMPLES
            )

            continue

        mean = statistics.mean(valid)
        std = statistics.pstdev(valid)

        # Constant signal: use a small minimum variation.
        if std == 0:
            std = max(abs(mean) * 0.05, 0.01)

        warning_max = mean + WARN_K * std
        critical_max = mean + CRIT_K * std

        plausibility = PLAUSIBILITY.get(sensor, {})
        physical_max = plausibility.get("max")

        if physical_max is not None:

            critical_max = min(
                critical_max,
                physical_max
            )

            warning_cap = mean + (
                0.9 * (critical_max - mean)
            )

            warning_max = min(
                warning_max,
                warning_cap
            )

        # Validate final threshold ordering.
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

            "warning_max": round(
                warning_max, 4
            ),

            "critical_max": round(
                critical_max, 4
            ),

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
    Push derived thresholds into engine operating_limits.
    """

    limits = {}

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
            "Calibration thresholds applied to engine: %s",
            limits
        )


# ============================================================
# 4. PERSIST CALIBRATION
# ============================================================

def save_calibration(
    thresholds: Dict[str, Dict[str, Any]],
    source: str = "hardware"
) -> None:
    """
    Persist calibration with an explicit source.

    Only hardware calibration is written to the operational
    equipment-specific threshold table.

    Simulation calibration is retained separately in the
    calibration audit history.
    """

    source = _validate_source(source)

    if not isinstance(thresholds, dict) or not thresholds:
        raise ValueError(
            "Valid calibration thresholds are required."
        )

    if source == "hardware":

        parameter_map = {
            "vibration": "vibration_calibrated",
            "temperature": "temperature_calibrated",
            "current": "current_calibrated",
        }

        from iso_standards import save_threshold_to_db

        for sensor, threshold in thresholds.items():

            parameter_name = parameter_map.get(sensor)

            if parameter_name is None:
                continue

            try:

                save_threshold_to_db(
                    parameter_name=parameter_name,
                    normal_max=threshold.get("mean", 0.0),
                    warning_max=threshold.get("warning_max", 1.0),
                    source_standard=None,
                    equipment_specific=1,
                )

            except Exception as exc:

                logger.warning(
                    "Could not persist hardware calibration "
                    "for %s: %s",
                    sensor,
                    exc
                )

    calibration_record = {

        "source": source,

        "thresholds": thresholds,

        "calibrated_at": datetime.now(
            timezone.utc
        ).isoformat(),

    }

    database.record_audit_entry(
        category="calibration",
        detail_json=json.dumps(
            calibration_record,
            default=str
        ),
    )

    logger.info(
        "%s calibration record saved.",
        source.capitalize()
    )


# ============================================================
# 5. LOAD CALIBRATION
# ============================================================

def load_calibration(
    source: str = "hardware"
) -> Optional[Dict[str, Any]]:
    """
    Load the latest calibration for the requested source.

    Legacy records without explicit source metadata are ignored.
    Simulation calibration is never restored as hardware calibration.
    """

    source = _validate_source(source)

    conn = database.get_connection()

    try:

        rows = conn.execute("""
            SELECT detail_json, timestamp
            FROM audit_entries
            WHERE category = 'calibration'
            ORDER BY timestamp DESC
        """).fetchall()

        for row in rows:

            try:
                record = json.loads(
                    row["detail_json"]
                )

            except (TypeError, ValueError):
                continue

            if not isinstance(record, dict):
                continue

            # Ignore legacy records without source information.
            if record.get("source") != source:
                continue

            thresholds = record.get("thresholds")

            if not isinstance(thresholds, dict):
                continue

            if not thresholds:
                continue

            return {
                "source": source,

                "thresholds": thresholds,

                "calibrated_at": record.get(
                    "calibrated_at",
                    row["timestamp"]
                ),
            }

        return None

    finally:
        conn.close()


# ============================================================
# 6. VALIDATION CHECK
# ============================================================

def validate_readings(
    readings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check whether sensor readings are physically plausible.

    This function does not make anomaly claims.
    """

    result = {
        "passed": True,
        "sensors": {},
    }

    if not isinstance(readings, dict):

        return {
            "passed": False,
            "sensors": {},
            "reason": "Invalid readings format."
        }

    for sensor in EXPECTED_SENSORS:

        reading = readings.get(sensor)

        if not isinstance(reading, dict):

            result["sensors"][sensor] = {
                "ok": False,
                "reason": "reading unavailable",
                "value": None,
            }

            result["passed"] = False
            continue

        value = reading.get("value")

        quality = str(
            reading.get("quality", "GOOD")
        ).upper()

        if (
            quality in ("ERROR", "BAD", "INVALID")
            or value is None
        ):

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
# 7. FULL CALIBRATION RUN
# ============================================================

def run_calibration(
    engine,
    n: int = MIN_BASELINE_SAMPLES,
    reader=None,
    source: str = "hardware"
) -> Dict[str, Any]:
    """
    Full calibration pipeline:

        sample -> verify -> derive -> apply -> persist

    Hardware calibration requires at least 30 valid readings
    from each expected physical sensor.

    Simulation calibration must be explicitly requested.
    """

    source = _validate_source(source)

    n = max(
        MIN_BASELINE_SAMPLES,
        int(n)
    )

    logger.info(
        "Starting %s calibration with %d samples per sensor...",
        source,
        n
    )

    samples = baseline_sample(
        n=n,
        reader=reader,
        source=source
    )

    sample_counts = {
        sensor: len(samples.get(sensor, []))
        for sensor in EXPECTED_SENSORS
    }

    insufficient = {
        sensor: count
        for sensor, count in sample_counts.items()
        if count < MIN_BASELINE_SAMPLES
    }

    if insufficient:

        logger.warning(
            "%s calibration rejected. Insufficient sensor samples: %s",
            source,
            insufficient
        )

        return {
            "success": False,
            "source": source,
            "reason": (
                "Insufficient valid readings. "
                "Every expected sensor requires at least "
                f"{MIN_BASELINE_SAMPLES} samples."
            ),
            "sample_counts": sample_counts,
            "thresholds": {},
        }

    thresholds = derive_thresholds(samples)

    if len(thresholds) != len(EXPECTED_SENSORS):

        return {
            "success": False,
            "source": source,
            "reason": "Threshold derivation incomplete.",
            "sample_counts": sample_counts,
            "thresholds": {},
        }

    apply_thresholds(
        engine,
        thresholds
    )

    save_calibration(
        thresholds,
        source=source
    )

    logger.info(
        "%s calibration complete: %s",
        source.capitalize(),
        list(thresholds.keys())
    )

    return {
        "success": True,
        "source": source,
        "sample_counts": sample_counts,
        "thresholds": thresholds,
    }