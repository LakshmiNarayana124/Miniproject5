
import hashlib
import sqlite3
from datetime import datetime, timezone, timedelta
import database


DATABASE_PATH = database.DATABASE_PATH

TOKEN_TYPES = {"PASSWORD_RESET", "ADMIN_INVITE"}


# =========================================================
# SHARED HELPERS
# =========================================================

def _now():
    return datetime.now(timezone.utc)


def _timestamp(value=None):
    if value is None:
        value = _now()

    if not isinstance(value, datetime):
        raise ValueError("A valid datetime is required.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime values must include a timezone.")

    return value.astimezone(timezone.utc).isoformat()


def _hash_identifier(value):
    if not isinstance(value, str) or not value:
        raise ValueError("A valid identifier is required.")

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _validate_token_type(token_type):
    if token_type not in TOKEN_TYPES:
        raise ValueError("Invalid security token type.")


def _validate_rate_limit_settings(
    max_attempts,
    window_seconds,
    block_seconds,
):
    for value in (max_attempts, window_seconds, block_seconds):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("Rate-limit settings must be positive integers.")


class _PostgresConnection:
    """Adapt the security store's parameterized SQLite queries to PostgreSQL."""
    def __init__(self):
        self.connection = database.get_connection()

    def execute(self, query, params=()):
        query = query.replace("BEGIN IMMEDIATE", "BEGIN")
        query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        if query.strip() == "PRAGMA table_info(users)":
            query = ("SELECT column_name AS name FROM information_schema.columns "
                     "WHERE table_schema = 'public' AND table_name = 'users'")
        cursor = self.connection.cursor()
        cursor.execute(query.replace("?", "%s"), params)
        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def _connect():
    if database._USE_POSTGRES:
        return _PostgresConnection()
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
        isolation_level=None,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_security_storage():
    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS auth_security_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                token_type TEXT NOT NULL
                    CHECK (
                        token_type IN (
                            'PASSWORD_RESET',
                            'ADMIN_INVITE'
                        )
                    ),
                user_id INTEGER,
                created_by_user_id INTEGER,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                revoked_at TEXT,
                metadata_json TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_user_id)
                    REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS auth_rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                subject_hash TEXT NOT NULL,
                window_started_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
                    CHECK (attempts >= 0),
                blocked_until TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE (scope, subject_hash)
            )
        """)

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        if "session_version" not in columns:
            connection.execute("""
                ALTER TABLE users
                ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0
                    CHECK (session_version >= 0)
            """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_auth_tokens_type_expiry
            ON auth_security_tokens(token_type, expires_at)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_auth_tokens_user
            ON auth_security_tokens(user_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_auth_rate_blocked
            ON auth_rate_limits(blocked_until)
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# SECURITY TOKEN STORAGE
# =========================================================

def store_token(
    token,
    token_type,
    expires_at,
    user_id=None,
    created_by_user_id=None,
    metadata_json=None,
):
    _validate_token_type(token_type)

    token_hash = _hash_identifier(token)
    expiry = _timestamp(expires_at)

    if metadata_json is not None and not isinstance(metadata_json, str):
        raise ValueError("metadata_json must be a string or None.")

    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        token_insert = """
            INSERT INTO auth_security_tokens (
                token_hash,
                token_type,
                user_id,
                created_by_user_id,
                created_at,
                expires_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        if database._USE_POSTGRES:
            token_insert += " RETURNING id"
        cursor = connection.execute(token_insert, (
            token_hash,
            token_type,
            user_id,
            created_by_user_id,
            _timestamp(),
            expiry,
            metadata_json,
        ))

        token_id = cursor.fetchone()["id"] if database._USE_POSTGRES else cursor.lastrowid
        connection.commit()
        return token_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def consume_token(token, token_type):
    _validate_token_type(token_type)

    token_hash = _hash_identifier(token)
    now = _timestamp()

    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT *
            FROM auth_security_tokens
            WHERE token_hash = ?
              AND token_type = ?
              AND consumed_at IS NULL
              AND revoked_at IS NULL
              AND expires_at > ?
        """, (
            token_hash,
            token_type,
            now,
        )).fetchone()

        if row is None:
            connection.rollback()
            return None

        cursor = connection.execute("""
            UPDATE auth_security_tokens
            SET consumed_at = ?
            WHERE id = ?
              AND consumed_at IS NULL
              AND revoked_at IS NULL
              AND expires_at > ?
        """, (
            now,
            row["id"],
            now,
        ))

        if cursor.rowcount != 1:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def revoke_token(token, token_type):
    _validate_token_type(token_type)

    token_hash = _hash_identifier(token)

    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute("""
            UPDATE auth_security_tokens
            SET revoked_at = ?
            WHERE token_hash = ?
              AND token_type = ?
              AND consumed_at IS NULL
              AND revoked_at IS NULL
        """, (
            _timestamp(),
            token_hash,
            token_type,
        ))

        connection.commit()
        return cursor.rowcount == 1

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def revoke_user_tokens(user_id, token_type=None):
    if token_type is not None:
        _validate_token_type(token_type)

    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        if token_type is None:
            cursor = connection.execute("""
                UPDATE auth_security_tokens
                SET revoked_at = ?
                WHERE user_id = ?
                  AND consumed_at IS NULL
                  AND revoked_at IS NULL
            """, (
                _timestamp(),
                user_id,
            ))
        else:
            cursor = connection.execute("""
                UPDATE auth_security_tokens
                SET revoked_at = ?
                WHERE user_id = ?
                  AND token_type = ?
                  AND consumed_at IS NULL
                  AND revoked_at IS NULL
            """, (
                _timestamp(),
                user_id,
                token_type,
            ))

        connection.commit()
        return cursor.rowcount

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# SESSION VERSION MANAGEMENT
# =========================================================

def increment_session_version(user_id):
    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute("""
            UPDATE users
            SET session_version = session_version + 1
            WHERE id = ?
              AND is_active = 1
              AND is_deleted = 0
        """, (user_id,))

        if cursor.rowcount != 1:
            connection.rollback()
            return None

        row = connection.execute("""
            SELECT session_version
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        connection.commit()
        return row["session_version"]

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_session_version(user_id):
    connection = _connect()

    try:
        row = connection.execute("""
            SELECT session_version
            FROM users
            WHERE id = ?
              AND is_active = 1
              AND is_deleted = 0
        """, (user_id,)).fetchone()

        return row["session_version"] if row else None

    finally:
        connection.close()


# =========================================================
# RATE LIMIT CHECKING
# =========================================================

def check_rate_limit(
    scope,
    subject,
    max_attempts=5,
    window_seconds=900,
    block_seconds=900,
):
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("A valid rate-limit scope is required.")

    _validate_rate_limit_settings(
        max_attempts,
        window_seconds,
        block_seconds,
    )

    subject_hash = _hash_identifier(subject)
    now = _now()
    now_text = now.isoformat()

    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT *
            FROM auth_rate_limits
            WHERE scope = ?
              AND subject_hash = ?
        """, (
            scope,
            subject_hash,
        )).fetchone()

        if row and row["blocked_until"]:
            blocked_until = datetime.fromisoformat(
                row["blocked_until"]
            )

            if blocked_until > now:
                connection.commit()

                return {
                    "allowed": False,
                    "retry_after_seconds": max(
                        1,
                        int((blocked_until - now).total_seconds()),
                    ),
                }

        if row is None:
            connection.execute("""
                INSERT INTO auth_rate_limits (
                    scope,
                    subject_hash,
                    window_started_at,
                    attempts,
                    blocked_until,
                    updated_at
                )
                VALUES (?, ?, ?, 0, NULL, ?)
            """, (
                scope,
                subject_hash,
                now_text,
                now_text,
            ))

            attempts = 0
            window_started = now

        else:
            window_started = datetime.fromisoformat(
                row["window_started_at"]
            )

            attempts = row["attempts"]

            if (now - window_started).total_seconds() >= window_seconds:
                attempts = 0
                window_started = now

                connection.execute("""
                    UPDATE auth_rate_limits
                    SET attempts = 0,
                        window_started_at = ?,
                        blocked_until = NULL,
                        updated_at = ?
                    WHERE scope = ?
                      AND subject_hash = ?
                """, (
                    now_text,
                    now_text,
                    scope,
                    subject_hash,
                ))

        if attempts >= max_attempts:
            blocked_until = now + timedelta(
                seconds=block_seconds
            )

            connection.execute("""
                UPDATE auth_rate_limits
                SET blocked_until = ?,
                    updated_at = ?
                WHERE scope = ?
                  AND subject_hash = ?
            """, (
                blocked_until.isoformat(),
                now_text,
                scope,
                subject_hash,
            ))

            connection.commit()

            return {
                "allowed": False,
                "retry_after_seconds": block_seconds,
            }

        connection.commit()

        return {
            "allowed": True,
            "retry_after_seconds": 0,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# RATE LIMIT FAILURE RECORDING
# =========================================================

def record_rate_limit_failure(
    scope,
    subject,
    max_attempts=5,
    window_seconds=900,
    block_seconds=900,
):
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("A valid rate-limit scope is required.")

    _validate_rate_limit_settings(
        max_attempts,
        window_seconds,
        block_seconds,
    )

    subject_hash = _hash_identifier(subject)
    now = _now()
    now_text = now.isoformat()

    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT *
            FROM auth_rate_limits
            WHERE scope = ?
              AND subject_hash = ?
        """, (
            scope,
            subject_hash,
        )).fetchone()

        if row is None:
            attempts = 1
            window_started = now

        else:
            window_started = datetime.fromisoformat(
                row["window_started_at"]
            )

            if (now - window_started).total_seconds() >= window_seconds:
                attempts = 1
                window_started = now
            else:
                attempts = row["attempts"] + 1

        blocked_until = None

        if attempts >= max_attempts:
            blocked_until = (
                now + timedelta(seconds=block_seconds)
            ).isoformat()

        connection.execute("""
            INSERT INTO auth_rate_limits (
                scope,
                subject_hash,
                window_started_at,
                attempts,
                blocked_until,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope, subject_hash)
            DO UPDATE SET
                window_started_at = excluded.window_started_at,
                attempts = excluded.attempts,
                blocked_until = excluded.blocked_until,
                updated_at = excluded.updated_at
        """, (
            scope,
            subject_hash,
            window_started.isoformat(),
            attempts,
            blocked_until,
            now_text,
        ))

        connection.commit()

        return {
            "attempts": attempts,
            "blocked": blocked_until is not None,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# RATE LIMIT RESET
# =========================================================

def clear_rate_limit(scope, subject):
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("A valid rate-limit scope is required.")

    subject_hash = _hash_identifier(subject)
    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute("""
            DELETE FROM auth_rate_limits
            WHERE scope = ?
              AND subject_hash = ?
        """, (
            scope,
            subject_hash,
        ))

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# EXPIRED RECORD CLEANUP
# =========================================================

def cleanup_expired_security_records():
    now = _timestamp()
    old_rate_limit_cutoff = _timestamp(
        _now() - timedelta(days=2)
    )

    connection = _connect()

    try:
        connection.execute("BEGIN IMMEDIATE")

        token_cursor = connection.execute("""
            DELETE FROM auth_security_tokens
            WHERE expires_at < ?
               OR consumed_at IS NOT NULL
               OR revoked_at IS NOT NULL
        """, (now,))

        rate_cursor = connection.execute("""
            DELETE FROM auth_rate_limits
            WHERE blocked_until IS NOT NULL
              AND blocked_until < ?
              AND updated_at < ?
        """, (
            now,
            old_rate_limit_cutoff,
        ))

        connection.commit()

        return {
            "security_tokens_removed": token_cursor.rowcount,
            "rate_limit_records_removed": rate_cursor.rowcount,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
