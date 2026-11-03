"""
INTELLIWATCH BRAIN
Version: 2.0

Coordinates sensor acquisition, ML inference (with cold-start fallback),
recommendation generation and SQLite persistence.

Task 15.1: run_cycle now calls inference.determine_status first;
the Welford engine is the cold-start fallback when no trained model is active.
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

# ML inference module (Req 2.6, 11.1)
try:
    import inference as _inference
    _HAS_INFERENCE = True
except Exception:
    _HAS_INFERENCE = False

# Calibration service
try:
    from calibration import run_calibration, validate_readings, load_calibration, apply_thresholds
    _HAS_CALIBRATION = True
except Exception:
    _HAS_CALIBRATION = False


EXPECTED_SENSORS = (
    "vibration",
    "temperature",
    "current",
)


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


class IntelliWatchBrain:

    def __init__(self, auto_calibrate: bool = True, calibration_samples: int = 30):
        initialize_database()
        self.engine = IntelliWatchEngine()
        self._calibrated = False

        # Restore previous calibration from DB if available
        if _HAS_CALIBRATION:
            prev = load_calibration()
            if prev and prev.get("thresholds"):
                try:
                    apply_thresholds(self.engine, prev["thresholds"])
                    self._calibrated = True
                    print(f"[Brain] Restored calibration from {prev.get('calibrated_at','?')}")
                except Exception:
                    pass

        # Auto-calibrate on first startup if no prior calibration
        if auto_calibrate and not self._calibrated and _HAS_CALIBRATION:
            try:
                result = run_calibration(self.engine, n=calibration_samples)
                self._calibrated = result.get("success", False)
                if self._calibrated:
                    print("[Brain] Auto-calibration complete.")
            except Exception as e:
                print(f"[Brain] Auto-calibration skipped: {e}")

    # --------------------------------------------------------
    # 0. RECALIBRATE (on-demand mid-run)
    # --------------------------------------------------------

    def recalibrate(self, n: int = 30) -> dict:
        """Re-derive thresholds from a fresh baseline window."""
        if not _HAS_CALIBRATION:
            return {"success": False, "reason": "calibration module unavailable"}
        result = run_calibration(self.engine, n=n)
        self._calibrated = result.get("success", False)
        return result

    # --------------------------------------------------------
    # 1. SAVE RAW SENSOR READINGS
    # --------------------------------------------------------

    def store_raw_readings(self, readings):

        records = []

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
                "unit": reading.get("unit", ""),
                "timestamp": reading.get(
                    "timestamp",
                    current_timestamp()
                ),
                "quality": (
                    "VALID"
                    if reading.get("quality") == "GOOD"
                    else "ERROR"
                ),
                "metadata": reading.get("metadata", {}),
            })

        if records:
            save_sensor_readings(records)

        return len(records)

    # --------------------------------------------------------
    # 2. PREPARE SENSOR ASSESSMENTS
    # --------------------------------------------------------

    def prepare_sensor_assessments(self, sensor_statuses):

        assessments = {}

        for sensor_key in EXPECTED_SENSORS:

            sensor_data = sensor_statuses.get(sensor_key)

            if not sensor_data:
                continue

            if sensor_data.get("status") == "UNAVAILABLE":
                continue

            assessments[sensor_key] = {
                "status": sensor_data.get("status"),
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

    # --------------------------------------------------------
    # 3. GENERATE RECOMMENDATIONS
    # --------------------------------------------------------

    def create_recommendations(
        self,
        sensor_statuses,
        overall_system_status
    ):

        assessments = self.prepare_sensor_assessments(
            sensor_statuses
        )

        if assessments:

            result = generate_recommendations(assessments)

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

        sensor_recommendations = result.get(
            "sensor_recommendations",
            {}
        )

        # Keep unavailable sensors visible.
        for sensor_key in EXPECTED_SENSORS:

            if sensor_statuses.get(sensor_key, {}).get(
                "status"
            ) == "UNAVAILABLE":

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
        overall = result.get("overall_recommendation", {})
        overall["status"] = overall_system_status
        result["overall_recommendation"] = overall

        return result

    # --------------------------------------------------------
    # 4. SAVE RECOMMENDATIONS
    # --------------------------------------------------------

    def store_recommendations(self, result):

        records = []

        sensor_recommendations = result.get(
            "sensor_recommendations",
            {}
        )

        for sensor_key, recommendation in (
            sensor_recommendations.items()
        ):

            if not recommendation:
                continue

            actions = (
                recommendation.get("recommended_actions", [])
                + recommendation.get("immediate_relief_actions", [])
                + recommendation.get("corrective_actions", [])
            )

            if not actions:

                observation = recommendation.get("observation")

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

        overall = result.get("overall_recommendation", {})

        overall_actions = (
            overall.get("recommended_actions", [])
            + overall.get("immediate_relief_actions", [])
            + overall.get("corrective_actions", [])
        )

        if not overall_actions and overall.get("observation"):
            overall_actions = [overall["observation"]]

        for action in overall_actions:

            records.append({
                "category": "OVERALL_RECOMMENDATION",
                "priority": overall.get("priority", "NORMAL"),
                "recommendation": str(action),
                "reason": overall.get("observation", ""),
                "sensor_name": "overall_system",
                "timestamp": current_timestamp(),
            })

        if records:
            save_recommendations(records)

        return len(records)

    # --------------------------------------------------------
    # 5. COMPLETE MONITORING CYCLE
    # --------------------------------------------------------

    def run_cycle(self, mode="automatic"):

        timestamp = current_timestamp()

        # Read sensors only once.
        readings = read_all_sensors()

        # Store raw readings.
        saved_readings = self.store_raw_readings(readings)

        # Validate readings are physically plausible before analysis.
        validation = None
        if _HAS_CALIBRATION:
            try:
                validation = validate_readings(readings)
                if not validation["passed"]:
                    bad = [s for s, d in validation["sensors"].items() if not d["ok"]]
                    print(f"[Brain] Validation warning — implausible sensors: {bad}")
            except Exception:
                pass

        try:
            # Try ML inference first (Req 2.6, 11.1); fall back to Welford.
            if _HAS_INFERENCE:
                try:
                    # Build a simple flat feature vector from readings for inference.
                    fv, names = _build_feature_vector_from_readings(readings)
                    ml_status, trace = _inference.determine_status(
                        feature_vector=fv,
                        ts=timestamp,
                        parameter_names=names,
                    )
                    # Still run Welford for sensor-level statuses (it has richer detail).
                    engine_result = self.engine.process_readings(readings, mode=mode)
                    # Override overall status with ML result (most severe wins).
                    engine_overall = engine_result.get("overall_system_status", {}).get("status", "NORMAL")
                    from inference import _most_severe
                    final_status = _most_severe(ml_status, engine_overall)
                    engine_result["overall_system_status"]["status"] = final_status
                    engine_result["detection_trace"] = {
                        "model_version": trace.model_version,
                        "method": trace.method,
                        "ml_status": ml_status,
                    }
                except Exception:
                    engine_result = self.engine.process_readings(readings, mode=mode)
            else:
                engine_result = self.engine.process_readings(readings, mode=mode)

        except ValueError as error:
            return {
                "success": False,
                "timestamp": timestamp,
                "message": str(error),
                "sensor_readings_saved": saved_readings,
                "overall_system_status": "UNAVAILABLE",
            }

        sensor_statuses = engine_result.get("sensor_statuses", {})
        overall_status = engine_result.get("overall_system_status", {})
        if isinstance(overall_status, dict):
            overall_status_str = overall_status.get("status", "UNDER_OBSERVATION")
        else:
            overall_status_str = str(overall_status)

        recommendation_result = self.create_recommendations(sensor_statuses, overall_status_str)
        saved_recommendations = self.store_recommendations(recommendation_result)

        return {
            "success": True,
            "timestamp": timestamp,
            "mode": mode,
            "sensor_readings_saved": saved_readings,
            "sensor_statuses": sensor_statuses,
            "overall_system_status": overall_status_str,
            "engine_analysis": engine_result,
            "recommendations": recommendation_result,
            "recommendations_saved": saved_recommendations,
        }


# --------------------------------------------------------
# HELPER: build flat feature vector from raw readings dict
# --------------------------------------------------------

def _build_feature_vector_from_readings(readings):
    """Convert sensor readings dict to a flat (values, names) pair for inference."""
    if not isinstance(readings, dict):
        return [], []
    values, names = [], []
    for key, reading in readings.items():
        if not isinstance(reading, dict):
            continue
        v = reading.get("value")
        try:
            v = float(v)
            values.append(v)
            names.append(key)
        except (TypeError, ValueError):
            pass
    return values, names


# ------------------------------------------------------------
# STANDALONE TEST ENTRY POINT
# ------------------------------------------------------------

if __name__ == "__main__":

    brain = IntelliWatchBrain()

    result = brain.run_cycle(mode="automatic")

    print("\nINTELLIWATCH BRAIN RESULT")
    print("=" * 55)

    print("Success:", result["success"])

    print(
        "Overall Status:",
        result["overall_system_status"]
    )

    if result["success"]:

        print("\nSensor Statuses:")

        for sensor, data in result["sensor_statuses"].items():

            print(
                sensor,
                "->",
                data.get("status")
            )

        print(
            "\nRecommendations Saved:",
            result["recommendations_saved"]
        )

    else:

        print("\nMessage:", result["message"])