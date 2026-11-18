
"""
INTELLIWATCH ENGINE
Version: 3.0

Purpose:
- Independent vibration, temperature and current tracking.
- Separate normal and abnormal sensor knowledge.
- Unknown sensor and combined-pattern investigation.
- Multi-sensor correlation and unified system assessment.
- Stability and scenario analysis.
- Manual and automatic analysis modes.
- SQLite persistence and historical tracking.

Dependencies:
- Python standard library.
- Existing sensor_reader.py

IMPORTANT:
Scenario scores are heuristic, not calibrated probabilities.
No universal equipment thresholds are assumed.
Unknown patterns are not automatically deleted due to instability.
"""

import json
import math
import sqlite3
import statistics

from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager


# ============================================================
# 1. CONFIGURATION
# ============================================================

DATABASE_PATH = (
    Path(__file__).resolve().parent
    / "database"
    / "intelliwatch.db"
)

MIN_PATTERN_OBSERVATIONS = 8
DECISION_CONFIDENCE_THRESHOLD = 0.65

KNOWN_PATTERN_DISTANCE = 3.5
UNKNOWN_PATTERN_DISTANCE = 3.0

TREND_WINDOW = 20

ANALYSIS_MODES = ("automatic", "manual")

SENSOR_NAMES = {
    "vibration": "Vibration",
    "temperature": "Temperature",
    "current": "Electrical Current"
}

EXPECTED_SENSORS = (
    "vibration",
    "temperature",
    "current"
)

STATUS_PRIORITY = {
    "NORMAL": 0,
    "UNKNOWN": 1,
    "UNDER_OBSERVATION": 2,
    "UNAVAILABLE": 3,
    "WARNING": 4,
    "CRITICAL": 5
}


# ============================================================
# 2. GENERAL UTILITIES
# ============================================================

def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def safe_json(value):
    return json.dumps(value, default=str)


def load_json(value, fallback=None):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback if fallback is not None else {}


def normalise_name(value):
    return str(value or "").strip().lower().replace(" ", "_")


def sensor_group(feature_name):
    """Identify the physical sensor responsible for a feature."""

    name = normalise_name(feature_name)

    if name.startswith("vibration"):
        return "vibration"

    if name.startswith("temperature"):
        return "temperature"

    if name.startswith("current"):
        return "current"

    return "other"


def safe_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


# ============================================================
# 3. SENSOR NORMALISATION
# ============================================================

def normalise_readings(data):

    if isinstance(data, dict):

        if isinstance(data.get("readings"), list):
            data = data["readings"]

        elif "value" in data:
            data = [data]

        else:
            data = [
                item for item in data.values()
                if isinstance(item, dict) and "value" in item
            ]

    if not isinstance(data, list):
        raise ValueError(
            "Sensor data must be a list or dictionary."
        )

    features = {}
    timestamp = current_timestamp()
    quality_values = []

    for reading in data:

        if not isinstance(reading, dict):
            continue

        quality = str(
            reading.get("quality", "GOOD")
        ).upper()

        if quality in (
            "BAD",
            "ERROR",
            "INVALID"
        ):
            continue

        value = safe_number(reading.get("value"))

        if value is None:
            continue

        sensor_type = normalise_name(
            reading.get("sensor_type")
            or reading.get("sensor_name")
        )

        parameter = normalise_name(
            reading.get("parameter", "value")
        )

        if any(
            word in sensor_type
            for word in ("vibration", "adxl")
        ):

            if (
                "magnitude" in parameter
                or parameter in ("value", "vibration")
            ):
                feature_name = "vibration"

            else:
                feature_name = f"vibration_{parameter}"

        elif any(
            word in sensor_type
            for word in ("temperature", "ds18")
        ):

            feature_name = "temperature"

        elif any(
            word in sensor_type
            for word in ("current", "acs712")
        ):

            feature_name = "current"

        else:

            feature_name = (
                f"{sensor_type}_{parameter}".strip("_")
            )

        features[feature_name] = value

        if reading.get("timestamp"):
            timestamp = reading["timestamp"]

        quality_values.append(quality)

    if not features:
        raise ValueError(
            "No valid numerical sensor readings received."
        )

    return {
        "timestamp": timestamp,
        "features": features,
        "quality": (
            "GOOD"
            if all(q == "GOOD" for q in quality_values)
            else "CHECK"
        )
    }


# ============================================================
# 4. MAIN ENGINE
# ============================================================

class IntelliWatchEngine:

    def __init__(self, database_path=None):

        self.database_path = Path(
            database_path or DATABASE_PATH
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.operating_limits = {}

        self.initialise_database()

    # ========================================================
    # 5. DATABASE
    # ========================================================

    @contextmanager
    def connect(self):

        connection = sqlite3.connect(
            self.database_path,
            timeout=30
        )

        connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def initialise_database(self):

        with self.connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    feature_names TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    means TEXT NOT NULL,
                    m2_values TEXT NOT NULL,
                    minimums TEXT NOT NULL,
                    maximums TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS unknown_patterns (
                    pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_names TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    means TEXT NOT NULL,
                    m2_values TEXT NOT NULL,
                    minimums TEXT NOT NULL,
                    maximums TEXT NOT NULL,
                    status TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS engine_observations (
                    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id INTEGER,
                    timestamp TEXT NOT NULL,
                    features TEXT NOT NULL,
                    quality TEXT,
                    FOREIGN KEY(pattern_id)
                    REFERENCES unknown_patterns(pattern_id)
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS analysis_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id INTEGER,
                    timestamp TEXT NOT NULL,
                    analysis_mode TEXT NOT NULL,
                    stability_score REAL,
                    scenarios TEXT,
                    decision TEXT,
                    explanation TEXT,
                    manual_note TEXT
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS sensor_knowledge_profiles (
                    sensor_profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_name TEXT NOT NULL,
                    feature_name TEXT NOT NULL,
                    label TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    mean_value REAL NOT NULL,
                    m2_value REAL NOT NULL,
                    minimum_value REAL NOT NULL,
                    maximum_value REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS sensor_status_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sensor_name TEXT NOT NULL,
                    feature_name TEXT NOT NULL,
                    sensor_value REAL NOT NULL,
                    status TEXT NOT NULL,
                    classification TEXT,
                    explanation TEXT
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS system_status_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    overall_status TEXT NOT NULL,
                    sensor_statuses TEXT NOT NULL,
                    explanation TEXT
                )
            """)

    # ========================================================
    # 6. STATISTICAL UTILITIES
    # ========================================================

    @staticmethod
    def feature_distance(
        features,
        means,
        m2_values,
        count
    ):

        if set(features) != set(means):
            return float("inf")

        distances = []

        for name, value in features.items():

            mean = means[name]

            variance = (
                m2_values[name] / (count - 1)
                if count > 1 else 0
            )

            std_dev = math.sqrt(
                max(variance, 0)
            )

            scale = max(
                std_dev,
                abs(mean) * 0.05,
                0.05
            )

            distances.append(
                abs(value - mean) / scale
            )

        return (
            statistics.mean(distances)
            if distances else float("inf")
        )

    @staticmethod
    def update_statistics(
        features,
        count,
        means,
        m2_values,
        minimums,
        maximums
    ):

        new_count = count + 1

        for name, value in features.items():

            if name not in means:
                means[name] = value
                m2_values[name] = 0.0
                minimums[name] = value
                maximums[name] = value
                continue

            delta = value - means[name]

            new_mean = (
                means[name] + delta / new_count
            )

            delta_after = value - new_mean

            m2_values[name] += (
                delta * delta_after
            )

            means[name] = new_mean

            minimums[name] = min(
                minimums[name],
                value
            )

            maximums[name] = max(
                maximums[name],
                value
            )

        return (
            new_count,
            means,
            m2_values,
            minimums,
            maximums
        )

    # ========================================================
    # 7. COMBINED KNOWLEDGE PROFILES
    # ========================================================

    def get_profiles(self, label=None):

        with self.connect() as connection:

            if label:

                rows = connection.execute("""
                    SELECT * FROM knowledge_profiles
                    WHERE label = ?
                """, (label,)).fetchall()

            else:

                rows = connection.execute("""
                    SELECT * FROM knowledge_profiles
                """).fetchall()

        return [
            {
                "profile_id": row["profile_id"],
                "label": row["label"],
                "feature_names": load_json(
                    row["feature_names"], []
                ),
                "sample_count": row["sample_count"],
                "means": load_json(row["means"]),
                "m2_values": load_json(row["m2_values"]),
                "minimums": load_json(row["minimums"]),
                "maximums": load_json(row["maximums"])
            }
            for row in rows
        ]

    def recognise_known_pattern(self, features):

        best_match = None
        best_distance = float("inf")

        for profile in self.get_profiles():

            distance = self.feature_distance(
                features,
                profile["means"],
                profile["m2_values"],
                profile["sample_count"]
            )

            if distance < best_distance:
                best_distance = distance
                best_match = profile

        if (
            best_match
            and best_distance <= KNOWN_PATTERN_DISTANCE
        ):

            return {
                "matched": True,
                "label": best_match["label"],
                "profile_id": best_match["profile_id"],
                "distance": round(best_distance, 4),
                "similarity_score": round(
                    math.exp(
                        -best_distance / KNOWN_PATTERN_DISTANCE
                    ),
                    4
                )
            }

        return {
            "matched": False,
            "label": "UNKNOWN",
            "distance": (
                round(best_distance, 4)
                if math.isfinite(best_distance)
                else None
            )
        }

    # ========================================================
    # 8. INDEPENDENT SENSOR KNOWLEDGE
    # ========================================================

    def get_sensor_profiles(
        self,
        sensor_name,
        feature_name
    ):

        with self.connect() as connection:

            rows = connection.execute("""
                SELECT * FROM sensor_knowledge_profiles
                WHERE sensor_name = ?
                AND feature_name = ?
            """, (
                sensor_name,
                feature_name
            )).fetchall()

        return [dict(row) for row in rows]

    def learn_sensor_feature(
        self,
        sensor_name,
        feature_name,
        value,
        label
    ):

        if label not in ("normal", "abnormal"):
            raise ValueError(
                "Invalid sensor knowledge label."
            )

        now = current_timestamp()

        with self.connect() as connection:

            rows = connection.execute("""
                SELECT * FROM sensor_knowledge_profiles
                WHERE sensor_name = ?
                AND feature_name = ?
                AND label = ?
            """, (
                sensor_name,
                feature_name,
                label
            )).fetchall()

            if rows:

                row = rows[0]

                count = row["sample_count"]
                mean = row["mean_value"]
                m2 = row["m2_value"]

                new_count = count + 1

                delta = value - mean

                new_mean = (
                    mean + delta / new_count
                )

                m2 += delta * (
                    value - new_mean
                )

                connection.execute("""
                    UPDATE sensor_knowledge_profiles
                    SET sample_count = ?,
                        mean_value = ?,
                        m2_value = ?,
                        minimum_value = ?,
                        maximum_value = ?,
                        updated_at = ?
                    WHERE sensor_profile_id = ?
                """, (
                    new_count,
                    new_mean,
                    m2,
                    min(row["minimum_value"], value),
                    max(row["maximum_value"], value),
                    now,
                    row["sensor_profile_id"]
                ))

            else:

                connection.execute("""
                    INSERT INTO sensor_knowledge_profiles (
                        sensor_name,
                        feature_name,
                        label,
                        sample_count,
                        mean_value,
                        m2_value,
                        minimum_value,
                        maximum_value,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sensor_name,
                    feature_name,
                    label,
                    1,
                    value,
                    0.0,
                    value,
                    value,
                    now,
                    now
                ))

    # ========================================================
    # 9. VERIFIED KNOWLEDGE REGISTRATION
    # ========================================================

    def learn_from_verified_pattern(
        self,
        readings,
        label,
        verified_by
    ):

        label = normalise_name(label)

        if label not in ("normal", "abnormal"):
            raise ValueError(
                "Label must be normal or abnormal."
            )

        if not str(verified_by).strip():
            raise ValueError(
                "Verification identity required."
            )

        result = normalise_readings(readings)

        features = result["features"]

        now = current_timestamp()

        with self.connect() as connection:

            connection.execute("""
                INSERT INTO knowledge_profiles (
                    label,
                    feature_names,
                    sample_count,
                    means,
                    m2_values,
                    minimums,
                    maximums,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                label,
                safe_json(list(features.keys())),
                1,
                safe_json(features),
                safe_json({
                    key: 0.0 for key in features
                }),
                safe_json(features),
                safe_json(features),
                now,
                now
            ))

        for feature_name, value in features.items():

            group = sensor_group(feature_name)

            if group == "other":
                continue

            self.learn_sensor_feature(
                group,
                feature_name,
                value,
                label
            )

        with self.connect() as connection:

            connection.execute("""
                INSERT INTO analysis_events (
                    timestamp,
                    analysis_mode,
                    decision,
                    explanation,
                    manual_note
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                now,
                "verified_registration",
                label,
                "Verified combined and individual sensor knowledge registered.",
                f"Verified by: {verified_by}"
            ))

        return {
            "success": True,
            "stored_as": label,
            "features": features
        }

    # ========================================================
    # 10. SENSOR-WISE STATUS ANALYSIS
    # ========================================================

    def get_sensor_limit(self, feature_name):

        return self.operating_limits.get(
            feature_name,
            {}
        )

    def analyse_sensor(self, feature_name, value):

        group = sensor_group(feature_name)

        if group == "other":

            return {
                "sensor": feature_name,
                "sensor_key": group,
                "feature": feature_name,
                "value": value,
                "status": "UNKNOWN",
                "classification": "UNKNOWN",
                "explanation": (
                    "No sensor-specific analysis configured."
                )
            }

        profiles = self.get_sensor_profiles(
            group,
            feature_name
        )

        normal_matches = []
        abnormal_matches = []

        for profile in profiles:

            count = profile["sample_count"]

            variance = (
                profile["m2_value"] / (count - 1)
                if count > 1 else 0
            )

            scale = max(
                math.sqrt(max(variance, 0)),
                abs(profile["mean_value"]) * 0.05,
                0.05
            )

            distance = abs(
                value - profile["mean_value"]
            ) / scale

            item = {
                "distance": distance,
                "profile": profile
            }

            if profile["label"] == "normal":
                normal_matches.append(item)

            elif profile["label"] == "abnormal":
                abnormal_matches.append(item)

        nearest_normal = (
            min(
                normal_matches,
                key=lambda item: item["distance"]
            )
            if normal_matches else None
        )

        nearest_abnormal = (
            min(
                abnormal_matches,
                key=lambda item: item["distance"]
            )
            if abnormal_matches else None
        )

        limits = self.get_sensor_limit(
            feature_name
        )

        critical_min = limits.get(
            "critical_minimum"
        )

        critical_max = limits.get(
            "critical_maximum"
        )

        if (
            critical_min is not None
            and value < critical_min
        ) or (
            critical_max is not None
            and value > critical_max
        ):

            status = "CRITICAL"
            classification = "ABNORMAL"

            explanation = (
                "Configured critical operating limit exceeded."
            )

        else:

            warning_min = limits.get(
                "warning_minimum"
            )

            warning_max = limits.get(
                "warning_maximum"
            )

            outside_warning = (
                warning_min is not None
                and value < warning_min
            ) or (
                warning_max is not None
                and value > warning_max
            )

            if outside_warning:

                status = "WARNING"
                classification = "ABNORMAL"

                explanation = (
                    "Configured warning operating limit exceeded."
                )

            elif (
                nearest_abnormal
                and nearest_abnormal["distance"]
                <= KNOWN_PATTERN_DISTANCE
                and (
                    not nearest_normal
                    or nearest_abnormal["distance"]
                    < nearest_normal["distance"]
                )
            ):

                status = "WARNING"
                classification = "ABNORMAL"

                explanation = (
                    "Sensor behaviour resembles established abnormal knowledge."
                )

            elif (
                nearest_normal
                and nearest_normal["distance"]
                <= KNOWN_PATTERN_DISTANCE
            ):

                status = "NORMAL"
                classification = "NORMAL"

                explanation = (
                    "Sensor behaviour matches established normal knowledge."
                )

            else:

                status = "UNKNOWN"
                classification = "UNKNOWN"

                explanation = (
                    "Insufficient sensor-specific knowledge to classify behaviour."
                )

        result = {
            "sensor": SENSOR_NAMES.get(group, group),
            "sensor_key": group,
            "feature": feature_name,
            "value": value,
            "status": status,
            "classification": classification,
            "explanation": explanation
        }

        self.save_sensor_status(result)

        return result

    # ========================================================
    # 11. SENSOR FEATURE AGGREGATION
    # ========================================================

    def aggregate_sensor_results(self, feature_results):
        """
        Preserve every feature result while producing one
        consolidated status for each physical sensor.

        The most severe feature status determines the
        consolidated physical sensor status.
        """

        grouped = {}

        for feature_name, result in feature_results.items():

            group = sensor_group(feature_name)

            if group == "other":
                continue

            grouped.setdefault(group, []).append(result)

        sensor_statuses = {}

        for group, results in grouped.items():

            representative = max(
                results,
                key=lambda item: STATUS_PRIORITY.get(
                    item["status"],
                    1
                )
            )

            status = representative["status"]

            explanations = [
                (
                    f"{item['feature']}: "
                    f"{item['status']} - "
                    f"{item['explanation']}"
                )
                for item in results
                if item["status"] != "NORMAL"
            ]

            if not explanations:

                explanation = (
                    "All analysed features of this sensor are normal."
                )

            else:

                explanation = "; ".join(
                    explanations
                )

            sensor_statuses[group] = {
                "sensor": SENSOR_NAMES[group],
                "sensor_key": group,
                "status": status,
                "classification": representative[
                    "classification"
                ],
                "value": representative["value"],
                "representative_feature": representative[
                    "feature"
                ],
                "feature_count": len(results),
                "feature_results": results,
                "explanation": explanation
            }

        return sensor_statuses

    def add_unavailable_sensors(self, sensor_statuses):
        """
        Missing physical sensors must not silently disappear
        or be treated as normal.
        """

        for sensor_key in EXPECTED_SENSORS:

            if sensor_key not in sensor_statuses:

                sensor_statuses[sensor_key] = {
                    "sensor": SENSOR_NAMES[sensor_key],
                    "sensor_key": sensor_key,
                    "status": "UNAVAILABLE",
                    "classification": "UNKNOWN",
                    "value": None,
                    "representative_feature": None,
                    "feature_count": 0,
                    "feature_results": [],
                    "explanation": (
                        "No valid reading was received from this sensor."
                    )
                }

        return sensor_statuses

    # ========================================================
    # 12. SENSOR STATUS HISTORY
    # ========================================================

    def save_sensor_status(self, result):

        with self.connect() as connection:

            connection.execute("""
                INSERT INTO sensor_status_history (
                    timestamp,
                    sensor_name,
                    feature_name,
                    sensor_value,
                    status,
                    classification,
                    explanation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                current_timestamp(),
                result["sensor_key"],
                result["feature"],
                result["value"],
                result["status"],
                result["classification"],
                result["explanation"]
            ))

    def get_sensor_history(
        self,
        sensor_name,
        limit=50
    ):

        with self.connect() as connection:

            rows = connection.execute("""
                SELECT * FROM sensor_status_history
                WHERE sensor_name = ?
                ORDER BY history_id DESC
                LIMIT ?
            """, (
                normalise_name(sensor_name),
                limit
            )).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ========================================================
    # 13. UNKNOWN COMBINED PATTERNS
    # ========================================================

    def get_unknown_patterns(self):

        with self.connect() as connection:

            rows = connection.execute("""
                SELECT * FROM unknown_patterns
                WHERE status = 'investigating'
            """).fetchall()

        return [
            {
                "pattern_id": row["pattern_id"],
                "feature_names": load_json(
                    row["feature_names"], []
                ),
                "sample_count": row["sample_count"],
                "means": load_json(row["means"]),
                "m2_values": load_json(row["m2_values"]),
                "minimums": load_json(row["minimums"]),
                "maximums": load_json(row["maximums"])
            }
            for row in rows
        ]

    def find_unknown_pattern(self, features):

        best_match = None
        best_distance = float("inf")

        for pattern in self.get_unknown_patterns():

            distance = self.feature_distance(
                features,
                pattern["means"],
                pattern["m2_values"],
                pattern["sample_count"]
            )

            if distance < best_distance:

                best_distance = distance
                best_match = pattern

        if (
            best_match
            and best_distance <= UNKNOWN_PATTERN_DISTANCE
        ):
            return best_match

        return None

    def store_unknown_observation(self, result):

        features = result["features"]
        timestamp = result["timestamp"]

        pattern = self.find_unknown_pattern(
            features
        )

        with self.connect() as connection:

            if pattern:

                pattern_id = pattern["pattern_id"]

                (
                    count,
                    means,
                    m2,
                    minimums,
                    maximums
                ) = self.update_statistics(
                    features,
                    pattern["sample_count"],
                    pattern["means"],
                    pattern["m2_values"],
                    pattern["minimums"],
                    pattern["maximums"]
                )

                connection.execute("""
                    UPDATE unknown_patterns
                    SET sample_count = ?,
                        means = ?,
                        m2_values = ?,
                        minimums = ?,
                        maximums = ?,
                        last_seen = ?
                    WHERE pattern_id = ?
                """, (
                    count,
                    safe_json(means),
                    safe_json(m2),
                    safe_json(minimums),
                    safe_json(maximums),
                    timestamp,
                    pattern_id
                ))

            else:

                pattern_id = connection.execute("""
                    INSERT INTO unknown_patterns (
                        feature_names,
                        sample_count,
                        means,
                        m2_values,
                        minimums,
                        maximums,
                        status,
                        first_seen,
                        last_seen
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    safe_json(list(features.keys())),
                    1,
                    safe_json(features),
                    safe_json({
                        key: 0.0 for key in features
                    }),
                    safe_json(features),
                    safe_json(features),
                    "investigating",
                    timestamp,
                    timestamp
                )).lastrowid

            connection.execute("""
                INSERT INTO engine_observations (
                    pattern_id,
                    timestamp,
                    features,
                    quality
                )
                VALUES (?, ?, ?, ?)
            """, (
                pattern_id,
                timestamp,
                safe_json(features),
                result["quality"]
            ))

        return pattern_id

    # ========================================================
    # 14. PATTERN HISTORY AND STABILITY
    # ========================================================

    def get_pattern_history(
        self,
        pattern_id,
        limit=TREND_WINDOW
    ):

        with self.connect() as connection:

            rows = connection.execute("""
                SELECT features, timestamp
                FROM engine_observations
                WHERE pattern_id = ?
                ORDER BY observation_id DESC
                LIMIT ?
            """, (
                pattern_id,
                limit
            )).fetchall()

        return [
            {
                "features": load_json(row["features"]),
                "timestamp": row["timestamp"]
            }
            for row in reversed(rows)
        ]

    def analyse_stability(self, pattern_id):

        history = self.get_pattern_history(
            pattern_id,
            TREND_WINDOW
        )

        if not history:

            return {
                "stability_score": 0.0,
                "consistency_score": 0.0,
                "trend_score": 0.0,
                "range_score": None,
                "observations": 0
            }

        feature_names = history[-1]["features"].keys()

        consistency_scores = []
        trend_scores = []
        range_scores = []

        for name in feature_names:

            values = [
                item["features"][name]
                for item in history
                if name in item["features"]
            ]

            if not values:
                continue

            mean_value = statistics.mean(values)

            if len(values) > 1:

                std_dev = statistics.pstdev(values)

                scale = max(
                    abs(mean_value),
                    0.05
                )

                consistency = 1 / (
                    1 + std_dev / scale
                )

                x_values = list(
                    range(len(values))
                )

                x_mean = statistics.mean(
                    x_values
                )

                denominator = sum(
                    (x - x_mean) ** 2
                    for x in x_values
                )

                slope = (
                    sum(
                        (x - x_mean) * (y - mean_value)
                        for x, y in zip(x_values, values)
                    ) / denominator
                    if denominator else 0
                )

                trend = 1 / (
                    1 + abs(slope) / scale
                )

            else:

                consistency = 0.5
                trend = 0.5

            consistency_scores.append(
                consistency
            )

            trend_scores.append(
                trend
            )

            limits = self.operating_limits.get(
                name
            )

            if limits:

                minimum = limits.get("minimum")
                maximum = limits.get("maximum")

                if (
                    minimum is not None
                    and maximum is not None
                ):

                    range_scores.append(
                        1.0
                        if minimum <= values[-1] <= maximum
                        else 0.0
                    )

        consistency_score = (
            statistics.mean(consistency_scores)
            if consistency_scores else 0.0
        )

        trend_score = (
            statistics.mean(trend_scores)
            if trend_scores else 0.0
        )

        range_score = (
            statistics.mean(range_scores)
            if range_scores else None
        )

        if range_score is None:

            stability = (
                consistency_score * 0.60
                + trend_score * 0.40
            )

        else:

            stability = (
                consistency_score * 0.40
                + trend_score * 0.30
                + range_score * 0.30
            )

        return {
            "stability_score": round(
                stability, 4
            ),
            "consistency_score": round(
                consistency_score, 4
            ),
            "trend_score": round(
                trend_score, 4
            ),
            "range_score": (
                round(range_score, 4)
                if range_score is not None
                else None
            ),
            "observations": len(history)
        }

    # ========================================================
    # 15. ABNORMAL SIMILARITY
    # ========================================================

    def abnormal_similarity(self, features):

        profiles = self.get_profiles(
            "abnormal"
        )

        distances = []

        for profile in profiles:

            distance = self.feature_distance(
                features,
                profile["means"],
                profile["m2_values"],
                profile["sample_count"]
            )

            if math.isfinite(distance):
                distances.append(distance)

        if not distances:
            return 0.0

        return 1 / (
            1 + min(distances)
        )

    # ========================================================
    # 16. SCENARIO ANALYSIS
    # ========================================================

    def predict_scenarios(
        self,
        features,
        stability
    ):

        stability_score = stability[
            "stability_score"
        ]

        abnormal_score = self.abnormal_similarity(
            features
        )

        instability = 1 - stability_score

        scores = {

            "temporary_operating_variation": (
                instability * 0.60
                + (1 - abnormal_score) * 0.20
                + (1 - stability["trend_score"]) * 0.20
            ),

            "developing_abnormal_behaviour": (
                abnormal_score * 0.65
                + instability * 0.35
            ),

            "new_stable_behaviour": (
                stability_score * 0.70
                + (1 - abnormal_score) * 0.30
            )
        }

        total = sum(scores.values())

        estimates = (
            {
                name: round(
                    score / total * 100,
                    2
                )
                for name, score in scores.items()
            }
            if total > 0 else
            {
                name: 0.0
                for name in scores
            }
        )

        return {
            "estimated_scenarios": estimates,
            "abnormal_similarity": round(
                abnormal_score, 4
            ),
            "interpretation": (
                "Relative heuristic estimates, not calibrated probabilities."
            )
        }

    # ========================================================
    # 17. AUTOMATIC UNKNOWN DECISION
    # ========================================================

    def make_automatic_decision(
        self,
        pattern_id,
        features,
        stability,
        scenarios
    ):

        probabilities = scenarios[
            "estimated_scenarios"
        ]

        if (
            stability["observations"]
            < MIN_PATTERN_OBSERVATIONS
        ):

            return {
                "decision": "continue_investigation",
                "reason": "Insufficient observations."
            }

        best_scenario = max(
            probabilities,
            key=probabilities.get
        )

        best_probability = (
            probabilities[best_scenario] / 100
        )

        # An unstable pattern is retained for investigation.
        # Instability alone is not evidence that it is invalid.
        if stability["stability_score"] < 0.25:

            return {
                "decision": "continue_investigation",
                "reason": (
                    "Pattern is unstable. Retained for further observation; "
                    "no knowledge update or deletion performed."
                )
            }

        if (
            best_scenario == "new_stable_behaviour"
            and best_probability >= DECISION_CONFIDENCE_THRESHOLD
            and stability["stability_score"] >= 0.65
        ):

            self.store_pattern_as_knowledge(
                pattern_id,
                "normal"
            )

            return {
                "decision": "learned_as_normal",
                "reason": (
                    "Stable behaviour met the initial evidence criteria."
                )
            }

        if (
            best_scenario == "developing_abnormal_behaviour"
            and best_probability >= DECISION_CONFIDENCE_THRESHOLD
            and scenarios["abnormal_similarity"] >= 0.55
        ):

            self.store_pattern_as_knowledge(
                pattern_id,
                "abnormal"
            )

            return {
                "decision": "learned_as_abnormal",
                "reason": (
                    "Behaviour resembles established abnormal knowledge."
                )
            }

        return {
            "decision": "continue_investigation",
            "reason": (
                "Evidence is not sufficient for a knowledge update."
            )
        }

    # ========================================================
    # 18. STORE VALIDATED COMBINED KNOWLEDGE
    # ========================================================

    def store_pattern_as_knowledge(
        self,
        pattern_id,
        label
    ):

        if label not in ("normal", "abnormal"):
            raise ValueError(
                "Knowledge label must be normal or abnormal."
            )

        # Retrieve ALL observations for learning.
        # The trend window is used for stability analysis,
        # not for discarding older learning history.
        with self.connect() as connection:

            rows = connection.execute("""
                SELECT features
                FROM engine_observations
                WHERE pattern_id = ?
                ORDER BY observation_id ASC
            """, (pattern_id,)).fetchall()

        history = [
            load_json(row["features"])
            for row in rows
        ]

        if not history:
            return

        feature_names = list(
            history[0].keys()
        )

        count = 0

        means = {
            key: 0.0
            for key in feature_names
        }

        m2 = {
            key: 0.0
            for key in feature_names
        }

        minimums = {
            key: float("inf")
            for key in feature_names
        }

        maximums = {
            key: float("-inf")
            for key in feature_names
        }

        for features in history:

            if set(features) != set(feature_names):
                continue

            (
                count,
                means,
                m2,
                minimums,
                maximums
            ) = self.update_statistics(
                features,
                count,
                means,
                m2,
                minimums,
                maximums
            )

        if count == 0:
            return

        now = current_timestamp()

        with self.connect() as connection:

            connection.execute("""
                INSERT INTO knowledge_profiles (
                    label,
                    feature_names,
                    sample_count,
                    means,
                    m2_values,
                    minimums,
                    maximums,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                label,
                safe_json(feature_names),
                count,
                safe_json(means),
                safe_json(m2),
                safe_json(minimums),
                safe_json(maximums),
                now,
                now
            ))

            connection.execute("""
                UPDATE unknown_patterns
                SET status = ?
                WHERE pattern_id = ?
            """, (
                f"learned_{label}",
                pattern_id
            ))

        # Register individual sensor knowledge.
        for feature_name in feature_names:

            group = sensor_group(feature_name)

            if group == "other":
                continue

            for features in history:

                if feature_name not in features:
                    continue

                self.learn_sensor_feature(
                    group,
                    feature_name,
                    features[feature_name],
                    label
                )

    def update_unknown_status(
        self,
        pattern_id,
        status
    ):

        with self.connect() as connection:

            connection.execute("""
                UPDATE unknown_patterns
                SET status = ?
                WHERE pattern_id = ?
            """, (
                status,
                pattern_id
            ))

    # ========================================================
    # 19. ANALYSIS EVENT HISTORY
    # ========================================================

    def save_analysis_event(
        self,
        pattern_id,
        mode,
        stability,
        scenarios,
        decision,
        explanation,
        manual_note=None
    ):

        with self.connect() as connection:

            connection.execute("""
                INSERT INTO analysis_events (
                    pattern_id,
                    timestamp,
                    analysis_mode,
                    stability_score,
                    scenarios,
                    decision,
                    explanation,
                    manual_note
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern_id,
                current_timestamp(),
                mode,
                stability["stability_score"],
                safe_json(scenarios),
                decision,
                explanation,
                manual_note
            ))

    # ========================================================
    # 20. MANUAL REVIEW
    # ========================================================

    def add_manual_review_note(
        self,
        pattern_id,
        reviewer,
        note
    ):

        if not str(reviewer).strip():
            raise ValueError(
                "Reviewer identity required."
            )

        if not str(note).strip():
            raise ValueError(
                "Review note cannot be empty."
            )

        stability = self.analyse_stability(
            pattern_id
        )

        scenarios = {
            "review_type": "manual",
            "human_observation": note,
            "reviewer": reviewer
        }

        self.save_analysis_event(
            pattern_id,
            "manual",
            stability,
            scenarios,
            "human_note_recorded",
            "Manual note recorded without changing system findings.",
            note
        )

        return {
            "success": True,
            "message": "Manual review recorded."
        }

    # ========================================================
    # 21. UNIFIED SYSTEM STATUS
    # ========================================================

    def calculate_overall_status(
        self,
        sensor_statuses
    ):

        statuses = [
            item["status"]
            for item in sensor_statuses.values()
        ]

        if "CRITICAL" in statuses:

            overall = "CRITICAL"

        elif "WARNING" in statuses:

            overall = "WARNING"

        elif (
            statuses
            and all(
                status == "NORMAL"
                for status in statuses
            )
        ):

            overall = "NORMAL"

        else:

            overall = "UNDER_OBSERVATION"

        explanations = []

        for sensor_name, result in sensor_statuses.items():

            if result["status"] != "NORMAL":

                explanations.append(
                    f"{result['sensor']}: "
                    f"{result['status']} - "
                    f"{result['explanation']}"
                )

        explanation = (
            "; ".join(explanations)
            if explanations else
            "All expected sensor assessments are normal."
        )

        return {
            "status": overall,
            "explanation": explanation
        }

    def save_system_status(
        self,
        overall,
        sensor_statuses
    ):

        with self.connect() as connection:

            connection.execute("""
                INSERT INTO system_status_history (
                    timestamp,
                    overall_status,
                    sensor_statuses,
                    explanation
                )
                VALUES (?, ?, ?, ?)
            """, (
                current_timestamp(),
                overall["status"],
                safe_json(sensor_statuses),
                overall["explanation"]
            ))

    # ========================================================
    # 22. MAIN PROCESSING
    # ========================================================

    def process_readings(
        self,
        readings,
        mode="automatic"
    ):

        mode = normalise_name(mode)

        if mode not in ANALYSIS_MODES:
            raise ValueError(
                "Mode must be automatic or manual."
            )

        result = normalise_readings(
            readings
        )

        features = result["features"]

        # A. Analyse every feature independently.
        feature_results = {}

        for feature_name, value in features.items():

            feature_results[feature_name] = (
                self.analyse_sensor(
                    feature_name,
                    value
                )
            )

        # B. Aggregate feature findings into physical
        # sensor-level findings without overwriting data.
        sensor_statuses = (
            self.aggregate_sensor_results(
                feature_results
            )
        )

        # C. Explicitly represent missing physical sensors.
        sensor_statuses = (
            self.add_unavailable_sensors(
                sensor_statuses
            )
        )

        # D. Recognise the complete combined pattern.
        known = self.recognise_known_pattern(
            features
        )

        pattern_id = None
        stability = None
        scenarios = None

        if known["matched"]:

            combined_decision = {
                "decision": "known_pattern",
                "classification": known["label"],
                "reason": (
                    "Combined behaviour matches established knowledge."
                )
            }

        else:

            # E. Investigate unfamiliar combined behaviour.
            pattern_id = self.store_unknown_observation(
                result
            )

            stability = self.analyse_stability(
                pattern_id
            )

            scenarios = self.predict_scenarios(
                features,
                stability
            )

            if mode == "manual":

                combined_decision = {
                    "decision": "awaiting_human_analysis",
                    "reason": (
                        "Manual analysis selected. "
                        "Human review is required."
                    )
                }

            else:

                combined_decision = (
                    self.make_automatic_decision(
                        pattern_id,
                        features,
                        stability,
                        scenarios
                    )
                )

        # F. Calculate the unified system status.
        overall = self.calculate_overall_status(
            sensor_statuses
        )

        self.save_system_status(
            overall,
            sensor_statuses
        )

        if pattern_id is not None:

            self.save_analysis_event(
                pattern_id,
                mode,
                stability,
                scenarios,
                combined_decision["decision"],
                combined_decision["reason"]
            )

        # G. Return the complete result.
        return {
            "timestamp": result["timestamp"],

            "sensor_statuses": sensor_statuses,

            "feature_results": feature_results,

            "overall_system_status": overall,

            "combined_pattern": {
                "recognition": known,
                "pattern_id": pattern_id,
                "decision": combined_decision
            },

            "internal_analysis": {
                "features": features,
                "stability": stability,
                "scenarios": scenarios,
                "analysis_mode": mode,
                "quality": result["quality"]
            }
        }

    # ========================================================
    # 23. LIVE SENSOR READER
    # ========================================================

    def process_live_cycle(
        self,
        mode="automatic"
    ):

        from sensor_reader import read_all_sensors

        readings = read_all_sensors()

        return self.process_readings(
            readings,
            mode
        )

    # ========================================================
    # 24. OPERATING LIMITS
    # ========================================================

    def set_operating_limits(self, limits):

        if not isinstance(limits, dict):
            raise ValueError(
                "Limits must be a dictionary."
            )

        self.operating_limits = limits

    # ========================================================
    # 25. KNOWLEDGE SUMMARY
    # ========================================================

    def get_knowledge_summary(self):

        with self.connect() as connection:

            normal_count = connection.execute("""
                SELECT COUNT(*) FROM knowledge_profiles
                WHERE label = 'normal'
            """).fetchone()[0]

            abnormal_count = connection.execute("""
                SELECT COUNT(*) FROM knowledge_profiles
                WHERE label = 'abnormal'
            """).fetchone()[0]

            unknown_count = connection.execute("""
                SELECT COUNT(*) FROM unknown_patterns
                WHERE status = 'investigating'
            """).fetchone()[0]

            removed_count = connection.execute("""
                SELECT COUNT(*) FROM unknown_patterns
                WHERE status = 'removed'
            """).fetchone()[0]

            sensor_normal = connection.execute("""
                SELECT COUNT(*) FROM sensor_knowledge_profiles
                WHERE label = 'normal'
            """).fetchone()[0]

            sensor_abnormal = connection.execute("""
                SELECT COUNT(*) FROM sensor_knowledge_profiles
                WHERE label = 'abnormal'
            """).fetchone()[0]

        return {
            "combined_normal_profiles": normal_count,
            "combined_abnormal_profiles": abnormal_count,
            "sensor_normal_profiles": sensor_normal,
            "sensor_abnormal_profiles": sensor_abnormal,
            "unknown_patterns_under_investigation": unknown_count,
            "removed_patterns": removed_count
        }


# ============================================================
# 26. STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    engine = IntelliWatchEngine()

    print("\n====================================")
    print("       INTELLIWATCH ENGINE")
    print("====================================")

    print("\nDatabase:", engine.database_path)

    print("\nKnowledge Summary:")

    print(
        json.dumps(
            engine.get_knowledge_summary(),
            indent=4
        )
    )

    print("\nTesting with simulated sensor readings...")

    try:

        result = engine.process_live_cycle(
            mode="automatic"
        )

        print("\nINDIVIDUAL SENSOR STATUSES")

        for sensor, details in result[
            "sensor_statuses"
        ].items():

            print(
                f"{details['sensor']}: "
                f"{details['status']}"
            )

        print("\nOVERALL SYSTEM STATUS")

        print(
            result["overall_system_status"]["status"]
        )

        print(
            result["overall_system_status"]["explanation"]
        )

        print("\nCOMPLETE ANALYSIS")

        print(
            json.dumps(
                result,
                indent=4
            )
        )

    except Exception as error:

        print("\nEngine test could not complete:")

        print(
            type(error).__name__,
            error
        )

    print("\nIntelliWatch Engine Test Finished.")
