"""
IntelliWatch — Database Layer
Supports PostgreSQL (via DATABASE_URL env var, e.g. Neon) with SQLite
fallback for local development.

Postgres is used when DATABASE_URL is set. SQLite is used otherwise.
All query syntax uses %s placeholders (psycopg2). SQLite receives
the same placeholders via a thin adapter that rewrites them back to ?.
"""

import os
import re
import json
import hashlib
import sqlite3

from pathlib import Path
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager


# =====================================================
# CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_USE_POSTGRES = bool(DATABASE_URL)

_env_db_path = os.getenv("INTELLIWATCH_DB_PATH", "").strip()
if _env_db_path:
    DATABASE_PATH = Path(_env_db_path)
    DATABASE_DIR = DATABASE_PATH.parent
else:
    DATABASE_DIR = BASE_DIR / "database"
    DATABASE_PATH = DATABASE_DIR / "intelliwatch.db"

if not _USE_POSTGRES:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

VALID_ROLES = {
    "ADMIN",
    "OPERATOR",
    "MAINTENANCE_ENGINEER",
}

EXPLORER_HISTORY_MAX_ROWS = 500
DEFAULT_RETENTION_DAYS = 365


# =====================================================
# CONNECTION
# =====================================================

def get_connection():
    if _USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        conn.autocommit = False
        return conn

    conn = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _cursor(conn):
    """Return a cursor. Works for both psycopg2 and sqlite3."""
    if _USE_POSTGRES:
        return conn.cursor()
    return conn.cursor()


def _sql(query):
    """Convert %s placeholders to ? for SQLite."""
    if _USE_POSTGRES:
        return query
    return re.sub(r'%s', '?', query)


def _exec(conn, query, params=()):
    """Execute a query on conn, returning the cursor."""
    cur = conn.cursor()
    cur.execute(_sql(query), params)
    return cur


def _fetchone(conn, query, params=()):
    cur = _exec(conn, query, params)
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def _fetchall(conn, query, params=()):
    cur = _exec(conn, query, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def _lastrowid(conn, cur, table=""):
    """Get the last inserted row id in a backend-agnostic way."""
    if _USE_POSTGRES:
        row = cur.fetchone()
        if row:
            return row.get("id") or row.get(list(row.keys())[0])
        return None
    return cur.lastrowid


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def _begin_transaction(conn):
    if not _USE_POSTGRES:
        _exec(conn, "BEGIN IMMEDIATE")
    # psycopg2 is implicitly transactional; no explicit BEGIN needed.


# =====================================================
# AUDIT CHAIN
# =====================================================

def _insert_audit_entry(
    conn,
    category,
    detail_json,
    actor=None,
    target=None,
    hash_value=None,
):
    timestamp = current_timestamp()

    if hash_value is None:
        previous = _fetchone(conn, """
            SELECT hash FROM audit_entries
            ORDER BY id DESC LIMIT 1
        """)
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

    if _USE_POSTGRES:
        cur = _exec(conn, """
            INSERT INTO audit_entries (
                timestamp, category, actor, target, detail_json, hash
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (timestamp, category, actor,
              str(target) if target is not None else None,
              detail_json, hash_value))
        return _lastrowid(conn, cur)
    else:
        cur = _exec(conn, """
            INSERT INTO audit_entries (
                timestamp, category, actor, target, detail_json, hash
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, category, actor,
              str(target) if target is not None else None,
              detail_json, hash_value))
        return cur.lastrowid


def _audit_details(conn, category, actor, target, details):
    return _insert_audit_entry(
        conn, category,
        json.dumps(details or {}, default=str),
        actor=actor, target=target,
    )


# =====================================================
# DATABASE INITIALIZATION
# =====================================================

def initialize_database():
    conn = get_connection()
    try:
        if not _USE_POSTGRES:
            _exec(conn, "PRAGMA journal_mode = WAL")
            _exec(conn, "PRAGMA synchronous = NORMAL")

        # 1. SENSOR READINGS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                axis TEXT,
                quality TEXT DEFAULT 'VALID',
                metadata_json TEXT
            )
        """ if _USE_POSTGRES else """
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

        # 2. SENSOR ANALYTICS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS sensor_analytics (
                id SERIAL PRIMARY KEY,
                sensor_name TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                sample_count INTEGER DEFAULT 0,
                minimum REAL, maximum REAL, average REAL,
                rms REAL, standard_deviation REAL,
                anomaly_count INTEGER DEFAULT 0,
                anomaly_rate REAL DEFAULT 0,
                trend TEXT, status TEXT,
                created_at TEXT NOT NULL
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS sensor_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_name TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                sample_count INTEGER DEFAULT 0,
                minimum REAL, maximum REAL, average REAL,
                rms REAL, standard_deviation REAL,
                anomaly_count INTEGER DEFAULT 0,
                anomaly_rate REAL DEFAULT 0,
                trend TEXT, status TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 3. MACHINE ASSESSMENTS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS machine_assessments (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                confidence_score REAL, anomaly_rate REAL,
                health_score REAL, probable_causes_json TEXT,
                sensor_summary_json TEXT, assessment_notes TEXT
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS machine_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                confidence_score REAL, anomaly_rate REAL,
                health_score REAL, probable_causes_json TEXT,
                sensor_summary_json TEXT, assessment_notes TEXT
            )
        """)

        # 4. ANOMALY EVENTS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS anomaly_events (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                observed_value REAL, expected_min REAL,
                expected_max REAL, deviation REAL,
                probable_cause TEXT, description TEXT,
                assessment_id INTEGER,
                FOREIGN KEY (assessment_id)
                    REFERENCES machine_assessments(id)
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS anomaly_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                observed_value REAL, expected_min REAL,
                expected_max REAL, deviation REAL,
                probable_cause TEXT, description TEXT,
                assessment_id INTEGER,
                FOREIGN KEY (assessment_id)
                    REFERENCES machine_assessments(id)
            )
        """)

        # 5. RECOMMENDATIONS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS recommendations (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                assessment_id INTEGER,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                reason TEXT, sensor_name TEXT,
                action_status TEXT DEFAULT 'PENDING',
                FOREIGN KEY (assessment_id)
                    REFERENCES machine_assessments(id)
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                assessment_id INTEGER,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                reason TEXT, sensor_name TEXT,
                action_status TEXT DEFAULT 'PENDING',
                FOREIGN KEY (assessment_id)
                    REFERENCES machine_assessments(id)
            )
        """)

        # 6. MACHINE CONFIG
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS machine_config (
                id SERIAL PRIMARY KEY,
                parameter_name TEXT NOT NULL UNIQUE,
                parameter_value TEXT NOT NULL,
                unit TEXT, description TEXT,
                updated_at TEXT NOT NULL
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS machine_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter_name TEXT NOT NULL UNIQUE,
                parameter_value TEXT NOT NULL,
                unit TEXT, description TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # 7. USERS
        if _USE_POSTGRES:
            _exec(conn, """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN (
                        'ADMIN','OPERATOR','MAINTENANCE_ENGINEER')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    deleted_at TEXT,
                    deleted_by TEXT,
                    deletion_reason TEXT,
                    deleted_was_active INTEGER NOT NULL DEFAULT 1,
                    session_version INTEGER NOT NULL DEFAULT 0
                )
            """)
        else:
            _exec(conn, """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN (
                        'ADMIN','OPERATOR','MAINTENANCE_ENGINEER')),
                    is_active INTEGER NOT NULL DEFAULT 1
                        CHECK (is_active IN (0,1)),
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    is_deleted INTEGER NOT NULL DEFAULT 0
                        CHECK (is_deleted IN (0,1)),
                    deleted_at TEXT,
                    deleted_by TEXT,
                    deletion_reason TEXT,
                    deleted_was_active INTEGER NOT NULL DEFAULT 1
                        CHECK (deleted_was_active IN (0,1)),
                    session_version INTEGER NOT NULL DEFAULT 0
                )
            """)

        # 7A. USER PERMISSIONS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS user_permissions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                permission_key TEXT NOT NULL,
                is_granted INTEGER NOT NULL,
                updated_by INTEGER,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (updated_by)
                    REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE (user_id, permission_key)
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_key TEXT NOT NULL,
                is_granted INTEGER NOT NULL
                    CHECK (is_granted IN (0,1)),
                updated_by INTEGER,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (updated_by)
                    REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE (user_id, permission_key)
            )
        """)

        # 8. ML MODELS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS ml_models (
                id SERIAL PRIMARY KEY,
                family TEXT NOT NULL,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                training_timestamp TEXT NOT NULL,
                dataset_hash TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                metrics_json TEXT,
                schema_version TEXT DEFAULT '1.0',
                UNIQUE(family, version)
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS ml_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family TEXT NOT NULL,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0
                    CHECK (is_active IN (0,1)),
                training_timestamp TEXT NOT NULL,
                dataset_hash TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                metrics_json TEXT,
                schema_version TEXT DEFAULT '1.0',
                UNIQUE(family, version)
            )
        """)

        # 9. VERIFIED LABELS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS verified_labels (
                id SERIAL PRIMARY KEY,
                event_id INTEGER,
                label TEXT NOT NULL,
                feature_vector_json TEXT NOT NULL,
                model_version TEXT NOT NULL,
                verified_by TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                FOREIGN KEY (event_id)
                    REFERENCES anomaly_events(id)
            )
        """ if _USE_POSTGRES else """
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
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS accuracy_trend (
                id SERIAL PRIMARY KEY,
                model_id INTEGER NOT NULL,
                f1_score REAL NOT NULL,
                measured_at TEXT NOT NULL,
                FOREIGN KEY (model_id) REFERENCES ml_models(id)
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS accuracy_trend (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                f1_score REAL NOT NULL,
                measured_at TEXT NOT NULL,
                FOREIGN KEY (model_id) REFERENCES ml_models(id)
            )
        """)

        # 11. CONTROL SIGNALS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS control_signals (
                id SERIAL PRIMARY KEY,
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
        """ if _USE_POSTGRES else """
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
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS audit_entries (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                actor TEXT, target TEXT,
                detail_json TEXT NOT NULL,
                hash TEXT NOT NULL
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS audit_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                actor TEXT, target TEXT,
                detail_json TEXT NOT NULL,
                hash TEXT NOT NULL
            )
        """)

        # 13. EDGE DEVICES
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS edge_devices (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL UNIQUE,
                protocol TEXT NOT NULL,
                capabilities_json TEXT,
                status TEXT NOT NULL DEFAULT 'offline',
                last_known_state_json TEXT,
                last_heartbeat TEXT,
                registered_at TEXT NOT NULL
            )
        """ if _USE_POSTGRES else """
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
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS control_signal_queue (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                priority INTEGER NOT NULL,
                queued_at TEXT NOT NULL,
                delivered_at TEXT,
                FOREIGN KEY (device_id)
                    REFERENCES edge_devices(device_id)
            )
        """ if _USE_POSTGRES else """
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
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS explorer_history (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                active_user TEXT,
                arrangement_json TEXT,
                classification_label TEXT,
                confidence REAL,
                model_version TEXT,
                UNIQUE(timestamp, entry_type)
            )
        """ if _USE_POSTGRES else """
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
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS threshold_definitions (
                id SERIAL PRIMARY KEY,
                parameter_name TEXT NOT NULL,
                normal_max REAL NOT NULL,
                warning_max REAL NOT NULL,
                source_standard TEXT,
                equipment_specific INTEGER NOT NULL DEFAULT 0,
                confirmed_by TEXT, confirmed_at TEXT,
                active INTEGER NOT NULL DEFAULT 0
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS threshold_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter_name TEXT NOT NULL,
                normal_max REAL NOT NULL,
                warning_max REAL NOT NULL,
                source_standard TEXT,
                equipment_specific INTEGER NOT NULL DEFAULT 0
                    CHECK (equipment_specific IN (0,1)),
                confirmed_by TEXT, confirmed_at TEXT,
                active INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 17. ADMIN PROMOTION REQUESTS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS admin_promotion_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                request_reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','APPROVED','REJECTED')),
                reviewed_by INTEGER,
                review_remarks TEXT,
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by)
                    REFERENCES users(id) ON DELETE SET NULL
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS admin_promotion_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','APPROVED','REJECTED')),
                reviewed_by INTEGER,
                review_remarks TEXT,
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by)
                    REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # 18. ACCOUNT RECOVERY REQUESTS
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS account_recovery_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                recovery_reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','APPROVED','REJECTED')),
                reviewed_by INTEGER,
                review_remarks TEXT,
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by)
                    REFERENCES users(id) ON DELETE SET NULL
            )
        """ if _USE_POSTGRES else """
            CREATE TABLE IF NOT EXISTS account_recovery_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recovery_reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','APPROVED','REJECTED')),
                reviewed_by INTEGER,
                review_remarks TEXT,
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by)
                    REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # MIGRATE EXISTING DATABASES (add missing columns)
        if _USE_POSTGRES:
            existing = {
                r["column_name"]
                for r in _fetchall(conn, """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users'
                      AND table_schema = 'public'
                """)
            }
        else:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(users)")
            existing = {row["name"] for row in cur.fetchall()}

        lifecycle_columns = {
            "is_deleted": "INTEGER NOT NULL DEFAULT 0",
            "deleted_at": "TEXT",
            "deleted_by": "TEXT",
            "deletion_reason": "TEXT",
            "deleted_was_active": "INTEGER NOT NULL DEFAULT 1",
            "session_version": "INTEGER NOT NULL DEFAULT 0",
        }
        for col, defn in lifecycle_columns.items():
            if col not in existing:
                _exec(conn, f"ALTER TABLE users ADD COLUMN {col} {defn}")

        # INDEXES
        indexes = (
            ("idx_sensor_timestamp",
             "sensor_readings(timestamp)"),
            ("idx_sensor_name_timestamp",
             "sensor_readings(sensor_name, timestamp)"),
            ("idx_analytics_sensor_window",
             "sensor_analytics(sensor_name, window_end)"),
            ("idx_assessment_timestamp",
             "machine_assessments(timestamp)"),
            ("idx_anomaly_severity_timestamp",
             "anomaly_events(severity, timestamp)"),
            ("idx_recommendation_assessment",
             "recommendations(assessment_id)"),
            ("idx_users_role_active",
             "users(role, is_active)"),
            ("idx_user_permissions_user_id",
             "user_permissions(user_id)"),
            ("idx_ml_models_active",
             "ml_models(family, is_active)"),
            ("idx_verified_model_ts",
             "verified_labels(model_version, verified_at)"),
            ("idx_trend_model_time",
             "accuracy_trend(model_id, measured_at)"),
            ("idx_control_intent_ts",
             "control_signals(intent, timestamp)"),
            ("idx_audit_category_ts",
             "audit_entries(category, timestamp)"),
            ("idx_edge_status",
             "edge_devices(status)"),
            ("idx_queue_device_delivered",
             "control_signal_queue(device_id, delivered_at)"),
            ("idx_explorer_ts",
             "explorer_history(timestamp)"),
            ("idx_users_deleted_active",
             "users(is_deleted, is_active)"),
        )
        for idx_name, expr in indexes:
            _exec(conn,
                  f"CREATE INDEX IF NOT EXISTS {idx_name} ON {expr}")

        # Partial indexes (supported in both SQLite and Postgres)
        _exec(conn, """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_one_pending_admin_promotion
            ON admin_promotion_requests(user_id)
            WHERE status = 'PENDING'
        """)
        _exec(conn, """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_one_pending_account_recovery
            ON account_recovery_requests(user_id)
            WHERE status = 'PENDING'
        """)

        conn.commit()
        print("IntelliWatch database initialized successfully!")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =====================================================
# SENSOR READINGS AND ANALYTICS
# =====================================================

def save_sensor_readings(readings):
    if not readings:
        return 0
    timestamp = current_timestamp()
    records = [
        (item.get("timestamp", timestamp), item["sensor_name"],
         item["value"], item["unit"], item.get("axis"),
         item.get("quality", "VALID"),
         json.dumps(item.get("metadata", {})))
        for item in readings
    ]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executemany(_sql("""
            INSERT INTO sensor_readings (
                timestamp, sensor_name, value, unit,
                axis, quality, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """), records)
        conn.commit()
        return len(records)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_sensor_analytics(analytics):
    conn = get_connection()
    try:
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO sensor_analytics (
                    sensor_name, window_start, window_end,
                    sample_count, minimum, maximum, average,
                    rms, standard_deviation, anomaly_count,
                    anomaly_rate, trend, status, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (analytics["sensor_name"], analytics["window_start"],
                  analytics["window_end"],
                  analytics.get("sample_count", 0),
                  analytics.get("minimum"), analytics.get("maximum"),
                  analytics.get("average"), analytics.get("rms"),
                  analytics.get("standard_deviation"),
                  analytics.get("anomaly_count", 0),
                  analytics.get("anomaly_rate", 0),
                  analytics.get("trend"), analytics.get("status"),
                  current_timestamp()))
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO sensor_analytics (
                    sensor_name, window_start, window_end,
                    sample_count, minimum, maximum, average,
                    rms, standard_deviation, anomaly_count,
                    anomaly_rate, trend, status, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (analytics["sensor_name"], analytics["window_start"],
                  analytics["window_end"],
                  analytics.get("sample_count", 0),
                  analytics.get("minimum"), analytics.get("maximum"),
                  analytics.get("average"), analytics.get("rms"),
                  analytics.get("standard_deviation"),
                  analytics.get("anomaly_count", 0),
                  analytics.get("anomaly_rate", 0),
                  analytics.get("trend"), analytics.get("status"),
                  current_timestamp()))
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# MACHINE HEALTH AND ANOMALIES
# =====================================================

def save_machine_assessment(assessment):
    conn = get_connection()
    try:
        params = (
            assessment.get("timestamp", current_timestamp()),
            assessment["overall_status"],
            assessment.get("confidence_score"),
            assessment.get("anomaly_rate"),
            assessment.get("health_score"),
            json.dumps(assessment.get("probable_causes", [])),
            json.dumps(assessment.get("sensor_summary", {})),
            assessment.get("assessment_notes"),
        )
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO machine_assessments (
                    timestamp, overall_status, confidence_score,
                    anomaly_rate, health_score, probable_causes_json,
                    sensor_summary_json, assessment_notes
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, params)
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO machine_assessments (
                    timestamp, overall_status, confidence_score,
                    anomaly_rate, health_score, probable_causes_json,
                    sensor_summary_json, assessment_notes
                ) VALUES (?,?,?,?,?,?,?,?)
            """, params)
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_anomaly_event(event):
    conn = get_connection()
    try:
        params = (
            event.get("timestamp", current_timestamp()),
            event["sensor_name"], event["severity"],
            event.get("observed_value"), event.get("expected_min"),
            event.get("expected_max"), event.get("deviation"),
            event.get("probable_cause"), event.get("description"),
            event.get("assessment_id"),
        )
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO anomaly_events (
                    timestamp, sensor_name, severity,
                    observed_value, expected_min, expected_max,
                    deviation, probable_cause, description,
                    assessment_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, params)
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO anomaly_events (
                    timestamp, sensor_name, severity,
                    observed_value, expected_min, expected_max,
                    deviation, probable_cause, description,
                    assessment_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """, params)
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_recommendations(recommendations):
    if not recommendations:
        return 0
    timestamp = current_timestamp()
    records = [
        (item.get("timestamp", timestamp),
         item.get("assessment_id"), item["category"],
         item["priority"], item["recommendation"],
         item.get("reason"), item.get("sensor_name"),
         item.get("action_status", "PENDING"))
        for item in recommendations
    ]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executemany(_sql("""
            INSERT INTO recommendations (
                timestamp, assessment_id, category,
                priority, recommendation, reason,
                sensor_name, action_status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """), records)
        conn.commit()
        return len(records)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# MACHINE CONFIGURATION
# =====================================================

def set_machine_config(name, value, unit=None, description=None):
    conn = get_connection()
    try:
        _exec(conn, """
            INSERT INTO machine_config (
                parameter_name, parameter_value,
                unit, description, updated_at
            ) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT(parameter_name) DO UPDATE SET
                parameter_value = EXCLUDED.parameter_value,
                unit = EXCLUDED.unit,
                description = EXCLUDED.description,
                updated_at = EXCLUDED.updated_at
        """, (name, str(value), unit, description, current_timestamp()))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_machine_config(name):
    conn = get_connection()
    try:
        row = _fetchone(conn,
            "SELECT parameter_value FROM machine_config WHERE parameter_name = %s",
            (name,))
        return row["parameter_value"] if row else None
    finally:
        conn.close()


# =====================================================
# HISTORICAL DATA RETRIEVAL
# =====================================================

def get_recent_sensor_readings(sensor_name, limit=100):
    limit = max(1, min(int(limit), 10000))
    conn = get_connection()
    try:
        return _fetchall(conn, """
            SELECT * FROM sensor_readings
            WHERE sensor_name = %s
            ORDER BY timestamp DESC, id DESC
            LIMIT %s
        """, (sensor_name, limit))
    finally:
        conn.close()


def get_recent_assessments(limit=50):
    limit = max(1, min(int(limit), 10000))
    conn = get_connection()
    try:
        return _fetchall(conn, """
            SELECT * FROM machine_assessments
            ORDER BY timestamp DESC, id DESC LIMIT %s
        """, (limit,))
    finally:
        conn.close()


def get_recent_anomalies(limit=50):
    limit = max(1, min(int(limit), 10000))
    conn = get_connection()
    try:
        return _fetchall(conn, """
            SELECT * FROM anomaly_events
            ORDER BY timestamp DESC, id DESC LIMIT %s
        """, (limit,))
    finally:
        conn.close()


# =====================================================
# USER ACCOUNT MANAGEMENT
# =====================================================

def create_user(username, full_name, password_hash, role):
    if not all(isinstance(v, str) for v in (
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

    conn = get_connection()
    try:
        params = (username, full_name, password_hash, role,
                  current_timestamp())
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO users (
                    username, full_name, password_hash,
                    role, created_at
                ) VALUES (%s,%s,%s,%s,%s) RETURNING id
            """, params)
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO users (
                    username, full_name, password_hash,
                    role, created_at
                ) VALUES (?,?,?,?,?)
            """, params)
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_connection()
    try:
        if _USE_POSTGRES:
            row = _fetchone(conn,
                "SELECT * FROM users WHERE LOWER(username) = LOWER(%s)",
                (username.strip(),))
        else:
            row = _fetchone(conn,
                "SELECT * FROM users WHERE username = ?",
                (username.strip(),))
        return row
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        return _fetchone(conn, """
            SELECT id, username, full_name, role,
                   is_active, created_at, last_login,
                   is_deleted, deleted_at
            FROM users WHERE id = %s
        """, (user_id,))
    finally:
        conn.close()


def get_all_users(include_deleted=False):
    conn = get_connection()
    try:
        query = """
            SELECT id, username, full_name, role,
                   is_active, created_at, last_login,
                   is_deleted, deleted_at
            FROM users
        """
        if not include_deleted:
            query += " WHERE is_deleted = 0"
        query += " ORDER BY id"
        return _fetchall(conn, query)
    finally:
        conn.close()


def update_last_login(user_id):
    conn = get_connection()
    try:
        _exec(conn, """
            UPDATE users SET last_login = %s
            WHERE id = %s AND is_active = 1 AND is_deleted = 0
        """, (current_timestamp(), user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_user_active(user_id, is_active, actor=None):
    conn = get_connection()
    try:
        _begin_transaction(conn)
        target = _fetchone(conn,
            "SELECT id, username, role, is_active, is_deleted FROM users WHERE id = %s",
            (user_id,))
        if not target or target["is_deleted"]:
            conn.rollback()
            return False

        active = int(bool(is_active))

        if target["role"] == "ADMIN" and target["is_active"] and not active:
            count_row = _fetchone(conn, """
                SELECT COUNT(*) AS total FROM users
                WHERE role = 'ADMIN' AND is_active = 1 AND is_deleted = 0
            """)
            if (count_row["total"] if count_row else 0) <= 1:
                raise ValueError(
                    "The last active administrator cannot be deactivated."
                )

        cur = _exec(conn,
            "UPDATE users SET is_active = %s WHERE id = %s AND is_deleted = 0",
            (active, user_id))

        if cur.rowcount:
            _audit_details(conn,
                "USER_UNLOCKED" if active else "USER_LOCKED",
                actor, user_id,
                {"username": target["username"],
                 "role": target["role"],
                 "is_active": bool(active)})

        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# ACCOUNT LIFECYCLE
# =====================================================

def delete_user(user_id, deleted_by=None, reason=None):
    conn = get_connection()
    try:
        _begin_transaction(conn)
        target = _fetchone(conn,
            "SELECT * FROM users WHERE id = %s", (user_id,))
        if (not target or target["is_deleted"]
                or target["role"] == "ADMIN"):
            conn.rollback()
            return False

        _exec(conn, """
            UPDATE users SET
                is_deleted = 1, is_active = 0,
                deleted_at = %s, deleted_by = %s,
                deletion_reason = %s,
                deleted_was_active = is_active
            WHERE id = %s
        """, (current_timestamp(),
              str(deleted_by) if deleted_by is not None else None,
              reason, user_id))

        _audit_details(conn, "USER_TEMPORARILY_DELETED",
            deleted_by, user_id,
            {"username": target["username"],
             "role": target["role"], "reason": reason,
             "previously_active": bool(target["is_active"])})

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def restore_user(user_id, restored_by=None):
    conn = get_connection()
    try:
        _begin_transaction(conn)
        target = _fetchone(conn,
            "SELECT * FROM users WHERE id = %s", (user_id,))
        if not target or not target["is_deleted"]:
            conn.rollback()
            return False

        _exec(conn, """
            UPDATE users SET
                is_deleted = 0,
                is_active = deleted_was_active,
                deleted_at = NULL, deleted_by = NULL,
                deletion_reason = NULL,
                deleted_was_active = 1
            WHERE id = %s
        """, (user_id,))

        _audit_details(conn, "USER_RESTORED",
            restored_by, user_id,
            {"username": target["username"],
             "previous_role": target["role"]})

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def permanently_delete_user(user_id, deleted_by=None):
    conn = get_connection()
    try:
        _begin_transaction(conn)
        target = _fetchone(conn,
            "SELECT * FROM users WHERE id = %s", (user_id,))
        if (not target or not target["is_deleted"]
                or target["role"] == "ADMIN"):
            conn.rollback()
            return False

        _audit_details(conn, "USER_PERMANENTLY_DELETED",
            deleted_by, user_id,
            {"username": target["username"],
             "full_name": target["full_name"],
             "role": target["role"],
             "deleted_at": target["deleted_at"],
             "reason": target["deletion_reason"],
             "permanently_deleted_at": current_timestamp()})

        _exec(conn, "DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# CONTROL ACKNOWLEDGEMENTS
# =====================================================

def save_control_ack(control_signal_id, ack_timestamp,
                     resulting_equipment_state):
    conn = get_connection()
    try:
        cur = _exec(conn, """
            UPDATE control_signals
            SET ack_timestamp = %s,
                resulting_equipment_state = %s
            WHERE id = %s
        """, (ack_timestamp, resulting_equipment_state,
              control_signal_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# AUDIT LOG
# =====================================================

def record_audit_entry(category, detail_json,
                       actor=None, target=None, hash_value=None):
    conn = get_connection()
    try:
        _begin_transaction(conn)
        entry_id = _insert_audit_entry(
            conn, category, detail_json, actor, target, hash_value)
        conn.commit()
        return entry_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# ML LABELS AND ACCURACY
# =====================================================

def save_verified_label(event_id, label, feature_vector_json,
                        model_version, verified_by):
    conn = get_connection()
    try:
        params = (event_id, label, feature_vector_json,
                  model_version, verified_by, current_timestamp())
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO verified_labels (
                    event_id, label, feature_vector_json,
                    model_version, verified_by, verified_at
                ) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
            """, params)
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO verified_labels (
                    event_id, label, feature_vector_json,
                    model_version, verified_by, verified_at
                ) VALUES (?,?,?,?,?,?)
            """, params)
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def append_accuracy_trend(model_id, f1_score):
    conn = get_connection()
    try:
        params = (model_id, f1_score, current_timestamp())
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO accuracy_trend (
                    model_id, f1_score, measured_at
                ) VALUES (%s,%s,%s) RETURNING id
            """, params)
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO accuracy_trend (
                    model_id, f1_score, measured_at
                ) VALUES (?,?,?)
            """, params)
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# EXPLORER HISTORY
# =====================================================

def _evict_explorer_history(conn):
    _exec(conn, """
        DELETE FROM explorer_history
        WHERE id NOT IN (
            SELECT id FROM explorer_history
            ORDER BY timestamp DESC, id DESC
            LIMIT %s
        )
    """, (EXPLORER_HISTORY_MAX_ROWS,))


def save_explorer_history_entry(
    entry_type, active_user=None, arrangement_json=None,
    classification_label=None, confidence=None, model_version=None,
):
    conn = get_connection()
    try:
        params = (current_timestamp(), entry_type, active_user,
                  arrangement_json, classification_label,
                  confidence, model_version)
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO explorer_history (
                    timestamp, entry_type, active_user,
                    arrangement_json, classification_label,
                    confidence, model_version
                ) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, params)
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO explorer_history (
                    timestamp, entry_type, active_user,
                    arrangement_json, classification_label,
                    confidence, model_version
                ) VALUES (?,?,?,?,?,?,?)
            """, params)
            row_id = cur.lastrowid
        _evict_explorer_history(conn)
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_explorer_history(limit=100):
    limit = max(1, min(int(limit), 10000))
    conn = get_connection()
    try:
        return _fetchall(conn, """
            SELECT * FROM explorer_history
            ORDER BY timestamp DESC, id DESC LIMIT %s
        """, (limit,))
    finally:
        conn.close()


def get_explorer_history_entry(entry_id):
    conn = get_connection()
    try:
        return _fetchone(conn,
            "SELECT * FROM explorer_history WHERE id = %s",
            (entry_id,))
    finally:
        conn.close()


# =====================================================
# DATA RETENTION
# =====================================================

def cleanup_old_records(retention_days=None):
    days = (DEFAULT_RETENTION_DAYS if retention_days is None
            else max(1, int(retention_days)))
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()

    deleted = {}
    conn = get_connection()
    try:
        for table in ("sensor_readings", "anomaly_events"):
            cur = _exec(conn,
                f"DELETE FROM {table} WHERE timestamp < %s",
                (cutoff,))
            deleted[table] = cur.rowcount
        deleted["audit_entries"] = 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# EDGE DEVICE MANAGEMENT
# =====================================================

def save_edge_device(device_id, protocol,
                     capabilities_json=None, status="offline"):
    conn = get_connection()
    try:
        _exec(conn, """
            INSERT INTO edge_devices (
                device_id, protocol, capabilities_json,
                status, registered_at
            ) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT(device_id) DO UPDATE SET
                protocol = EXCLUDED.protocol,
                capabilities_json = EXCLUDED.capabilities_json,
                status = EXCLUDED.status
        """, (device_id, protocol, capabilities_json,
              status, current_timestamp()))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_edge_device_status(device_id, status,
                              last_known_state_json=None):
    conn = get_connection()
    try:
        cur = _exec(conn, """
            UPDATE edge_devices
            SET status = %s,
                last_known_state_json =
                    COALESCE(%s, last_known_state_json)
            WHERE device_id = %s
        """, (status, last_known_state_json, device_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# CONTROL SIGNAL QUEUE
# =====================================================

def queue_control_signal(device_id, intent, priority):
    conn = get_connection()
    try:
        params = (device_id, intent, priority, current_timestamp())
        if _USE_POSTGRES:
            cur = _exec(conn, """
                INSERT INTO control_signal_queue (
                    device_id, intent, priority, queued_at
                ) VALUES (%s,%s,%s,%s) RETURNING id
            """, params)
            row_id = _lastrowid(conn, cur)
        else:
            cur = _exec(conn, """
                INSERT INTO control_signal_queue (
                    device_id, intent, priority, queued_at
                ) VALUES (?,?,?,?)
            """, params)
            row_id = cur.lastrowid
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_queued_signals(device_id, undelivered_only=True):
    conn = get_connection()
    try:
        query = """
            SELECT * FROM control_signal_queue
            WHERE device_id = %s
        """
        if undelivered_only:
            query += " AND delivered_at IS NULL"
        query += " ORDER BY priority DESC, queued_at ASC, id ASC"
        return _fetchall(conn, query, (device_id,))
    finally:
        conn.close()


def mark_signal_delivered(queue_id):
    conn = get_connection()
    try:
        cur = _exec(conn, """
            UPDATE control_signal_queue
            SET delivered_at = %s WHERE id = %s
        """, (current_timestamp(), queue_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# USER PERMISSION MANAGEMENT
# =====================================================

def get_user_permission_overrides(user_id):
    conn = get_connection()
    try:
        rows = _fetchall(conn,
            "SELECT permission_key, is_granted FROM user_permissions WHERE user_id = %s",
            (user_id,))
        return {r["permission_key"]: bool(r["is_granted"]) for r in rows}
    finally:
        conn.close()


def set_user_permission(user_id, permission_key,
                        is_granted, updated_by=None):
    if not isinstance(permission_key, str) or not permission_key.strip():
        raise ValueError("A valid permission key is required.")
    if type(is_granted) is not bool:
        raise ValueError("is_granted must be a boolean.")

    conn = get_connection()
    try:
        _exec(conn, """
            INSERT INTO user_permissions (
                user_id, permission_key, is_granted,
                updated_by, updated_at
            ) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT(user_id, permission_key) DO UPDATE SET
                is_granted = EXCLUDED.is_granted,
                updated_by = EXCLUDED.updated_by,
                updated_at = EXCLUDED.updated_at
        """, (user_id, permission_key.strip(), int(is_granted),
              updated_by, current_timestamp()))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def clear_user_permission_override(user_id, permission_key):
    conn = get_connection()
    try:
        cur = _exec(conn, """
            DELETE FROM user_permissions
            WHERE user_id = %s AND permission_key = %s
        """, (user_id, permission_key))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =====================================================
# DATABASE STARTUP
# =====================================================

if __name__ == "__main__":
    initialize_database()
    if _USE_POSTGRES:
        print("Database: Neon/Postgres")
    else:
        print(f"Database location: {DATABASE_PATH}")
