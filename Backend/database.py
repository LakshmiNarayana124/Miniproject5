
import sqlite3
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone


# =====================================================
# INTELLIWATCH DATABASE CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "intelliwatch.db"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)

VALID_ROLES = {
    "ADMIN",
    "OPERATOR",
    "MAINTENANCE_ENGINEER"
}


def get_connection():
    """Create a configured SQLite connection."""

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def current_timestamp():
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


# =====================================================
# DATABASE INITIALIZATION
# =====================================================

def initialize_database():

    connection = get_connection()

    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")

        cursor = connection.cursor()

        # 1. RAW SENSOR READINGS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                axis TEXT,
                quality TEXT DEFAULT 'VALID',
                metadata_json TEXT
            )
        """)

        # 2. PROCESSED SENSOR ANALYTICS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_name TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                sample_count INTEGER DEFAULT 0,
                minimum REAL,
                maximum REAL,
                average REAL,
                rms REAL,
                standard_deviation REAL,
                anomaly_count INTEGER DEFAULT 0,
                anomaly_rate REAL DEFAULT 0,
                trend TEXT,
                status TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 3. MACHINE HEALTH ASSESSMENTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS machine_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                confidence_score REAL,
                anomaly_rate REAL,
                health_score REAL,
                probable_causes_json TEXT,
                sensor_summary_json TEXT,
                assessment_notes TEXT
            )
        """)

        # 4. ANOMALY EVENTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                observed_value REAL,
                expected_min REAL,
                expected_max REAL,
                deviation REAL,
                probable_cause TEXT,
                description TEXT,
                assessment_id INTEGER,
                FOREIGN KEY (assessment_id)
                    REFERENCES machine_assessments(id)
            )
        """)

        # 5. RECOMMENDATIONS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                assessment_id INTEGER,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                reason TEXT,
                sensor_name TEXT,
                action_status TEXT DEFAULT 'PENDING',
                FOREIGN KEY (assessment_id)
                    REFERENCES machine_assessments(id)
            )
        """)

        # 6. MACHINE CONFIGURATION
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS machine_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter_name TEXT NOT NULL UNIQUE,
                parameter_value TEXT NOT NULL,
                unit TEXT,
                description TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # 7. USER ACCOUNTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (
                    role IN (
                        'ADMIN',
                        'OPERATOR',
                        'MAINTENANCE_ENGINEER'
                    )
                ),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)

        # 8. ML MODELS REGISTRY
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family TEXT NOT NULL,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0
                    CHECK (is_active IN (0, 1)),
                training_timestamp TEXT NOT NULL,
                dataset_hash TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                metrics_json TEXT,
                schema_version TEXT DEFAULT '1.0',
                UNIQUE(family, version)
            )
        """)

        # 9. VERIFIED LABELS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verified_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                label TEXT NOT NULL,
                feature_vector_json TEXT NOT NULL,
                model_version TEXT NOT NULL,
                verified_by TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                FOREIGN KEY (event_id)
                    REFERENCES anomaly_events(id)
            )
        """)

        # 10. ACCURACY TREND
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accuracy_trend (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                f1_score REAL NOT NULL,
                measured_at TEXT NOT NULL,
                FOREIGN KEY (model_id)
                    REFERENCES ml_models(id)
            )
        """)

        # 11. CONTROL SIGNALS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS control_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                intent TEXT NOT NULL,
                system_status TEXT NOT NULL,
                target_equipment TEXT,
                priority INTEGER NOT NULL,
                triggering_params_json TEXT,
                model_version TEXT,
                ack_timestamp TEXT,
                resulting_equipment_state TEXT
            )
        """)

        # 12. AUDIT ENTRIES
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                actor TEXT,
                target TEXT,
                detail_json TEXT NOT NULL,
                hash TEXT NOT NULL
            )
        """)

        # 13. EDGE DEVICES
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edge_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                protocol TEXT NOT NULL,
                capabilities_json TEXT,
                status TEXT NOT NULL DEFAULT 'offline',
                last_known_state_json TEXT,
                last_heartbeat TEXT,
                registered_at TEXT NOT NULL
            )
        """)

        # 14. CONTROL SIGNAL QUEUE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS control_signal_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                priority INTEGER NOT NULL,
                queued_at TEXT NOT NULL,
                delivered_at TEXT,
                FOREIGN KEY (device_id)
                    REFERENCES edge_devices(device_id)
            )
        """)

        # 15. EXPLORER HISTORY
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS explorer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                active_user TEXT,
                arrangement_json TEXT,
                classification_label TEXT,
                confidence REAL,
                model_version TEXT,
                UNIQUE(timestamp, entry_type)
            )
        """)

        # 16. THRESHOLD DEFINITIONS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threshold_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter_name TEXT NOT NULL,
                normal_max REAL NOT NULL,
                warning_max REAL NOT NULL,
                source_standard TEXT,
                equipment_specific INTEGER NOT NULL DEFAULT 0
                    CHECK (equipment_specific IN (0, 1)),
                confirmed_by TEXT,
                confirmed_at TEXT,
                active INTEGER NOT NULL DEFAULT 0
            )
        """)

        # PERFORMANCE INDEXES

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_sensor_timestamp
            ON sensor_readings(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_sensor_name_timestamp
            ON sensor_readings(sensor_name, timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_analytics_sensor_window
            ON sensor_analytics(sensor_name, window_end)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_assessment_timestamp
            ON machine_assessments(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_anomaly_severity_timestamp
            ON anomaly_events(severity, timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_recommendation_assessment
            ON recommendations(assessment_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_users_role_active
            ON users(role, is_active)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_ml_models_active
            ON ml_models(family, is_active)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_verified_model_ts
            ON verified_labels(model_version, verified_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_trend_model_time
            ON accuracy_trend(model_id, measured_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_control_intent_ts
            ON control_signals(intent, timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_audit_category_ts
            ON audit_entries(category, timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_edge_status
            ON edge_devices(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_queue_device_delivered
            ON control_signal_queue(device_id, delivered_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_explorer_ts
            ON explorer_history(timestamp)
        """)

        connection.commit()

        print(
            "IntelliWatch SQLite database initialized successfully!"
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 8. SAVE RAW SENSOR READINGS
# =====================================================

def save_sensor_readings(readings):

    if not readings:
        return 0

    timestamp = current_timestamp()
    records = []

    for reading in readings:
        records.append((
            reading.get("timestamp", timestamp),
            reading["sensor_name"],
            reading["value"],
            reading["unit"],
            reading.get("axis"),
            reading.get("quality", "VALID"),
            json.dumps(reading.get("metadata", {}))
        ))

    connection = get_connection()

    try:
        connection.executemany("""
            INSERT INTO sensor_readings (
                timestamp,
                sensor_name,
                value,
                unit,
                axis,
                quality,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, records)

        connection.commit()
        return len(records)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 9. SAVE SENSOR ANALYTICS
# =====================================================

def save_sensor_analytics(analytics):

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO sensor_analytics (
                sensor_name,
                window_start,
                window_end,
                sample_count,
                minimum,
                maximum,
                average,
                rms,
                standard_deviation,
                anomaly_count,
                anomaly_rate,
                trend,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analytics["sensor_name"],
            analytics["window_start"],
            analytics["window_end"],
            analytics.get("sample_count", 0),
            analytics.get("minimum"),
            analytics.get("maximum"),
            analytics.get("average"),
            analytics.get("rms"),
            analytics.get("standard_deviation"),
            analytics.get("anomaly_count", 0),
            analytics.get("anomaly_rate", 0),
            analytics.get("trend"),
            analytics.get("status"),
            current_timestamp()
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 10. SAVE MACHINE ASSESSMENT
# =====================================================

def save_machine_assessment(assessment):

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO machine_assessments (
                timestamp,
                overall_status,
                confidence_score,
                anomaly_rate,
                health_score,
                probable_causes_json,
                sensor_summary_json,
                assessment_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assessment.get("timestamp", current_timestamp()),
            assessment["overall_status"],
            assessment.get("confidence_score"),
            assessment.get("anomaly_rate"),
            assessment.get("health_score"),
            json.dumps(assessment.get("probable_causes", [])),
            json.dumps(assessment.get("sensor_summary", {})),
            assessment.get("assessment_notes")
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 11. SAVE ANOMALY EVENTS
# =====================================================

def save_anomaly_event(event):

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO anomaly_events (
                timestamp,
                sensor_name,
                severity,
                observed_value,
                expected_min,
                expected_max,
                deviation,
                probable_cause,
                description,
                assessment_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get("timestamp", current_timestamp()),
            event["sensor_name"],
            event["severity"],
            event.get("observed_value"),
            event.get("expected_min"),
            event.get("expected_max"),
            event.get("deviation"),
            event.get("probable_cause"),
            event.get("description"),
            event.get("assessment_id")
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 12. SAVE RECOMMENDATIONS
# =====================================================

def save_recommendations(recommendations):

    if not recommendations:
        return 0

    timestamp = current_timestamp()
    records = []

    for item in recommendations:
        records.append((
            item.get("timestamp", timestamp),
            item.get("assessment_id"),
            item["category"],
            item["priority"],
            item["recommendation"],
            item.get("reason"),
            item.get("sensor_name"),
            item.get("action_status", "PENDING")
        ))

    connection = get_connection()

    try:
        connection.executemany("""
            INSERT INTO recommendations (
                timestamp,
                assessment_id,
                category,
                priority,
                recommendation,
                reason,
                sensor_name,
                action_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

        connection.commit()
        return len(records)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 13. MACHINE CONFIGURATION
# =====================================================

def set_machine_config(
    name,
    value,
    unit=None,
    description=None
):

    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO machine_config (
                parameter_name,
                parameter_value,
                unit,
                description,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(parameter_name)
            DO UPDATE SET
                parameter_value = excluded.parameter_value,
                unit = excluded.unit,
                description = excluded.description,
                updated_at = excluded.updated_at
        """, (
            name,
            str(value),
            unit,
            description,
            current_timestamp()
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_machine_config(name):

    connection = get_connection()

    try:
        result = connection.execute("""
            SELECT parameter_value
            FROM machine_config
            WHERE parameter_name = ?
        """, (name,)).fetchone()

        return result["parameter_value"] if result else None

    finally:
        connection.close()


# =====================================================
# 14. RETRIEVE HISTORICAL DATA
# =====================================================

def get_recent_sensor_readings(sensor_name, limit=100):

    limit = max(1, min(int(limit), 10000))

    connection = get_connection()

    try:
        results = connection.execute("""
            SELECT *
            FROM sensor_readings
            WHERE sensor_name = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (sensor_name, limit)).fetchall()

        return [dict(row) for row in results]

    finally:
        connection.close()


def get_recent_assessments(limit=50):

    limit = max(1, min(int(limit), 10000))

    connection = get_connection()

    try:
        results = connection.execute("""
            SELECT *
            FROM machine_assessments
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in results]

    finally:
        connection.close()


def get_recent_anomalies(limit=50):

    limit = max(1, min(int(limit), 10000))

    connection = get_connection()

    try:
        results = connection.execute("""
            SELECT *
            FROM anomaly_events
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in results]

    finally:
        connection.close()


# =====================================================
# 15. USER ACCOUNT MANAGEMENT
# =====================================================

def create_user(username, full_name, password_hash, role):

    username = username.strip()
    full_name = full_name.strip()
    role = role.upper().strip()

    if not username or not full_name or not password_hash:
        raise ValueError("All user details are required.")

    if role not in VALID_ROLES:
        raise ValueError("Invalid user role.")

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO users (
                username,
                full_name,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            username,
            full_name,
            password_hash,
            role,
            current_timestamp()
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_user_by_username(username):

    connection = get_connection()

    try:
        result = connection.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (username.strip(),)).fetchone()

        return dict(result) if result else None

    finally:
        connection.close()


def get_user_by_id(user_id):

    connection = get_connection()

    try:
        result = connection.execute("""
            SELECT
                id,
                username,
                full_name,
                role,
                is_active,
                created_at,
                last_login
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        return dict(result) if result else None

    finally:
        connection.close()


def get_all_users():

    connection = get_connection()

    try:
        results = connection.execute("""
            SELECT
                id,
                username,
                full_name,
                role,
                is_active,
                created_at,
                last_login
            FROM users
            ORDER BY id
        """).fetchall()

        return [dict(row) for row in results]

    finally:
        connection.close()


def update_last_login(user_id):

    connection = get_connection()

    try:
        connection.execute("""
            UPDATE users
            SET last_login = ?
            WHERE id = ?
        """, (current_timestamp(), user_id))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def set_user_active(user_id, is_active):

    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ?
        """, (int(bool(is_active)), user_id))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 16. PERMANENT USER DELETION
# =====================================================

def delete_user(user_id: int) -> bool:
    """
    Permanently delete an Operator or Maintenance Engineer.

    Administrator accounts are protected.

    Returns:
        True: Account deleted.
        False: Account not found or deletion not permitted.
    """

    connection = get_connection()

    try:
        cursor = connection.execute("""
            DELETE FROM users
            WHERE id = ?
            AND role IN (
                'OPERATOR',
                'MAINTENANCE_ENGINEER'
            )
        """, (user_id,))

        connection.commit()

        return cursor.rowcount == 1

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 17. AIML PERSISTENCE HELPERS
# =====================================================

def save_control_ack(control_signal_id, ack_timestamp, resulting_equipment_state):
    """
    Record a control-signal acknowledgement.

    Updates the matching control_signals row with the acknowledgement
    timestamp and the resulting equipment state (Req 3.8).

    Returns:
        True when a row was updated, False otherwise.
    """

    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE control_signals
            SET ack_timestamp = ?,
                resulting_equipment_state = ?
            WHERE id = ?
        """, (
            ack_timestamp,
            resulting_equipment_state,
            control_signal_id
        ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def record_audit_entry(category, detail_json, actor=None, target=None, hash_value=None):
    """
    Append an immutable audit entry to the audit log (Req 13.1).

    When no hash is supplied, a tamper-evident chain hash is computed from
    the previous entry's hash chained with the current row content. Passing
    an explicit hash_value bypasses the chain computation.

    Returns:
        The id of the inserted audit entry.
    """

    timestamp = current_timestamp()

    connection = get_connection()

    try:
        if hash_value is None:
            previous = connection.execute("""
                SELECT hash
                FROM audit_entries
                ORDER BY id DESC
                LIMIT 1
            """).fetchone()

            previous_hash = previous["hash"] if previous else ""

            chain_input = "|".join([
                str(previous_hash),
                timestamp,
                str(category),
                str(actor),
                str(target),
                str(detail_json)
            ])

            hash_value = hashlib.sha256(
                chain_input.encode("utf-8")
            ).hexdigest()

        cursor = connection.execute("""
            INSERT INTO audit_entries (
                timestamp,
                category,
                actor,
                target,
                detail_json,
                hash
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            category,
            actor,
            target,
            detail_json,
            hash_value
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_verified_label(event_id, label, feature_vector_json, model_version, verified_by):
    """
    Persist an operator-verified label alongside its originating feature
    vector, the model version that produced the original decision, and the
    verification timestamp (Req 8.1/8.2).

    Returns:
        The id of the inserted verified_labels row.
    """

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO verified_labels (
                event_id,
                label,
                feature_vector_json,
                model_version,
                verified_by,
                verified_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            label,
            feature_vector_json,
            model_version,
            verified_by,
            current_timestamp()
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def append_accuracy_trend(model_id, f1_score):
    """
    Append an F1-score measurement to the accuracy trend for a model
    (Req 8.5).

    Returns:
        The id of the inserted accuracy_trend row.
    """

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO accuracy_trend (
                model_id,
                f1_score,
                measured_at
            )
            VALUES (?, ?, ?)
        """, (
            model_id,
            f1_score,
            current_timestamp()
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_explorer_history_entry(
    entry_type,
    active_user=None,
    arrangement_json=None,
    classification_label=None,
    confidence=None,
    model_version=None
):
    """
    Persist a 3D Sensor Explorer workspace state change or ML classification
    to the explorer history log (Req 6.1/6.2).

    After each insert, evicts the oldest entries beyond the retention cap
    (Req 6.5/6.6) so the log never grows unbounded.

    Returns:
        The id of the inserted explorer_history row.
    """

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO explorer_history (
                timestamp,
                entry_type,
                active_user,
                arrangement_json,
                classification_label,
                confidence,
                model_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            current_timestamp(),
            entry_type,
            active_user,
            arrangement_json,
            classification_label,
            confidence,
            model_version
        ))

        # Evict oldest entries beyond the retention cap (Req 6.5/6.6).
        _evict_explorer_history(connection)

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# Maximum number of explorer history rows retained (Req 6.5/6.6).
EXPLORER_HISTORY_MAX_ROWS = 500

# Default data retention period in days (Req 13.4).
DEFAULT_RETENTION_DAYS = 365


def _evict_explorer_history(connection):
    """Evict oldest explorer_history rows beyond the retention cap.

    Retains the most recent ``EXPLORER_HISTORY_MAX_ROWS`` entries and
    deletes the rest so the log is capped at 500 rows (Req 6.5/6.6).
    """

    connection.execute("""
        DELETE FROM explorer_history
        WHERE id NOT IN (
            SELECT id
            FROM explorer_history
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        )
    """, (EXPLORER_HISTORY_MAX_ROWS,))


def cleanup_old_records(retention_days=None):
    """
    Delete records older than a configurable retention period (Req 13.4).

    Removes rows from ``sensor_readings``, ``anomaly_events``, and
    ``audit_entries`` whose timestamp is older than ``retention_days``
    (default 365).  The cutoff is computed from the current UTC time.

    Parameters
    ----------
    retention_days : int | None
        Number of days to retain.  Defaults to
        ``DEFAULT_RETENTION_DAYS`` (365).

    Returns
    -------
    dict
        Counts of deleted rows per table.
    """

    if retention_days is None:
        retention_days = DEFAULT_RETENTION_DAYS

    retention_days = max(1, int(retention_days))

    cutoff = (
        datetime.now(timezone.utc) - _timedelta(days=retention_days)
    ).isoformat()

    deleted = {}
    connection = get_connection()

    try:
        for table, ts_column in (
            ("sensor_readings", "timestamp"),
            ("anomaly_events", "timestamp"),
            ("audit_entries", "timestamp"),
        ):
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE {ts_column} < ?",
                (cutoff,)
            )
            deleted[table] = cursor.rowcount

        connection.commit()
        return deleted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _timedelta(days):
    """Return a timedelta without importing the name at module level."""
    from datetime import timedelta
    return timedelta(days=days)


def get_explorer_history(limit=100):
    """
    Return recent explorer history entries in reverse-chronological order
    (Req 6.3).
    """

    limit = max(1, min(int(limit), 10000))

    connection = get_connection()

    try:
        results = connection.execute("""
            SELECT *
            FROM explorer_history
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in results]

    finally:
        connection.close()


def get_explorer_history_entry(entry_id):
    """
    Return a single explorer history entry by id (Req 6.4).
    """

    connection = get_connection()

    try:
        result = connection.execute("""
            SELECT *
            FROM explorer_history
            WHERE id = ?
        """, (entry_id,)).fetchone()

        return dict(result) if result else None

    finally:
        connection.close()


def save_edge_device(device_id, protocol, capabilities_json=None, status='offline'):
    """
    Upsert an edge device registration. Inserts a new device or updates the
    protocol, capabilities, and status of an existing device while keeping
    the original registration timestamp.
    """

    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO edge_devices (
                device_id,
                protocol,
                capabilities_json,
                status,
                registered_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(device_id)
            DO UPDATE SET
                protocol = excluded.protocol,
                capabilities_json = excluded.capabilities_json,
                status = excluded.status
        """, (
            device_id,
            protocol,
            capabilities_json,
            status,
            current_timestamp()
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_edge_device_status(device_id, status, last_known_state_json=None):
    """
    Update an edge device's status and, optionally, its last known state
    (Req 4.6).

    Returns:
        True when a row was updated, False otherwise.
    """

    connection = get_connection()

    try:
        if last_known_state_json is not None:
            cursor = connection.execute("""
                UPDATE edge_devices
                SET status = ?,
                    last_known_state_json = ?
                WHERE device_id = ?
            """, (
                status,
                last_known_state_json,
                device_id
            ))
        else:
            cursor = connection.execute("""
                UPDATE edge_devices
                SET status = ?
                WHERE device_id = ?
            """, (
                status,
                device_id
            ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def queue_control_signal(device_id, intent, priority):
    """
    Queue an outbound control signal for an edge device while it is
    temporarily disconnected (Req 12.3).

    Returns:
        The id of the inserted control_signal_queue row.
    """

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO control_signal_queue (
                device_id,
                intent,
                priority,
                queued_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            device_id,
            intent,
            priority,
            current_timestamp()
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_queued_signals(device_id, undelivered_only=True):
    """
    Return queued control signals for a device, ordered by priority
    (highest first) then queue time (oldest first). When undelivered_only
    is True, only signals that have not yet been delivered are returned.
    """

    connection = get_connection()

    try:
        if undelivered_only:
            results = connection.execute("""
                SELECT *
                FROM control_signal_queue
                WHERE device_id = ?
                  AND delivered_at IS NULL
                ORDER BY priority DESC, queued_at ASC, id ASC
            """, (device_id,)).fetchall()
        else:
            results = connection.execute("""
                SELECT *
                FROM control_signal_queue
                WHERE device_id = ?
                ORDER BY priority DESC, queued_at ASC, id ASC
            """, (device_id,)).fetchall()

        return [dict(row) for row in results]

    finally:
        connection.close()


def mark_signal_delivered(queue_id):
    """
    Mark a queued control signal as delivered (Req 12.3).

    Returns:
        True when a row was updated, False otherwise.
    """

    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE control_signal_queue
            SET delivered_at = ?
            WHERE id = ?
        """, (
            current_timestamp(),
            queue_id
        ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 18. DATABASE STARTUP
# =====================================================

if __name__ == "__main__":

    initialize_database()

    print(f"Database location: {DATABASE_PATH}")
