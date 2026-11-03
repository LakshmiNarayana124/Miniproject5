
import os
import getpass
import sqlite3

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
    set_user_active,
    delete_user,
    get_connection,
)


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hasher = PasswordHasher()

security = HTTPBearer()

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ---------------------------------------------------------
# SECRET KEY
# ---------------------------------------------------------

def get_secret_key():

    secret_key = os.getenv("INTELLIWATCH_SECRET_KEY")

    if not secret_key or len(secret_key) < 32:
        raise RuntimeError(
            "INTELLIWATCH_SECRET_KEY is missing or too short. "
            "Set a secure secret key before starting IntelliWatch."
        )

    return secret_key


# ---------------------------------------------------------
# PASSWORD HASHING
# ---------------------------------------------------------

def hash_password(password: str) -> str:

    if not isinstance(password, str):
        raise ValueError("Password must be a string.")

    if len(password) < 12 or len(password) > 128:
        raise ValueError(
            "Password must contain between 12 and 128 characters."
        )

    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:

    try:
        return password_hasher.verify(
            password_hash,
            plain_password,
        )

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


# ---------------------------------------------------------
# USER AUTHENTICATION
# ---------------------------------------------------------

def authenticate_user(
    username: str,
    password: str,
):

    user = get_user_by_username(username)

    if not user:
        return None

    if not user["is_active"]:
        return None

    if not verify_password(
        password,
        user["password_hash"],
    ):
        return None

    return user


# ---------------------------------------------------------
# JWT TOKEN GENERATION
# ---------------------------------------------------------

def create_access_token(user):

    now = datetime.now(timezone.utc)

    expiration = now + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user["id"]),
        "iat": now,
        "exp": expiration,
    }

    token = jwt.encode(
        payload,
        get_secret_key(),
        algorithm=ALGORITHM,
    )

    return token


# ---------------------------------------------------------
# CURRENT USER AUTHENTICATION
# ---------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):

    token = credentials.credentials

    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise unauthorized_error

        user = get_user_by_id(int(user_id))

        if not user:
            raise unauthorized_error

        if not user["is_active"]:
            raise unauthorized_error

        return user

    except (
        jwt.ExpiredSignatureError,
        jwt.InvalidTokenError,
        ValueError,
    ):
        raise unauthorized_error


# ---------------------------------------------------------
# ROLE-BASED ACCESS CONTROL
# ---------------------------------------------------------

def require_roles(*allowed_roles):

    async def role_checker(
        current_user=Depends(get_current_user),
    ):

        if current_user["role"] not in allowed_roles:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )

        return current_user

    return role_checker


admin_access = require_roles("ADMIN")

operator_access = require_roles("OPERATOR")

maintenance_access = require_roles("MAINTENANCE_ENGINEER")


# ---------------------------------------------------------
# REQUEST / RESPONSE MODELS
# ---------------------------------------------------------

class LoginRequest(BaseModel):

    username: str = Field(
        min_length=3,
        max_length=50,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class LoginResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"

    expires_in: int

    user_id: int

    username: str

    full_name: str

    role: str


class UserCreateRequest(BaseModel):

    username: str = Field(
        min_length=3,
        max_length=50,
    )

    full_name: str = Field(
        min_length=2,
        max_length=100,
    )

    password: str = Field(
        min_length=12,
        max_length=128,
    )

    role: Literal[
        "ADMIN",
        "OPERATOR",
        "MAINTENANCE_ENGINEER",
    ]


class UserStatusRequest(BaseModel):

    is_active: bool


# ---------------------------------------------------------
# LOGIN ENDPOINT
# ---------------------------------------------------------

@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):

    user = authenticate_user(
        request.username,
        request.password,
    )

    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password, or account inactive.",
        )

    update_last_login(user["id"])

    access_token = create_access_token(user)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
    }


# ---------------------------------------------------------
# CURRENT USER DETAILS
# ---------------------------------------------------------

@auth_router.get("/me")
async def get_my_account(
    current_user=Depends(get_current_user),
):

    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "is_active": current_user["is_active"],
        "created_at": current_user["created_at"],
        "last_login": current_user["last_login"],
    }


# ---------------------------------------------------------
# CREATE USER - ADMIN ONLY
# ---------------------------------------------------------

@auth_router.post(
    "/users",
    dependencies=[Depends(admin_access)],
)
async def create_user_account(
    request: UserCreateRequest,
):

    try:

        password_hash = hash_password(request.password)

        user_id = create_user(
            username=request.username,
            full_name=request.full_name,
            password_hash=password_hash,
            role=request.role,
        )

        return {
            "success": True,
            "user_id": user_id,
            "username": request.username,
            "role": request.role,
            "message": "User account created successfully.",
        }

    except sqlite3.IntegrityError:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists or user data violates a database constraint.",
        )

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


# ---------------------------------------------------------
# VIEW ALL USERS - ADMIN ONLY
# ---------------------------------------------------------

@auth_router.get(
    "/users",
    dependencies=[Depends(admin_access)],
)
async def list_users():

    users = get_all_users()

    return {
        "success": True,
        "total_users": len(users),
        "users": [
            {
                "id": user["id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "role": user["role"],
                "is_active": user["is_active"],
                "created_at": user["created_at"],
                "last_login": user["last_login"],
            }
            for user in users
        ],
    }


# ---------------------------------------------------------
# ACTIVATE / DEACTIVATE USER - ADMIN ONLY
# ---------------------------------------------------------

@auth_router.patch(
    "/users/{user_id}/status",
    dependencies=[Depends(admin_access)],
)
async def update_user_status(
    user_id: int,
    request: UserStatusRequest,
    current_admin=Depends(admin_access),
):

    target_user = get_user_by_id(user_id)

    if not target_user:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if user_id == current_admin["id"] and not request.is_active:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    if (
        target_user["role"] == "ADMIN"
        and not request.is_active
    ):

        all_users = get_all_users()

        active_admins = [
            user for user in all_users
            if user["role"] == "ADMIN"
            and user["is_active"]
        ]

        if len(active_admins) <= 1:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active administrator cannot be deactivated.",
            )

    updated = set_user_active(
        user_id,
        request.is_active,
    )

    if not updated:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unable to update user status.",
        )

    return {
        "success": True,
        "user_id": user_id,
        "is_active": request.is_active,
        "message": "User account status updated successfully.",
    }


# ---------------------------------------------------------
# CHANGE USER ROLE - ADMIN ONLY
# Promote operator/engineer to admin, or demote admin to
# operator.  Protects: cannot demote self, cannot demote
# the last active admin.
# ---------------------------------------------------------

class RoleChangeRequest(BaseModel):
    role: Literal["ADMIN", "OPERATOR", "MAINTENANCE_ENGINEER"]


@auth_router.patch(
    "/users/{user_id}/role",
    dependencies=[Depends(admin_access)],
)
async def change_user_role(
    user_id: int,
    request: RoleChangeRequest,
    current_admin=Depends(admin_access),
):
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user_id == current_admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role.",
        )

    # Prevent demoting the last active admin
    if target["role"] == "ADMIN" and request.role != "ADMIN":
        all_users = get_all_users()
        active_admins = [u for u in all_users if u["role"] == "ADMIN" and u["is_active"]]
        if len(active_admins) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last active administrator.",
            )

    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE users SET role = ? WHERE id = ?", (request.role, user_id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "success":  True,
        "user_id":  user_id,
        "new_role": request.role,
        "message":  f"Role updated to {request.role} successfully.",
    }


# ---------------------------------------------------------
# DELETE USER - ADMIN ONLY
# ---------------------------------------------------------

@auth_router.delete("/users/{user_id}")
async def delete_user_account(
    user_id: int,
    current_admin=Depends(admin_access),
):

    # Prevent administrator from deleting their own account.
    if user_id == current_admin["id"]:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    target_user = get_user_by_id(user_id)

    if not target_user:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Database function only permits deletion of
    # OPERATOR and MAINTENANCE_ENGINEER accounts.
    try:

        deleted = delete_user(user_id)

    except sqlite3.IntegrityError:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User cannot be deleted because related records exist.",
        )

    if not deleted:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or deletion not permitted.",
        )

    return {
        "success": True,
        "user_id": user_id,
        "message": f"User account {user_id} permanently deleted.",
    }


# ---------------------------------------------------------
# INITIAL ADMINISTRATOR SETUP
# ---------------------------------------------------------

def bootstrap_admin():

    initialize_database()

    users = get_all_users()

    existing_admins = [
        user for user in users
        if user["role"] == "ADMIN"
    ]

    if existing_admins:

        print("Administrator account already exists.")
        return

    print("\nINTELLIWATCH - INITIAL ADMINISTRATOR SETUP")
    print("=" * 50)

    username = input("Admin username: ").strip()

    full_name = input("Admin full name: ").strip()

    password = getpass.getpass(
        "Admin password (minimum 12 characters): "
    )

    confirm_password = getpass.getpass(
        "Confirm admin password: "
    )

    if password != confirm_password:

        print("Passwords do not match.")
        return

    try:

        password_hash = hash_password(password)

        user_id = create_user(
            username=username,
            full_name=full_name,
            password_hash=password_hash,
            role="ADMIN",
        )

        print("\nAdministrator created successfully.")
        print(f"Admin ID: {user_id}")
        print(f"Username: {username}")

    except (ValueError, sqlite3.IntegrityError) as error:

        print(f"\nAdministrator setup failed: {error}")


# ---------------------------------------------------------
# DIRECT EXECUTION
# ---------------------------------------------------------

if __name__ == "__main__":

    bootstrap_admin()


# ---------------------------------------------------------
# TOKEN REFRESH ENDPOINT
# Allows long-running monitoring sessions to renew the
# access token without re-entering credentials.
# ---------------------------------------------------------

@auth_router.post("/refresh", response_model=LoginResponse)
async def refresh_token(current_user=Depends(get_current_user)):
    """
    Exchange a still-valid JWT for a fresh one with a new expiry.
    The frontend calls this automatically before the token expires.
    """
    new_token = create_access_token(current_user)
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": current_user["role"],
    }


# ---------------------------------------------------------
# SELF-REGISTRATION WITH INVITE CODE
# Anyone with the correct invite code can create an account.
# The invite code is set via the INTELLIWATCH_INVITE_CODE env var.
# If the env var is not set, self-registration is disabled.
# ---------------------------------------------------------

import secrets as _secrets

def _get_invite_code() -> str | None:
    return os.getenv("INTELLIWATCH_INVITE_CODE", "").strip() or None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["OPERATOR", "MAINTENANCE_ENGINEER"]
    invite_code: str = Field(min_length=1, max_length=128)


@auth_router.post("/register", tags=["Authentication"])
async def register(request: RegisterRequest):
    """
    Self-registration endpoint.
    Requires a valid invite code (INTELLIWATCH_INVITE_CODE env var).
    Only OPERATOR and MAINTENANCE_ENGINEER roles are allowed here.
    """
    invite = _get_invite_code()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is disabled. Contact your administrator.",
        )
    # Constant-time comparison to prevent timing attacks
    if not _secrets.compare_digest(request.invite_code.strip(), invite):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid invite code.",
        )
    try:
        password_hash = hash_password(request.password)
        user_id = create_user(
            username=request.username,
            full_name=request.full_name,
            password_hash=password_hash,
            role=request.role,
        )
        return {
            "success": True,
            "user_id": user_id,
            "username": request.username,
            "role": request.role,
            "message": "Account created successfully. You can now sign in.",
        }
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------
# PASSWORD RESET — TOKEN-BASED
# No email server required: the reset token is returned
# in the API response (for display to an admin / on-prem).
# In production, replace the token delivery with email.
# ---------------------------------------------------------

import threading as _threading

# In-memory store: { token: { user_id, expires_at } }
# Backed by a lock for thread-safety.
_reset_tokens: dict = {}
_reset_lock = _threading.Lock()
_RESET_TOKEN_TTL_SECONDS = 900   # 15 minutes


def _purge_expired_tokens():
    import time as _time
    now = _time.time()
    with _reset_lock:
        expired = [t for t, v in _reset_tokens.items() if v["expires_at"] < now]
        for t in expired:
            del _reset_tokens[t]


class ForgotPasswordRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


@auth_router.post("/forgot-password", tags=["Authentication"])
async def forgot_password(request: ForgotPasswordRequest):
    """
    Generate a password-reset token for the given username.

    Security model (on-prem / no email):
      - The reset token is returned in the response body.
      - An admin should deliver this token to the user securely
        (e.g. over a private channel or SMS).
      - The token expires in 15 minutes.
      - We return 200 even if the user doesn't exist to prevent
        username enumeration.
    """
    import time as _time
    _purge_expired_tokens()

    user = get_user_by_username(request.username)
    if not user or not user["is_active"]:
        # Always return 200 to prevent enumeration
        return {
            "success": True,
            "message": "If that account exists, a reset token has been generated.",
            "reset_token": None,
            "expires_in_seconds": _RESET_TOKEN_TTL_SECONDS,
            "note": "Account not found or inactive.",
        }

    token = _secrets.token_urlsafe(32)
    with _reset_lock:
        _reset_tokens[token] = {
            "user_id": user["id"],
            "expires_at": _time.time() + _RESET_TOKEN_TTL_SECONDS,
        }

    return {
        "success": True,
        "message": "Reset token generated. Deliver it to the user securely. Expires in 15 minutes.",
        "reset_token": token,
        "expires_in_seconds": _RESET_TOKEN_TTL_SECONDS,
        "username": user["username"],
    }


@auth_router.post("/reset-password", tags=["Authentication"])
async def reset_password(request: ResetPasswordRequest):
    """
    Consume a reset token and set a new password.
    """
    import time as _time
    _purge_expired_tokens()

    with _reset_lock:
        entry = _reset_tokens.get(request.token)

    if not entry or entry["expires_at"] < _time.time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid or has expired.",
        )

    user = get_user_by_id(entry["user_id"])
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not found or inactive.",
        )

    try:
        new_hash = hash_password(request.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Update password in DB
    from database import get_connection as _get_conn
    conn = _get_conn()
    try:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        conn.commit()
    finally:
        conn.close()

    # Invalidate the token
    with _reset_lock:
        _reset_tokens.pop(request.token, None)

    return {
        "success": True,
        "message": "Password updated successfully. You can now sign in with your new password.",
    }


# ---------------------------------------------------------
# CHECK REGISTRATION STATUS
# Frontend uses this to know whether to show the register tab.
# ---------------------------------------------------------

@auth_router.get("/registration-status", tags=["Authentication"])
async def registration_status():
    """Returns whether self-registration is enabled."""
    return {"registration_enabled": _get_invite_code() is not None}


# ---------------------------------------------------------
# ADMIN INVITE SYSTEM
# ---------------------------------------------------------
# An existing ADMIN can generate a one-time admin invite
# token.  Anyone who holds that token can create exactly
# one new ADMIN account.  The token is single-use and
# expires in 24 hours.
#
# Flow:
#   1. Admin calls POST /auth/admin-invite  → gets token
#   2. Admin shares token with the new person securely
#   3. New person calls POST /auth/register-admin with
#      that token + their credentials
#   4. Token is consumed; new ADMIN account is active
# ---------------------------------------------------------

import threading as _admin_thread

_admin_invite_tokens: dict = {}   # token → { created_by_id, expires_at, used }
_admin_invite_lock = _admin_thread.Lock()
_ADMIN_INVITE_TTL = 86_400          # 24 hours


def _purge_admin_invites():
    import time as _t
    now = _t.time()
    with _admin_invite_lock:
        expired = [k for k, v in _admin_invite_tokens.items()
                   if v["expires_at"] < now or v.get("used")]
        for k in expired:
            del _admin_invite_tokens[k]


# ── Generate admin invite token (current admin only) ──────────────────────

@auth_router.post("/admin-invite", tags=["Authentication"],
                  dependencies=[Depends(admin_access)])
async def create_admin_invite(current_admin=Depends(admin_access)):
    """
    Generate a single-use 24-hour admin invite token.
    Only an existing ADMIN can call this endpoint.
    Returns the token that must be delivered to the prospective
    co-admin securely (e.g. in person, via secure channel).
    """
    import time as _t
    _purge_admin_invites()

    token = _secrets.token_urlsafe(40)
    with _admin_invite_lock:
        _admin_invite_tokens[token] = {
            "created_by_id":   current_admin["id"],
            "created_by_name": current_admin["username"],
            "expires_at":      _t.time() + _ADMIN_INVITE_TTL,
            "used":            False,
        }

    return {
        "success":            True,
        "admin_invite_token": token,
        "expires_in_hours":   24,
        "instructions": (
            "Share this token securely with the person you want to make a co-admin. "
            "They must use POST /auth/register-admin within 24 hours. "
            "The token is single-use — it becomes invalid immediately after use."
        ),
    }


# ── List pending admin invites (admins only) ───────────────────────────────

@auth_router.get("/admin-invite", tags=["Authentication"],
                 dependencies=[Depends(admin_access)])
async def list_admin_invites():
    """Return a summary of currently active (unused, unexpired) invite tokens."""
    import time as _t
    _purge_admin_invites()
    now = _t.time()
    with _admin_invite_lock:
        active = [
            {
                "created_by": v["created_by_name"],
                "expires_in_minutes": int((v["expires_at"] - now) / 60),
                "token_preview": k[:8] + "…",   # never expose the full token via GET
            }
            for k, v in _admin_invite_tokens.items()
            if not v.get("used") and v["expires_at"] > now
        ]
    return {"pending_invites": active, "count": len(active)}


# ── Revoke all pending admin invites (admins only) ─────────────────────────

@auth_router.delete("/admin-invite", tags=["Authentication"],
                    dependencies=[Depends(admin_access)])
async def revoke_all_admin_invites():
    """Immediately invalidate all pending admin invite tokens."""
    with _admin_invite_lock:
        _admin_invite_tokens.clear()
    return {"success": True, "message": "All pending admin invite tokens revoked."}


# ── Register-admin endpoint (uses invite token, no auth required) ──────────

class AdminRegisterRequest(BaseModel):
    username:     str = Field(min_length=3,  max_length=50)
    full_name:    str = Field(min_length=2,  max_length=100)
    password:     str = Field(min_length=12, max_length=128)
    invite_token: str = Field(min_length=8,  max_length=256)


@auth_router.post("/register-admin", tags=["Authentication"])
async def register_admin(request: AdminRegisterRequest):
    """
    Create a new ADMIN account using a one-time admin invite token.
    No existing authentication is required (the invite token IS the auth).

    Security properties:
    - Token must be unused and unexpired (24-hour TTL).
    - Token is invalidated immediately after first successful use.
    - Username must be unique (DB constraint).
    - Password must meet minimum strength (12+ chars, handled by hash_password).
    """
    import time as _t
    _purge_admin_invites()

    with _admin_invite_lock:
        entry = None
        matched_token = None
        for tok, val in _admin_invite_tokens.items():
            if _secrets.compare_digest(tok, request.invite_token.strip()):
                entry = val
                matched_token = tok
                break

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired admin invite token.",
        )

    if entry.get("used"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This admin invite token has already been used.",
        )

    if entry["expires_at"] < _t.time():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin invite token has expired.",
        )

    # Mark used immediately (before DB write — prevents race condition)
    with _admin_invite_lock:
        if matched_token in _admin_invite_tokens:
            _admin_invite_tokens[matched_token]["used"] = True

    try:
        password_hash = hash_password(request.password)
        user_id = create_user(
            username=request.username,
            full_name=request.full_name,
            password_hash=password_hash,
            role="ADMIN",
        )
    except sqlite3.IntegrityError:
        # On failure, un-mark the token so it can be retried
        with _admin_invite_lock:
            if matched_token in _admin_invite_tokens:
                _admin_invite_tokens[matched_token]["used"] = False
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists. Choose a different username.",
        )
    except ValueError as e:
        with _admin_invite_lock:
            if matched_token in _admin_invite_tokens:
                _admin_invite_tokens[matched_token]["used"] = False
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Permanently remove the consumed token
    with _admin_invite_lock:
        _admin_invite_tokens.pop(matched_token, None)

    return {
        "success":  True,
        "user_id":  user_id,
        "username": request.username,
        "role":     "ADMIN",
        "invited_by": entry["created_by_name"],
        "message":  (
            f"Admin account created successfully. "
            f"You were invited by '{entry['created_by_name']}'. "
            f"Sign in using the Admin Mode on the login page."
        ),
    }
