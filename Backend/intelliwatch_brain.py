
"""
INTELLIWATCH BRAIN
Version: 2.1

Coordinates:
1. Sensor acquisition
2. ML inference with Welford fallback
3. Sensor-level assessments
4. Recommendation generation
5. SQLite persistence
6. Calibration restoration and validation

Task 15.1:
ML inference is attempted first. The Welford engine remains
the fallback and provides sensor-level assessments.
"""

from datetime import datetime, timezone

from database import (
    initialize_database,
    save_sensor_readings,
    save_recommendations,
)

from sensor_reader import read_all_sensors
from intelliwatch_engine import IntelliWatchEngine
from recommendations import generate_recommendations


# ============================================================
# OPTIONAL ML INFERENCE MODULE
# ============================================================

try:
    import inference as _inference
    _HAS_INFERENCE = True
except Exception as exc:
    _HAS_INFERENCE = False
    print(f"[Brain] ML inference unavailable: {exc}")


# ============================================================
# OPTIONAL CALIBRATION MODULE
# ============================================================

try:
    from calibration import (
        run_calibration,
        validate_readings,
        load_calibration,
        apply_thresholds,
    )
    _HAS_CALIBRATION = True

except Exception as exc:
    _HAS_CALIBRATION = False
    print(f"[Brain] Calibration unavailable: {exc}")


# ============================================================
# CONFIGURATION
# ============================================================

EXPECTED_SENSORS = (
    "vibration",
    "temperature",
    "current",
)


def current_timestamp():
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _get_overall_status(overall):
    """Safely extract an overall status."""

    if isinstance(overall, dict):
        return overall.get("status", "UNDER_OBSERVATION")

    if isinstance(overall, str):
        return overall

    return "UNDER_OBSERVATION"


# ============================================================
# INTELLIWATCH BRAIN
# ============================================================

class IntelliWatchBrain:

    def __init__(
        self,
        auto_calibrate: bool = True,
        calibration_samples: int = 30
    ):

        initialize_database()

        self.engine = IntelliWatchEngine()
        self._calibrated = False

        # ----------------------------------------------------
        # Restore previous calibration
        # ----------------------------------------------------

        if _HAS_CALIBRATION:

            try:
                previous = load_calibration()

                if previous and previous.get("thresholds"):

                    apply_thresholds(
                        self.engine,
                        previous["thresholds"]
                    )

                    self._calibrated = True

                    print(
                        "[Brain] Restored calibration from "
                        f"{previous.get('calibrated_at', '?')}"
                    )

            except Exception as exc:
                print(
                    f"[Brain] Calibration restoration skipped: {exc}"
                )

        # ----------------------------------------------------
        # First-startup automatic calibration
        # ----------------------------------------------------

        if (
            auto_calibrate
            and not self._calibrated
            and _HAS_CALIBRATION
        ):

            try:

                result = run_calibration(
                    self.engine,
                    n=calibration_samples
                )

                self._calibrated = result.get(
                    "success",
                    False
                )

                if self._calibrated:
                    print("[Brain] Auto-calibration complete.")

            except Exception as exc:
                print(
                    f"[Brain] Auto-calibration skipped: {exc}"
                )

    # ========================================================
    # 0. RECALIBRATION
    # ========================================================

    def recalibrate(self, n: int = 30) -> dict:
        """Re-derive operating thresholds from a fresh baseline."""

        if not _HAS_CALIBRATION:

            return {
                "success": False,
                "reason": "Calibration module unavailable."
            }

        try:

            result = run_calibration(
                self.engine,
                n=n
            )

            self._calibrated = result.get(
                "success",
                False
            )

            return result

        except Exception as exc:

            return {
                "success": False,
                "reason": str(exc)
            }

    # ========================================================
    # 1. SAVE RAW SENSOR READINGS
    # ========================================================

    def store_raw_readings(self, readings):

        records = []

        if not isinstance(readings, dict):
            return 0

        for sensor_key, reading in readings.items():

            if not isinstance(reading, dict):
                continue

            value = reading.get("value")

            if value is None:
                continue

            records.append({
                "sensor_name": reading.get(
                    "sensor_name",
                    sensor_key
                ),

                "value": value,

                "unit": reading.get(
                    "unit",
                    ""
                ),

                "timestamp": reading.get(
                    "timestamp",
                    current_timestamp()
                ),

                "quality": (
                    "VALID"
                    if reading.get("quality") == "GOOD"
                    else "ERROR"
                ),

                "metadata": reading.get(
                    "metadata",
                    {}
                ),
            })

        if records:
            save_sensor_readings(records)

        return len(records)

    # ========================================================
    # 2. PREPARE SENSOR ASSESSMENTS
    # ========================================================

    def prepare_sensor_assessments(self, sensor_statuses):

        assessments = {}

        if not isinstance(sensor_statuses, dict):
            return assessments

        for sensor_key in EXPECTED_SENSORS:

            sensor_data = sensor_statuses.get(sensor_key)

            if not isinstance(sensor_data, dict):
                continue

            if sensor_data.get("status") == "UNAVAILABLE":
                continue

            assessments[sensor_key] = {

                "status": sensor_data.get(
                    "status"
                ),

                "classification": sensor_data.get(
                    "classification",
                    "UNKNOWN"
                ),

                "explanation": sensor_data.get(
                    "explanation",
                    "No explanation available."
                ),
            }

        return assessments

    # ========================================================
    # 3. GENERATE RECOMMENDATIONS
    # ========================================================

    def create_recommendations(
        self,
        sensor_statuses,
        overall_system_status
    ):

        assessments = self.prepare_sensor_assessments(
            sensor_statuses
        )

        if assessments:

            result = generate_recommendations(
                assessments
            )

        else:

            result = {
                "generated_at": current_timestamp(),

                "sensor_recommendations": {},

                "overall_recommendation": {

                    "sensor": "Overall System",

                    "status": overall_system_status,

                    "priority": "NORMAL",

                    "observation": (
                        "No valid sensor assessments are available."
                    ),

                    "recommended_actions": [],

                    "immediate_relief_actions": [],

                    "corrective_actions": [],
                },

                "disclaimer": (
                    "Recommendations are guidance, not a substitute "
                    "for equipment-specific engineering assessment."
                ),
            }

        if not isinstance(result, dict):
            result = {}

        sensor_recommendations = result.get(
            "sensor_recommendations",
            {}
        )

        if not isinstance(sensor_recommendations, dict):
            sensor_recommendations = {}

        # Keep unavailable sensors visible.

        for sensor_key in EXPECTED_SENSORS:

            sensor_data = sensor_statuses.get(
                sensor_key,
                {}
            )

            if (
                isinstance(sensor_data, dict)
                and sensor_data.get("status") == "UNAVAILABLE"
            ):

                sensor_recommendations[sensor_key] = {

                    "sensor": sensor_key,

                    "status": "UNAVAILABLE",

                    "priority": "LOW",

                    "observation": (
                        "No valid reading is available. "
                        "Check the sensor and its connection."
                    ),

                    "recommended_actions": [],

                    "immediate_relief_actions": [],

                    "corrective_actions": [],
                }

        result["sensor_recommendations"] = (
            sensor_recommendations
        )

        # Engine overall status remains authoritative.

        overall = result.get(
            "overall_recommendation",
            {}
        )

        if not isinstance(overall, dict):
            overall = {}

        overall["status"] = overall_system_status

        result["overall_recommendation"] = overall

        return result

    # ========================================================
    # 4. SAVE RECOMMENDATIONS
    # ========================================================

    def store_recommendations(self, result):

        records = []

        sensor_recommendations = result.get(
            "sensor_recommendations",
            {}
        )

        if not isinstance(sensor_recommendations, dict):
            sensor_recommendations = {}

        for sensor_key, recommendation in (
            sensor_recommendations.items()
        ):

            if not isinstance(recommendation, dict):
                continue

            actions = (
                recommendation.get("recommended_actions", [])
                + recommendation.get("immediate_relief_actions", [])
                + recommendation.get("corrective_actions", [])
            )

            if not actions:

                observation = recommendation.get(
                    "observation"
                )

                if observation:
                    actions = [observation]

            for action in actions:

                records.append({

                    "category": "SENSOR_RECOMMENDATION",

                    "priority": recommendation.get(
                        "priority",
                        "NORMAL"
                    ),

                    "recommendation": str(action),

                    "reason": recommendation.get(
                        "engine_explanation",
                        recommendation.get("observation", "")
                    ),

                    "sensor_name": sensor_key,

                    "timestamp": current_timestamp(),
                })

        overall = result.get(
            "overall_recommendation",
            {}
        )

        if not isinstance(overall, dict):
            overall = {}

        overall_actions = (
            overall.get("recommended_actions", [])
            + overall.get("immediate_relief_actions", [])
            + overall.get("corrective_actions", [])
        )

        if (
            not overall_actions
            and overall.get("observation")
        ):
            overall_actions = [
                overall["observation"]
            ]

        for action in overall_actions:

            records.append({

                "category": "OVERALL_RECOMMENDATION",

                "priority": overall.get(
                    "priority",
                    "NORMAL"
                ),

                "recommendation": str(action),

                "reason": overall.get(
                    "observation",
                    ""
                ),

                "sensor_name": "overall_system",

                "timestamp": current_timestamp(),
            })

        if records:
            save_recommendations(records)

        return len(records)

    # ========================================================
    # 5. COMPLETE MONITORING CYCLE
    # ========================================================

    def run_cycle(
        self,
        mode="automatic",
        readings=None
    ):

        timestamp = current_timestamp()

        # ----------------------------------------------------
        # Acquire readings only when not supplied.
        # This allows the server to share one sensor snapshot
        # between acquisition and assessment.
        # ----------------------------------------------------

        if readings is None:
            readings = read_all_sensors()

        if not isinstance(readings, dict):

            return {
                "success": False,
                "timestamp": timestamp,
                "message": "Invalid sensor readings format.",
                "sensor_readings_saved": 0,
                "overall_system_status": "UNAVAILABLE",
            }

        # ----------------------------------------------------
        # Save raw readings
        # ----------------------------------------------------

        saved_readings = self.store_raw_readings(
            readings
        )

        # ----------------------------------------------------
        # Validate readings
        # ----------------------------------------------------

        validation = None

        if _HAS_CALIBRATION:

            try:

                validation = validate_readings(
                    readings
                )

                if not validation.get("passed", False):

                    bad = [
                        sensor
                        for sensor, details
                        in validation.get("sensors", {}).items()
                        if not details.get("ok", False)
                    ]

                    print(
                        "[Brain] Validation warning - "
                        f"implausible sensors: {bad}"
                    )

            except Exception as exc:

                print(
                    f"[Brain] Reading validation skipped: {exc}"
                )

        # ----------------------------------------------------
        # ML inference with Welford fallback
        # ----------------------------------------------------

        try:

            engine_result = None

            if _HAS_INFERENCE:

                try:

                    feature_vector, parameter_names = (
                        _build_feature_vector_from_readings(
                            readings
                        )
                    )

                    ml_status, trace = (
                        _inference.determine_status(
                            feature_vector=feature_vector,
                            ts=timestamp,
                            parameter_names=parameter_names,
                        )
                    )

                    # Welford still performs sensor-level analysis.

                    engine_result = self.engine.process_readings(
                        readings,
                        mode=mode
                    )

                    engine_overall = _get_overall_status(
                        engine_result.get(
                            "overall_system_status",
                            {}
                        )
                    )

                    from inference import _most_severe

                    final_status = _most_severe(
                        ml_status,
                        engine_overall
                    )

                    # Support both dictionary and string formats.

                    overall_result = engine_result.get(
                        "overall_system_status"
                    )

                    if isinstance(overall_result, dict):

                        overall_result["status"] = final_status

                    else:

                        engine_result["overall_system_status"] = {
                            "status": final_status
                        }

                    engine_result["detection_trace"] = {

                        "model_version": getattr(
                            trace,
                            "model_version",
                            None
                        ),

                        "method": getattr(
                            trace,
                            "method",
                            "ML inference"
                        ),

                        "ml_status": ml_status,
                    }

                except Exception as exc:

                    print(
                        "[Brain] ML inference unavailable for "
                        f"this cycle; using Welford fallback: {exc}"
                    )

                    engine_result = None

            # ------------------------------------------------
            # Welford fallback
            # ------------------------------------------------

            if engine_result is None:

                engine_result = self.engine.process_readings(
                    readings,
                    mode=mode
                )

        except ValueError as error:

            return {

                "success": False,

                "timestamp": timestamp,

                "sensor_readings": readings,

                "message": str(error),

                "sensor_readings_saved": saved_readings,

                "overall_system_status": "UNAVAILABLE",
            }

        except Exception as error:

            print(
                f"[Brain] Monitoring cycle failed: {error}"
            )

            return {

                "success": False,

                "timestamp": timestamp,

                "sensor_readings": readings,

                "message": str(error),

                "sensor_readings_saved": saved_readings,

                "overall_system_status": "UNAVAILABLE",
            }

        # ----------------------------------------------------
        # Extract engine assessments
        # ----------------------------------------------------

        sensor_statuses = engine_result.get(
            "sensor_statuses",
            {}
        )

        overall_status = engine_result.get(
            "overall_system_status",
            {}
        )

        overall_status_str = _get_overall_status(
            overall_status
        )

        # ----------------------------------------------------
        # Generate recommendations
        # ----------------------------------------------------

        recommendation_result = self.create_recommendations(
            sensor_statuses,
            overall_status_str
        )

        # ----------------------------------------------------
        # Persist recommendations
        # ----------------------------------------------------

        saved_recommendations = self.store_recommendations(
            recommendation_result
        )

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        return {

            "success": True,

            "timestamp": timestamp,

            "sensor_readings": readings,

            "mode": mode,

            "sensor_readings_saved": saved_readings,

            "sensor_statuses": sensor_statuses,

            "overall_system_status": overall_status_str,

            "engine_analysis": engine_result,

            "recommendations": recommendation_result,

            "recommendations_saved": saved_recommendations,

            "validation": validation,
        }


# ============================================================
# HELPER: BUILD ML FEATURE VECTOR
# ============================================================

def _build_feature_vector_from_readings(readings):
    """
    Convert sensor readings into a flat feature vector.

    Returns:
        feature_vector: list of numeric sensor values
        parameter_names: corresponding sensor names
    """

    if not isinstance(readings, dict):
        return [], []

    values = []
    names = []

    for key, reading in readings.items():

        if not isinstance(reading, dict):
            continue

        value = reading.get("value")

        try:

            numeric_value = float(value)

            values.append(numeric_value)
            names.append(key)

        except (TypeError, ValueError):
            continue

    return values, names


# ============================================================
# STANDALONE TEST ENTRY POINT
# ============================================================

if __name__ == "__main__":

    brain = IntelliWatchBrain()

    result = brain.run_cycle(
        mode="automatic"
    )

    print("\nINTELLIWATCH BRAIN RESULT")
    print("=" * 55)

    print(
        "Success:",
        result.get("success")
    )

    print(
        "Overall Status:",
        result.get("overall_system_status")
    )

    if result.get("success"):

        print("\nSensor Statuses:")

        for sensor, data in result.get(
            "sensor_statuses",
            {}
        ).items():

            print(
                sensor,
                "->",
                data.get("status")
                if isinstance(data, dict)
                else data
            )

        print(
            "\nRecommendations Saved:",
            result.get("recommendations_saved", 0)
        )

    else:

        print(
            "\nMessage:",
            result.get("message")
        )
