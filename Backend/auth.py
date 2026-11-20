import os
import getpass
import sqlite3
import json
import hashlib
import secrets
import time
import ipaddress

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)

from pydantic import BaseModel, Field

from database import (
    initialize_database,
    create_user,
    get_user_by_username,
    get_user_by_id,
    get_all_users,
    update_last_login,
    get_connection,
    get_user_permission_overrides,
    set_user_permission,
    clear_user_permission_override,
    record_audit_entry,
)

from auth_security_store import (
    initialize_security_storage,
    store_token,
    consume_token,
    revoke_token,
    revoke_user_tokens,
    increment_session_version,
    get_session_version,
    check_rate_limit,
    record_rate_limit_failure,
    clear_rate_limit,
    cleanup_expired_security_records,
)


# =========================================================
# CONFIGURATION
# =========================================================

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_ISSUER = "IntelliWatch"
JWT_AUDIENCE = "IntelliWatch-API"

RESET_TOKEN_TTL_SECONDS = 900
ADMIN_INVITE_TTL_SECONDS = 86400

password_hasher = PasswordHasher()
security = HTTPBearer(auto_error=False)

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

VALID_ROLES = {
    "ADMIN",
    "OPERATOR",
    "MAINTENANCE_ENGINEER",
}

ROLE_DEFAULT_PERMISSIONS = {
    "ADMIN": {
        "dashboard.view",
        "sensors.view",
        "machine_status.view",
        "calibration.manage",
        "models.manage",
        "users.manage",
        "permissions.manage",
    },
    "OPERATOR": {
        "dashboard.view",
        "sensors.view",
        "machine_status.view",
        "alerts.view",
        "recommendations.operational.view",
    },
    "MAINTENANCE_ENGINEER": {
        "dashboard.view",
        "sensors.view",
        "machine_status.view",
        "alerts.view",
        "recommendations.operational.view",
        "diagnostics.view",
        "diagnostics.confidence.view",
        "recommendations.maintenance.view",
        "edge_devices.view",
    },
}

RESTRICTED_ADMIN_SESSION_PERMISSIONS = {
    "OPERATOR": "admin.operator_access",
    "MAINTENANCE_ENGINEER": "admin.engineer_access",
}

ALL_PERMISSION_KEYS = {
    "dashboard.view",
    "sensors.view",
    "machine_status.view",
    "alerts.view",
    "recommendations.operational.view",
    "diagnostics.view",
    "diagnostics.confidence.view",
    "recommendations.maintenance.view",
    "edge_devices.view",
    "control.execute",
    "control.acknowledge",
    "calibration.manage",
    "models.manage",
    "users.manage",
    "permissions.manage",
    "admin.operator_access",
    "admin.engineer_access",
}

ADMIN_ONLY_PERMISSIONS = {
    "calibration.manage",
    "models.manage",
    "users.manage",
    "permissions.manage",
    "admin.operator_access",
    "admin.engineer_access",
}


# =========================================================
# INITIALIZATION
# =========================================================

def initialize_auth_security():
    initialize_database()
    initialize_security_storage()
    cleanup_expired_security_records()


# =========================================================
# SHARED HELPERS
# =========================================================

def _now():
    return datetime.now(timezone.utc).isoformat()


def _audit_event(category, actor=None, target=None, details=None):
    record_audit_entry(
        category=category,
        actor=actor,
        target=str(target) if target is not None else None,
        detail_json=json.dumps(details or {}, default=str),
    )


def _begin_transaction():
    connection = get_connection()
    connection.execute("BEGIN IMMEDIATE")
    return connection


def _audit_transaction(connection, category, actor, target, details):
    timestamp = _now()
    detail_json = json.dumps(details or {}, default=str)

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
        detail_json,
    ))

    entry_hash = hashlib.sha256(
        chain_input.encode("utf-8")
    ).hexdigest()

    cursor = connection.execute("""
        INSERT INTO audit_entries (
            timestamp, category, actor, target, detail_json, hash
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        timestamp,
        category,
        actor,
        str(target) if target is not None else None,
        detail_json,
        entry_hash,
    ))

    return cursor.lastrowid


def _admin_in_transaction(connection, admin_id):
    admin = connection.execute("""
        SELECT id, username, role, is_active, is_deleted
        FROM users
        WHERE id = ?
    """, (admin_id,)).fetchone()

    if (
        not admin
        or admin["role"] != "ADMIN"
        or not admin["is_active"]
        or admin["is_deleted"]
    ):
        raise ValueError("An active administrator is required.")

    return dict(admin)


def _account_in_transaction(connection, user_id):
    row = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    return dict(row) if row else None


def _active_admin_count(connection):
    row = connection.execute("""
        SELECT COUNT(*) AS total
        FROM users
        WHERE role = 'ADMIN'
          AND is_active = 1
          AND is_deleted = 0
    """).fetchone()

    return row["total"]


def _validate_request_status(value):
    value = str(value).upper()

    if value not in {"PENDING", "APPROVED", "REJECTED", "ALL"}:
        raise ValueError("Invalid request status.")

    return value


def _client_ip(request):
    """
    Uses the direct connection address.

    Do not trust X-Forwarded-For unless a trusted reverse proxy
    is configured to overwrite and validate it.
    """
    if not request or not request.client:
        return "unknown"

    host = request.client.host or "unknown"

    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return "unknown"


# =========================================================
# RATE LIMITING
# =========================================================

def _rate_limit_key(action, request, subject=""):
    """
    Creates a rate-limit scope and a privacy-preserving subject.

    The subject includes the action, client IP and supplied account
    identifier. Only its SHA-256 hash is passed to the storage layer.
    """
    raw = (
        f"{action}|{_client_ip(request)}|"
        f"{str(subject).strip().lower()}"
    )

    subject_hash = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

    return f"{action}:{subject_hash}"


def _split_rate_limit_key(key):
    """
    Converts the internal combined key into the two arguments
    required by auth_security_store.py: scope and subject.
    """
    scope, separator, subject = str(key).partition(":")

    if not separator or not scope or not subject:
        raise ValueError("Invalid rate-limit key.")

    return scope, subject


def _enforce_rate_limit(
    action,
    request,
    subject="",
    max_attempts=5,
    window_seconds=300,
):
    key = _rate_limit_key(action, request, subject)
    scope, subject_hash = _split_rate_limit_key(key)

    allowed = check_rate_limit(
        scope,
        subject_hash,
        max_attempts=max_attempts,
        window_seconds=window_seconds,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": str(window_seconds)},
        )

    return key


def _record_failure(key):
    scope, subject_hash = _split_rate_limit_key(key)

    record_rate_limit_failure(
        scope,
        subject_hash,
    )


def _clear_failures(key):
    scope, subject_hash = _split_rate_limit_key(key)

    clear_rate_limit(
        scope,
        subject_hash,
    )


def _generic_recovery_message():
    return (
        "If the account is eligible, the request has been received."
    )


# =========================================================
# SECRET KEY AND PASSWORD SECURITY
# =========================================================

def get_secret_key():
    secret_key = os.getenv("INTELLIWATCH_SECRET_KEY")

    if not secret_key or len(secret_key) < 32:
        raise RuntimeError(
            "INTELLIWATCH_SECRET_KEY is missing or too short."
        )

    return secret_key


def hash_password(password: str) -> str:
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")

    if not 12 <= len(password) <= 128:
        raise ValueError(
            "Password must contain between 12 and 128 characters."
        )

    return password_hasher.hash(password)


def verify_password(plain_password, password_hash):
    if not isinstance(plain_password, str) or not isinstance(
        password_hash, str
    ):
        return False

    try:
        return password_hasher.verify(password_hash, plain_password)
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
        TypeError,
        ValueError,
    ):
        return False


# =========================================================
# AUTHENTICATION AND JWT
# =========================================================

def authenticate_user(username, password):
    user = get_user_by_username(username.strip())

    if not user or not user["is_active"]:
        return None

    if user.get("is_deleted", 0):
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return user


def create_access_token(user, session_role=None):
    account_role = user.get("account_role", user.get("role"))
    effective_role = session_role or user.get("role")

    if account_role not in VALID_ROLES or effective_role not in VALID_ROLES:
        raise ValueError("Invalid account or session role.")

    user_id = int(user["id"])
    session_version = get_session_version(user_id)

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "session_role": effective_role,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
        "jti": secrets.token_urlsafe(24),
        "sv": int(session_version),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    return jwt.encode(
        payload,
        get_secret_key(),
        algorithm=ALGORITHM,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_secret_key(),
            algorithms=[ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "session_role",
                    "iss",
                    "aud",
                    "typ",
                    "jti",
                    "sv",
                    "iat",
                    "exp",
                ]
            },
        )

        if payload.get("typ") != "access":
            raise unauthorized

        user_id = int(payload["sub"])

        if user_id <= 0:
            raise unauthorized

        session_role = payload.get("session_role")

        if session_role not in VALID_ROLES:
            raise unauthorized

        token_version = payload.get("sv")

        if not isinstance(token_version, int):
            raise unauthorized

        current_version = get_session_version(user_id)

        if token_version != current_version:
            raise unauthorized

        user = get_user_by_id(user_id)

        if (
            not user
            or not user["is_active"]
            or user.get("is_deleted", 0)
        ):
            raise unauthorized

        user = dict(user)
        account_role = user["role"]

        is_restricted_session = session_role != account_role

        if is_restricted_session:
            if account_role != "ADMIN":
                raise unauthorized

            required_permission = (
                RESTRICTED_ADMIN_SESSION_PERMISSIONS.get(session_role)
            )

            if not required_permission:
                raise unauthorized

            overrides = get_user_permission_overrides(user_id)

            if overrides.get(required_permission) is not True:
                raise unauthorized

        user["account_role"] = account_role
        user["role"] = session_role
        user["is_restricted_session"] = is_restricted_session

        return user

    except HTTPException:
        raise
    except (
        jwt.PyJWTError,
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
    ):
        raise unauthorized


# =========================================================
# ROLE AND PERMISSION AUTHORIZATION
# =========================================================

def require_roles(*allowed_roles):
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this resource.",
            )

        return current_user

    return role_checker


admin_access = require_roles("ADMIN")
operator_access = require_roles("OPERATOR")
maintenance_access = require_roles("MAINTENANCE_ENGINEER")


def get_effective_permissions(user_id, role, restricted_session=False):
    role = str(role).upper()

    permissions = set(ROLE_DEFAULT_PERMISSIONS.get(role, set()))

    if restricted_session:
        permissions.difference_update(ADMIN_ONLY_PERMISSIONS)
        return sorted(permissions)

    overrides = get_user_permission_overrides(user_id)

    for key, granted in overrides.items():
        if key not in ALL_PERMISSION_KEYS:
            continue

        if role != "ADMIN" and key in ADMIN_ONLY_PERMISSIONS:
            continue

        if granted:
            permissions.add(key)
        else:
            permissions.discard(key)

    return sorted(permissions)


def has_permission(user, permission_key):
    if permission_key not in ALL_PERMISSION_KEYS:
        return False

    if user.get("id") is None:
        return False

    permissions = get_effective_permissions(
        user["id"],
        user.get("role"),
        restricted_session=user.get("is_restricted_session", False),
    )

    return permission_key in permissions


def require_permissions(*permission_keys):
    if not permission_keys:
        raise ValueError("At least one permission must be specified.")

    invalid = set(permission_keys) - ALL_PERMISSION_KEYS

    if invalid:
        raise ValueError(f"Unknown permissions: {sorted(invalid)}")

    async def permission_checker(current_user=Depends(get_current_user)):
        missing = [
            key for key in permission_keys
            if not has_permission(current_user, key)
        ]

        if missing:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Insufficient permissions.",
                    "missing_permissions": missing,
                },
            )

        return current_user

    return permission_checker


# =========================================================
# REQUEST MODELS
# =========================================================

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=128)
    requested_role: Literal[
        "ADMIN", "OPERATOR", "MAINTENANCE_ENGINEER"
    ] = "OPERATOR"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    username: str
    full_name: str
    role: str
    account_role: str | None = None
    is_restricted_session: bool = False


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["OPERATOR", "MAINTENANCE_ENGINEER"]


class UserStatusRequest(BaseModel):
    is_active: bool


class UserPermissionRequest(BaseModel):
    is_granted: bool


class RoleChangeRequest(BaseModel):
    role: Literal["OPERATOR", "MAINTENANCE_ENGINEER"]


class PromotionRequestModel(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class PromotionReviewRequest(BaseModel):
    approve: bool
    remarks: str | None = Field(default=None, max_length=1000)


class RecoveryRequestModel(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    reason: str = Field(min_length=5, max_length=1000)


class RecoveryReviewRequest(BaseModel):
    approve: bool
    remarks: str | None = Field(default=None, max_length=1000)


class ForgotPasswordRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class AdminRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    invite_token: str = Field(min_length=8, max_length=256)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["OPERATOR", "MAINTENANCE_ENGINEER"]


# =========================================================
# TRANSACTIONAL ACCOUNT MANAGEMENT
# =========================================================

def _change_user_status(user_id, is_active, admin_id):
    connection = _begin_transaction()

    try:
        admin = _admin_in_transaction(connection, admin_id)
        target = _account_in_transaction(connection, user_id)

        if not target or target["is_deleted"]:
            raise ValueError("User not found or temporarily deleted.")

        if target["role"] == "ADMIN" and not is_active:
            if _active_admin_count(connection) <= 1:
                raise ValueError(
                    "The last active administrator cannot be deactivated."
                )

        connection.execute("""
            UPDATE users
            SET is_active = ?,
                session_version = COALESCE(session_version, 0) + 1
            WHERE id = ?
        """, (int(is_active), user_id))

        _audit_transaction(
            connection,
            "USER_UNLOCKED" if is_active else "USER_LOCKED",
            admin["username"],
            user_id,
            {
                "username": target["username"],
                "role": target["role"],
                "is_active": bool(is_active),
            },
        )

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _change_user_role(user_id, new_role, admin_id):
    connection = _begin_transaction()

    try:
        admin = _admin_in_transaction(connection, admin_id)
        target = _account_in_transaction(connection, user_id)

        if not target or target["is_deleted"]:
            raise ValueError("User not found or temporarily deleted.")

        if new_role == "ADMIN":
            raise ValueError(
                "Admin promotion requires an approved promotion request."
            )

        if new_role not in {"OPERATOR", "MAINTENANCE_ENGINEER"}:
            raise ValueError("Invalid role.")

        if target["role"] == "ADMIN" and target["is_active"]:
            if _active_admin_count(connection) <= 1:
                raise ValueError(
                    "Cannot demote the last active administrator."
                )

        old_role = target["role"]

        connection.execute("""
            UPDATE users
            SET role = ?,
                session_version = COALESCE(session_version, 0) + 1
            WHERE id = ?
        """, (new_role, user_id))

        _audit_transaction(
            connection,
            "USER_ROLE_CHANGED",
            admin["username"],
            user_id,
            {
                "username": target["username"],
                "old_role": old_role,
                "new_role": new_role,
            },
        )

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _soft_delete_account(user_id, admin_id, reason=None):
    connection = _begin_transaction()

    try:
        admin = _admin_in_transaction(connection, admin_id)
        target = _account_in_transaction(connection, user_id)

        if not target:
            raise ValueError("User not found.")

        if target["is_deleted"]:
            raise ValueError("Account is already temporarily deleted.")

        if target["role"] == "ADMIN":
            raise ValueError(
                "Administrator accounts cannot be temporarily deleted."
            )

        connection.execute("""
            UPDATE users
            SET is_deleted = 1,
                deleted_at = ?,
                deleted_by = ?,
                deletion_reason = ?,
                deleted_was_active = is_active,
                is_active = 0,
                session_version = COALESCE(session_version, 0) + 1
            WHERE id = ?
        """, (
            _now(),
            admin["username"],
            reason,
            user_id,
        ))

        _audit_transaction(
            connection,
            "USER_TEMPORARILY_DELETED",
            admin["username"],
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


def _permanently_delete_account(user_id, admin_id):
    connection = _begin_transaction()

    try:
        admin = _admin_in_transaction(connection, admin_id)
        target = _account_in_transaction(connection, user_id)

        if not target:
            raise ValueError("User not found.")

        if not target["is_deleted"]:
            raise ValueError(
                "Temporarily delete the account before permanent deletion."
            )

        if target["role"] == "ADMIN":
            raise ValueError(
                "Administrator accounts cannot be permanently deleted."
            )

        _audit_transaction(
            connection,
            "USER_PERMANENTLY_DELETED",
            admin["username"],
            user_id,
            {
                "username": target["username"],
                "full_name": target["full_name"],
                "role": target["role"],
                "deleted_at": target["deleted_at"],
                "permanently_deleted_at": _now(),
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


# =========================================================
# PROMOTION REQUESTS
# =========================================================

def _create_promotion_request(user_id, reason):
    connection = _begin_transaction()

    try:
        user = _account_in_transaction(connection, user_id)

        if not user or not user["is_active"] or user["is_deleted"]:
            raise ValueError("An active account is required.")

        if user["role"] == "ADMIN":
            raise ValueError("This account is already an administrator.")

        cursor = connection.execute("""
            INSERT INTO admin_promotion_requests (
                user_id, request_reason, requested_at
            )
            VALUES (?, ?, ?)
        """, (user_id, reason, _now()))

        _audit_transaction(
            connection,
            "ADMIN_PROMOTION_REQUESTED",
            user["username"],
            user_id,
            {"reason": reason},
        )

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _get_promotion_requests(status_filter="PENDING"):
    status_filter = _validate_request_status(status_filter)
    connection = get_connection()

    try:
        query = """
            SELECT
                r.id, r.user_id, r.request_reason, r.status,
                r.reviewed_by, r.review_remarks,
                r.requested_at, r.reviewed_at,
                u.username, u.full_name, u.role, u.is_active
            FROM admin_promotion_requests r
            JOIN users u ON u.id = r.user_id
        """

        params = ()

        if status_filter != "ALL":
            query += " WHERE r.status = ?"
            params = (status_filter,)

        query += " ORDER BY r.requested_at DESC"

        return [
            dict(row)
            for row in connection.execute(query, params).fetchall()
        ]

    finally:
        connection.close()


def _review_promotion_request(request_id, admin_id, approve, remarks=None):
    connection = _begin_transaction()

    try:
        admin = _admin_in_transaction(connection, admin_id)

        request = connection.execute("""
            SELECT r.*, u.username, u.role, u.is_active, u.is_deleted
            FROM admin_promotion_requests r
            JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
        """, (request_id,)).fetchone()

        if not request:
            raise ValueError("Promotion request not found.")

        if request["status"] != "PENDING":
            raise ValueError("This request has already been reviewed.")

        if request["user_id"] == admin_id:
            raise ValueError("You cannot approve your own promotion request.")

        if approve:
            if not request["is_active"] or request["is_deleted"]:
                raise ValueError(
                    "The requesting account is inactive or deleted."
                )

            connection.execute("""
                UPDATE users
                SET role = 'ADMIN',
                    session_version = COALESCE(session_version, 0) + 1
                WHERE id = ?
            """, (request["user_id"],))

        new_status = "APPROVED" if approve else "REJECTED"

        connection.execute("""
            UPDATE admin_promotion_requests
            SET status = ?,
                reviewed_by = ?,
                review_remarks = ?,
                reviewed_at = ?
            WHERE id = ?
        """, (new_status, admin_id, remarks, _now(), request_id))

        _audit_transaction(
            connection,
            "ADMIN_PROMOTION_" + new_status,
            admin["username"],
            request["user_id"],
            {
                "request_id": request_id,
                "username": request["username"],
                "remarks": remarks,
            },
        )

        connection.commit()

        return {
            "request_id": request_id,
            "user_id": request["user_id"],
            "status": new_status,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# ACCOUNT RECOVERY REQUESTS
# =========================================================

def _create_recovery_request(username, reason):
    connection = _begin_transaction()

    try:
        user = connection.execute("""
            SELECT id, username, is_deleted
            FROM users
            WHERE username = ?
        """, (username.strip(),)).fetchone()

        if not user or not user["is_deleted"]:
            connection.rollback()
            return False

        cursor = connection.execute("""
            INSERT INTO account_recovery_requests (
                user_id, recovery_reason, requested_at
            )
            VALUES (?, ?, ?)
        """, (user["id"], reason, _now()))

        _audit_transaction(
            connection,
            "ACCOUNT_RECOVERY_REQUESTED",
            user["username"],
            user["id"],
            {"reason": reason},
        )

        connection.commit()
        return cursor.lastrowid

    except sqlite3.IntegrityError:
        connection.rollback()
        return False

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _get_recovery_requests(status_filter="PENDING"):
    status_filter = _validate_request_status(status_filter)
    connection = get_connection()

    try:
        query = """
            SELECT
                r.id, r.user_id, r.recovery_reason, r.status,
                r.reviewed_by, r.review_remarks,
                r.requested_at, r.reviewed_at,
                u.username, u.full_name, u.role
            FROM account_recovery_requests r
            JOIN users u ON u.id = r.user_id
        """

        params = ()

        if status_filter != "ALL":
            query += " WHERE r.status = ?"
            params = (status_filter,)

        query += " ORDER BY r.requested_at DESC"

        return [
            dict(row)
            for row in connection.execute(query, params).fetchall()
        ]

    finally:
        connection.close()


def _review_recovery_request(request_id, admin_id, approve, remarks=None):
    connection = _begin_transaction()

    try:
        admin = _admin_in_transaction(connection, admin_id)

        request = connection.execute("""
            SELECT r.*, u.username, u.is_deleted, u.deleted_was_active
            FROM account_recovery_requests r
            JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
        """, (request_id,)).fetchone()

        if not request:
            raise ValueError("Recovery request not found.")

        if request["status"] != "PENDING":
            raise ValueError("This request has already been reviewed.")

        if approve:
            if not request["is_deleted"]:
                raise ValueError("This account is no longer deleted.")

            connection.execute("""
                UPDATE users
                SET is_deleted = 0,
                    is_active = deleted_was_active,
                    deleted_at = NULL,
                    deleted_by = NULL,
                    deletion_reason = NULL,
                    deleted_was_active = 1,
                    session_version = COALESCE(session_version, 0) + 1
                WHERE id = ?
            """, (request["user_id"],))

        new_status = "APPROVED" if approve else "REJECTED"

        connection.execute("""
            UPDATE account_recovery_requests
            SET status = ?,
                reviewed_by = ?,
                review_remarks = ?,
                reviewed_at = ?
            WHERE id = ?
        """, (new_status, admin_id, remarks, _now(), request_id))

        _audit_transaction(
            connection,
            "ACCOUNT_RECOVERY_" + new_status,
            admin["username"],
            request["user_id"],
            {
                "request_id": request_id,
                "username": request["username"],
                "remarks": remarks,
            },
        )

        connection.commit()

        return {
            "request_id": request_id,
            "user_id": request["user_id"],
            "status": new_status,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# LOGIN
# =========================================================

@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, http_request: Request):
    rate_key = _enforce_rate_limit(
        "login",
        http_request,
        request.username,
        max_attempts=5,
        window_seconds=300,
    )

    user = authenticate_user(request.username, request.password)

    if not user:
        _record_failure(rate_key)
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password, or account inactive.",
        )

    account_role = user["role"]
    requested_role = request.requested_role
    is_restricted_session = False

    if requested_role == account_role:
        session_role = account_role

    elif account_role == "ADMIN":
        required_permission = (
            RESTRICTED_ADMIN_SESSION_PERMISSIONS.get(requested_role)
        )

        if not required_permission:
            raise HTTPException(
                status_code=403,
                detail="This account cannot sign in through the selected role.",
            )

        overrides = get_user_permission_overrides(user["id"])

        if overrides.get(required_permission) is not True:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Restricted access has not been granted for this role. "
                    "Sign in through the Admin tab or ask an administrator "
                    "to grant the required restricted access."
                ),
            )

        session_role = requested_role
        is_restricted_session = True

    else:
        raise HTTPException(
            status_code=403,
            detail="This account is not authorised for the selected role tab.",
        )

    _clear_failures(rate_key)

    update_last_login(user["id"])

    _audit_event(
        "USER_LOGIN",
        actor=user["username"],
        target=user["id"],
        details={
            "account_role": account_role,
            "session_role": session_role,
            "is_restricted_session": is_restricted_session,
        },
    )

    return {
        "access_token": create_access_token(user, session_role),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": session_role,
        "account_role": account_role,
        "is_restricted_session": is_restricted_session,
    }


# =========================================================
# CURRENT USER
# =========================================================

@auth_router.get("/me")
async def get_my_account(current_user=Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "account_role": current_user["account_role"],
        "is_restricted_session": current_user["is_restricted_session"],
        "is_active": current_user["is_active"],
        "created_at": current_user["created_at"],
        "last_login": current_user["last_login"],
        "effective_permissions": get_effective_permissions(
            current_user["id"],
            current_user["role"],
            restricted_session=current_user["is_restricted_session"],
        ),
    }


# =========================================================
# ADMIN: CREATE USER
# =========================================================

@auth_router.post("/users")
async def create_user_account(
    request: UserCreateRequest,
    current_admin=Depends(admin_access),
):
    try:
        user_id = create_user(
            username=request.username,
            full_name=request.full_name,
            password_hash=hash_password(request.password),
            role=request.role,
        )

        _audit_event(
            "USER_CREATED_BY_ADMIN",
            actor=current_admin["username"],
            target=user_id,
            details={"username": request.username, "role": request.role},
        )

        return {
            "success": True,
            "user_id": user_id,
            "username": request.username,
            "role": request.role,
            "message": "User account created successfully.",
        }

    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists.")

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# ADMIN: LIST USERS
# =========================================================

@auth_router.get("/users")
async def list_users(
    include_deleted: bool = False,
    current_admin=Depends(admin_access),
):
    connection = get_connection()

    try:
        query = """
            SELECT
                id, username, full_name, role, is_active, is_deleted,
                deleted_at, deletion_reason, created_at, last_login
            FROM users
        """

        if not include_deleted:
            query += " WHERE is_deleted = 0"

        query += " ORDER BY id"

        users = [
            dict(row)
            for row in connection.execute(query).fetchall()
        ]

        return {
            "success": True,
            "total_users": len(users),
            "users": users,
        }

    finally:
        connection.close()


# =========================================================
# ADMIN: USER PERMISSIONS
# =========================================================

@auth_router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    current_admin=Depends(admin_access),
):
    target = get_user_by_id(user_id)

    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    role = target["role"]
    overrides = get_user_permission_overrides(user_id)

    return {
        "success": True,
        "user_id": user_id,
        "username": target["username"],
        "role": role,
        "role_default_permissions": sorted(
            ROLE_DEFAULT_PERMISSIONS.get(role, set())
        ),
        "overrides": overrides,
        "effective_permissions": get_effective_permissions(user_id, role),
        "available_permissions": sorted(ALL_PERMISSION_KEYS),
    }


@auth_router.put("/users/{user_id}/permissions/{permission_key}")
async def update_user_permission(
    user_id: int,
    permission_key: str,
    request: UserPermissionRequest,
    current_admin=Depends(admin_access),
):
    target = get_user_by_id(user_id)

    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if permission_key not in ALL_PERMISSION_KEYS:
        raise HTTPException(status_code=400, detail="Unknown permission key.")

    if (
        permission_key in ADMIN_ONLY_PERMISSIONS
        and target["role"] != "ADMIN"
        and request.is_granted
    ):
        raise HTTPException(
            status_code=403,
            detail="This permission is restricted to administrator accounts.",
        )

    if (
        user_id == current_admin["id"]
        and permission_key == "permissions.manage"
        and not request.is_granted
    ):
        raise HTTPException(
            status_code=400,
            detail="You cannot revoke your own permission-management access.",
        )

    try:
        set_user_permission(
            user_id=user_id,
            permission_key=permission_key,
            is_granted=request.is_granted,
            updated_by=current_admin["id"],
        )

        if (
            target["role"] == "ADMIN"
            and permission_key in RESTRICTED_ADMIN_SESSION_PERMISSIONS.values()
        ):
            increment_session_version(user_id)

        _audit_event(
            "USER_PERMISSION_UPDATED",
            actor=current_admin["username"],
            target=user_id,
            details={
                "permission_key": permission_key,
                "is_granted": request.is_granted,
                "target_username": target["username"],
            },
        )

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=404,
            detail="Unable to update permission.",
        )

    return {
        "success": True,
        "user_id": user_id,
        "permission_key": permission_key,
        "is_granted": request.is_granted,
        "effective_permissions": get_effective_permissions(
            user_id, target["role"]
        ),
    }


@auth_router.delete("/users/{user_id}/permissions/{permission_key}")
async def reset_user_permission(
    user_id: int,
    permission_key: str,
    current_admin=Depends(admin_access),
):
    target = get_user_by_id(user_id)

    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if permission_key not in ALL_PERMISSION_KEYS:
        raise HTTPException(status_code=400, detail="Unknown permission key.")

    if (
        user_id == current_admin["id"]
        and permission_key == "permissions.manage"
    ):
        raise HTTPException(
            status_code=400,
            detail="You cannot reset your own permission-management override.",
        )

    removed = clear_user_permission_override(user_id, permission_key)

    if (
        target["role"] == "ADMIN"
        and permission_key in RESTRICTED_ADMIN_SESSION_PERMISSIONS.values()
    ):
        increment_session_version(user_id)

    _audit_event(
        "USER_PERMISSION_OVERRIDE_RESET",
        actor=current_admin["username"],
        target=user_id,
        details={
            "permission_key": permission_key,
            "override_removed": removed,
            "target_username": target["username"],
        },
    )

    return {
        "success": True,
        "user_id": user_id,
        "permission_key": permission_key,
        "override_removed": removed,
        "effective_permissions": get_effective_permissions(
            user_id, target["role"]
        ),
    }


# =========================================================
# ADMIN: LOCK / UNLOCK USER
# =========================================================

@auth_router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    request: UserStatusRequest,
    current_admin=Depends(admin_access),
):
    if user_id == current_admin["id"] and not request.is_active:
        raise HTTPException(
            status_code=400,
            detail="You cannot deactivate your own account.",
        )

    try:
        updated = _change_user_status(
            user_id, request.is_active, current_admin["id"]
        )

        return {
            "success": updated,
            "user_id": user_id,
            "is_active": request.is_active,
            "message": "User account status updated successfully.",
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# ADMIN: CHANGE ROLE
# =========================================================

@auth_router.patch("/users/{user_id}/role")
async def change_user_role(
    user_id: int,
    request: RoleChangeRequest,
    current_admin=Depends(admin_access),
):
    if user_id == current_admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own role.",
        )

    try:
        _change_user_role(user_id, request.role, current_admin["id"])

        return {
            "success": True,
            "user_id": user_id,
            "new_role": request.role,
            "message": "User role updated successfully.",
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# ADMIN: TEMPORARY DELETE
# =========================================================

@auth_router.delete("/users/{user_id}")
async def delete_user_account(
    user_id: int,
    reason: str | None = Query(default=None, max_length=1000),
    current_admin=Depends(admin_access),
):
    if user_id == current_admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account.",
        )

    try:
        _soft_delete_account(user_id, current_admin["id"], reason)

        return {
            "success": True,
            "user_id": user_id,
            "message": "Account temporarily deleted. Recovery remains possible.",
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# ADMIN: PERMANENT DELETE
# =========================================================

@auth_router.delete("/users/{user_id}/permanent-delete")
async def permanently_delete_user_account(
    user_id: int,
    current_admin=Depends(admin_access),
):
    if user_id == current_admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account.",
        )

    try:
        _permanently_delete_account(user_id, current_admin["id"])

        return {
            "success": True,
            "user_id": user_id,
            "message": "Account permanently deleted. Audit evidence retained.",
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# USER: REQUEST ADMIN PROMOTION
# =========================================================

@auth_router.post("/promotion-requests")
async def request_admin_promotion(
    request: PromotionRequestModel,
    current_user=Depends(get_current_user),
):
    try:
        request_id = _create_promotion_request(
            current_user["id"], request.reason
        )

        return {
            "success": True,
            "request_id": request_id,
            "status": "PENDING",
            "message": "Admin promotion request submitted for review.",
        }

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A pending promotion request already exists.",
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# ADMIN: REVIEW PROMOTION REQUESTS
# =========================================================

@auth_router.get("/promotion-requests")
async def list_promotion_requests(
    request_status: str = "PENDING",
    current_admin=Depends(admin_access),
):
    try:
        requests = _get_promotion_requests(request_status)

        return {
            "success": True,
            "total": len(requests),
            "requests": requests,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@auth_router.post("/promotion-requests/{request_id}/review")
async def review_promotion_request(
    request_id: int,
    request: PromotionReviewRequest,
    current_admin=Depends(admin_access),
):
    try:
        result = _review_promotion_request(
            request_id,
            current_admin["id"],
            request.approve,
            request.remarks,
        )

        return {
            "success": True,
            **result,
            "message": (
                "Promotion approved."
                if request.approve else "Promotion rejected."
            ),
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# PUBLIC: ACCOUNT RECOVERY REQUEST
# =========================================================

@auth_router.post("/account-recovery/request")
async def request_account_recovery(
    request: RecoveryRequestModel,
    http_request: Request,
):
    rate_key = _enforce_rate_limit(
        "account_recovery",
        http_request,
        request.username,
        max_attempts=3,
        window_seconds=900,
    )

    try:
        _create_recovery_request(request.username, request.reason)
        _record_failure(rate_key)

    except sqlite3.IntegrityError:
        _record_failure(rate_key)

    return {
        "success": True,
        "message": _generic_recovery_message(),
    }


# =========================================================
# ADMIN: REVIEW RECOVERY REQUESTS
# =========================================================

@auth_router.get("/account-recovery/requests")
async def list_recovery_requests(
    request_status: str = "PENDING",
    current_admin=Depends(admin_access),
):
    try:
        requests = _get_recovery_requests(request_status)

        return {
            "success": True,
            "total": len(requests),
            "requests": requests,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@auth_router.post("/account-recovery/requests/{request_id}/review")
async def review_recovery_request(
    request_id: int,
    request: RecoveryReviewRequest,
    current_admin=Depends(admin_access),
):
    try:
        result = _review_recovery_request(
            request_id,
            current_admin["id"],
            request.approve,
            request.remarks,
        )

        return {
            "success": True,
            **result,
            "message": (
                "Account recovery approved."
                if request.approve else "Account recovery rejected."
            ),
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# =========================================================
# INITIAL ADMINISTRATOR SETUP
# =========================================================

def bootstrap_admin():
    initialize_auth_security()

    users = get_all_users()

    if any(user["role"] == "ADMIN" for user in users):
        print("Administrator account already exists.")
        return

    print("\nINTELLIWATCH - INITIAL ADMINISTRATOR SETUP")
    print("=" * 50)

    username = input("Admin username: ").strip()
    full_name = input("Admin full name: ").strip()

    password = getpass.getpass(
        "Admin password (minimum 12 characters): "
    )
    confirm_password = getpass.getpass("Confirm admin password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    try:
        user_id = create_user(
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            role="ADMIN",
        )

        print("\nAdministrator created successfully.")
        print(f"Admin ID: {user_id}")
        print(f"Username: {username}")

    except (ValueError, sqlite3.IntegrityError) as error:
        print(f"\nAdministrator setup failed: {error}")


# =========================================================
# TOKEN REFRESH
# =========================================================

@auth_router.post("/refresh", response_model=LoginResponse)
async def refresh_token(current_user=Depends(get_current_user)):
    # Compatibility endpoint: this renews a still-valid access token.
    # It is not a separate long-lived refresh-token mechanism.
    return {
        "access_token": create_access_token(
            current_user,
            session_role=current_user["role"],
        ),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "account_role": current_user["account_role"],
        "is_restricted_session": current_user["is_restricted_session"],
    }


# =========================================================
# FIREBASE AUTHENTICATION  (Google Sign-In + Phone OTP)
# Verifies a Firebase ID token using Google's public keys.
# No service account private key needed — only PROJECT_ID.
# =========================================================

class FirebaseLoginRequest(BaseModel):
    id_token: str
    requested_role: str = Field(default="OPERATOR")


def _verify_firebase_token(id_token: str) -> dict:
    """Verify a Firebase ID token using Google's public X.509 certs."""
    import urllib.request
    import urllib.error

    FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")
    if not FIREBASE_PROJECT_ID:
        raise HTTPException(
            status_code=503,
            detail="Firebase authentication is not configured on this server.",
        )

    CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

    try:
        with urllib.request.urlopen(CERTS_URL, timeout=15) as resp:
            certs = json.loads(resp.read().decode())
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not reach Google's certificate endpoint. Try again shortly.",
        )

    last_error = None
    for kid, cert_pem in certs.items():
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            cert_obj = x509.load_pem_x509_certificate(cert_pem.encode())
            pub_key = cert_obj.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

            payload = jwt.decode(
                id_token,
                pub_key,
                algorithms=["RS256"],
                audience=FIREBASE_PROJECT_ID,
                issuer=f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}",
                options={"verify_exp": True},
            )
            return payload
        except Exception as e:
            last_error = e
            continue

    # Fallback: try without cryptography (pure jwt RS256)
    try:
        import base64
        header_b64 = id_token.split(".")[0]
        header_b64 += "=" * (-len(header_b64) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        kid = header.get("kid")
        if kid and kid in certs:
            payload = jwt.decode(
                id_token,
                certs[kid],
                algorithms=["RS256"],
                audience=FIREBASE_PROJECT_ID,
                issuer=f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}",
            )
            return payload
    except Exception as e:
        last_error = e

    raise HTTPException(
        status_code=401,
        detail=f"Firebase ID token verification failed: {last_error}",
    )


@auth_router.post("/firebase-login")
async def firebase_login(request: FirebaseLoginRequest, http_request: Request):
    """Exchange a Firebase ID token for an IntelliWatch JWT session."""
    rate_key = _enforce_rate_limit(
        "firebase_login",
        http_request,
        request.id_token[:16],
        max_attempts=10,
        window_seconds=300,
    )

    payload = _verify_firebase_token(request.id_token)

    uid        = payload.get("user_id") or payload.get("sub", "")
    email      = payload.get("email", "")
    name       = payload.get("name", "") or payload.get("email", uid)
    provider   = list((payload.get("firebase", {}).get("identities") or {}).keys())
    is_phone   = "phone" in str(provider)

    # Derive a stable username from email or phone UID
    if email:
        username_base = email.split("@")[0].replace(".", "_").replace("+", "_").lower()[:30]
    else:
        username_base = f"fb_{uid[:12]}"

    # Ensure role is valid
    allowed_roles = {"OPERATOR", "MAINTENANCE_ENGINEER"}
    requested_role = request.requested_role.upper()
    if requested_role not in allowed_roles:
        requested_role = "OPERATOR"

    # Find or create the user
    existing = get_user_by_username(username_base)

    if existing:
        user = existing
    else:
        try:
            user_id = create_user(
                username=username_base,
                full_name=name or username_base,
                password_hash=hash_password(secrets.token_hex(32)),
                role=requested_role,
            )
            user = get_user_by_id(user_id)
        except Exception:
            # Username collision — append uid suffix
            username_base = f"{username_base}_{uid[:6]}"
            user_id = create_user(
                username=username_base,
                full_name=name or username_base,
                password_hash=hash_password(secrets.token_hex(32)),
                role=requested_role,
            )
            user = get_user_by_id(user_id)

    if not user or not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account is inactive.")

    _clear_failures(rate_key)
    update_last_login(user["id"])

    _audit_event(
        "FIREBASE_LOGIN",
        actor=user["username"],
        target=user["id"],
        details={"provider": provider, "uid": uid, "role": requested_role},
    )

    return {
        "access_token": create_access_token(user, requested_role),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": requested_role,
        "account_role": user["role"],
        "is_restricted_session": False,
    }


# =========================================================
# PUBLIC SELF-REGISTRATION
# =========================================================

@auth_router.post("/register")
async def register(request: RegisterRequest, http_request: Request):
    rate_key = _enforce_rate_limit(
        "register",
        http_request,
        request.username,
        max_attempts=5,
        window_seconds=900,
    )

    try:
        user_id = create_user(
            username=request.username,
            full_name=request.full_name,
            password_hash=hash_password(request.password),
            role=request.role,
        )

        _clear_failures(rate_key)

        _audit_event(
            "USER_REGISTERED",
            actor=request.username,
            target=user_id,
            details={"role": request.role},
        )

        return {
            "success": True,
            "user_id": user_id,
            "username": request.username,
            "role": request.role,
            "message": "Account created successfully. You can now sign in.",
        }

    except sqlite3.IntegrityError:
        _record_failure(rate_key)
        raise HTTPException(status_code=409, detail="Username already exists.")

    except ValueError as error:
        _record_failure(rate_key)
        raise HTTPException(status_code=400, detail=str(error))


@auth_router.get("/registration-status")
async def registration_status():
    return {"registration_enabled": True}


# =========================================================
# PASSWORD RESET
# =========================================================

@auth_router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
):
    rate_key = _enforce_rate_limit(
        "forgot_password",
        http_request,
        request.username,
        max_attempts=3,
        window_seconds=900,
    )

    # No verified email/SMS recovery provider is configured here.
    # Therefore, do NOT create or return a reset token from this
    # public endpoint. Returning a token would allow account takeover.
    #
    # Once a trusted delivery provider is configured, generate a
    # random token, store only its hash using store_token(), and
    # deliver the raw token privately through that provider.

    user = get_user_by_username(request.username.strip())

    if user and user["is_active"] and not user.get("is_deleted", 0):
        _audit_event(
            "PASSWORD_RESET_REQUESTED",
            actor="PUBLIC_RECOVERY_REQUEST",
            target=user["id"],
            details={"status": "RECOVERY_CHANNEL_NOT_CONFIGURED"},
        )

    _record_failure(rate_key)

    return {
        "success": True,
        "message": (
            "If the account exists, password reset instructions "
            "will be sent through the configured recovery channel."
        ),
    }


@auth_router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    # Hash before consuming the token so a password validation error
    # does not unnecessarily destroy a valid recovery token.
    try:
        new_hash = hash_password(request.new_password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # Tokens are stored by hash, never in plaintext.
    try:
        entry = consume_token(request.token, "PASSWORD_RESET")
    except Exception:
        entry = None

    if not entry:
        raise HTTPException(
            status_code=400,
            detail="Reset token is invalid, expired or already used.",
        )

    user_id = entry.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="Reset token is invalid or expired.",
        )

    connection = _begin_transaction()

    try:
        user = connection.execute("""
            SELECT id, username, is_active, is_deleted
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if (
            not user
            or not user["is_active"]
            or user["is_deleted"]
        ):
            raise ValueError("Account not found or inactive.")

        cursor = connection.execute("""
            UPDATE users
            SET password_hash = ?,
                session_version = COALESCE(session_version, 0) + 1
            WHERE id = ?
              AND is_active = 1
              AND is_deleted = 0
        """, (new_hash, user_id))

        if cursor.rowcount != 1:
            raise ValueError("Account not found or inactive.")

        _audit_transaction(
            connection,
            "PASSWORD_RESET",
            user["username"],
            user_id,
            {"sessions_invalidated": True},
        )

        connection.commit()

    except Exception as error:
        connection.rollback()
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise

    finally:
        connection.close()

    # Revoke outstanding persistent tokens for this account.
    revoke_user_tokens(user_id)

    return {
        "success": True,
        "message": "Password updated successfully. Please sign in again.",
    }


# =========================================================
# ADMIN INVITATION SYSTEM
# =========================================================

@auth_router.post("/admin-invite")
async def create_admin_invite(current_admin=Depends(admin_access)):
    token = secrets.token_urlsafe(40)
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=ADMIN_INVITE_TTL_SECONDS
    )

    try:
        store_token(
            token,
            "ADMIN_INVITE",
            expires_at,
            created_by_user_id=current_admin["id"],
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to create Admin invitation.",
        )

    _audit_event(
        "ADMIN_INVITE_CREATED",
        actor=current_admin["username"],
        details={"expires_in_hours": 24},
    )

    # The raw token is shown only once to the authenticated Admin.
    # The persistent store must retain only its hash.
    return {
        "success": True,
        "admin_invite_token": token,
        "expires_in_hours": 24,
        "instructions": (
            "Share this token securely. It can be used once "
            "within 24 hours at POST /auth/register-admin."
        ),
    }


@auth_router.get("/admin-invite")
async def list_admin_invites(current_admin=Depends(admin_access)):
    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT
                id,
                created_by_user_id,
                created_at,
                expires_at
            FROM auth_security_tokens
            WHERE token_type = 'ADMIN_INVITE'
              AND consumed_at IS NULL
              AND revoked_at IS NULL
              AND expires_at > ?
            ORDER BY created_at DESC
        """, (_now(),)).fetchall()

        active = []

        for row in rows:
            creator = get_user_by_id(row["created_by_user_id"])
            active.append({
                "created_by": (
                    creator["username"] if creator else "Unavailable"
                ),
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
            })

        return {
            "pending_invites": active,
            "count": len(active),
        }

    finally:
        connection.close()


@auth_router.delete("/admin-invite")
async def revoke_admin_invites(current_admin=Depends(admin_access)):
    connection = _begin_transaction()

    try:
        cursor = connection.execute("""
            UPDATE auth_security_tokens
            SET revoked_at = ?
            WHERE token_type = 'ADMIN_INVITE'
              AND consumed_at IS NULL
              AND revoked_at IS NULL
        """, (_now(),))

        count = cursor.rowcount

        _audit_transaction(
            connection,
            "ADMIN_INVITES_REVOKED",
            current_admin["username"],
            None,
            {"revoked_count": count},
        )

        connection.commit()

        return {
            "success": True,
            "revoked_count": count,
            "message": "Pending Admin invitations revoked.",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# REGISTER CO-ADMIN USING INVITATION
# =========================================================

@auth_router.post("/register-admin")
async def register_admin(
    request: AdminRegisterRequest,
    http_request: Request,
):
    rate_key = _enforce_rate_limit(
        "register_admin",
        http_request,
        request.username,
        max_attempts=3,
        window_seconds=900,
    )

    try:
        new_hash = hash_password(request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # consume_token must atomically mark the invitation as consumed.
    try:
        entry = consume_token(
            request.invite_token.strip(),
            "ADMIN_INVITE",
        )
    except Exception:
        entry = None

    if not entry:
        _record_failure(rate_key)
        raise HTTPException(
            status_code=403,
            detail="Invalid, expired or already used Admin invitation.",
        )

    inviter_id = entry.get("created_by_user_id")

    if not inviter_id:
        _record_failure(rate_key)
        raise HTTPException(
            status_code=403,
            detail="The invitation creator is no longer valid.",
        )

    inviter = get_user_by_id(inviter_id)

    if (
        not inviter
        or inviter["role"] != "ADMIN"
        or not inviter["is_active"]
        or inviter.get("is_deleted", 0)
    ):
        _record_failure(rate_key)
        raise HTTPException(
            status_code=403,
            detail="The invitation creator is no longer an active Admin.",
        )

    try:
        user_id = create_user(
            username=request.username,
            full_name=request.full_name,
            password_hash=new_hash,
            role="ADMIN",
        )

        _clear_failures(rate_key)

        _audit_event(
            "ADMIN_REGISTERED_BY_INVITATION",
            actor=inviter["username"],
            target=user_id,
            details={"username": request.username},
        )

    except sqlite3.IntegrityError:
        _record_failure(rate_key)
        raise HTTPException(status_code=409, detail="Username already exists.")

    except ValueError as error:
        _record_failure(rate_key)
        raise HTTPException(status_code=400, detail=str(error))

    return {
        "success": True,
        "user_id": user_id,
        "username": request.username,
        "role": "ADMIN",
        "invited_by": inviter["username"],
        "message": "Co-Admin account created successfully.",
    }


# =========================================================
# DIRECT EXECUTION
# =========================================================

if __name__ == "__main__":
    bootstrap_admin()