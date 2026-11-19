
import sqlite3
import json
import hashlib

from pathlib import Path
from datetime import datetime, timezone, timedelta


# =====================================================
# DATABASE CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "intelliwatch.db"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)

VALID_ROLES = {
    "ADMIN",
    "OPERATOR",
    "MAINTENANCE_ENGINEER",
}

EXPLORER_HISTORY_MAX_ROWS = 500
DEFAULT_RETENTION_DAYS = 365


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def _begin_transaction(connection):
    connection.execute("BEGIN IMMEDIATE")


def _insert_audit_entry(
    connection,
    category,
    detail_json,
    actor=None,
    target=None,
    hash_value=None,
):
    """Insert an audit entry using the current transaction."""

    timestamp = current_timestamp()

    if hash_value is None:
        previous = connection.execute("""
            SELECT hash
            FROM audit_entries
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        previous_hash = previous["hash"] if previous else ""

        chain_input = "|".join((
            str(previous_hash),
            timestamp,
            str(category),
            str(actor),
            str(target),
            str(detail_json),
        ))

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
        str(target) if target is not None else None,
        detail_json,
        hash_value,
    ))

    return cursor.lastrowid


def _audit_details(connection, category, actor, target, details):
    return _insert_audit_entry(
        connection,
        category,
        json.dumps(details or {}, default=str),
        actor=actor,
        target=target,
    )


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
                last_login TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0
                    CHECK (is_deleted IN (0, 1)),
                deleted_at TEXT,
                deleted_by TEXT,
                deletion_reason TEXT,
                deleted_was_active INTEGER NOT NULL DEFAULT 1
                    CHECK (deleted_was_active IN (0, 1))
            )
        """)

        # 7A. USER PERMISSIONS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_key TEXT NOT NULL,
                is_granted INTEGER NOT NULL
                    CHECK (is_granted IN (0, 1)),
                updated_by INTEGER,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (updated_by)
                    REFERENCES users(id)
                    ON DELETE SET NULL,
                UNIQUE (user_id, permission_key)
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

        # 17. ADMIN PROMOTION REQUESTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_promotion_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (
                        status IN (
                            'PENDING',
                            'APPROVED',
                            'REJECTED'
                        )
                    ),
                reviewed_by INTEGER,
                review_remarks TEXT,
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            )
        """)

        # 18. ACCOUNT RECOVERY REQUESTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_recovery_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recovery_reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (
                        status IN (
                            'PENDING',
                            'APPROVED',
                            'REJECTED'
                        )
                    ),
                reviewed_by INTEGER,
                review_remarks TEXT,
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            )
        """)

        # MIGRATE EXISTING DATABASES
        user_columns = {
            column["name"]
            for column in cursor.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        lifecycle_columns = {
            "is_deleted": (
                "INTEGER NOT NULL DEFAULT 0 "
                "CHECK (is_deleted IN (0, 1))"
            ),
            "deleted_at": "TEXT",
            "deleted_by": "TEXT",
            "deletion_reason": "TEXT",
            "deleted_was_active": (
                "INTEGER NOT NULL DEFAULT 1 "
                "CHECK (deleted_was_active IN (0, 1))"
            ),
        }

        for name, definition in lifecycle_columns.items():
            if name not in user_columns:
                cursor.execute(
                    f"ALTER TABLE users ADD COLUMN {name} {definition}"
                )

        # PERFORMANCE INDEXES
        indexes = (
            ("idx_sensor_timestamp", "sensor_readings(timestamp)"),
            (
                "idx_sensor_name_timestamp",
                "sensor_readings(sensor_name, timestamp)",
            ),
            (
                "idx_analytics_sensor_window",
                "sensor_analytics(sensor_name, window_end)",
            ),
            (
                "idx_assessment_timestamp",
                "machine_assessments(timestamp)",
            ),
            (
                "idx_anomaly_severity_timestamp",
                "anomaly_events(severity, timestamp)",
            ),
            (
                "idx_recommendation_assessment",
                "recommendations(assessment_id)",
            ),
            ("idx_users_role_active", "users(role, is_active)"),
            (
                "idx_user_permissions_user_id",
                "user_permissions(user_id)",
            ),
            ("idx_ml_models_active", "ml_models(family, is_active)"),
            (
                "idx_verified_model_ts",
                "verified_labels(model_version, verified_at)",
            ),
            (
                "idx_trend_model_time",
                "accuracy_trend(model_id, measured_at)",
            ),
            (
                "idx_control_intent_ts",
                "control_signals(intent, timestamp)",
            ),
            (
                "idx_audit_category_ts",
                "audit_entries(category, timestamp)",
            ),
            ("idx_edge_status", "edge_devices(status)"),
            (
                "idx_queue_device_delivered",
                "control_signal_queue(device_id, delivered_at)",
            ),
            ("idx_explorer_ts", "explorer_history(timestamp)"),
            (
                "idx_users_deleted_active",
                "users(is_deleted, is_active)",
            ),
        )

        for index_name, expression in indexes:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {expression}"
            )

        # ONE PENDING REQUEST PER USER
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_one_pending_admin_promotion
            ON admin_promotion_requests(user_id)
            WHERE status = 'PENDING'
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_one_pending_account_recovery
            ON account_recovery_requests(user_id)
            WHERE status = 'PENDING'
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
# 8. SENSOR READINGS AND ANALYTICS
# =====================================================

def save_sensor_readings(readings):
    if not readings:
        return 0

    timestamp = current_timestamp()

    records = [
        (
            item.get("timestamp", timestamp),
            item["sensor_name"],
            item["value"],
            item["unit"],
            item.get("axis"),
            item.get("quality", "VALID"),
            json.dumps(item.get("metadata", {})),
        )
        for item in readings
    ]

    connection = get_connection()

    try:
        connection.executemany("""
            INSERT INTO sensor_readings (
                timestamp, sensor_name, value, unit,
                axis, quality, metadata_json
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


def save_sensor_analytics(analytics):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO sensor_analytics (
                sensor_name, window_start, window_end,
                sample_count, minimum, maximum, average,
                rms, standard_deviation, anomaly_count,
                anomaly_rate, trend, status, created_at
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
            current_timestamp(),
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 9. MACHINE HEALTH AND ANOMALIES
# =====================================================

def save_machine_assessment(assessment):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO machine_assessments (
                timestamp, overall_status, confidence_score,
                anomaly_rate, health_score, probable_causes_json,
                sensor_summary_json, assessment_notes
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
            assessment.get("assessment_notes"),
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_anomaly_event(event):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO anomaly_events (
                timestamp, sensor_name, severity,
                observed_value, expected_min, expected_max,
                deviation, probable_cause, description,
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
            event.get("assessment_id"),
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_recommendations(recommendations):
    if not recommendations:
        return 0

    timestamp = current_timestamp()

    records = [
        (
            item.get("timestamp", timestamp),
            item.get("assessment_id"),
            item["category"],
            item["priority"],
            item["recommendation"],
            item.get("reason"),
            item.get("sensor_name"),
            item.get("action_status", "PENDING"),
        )
        for item in recommendations
    ]

    connection = get_connection()

    try:
        connection.executemany("""
            INSERT INTO recommendations (
                timestamp, assessment_id, category,
                priority, recommendation, reason,
                sensor_name, action_status
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
# 10. MACHINE CONFIGURATION
# =====================================================

def set_machine_config(name, value, unit=None, description=None):
    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO machine_config (
                parameter_name, parameter_value,
                unit, description, updated_at
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
            current_timestamp(),
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
        row = connection.execute("""
            SELECT parameter_value
            FROM machine_config
            WHERE parameter_name = ?
        """, (name,)).fetchone()

        return row["parameter_value"] if row else None

    finally:
        connection.close()


# =====================================================
# 11. HISTORICAL DATA RETRIEVAL
# =====================================================

def get_recent_sensor_readings(sensor_name, limit=100):
    limit = max(1, min(int(limit), 10000))
    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT *
            FROM sensor_readings
            WHERE sensor_name = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (sensor_name, limit)).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def get_recent_assessments(limit=50):
    limit = max(1, min(int(limit), 10000))
    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT *
            FROM machine_assessments
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def get_recent_anomalies(limit=50):
    limit = max(1, min(int(limit), 10000))
    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT *
            FROM anomaly_events
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


# =====================================================
# 12. USER ACCOUNT MANAGEMENT
# =====================================================

def create_user(username, full_name, password_hash, role):
    if not all(isinstance(value, str) for value in (
        username, full_name, password_hash, role
    )):
        raise ValueError("All user details must be strings.")

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
                username, full_name, password_hash,
                role, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            username,
            full_name,
            password_hash,
            role,
            current_timestamp(),
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
        row = connection.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (username.strip(),)).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def get_user_by_id(user_id):
    connection = get_connection()

    try:
        row = connection.execute("""
            SELECT
                id, username, full_name, role,
                is_active, created_at, last_login,
                is_deleted, deleted_at
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def get_all_users(include_deleted=False):
    connection = get_connection()

    try:
        query = """
            SELECT
                id, username, full_name, role,
                is_active, created_at, last_login,
                is_deleted, deleted_at
            FROM users
        """

        if not include_deleted:
            query += " WHERE is_deleted = 0"

        query += " ORDER BY id"

        rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    finally:
        connection.close()


def update_last_login(user_id):
    connection = get_connection()

    try:
        connection.execute("""
            UPDATE users
            SET last_login = ?
            WHERE id = ?
              AND is_active = 1
              AND is_deleted = 0
        """, (current_timestamp(), user_id))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def set_user_active(user_id, is_active, actor=None):
    """
    Activate or deactivate an account transactionally.

    The last active Admin cannot be deactivated.
    """

    connection = get_connection()

    try:
        _begin_transaction(connection)

        target = connection.execute("""
            SELECT id, username, role, is_active, is_deleted
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if not target or target["is_deleted"]:
            connection.rollback()
            return False

        active = int(bool(is_active))

        if (
            target["role"] == "ADMIN"
            and target["is_active"]
            and not active
        ):
            count = connection.execute("""
                SELECT COUNT(*) AS total
                FROM users
                WHERE role = 'ADMIN'
                  AND is_active = 1
                  AND is_deleted = 0
            """).fetchone()["total"]

            if count <= 1:
                raise ValueError(
                    "The last active administrator cannot be deactivated."
                )

        cursor = connection.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ? AND is_deleted = 0
        """, (active, user_id))

        if cursor.rowcount:
            _audit_details(
                connection,
                "USER_UNLOCKED" if active else "USER_LOCKED",
                actor,
                user_id,
                {
                    "username": target["username"],
                    "role": target["role"],
                    "is_active": bool(active),
                },
            )

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 13. ACCOUNT LIFECYCLE
# =====================================================

def delete_user(user_id: int, deleted_by=None, reason=None) -> bool:
    """
    Temporarily delete an Operator or Maintenance Engineer.

    The user record, permissions and related history are preserved.
    """

    connection = get_connection()

    try:
        _begin_transaction(connection)

        target = connection.execute("""
            SELECT *
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if (
            not target
            or target["is_deleted"]
            or target["role"] == "ADMIN"
        ):
            connection.rollback()
            return False

        connection.execute("""
            UPDATE users
            SET is_deleted = 1,
                is_active = 0,
                deleted_at = ?,
                deleted_by = ?,
                deletion_reason = ?,
                deleted_was_active = is_active
            WHERE id = ?
        """, (
            current_timestamp(),
            str(deleted_by) if deleted_by is not None else None,
            reason,
            user_id,
        ))

        _audit_details(
            connection,
            "USER_TEMPORARILY_DELETED",
            deleted_by,
            user_id,
            {
                "username": target["username"],
                "role": target["role"],
                "reason": reason,
                "previously_active": bool(target["is_active"]),
            },
        )

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def restore_user(user_id: int, restored_by=None) -> bool:
    """Restore a temporarily deleted account and its previous active state."""

    connection = get_connection()

    try:
        _begin_transaction(connection)

        target = connection.execute("""
            SELECT *
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if not target or not target["is_deleted"]:
            connection.rollback()
            return False

        connection.execute("""
            UPDATE users
            SET is_deleted = 0,
                is_active = deleted_was_active,
                deleted_at = NULL,
                deleted_by = NULL,
                deletion_reason = NULL,
                deleted_was_active = 1
            WHERE id = ?
        """, (user_id,))

        _audit_details(
            connection,
            "USER_RESTORED",
            restored_by,
            user_id,
            {
                "username": target["username"],
                "previous_role": target["role"],
            },
        )

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def permanently_delete_user(user_id: int, deleted_by=None) -> bool:
    """
    Permanently delete a previously soft-deleted non-Admin account.

    The permanent-deletion audit entry is inserted before the account
    is removed. Audit history is intentionally independent of users.
    """

    connection = get_connection()

    try:
        _begin_transaction(connection)

        target = connection.execute("""
            SELECT *
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if (
            not target
            or not target["is_deleted"]
            or target["role"] == "ADMIN"
        ):
            connection.rollback()
            return False

        _audit_details(
            connection,
            "USER_PERMANENTLY_DELETED",
            deleted_by,
            user_id,
            {
                "username": target["username"],
                "full_name": target["full_name"],
                "role": target["role"],
                "deleted_at": target["deleted_at"],
                "reason": target["deletion_reason"],
                "permanently_deleted_at": current_timestamp(),
            },
        )

        connection.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,),
        )

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 14. CONTROL ACKNOWLEDGEMENTS
# =====================================================

def save_control_ack(
    control_signal_id,
    ack_timestamp,
    resulting_equipment_state,
):
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
            control_signal_id,
        ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 15. AUDIT LOG
# =====================================================

def record_audit_entry(
    category,
    detail_json,
    actor=None,
    target=None,
    hash_value=None,
):
    """
    Append an audit entry.

    Generated hashes are chained transactionally. The optional explicit
    hash parameter is retained for compatibility with existing callers
    and test_database_helpers.py.
    """

    connection = get_connection()

    try:
        _begin_transaction(connection)

        entry_id = _insert_audit_entry(
            connection,
            category,
            detail_json,
            actor,
            target,
            hash_value,
        )

        connection.commit()
        return entry_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 16. ML LABELS AND ACCURACY
# =====================================================

def save_verified_label(
    event_id,
    label,
    feature_vector_json,
    model_version,
    verified_by,
):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO verified_labels (
                event_id, label, feature_vector_json,
                model_version, verified_by, verified_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            label,
            feature_vector_json,
            model_version,
            verified_by,
            current_timestamp(),
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def append_accuracy_trend(model_id, f1_score):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO accuracy_trend (
                model_id, f1_score, measured_at
            )
            VALUES (?, ?, ?)
        """, (
            model_id,
            f1_score,
            current_timestamp(),
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 17. EXPLORER HISTORY
# =====================================================

def _evict_explorer_history(connection):
    connection.execute("""
        DELETE FROM explorer_history
        WHERE id NOT IN (
            SELECT id
            FROM explorer_history
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        )
    """, (EXPLORER_HISTORY_MAX_ROWS,))


def save_explorer_history_entry(
    entry_type,
    active_user=None,
    arrangement_json=None,
    classification_label=None,
    confidence=None,
    model_version=None,
):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO explorer_history (
                timestamp, entry_type, active_user,
                arrangement_json, classification_label,
                confidence, model_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            current_timestamp(),
            entry_type,
            active_user,
            arrangement_json,
            classification_label,
            confidence,
            model_version,
        ))

        _evict_explorer_history(connection)

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_explorer_history(limit=100):
    limit = max(1, min(int(limit), 10000))
    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT *
            FROM explorer_history
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def get_explorer_history_entry(entry_id):
    connection = get_connection()

    try:
        row = connection.execute("""
            SELECT *
            FROM explorer_history
            WHERE id = ?
        """, (entry_id,)).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


# =====================================================
# 18. DATA RETENTION
# =====================================================

def cleanup_old_records(retention_days=None):
    """
    Retain sensor and anomaly data for the configured period.

    Audit entries are deliberately excluded to preserve security history.
    """

    days = (
        DEFAULT_RETENTION_DAYS
        if retention_days is None
        else max(1, int(retention_days))
    )

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()

    deleted = {}
    connection = get_connection()

    try:
        for table in ("sensor_readings", "anomaly_events"):
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE timestamp < ?",
                (cutoff,),
            )

            deleted[table] = cursor.rowcount

        deleted["audit_entries"] = 0

        connection.commit()
        return deleted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 19. EDGE DEVICE MANAGEMENT
# =====================================================

def save_edge_device(
    device_id,
    protocol,
    capabilities_json=None,
    status="offline",
):
    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO edge_devices (
                device_id, protocol, capabilities_json,
                status, registered_at
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
            current_timestamp(),
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_edge_device_status(
    device_id,
    status,
    last_known_state_json=None,
):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE edge_devices
            SET status = ?,
                last_known_state_json =
                    COALESCE(?, last_known_state_json)
            WHERE device_id = ?
        """, (
            status,
            last_known_state_json,
            device_id,
        ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 20. CONTROL SIGNAL QUEUE
# =====================================================

def queue_control_signal(device_id, intent, priority):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO control_signal_queue (
                device_id, intent, priority, queued_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            device_id,
            intent,
            priority,
            current_timestamp(),
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_queued_signals(device_id, undelivered_only=True):
    connection = get_connection()

    try:
        query = """
            SELECT *
            FROM control_signal_queue
            WHERE device_id = ?
        """

        if undelivered_only:
            query += " AND delivered_at IS NULL"

        query += " ORDER BY priority DESC, queued_at ASC, id ASC"

        rows = connection.execute(query, (device_id,)).fetchall()
        return [dict(row) for row in rows]

    finally:
        connection.close()


def mark_signal_delivered(queue_id):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE control_signal_queue
            SET delivered_at = ?
            WHERE id = ?
        """, (
            current_timestamp(),
            queue_id,
        ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 21. USER PERMISSION MANAGEMENT
# =====================================================

def get_user_permission_overrides(user_id):
    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT permission_key, is_granted
            FROM user_permissions
            WHERE user_id = ?
        """, (user_id,)).fetchall()

        return {
            row["permission_key"]: bool(row["is_granted"])
            for row in rows
        }

    finally:
        connection.close()


def set_user_permission(
    user_id,
    permission_key,
    is_granted,
    updated_by=None,
):
    if not isinstance(permission_key, str) or not permission_key.strip():
        raise ValueError("A valid permission key is required.")

    if type(is_granted) is not bool:
        raise ValueError("is_granted must be a boolean.")

    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO user_permissions (
                user_id, permission_key, is_granted,
                updated_by, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, permission_key)
            DO UPDATE SET
                is_granted = excluded.is_granted,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
        """, (
            user_id,
            permission_key.strip(),
            int(is_granted),
            updated_by,
            current_timestamp(),
        ))

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def clear_user_permission_override(user_id, permission_key):
    connection = get_connection()

    try:
        cursor = connection.execute("""
            DELETE FROM user_permissions
            WHERE user_id = ?
              AND permission_key = ?
        """, (
            user_id,
            permission_key,
        ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =====================================================
# 22. DATABASE STARTUP
# =====================================================

if __name__ == "__main__":
    initialize_database()
    print(f"Database location: {DATABASE_PATH}")
