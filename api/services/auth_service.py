"""AYUR-INTEL — Authentication Service.

Handles user signup, login, password hashing, and token generation/verification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import hmac
import re
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, Union

from sqlalchemy.orm import Session
from fastapi import HTTPException

from api.models.models import User
from api.models.security import UserSession, AccessRequest
from api.services.audit_service import log_action
from api.services.email_service import dispatch_admin_notification
from api.core.config import settings

logger = logging.getLogger("ayur_intel.auth")

DEFAULT_TOKEN_EXPIRE_SECONDS = 86400      # 24 hours default
MIN_TOKEN_EXPIRE_SECONDS = 60              # 1 minute minimum
MAX_TOKEN_EXPIRE_SECONDS = 30 * 24 * 3600  # 30 days maximum

# Supported Inactivity Timeout options: 5m, 15m, 30m, 1h, 2h, 4h
IDLE_TIMEOUT_MAP: Dict[Union[str, int], int] = {
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    300: 300,
    900: 900,
    1800: 1800,
    3600: 3600,
    7200: 7200,
    14400: 14400,
}
DEFAULT_IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes

# Supported Maximum Session Lifetime options: 8h, 12h, 24h
MAX_LIFETIME_MAP: Dict[Union[str, int], int] = {
    "8h": 28800,
    "12h": 43200,
    "24h": 86400,
    28800: 28800,
    43200: 43200,
    86400: 86400,
}
DEFAULT_MAX_LIFETIME_SECONDS = 43200  # 12 hours (Default)


def parse_timeout_settings(
    session_timeout: Optional[Any] = None,
    max_lifetime: Optional[Any] = None,
) -> Tuple[int, int]:
    """Parse and validate session timeout (inactivity) and max session lifetime.

    Supported inactivity timeouts: 5m (300s), 15m (900s), 30m (1800s), 1h (3600s), 2h (7200s), 4h (14400s).
    Supported max session lifetimes: 8h (28800s), 12h (43200s), 24h (86400s).

    Security bounds:
    - Never allow frontend values to override server-enforced safety limits.
    - Clamped to safe predefined intervals.
    """
    idle_sec = DEFAULT_IDLE_TIMEOUT_SECONDS
    if session_timeout is not None:
        if isinstance(session_timeout, str) and session_timeout.strip().lower() in IDLE_TIMEOUT_MAP:
            idle_sec = IDLE_TIMEOUT_MAP[session_timeout.strip().lower()]
        elif session_timeout in IDLE_TIMEOUT_MAP:
            idle_sec = IDLE_TIMEOUT_MAP[session_timeout]

    max_sec = DEFAULT_MAX_LIFETIME_SECONDS
    if max_lifetime is not None:
        if isinstance(max_lifetime, str) and max_lifetime.strip().lower() in MAX_LIFETIME_MAP:
            max_sec = MAX_LIFETIME_MAP[max_lifetime.strip().lower()]
        elif max_lifetime in MAX_LIFETIME_MAP:
            max_sec = MAX_LIFETIME_MAP[max_lifetime]

    if idle_sec > max_sec:
        idle_sec = max_sec

    return idle_sec, max_sec



def get_token_ttl_seconds() -> int:
    """Return token expiration lifetime in seconds from configuration.

    Safely clamps to [60s, 30 days] security bounds and falls back to 86400s if unconfigured.
    """
    raw_ttl = getattr(settings, "AYURINTEL_SESSION_TTL_SECONDS", DEFAULT_TOKEN_EXPIRE_SECONDS)
    try:
        ttl = int(raw_ttl)
        if ttl < MIN_TOKEN_EXPIRE_SECONDS:
            logger.warning(
                "Configured AYURINTEL_SESSION_TTL_SECONDS (%s) is below minimum %s. Clamping to %s.",
                raw_ttl, MIN_TOKEN_EXPIRE_SECONDS, MIN_TOKEN_EXPIRE_SECONDS
            )
            return MIN_TOKEN_EXPIRE_SECONDS
        if ttl > MAX_TOKEN_EXPIRE_SECONDS:
            logger.warning(
                "Configured AYURINTEL_SESSION_TTL_SECONDS (%s) exceeds maximum %s. Clamping to %s.",
                raw_ttl, MAX_TOKEN_EXPIRE_SECONDS, MAX_TOKEN_EXPIRE_SECONDS
            )
            return MAX_TOKEN_EXPIRE_SECONDS
        return ttl
    except (ValueError, TypeError):
        logger.warning(
            "Non-integer AYURINTEL_SESSION_TTL_SECONDS (%s). Using default %s.",
            raw_ttl, DEFAULT_TOKEN_EXPIRE_SECONDS
        )
        return DEFAULT_TOKEN_EXPIRE_SECONDS

# Pre-computed valid dummy PBKDF2 hash (100,000 iterations) for timing equalization
# when verifying nonexistent accounts or accounts without configured passwords.
DUMMY_PASSWORD_HASH = (
    "adb17207625efae76d7eda7d1e331ef1:"
    "a8ba8ceb074ab1776bddc23fa7d458ec251648c82f3cc5852aeaf21f33e085c6"
)

# Known weak / placeholder default secrets that must be rejected in production
KNOWN_INSECURE_SECRETS = {
    "change-me-in-production",
    "ayur-intel-secret-key-signature-token-vault-2026",
    "secret",
    "password",
    "changeme",
    "admin",
    "12345678",
}
MIN_SECRET_LENGTH = 32


def validate_session_secret(
    secret: Optional[str] = None,
    is_production: Optional[bool] = None,
) -> str:
    """Validate token signing secret strength.

    In production (is_production=True or not settings.AYURINTEL_DEBUG):
    - Rejects missing, weak, or known default secrets with RuntimeError.
    - Enforces minimum length of 32 bytes (256 bits).

    In development:
    - Emits a warning if a default placeholder is used, but permits local development.

    Returns:
        The validated secret string.
    """
    sec = secret if secret is not None else getattr(settings, "AYURINTEL_SESSION_SECRET", "")
    if is_production is not None:
        prod = is_production
    elif hasattr(settings, "is_production"):
        prod = bool(settings.is_production)
    else:
        prod = not getattr(settings, "effective_debug", getattr(settings, "AYURINTEL_DEBUG", True))

    if prod:
        if not sec or not sec.strip():
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: AYURINTEL_SESSION_SECRET is empty. "
                "A strong secret of at least 32 bytes is required in production."
            )
        clean = sec.strip()
        if clean.lower() in KNOWN_INSECURE_SECRETS:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: AYURINTEL_SESSION_SECRET is set to a "
                "known default or placeholder. A secure 32+ byte secret must be configured in production."
            )
        if len(clean.encode("utf-8")) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"CRITICAL SECURITY CONFIGURATION ERROR: AYURINTEL_SESSION_SECRET is too short ({len(clean.encode('utf-8'))} bytes). "
                f"It must be at least {MIN_SECRET_LENGTH} bytes in production."
            )
    else:
        if not sec or sec.strip().lower() in KNOWN_INSECURE_SECRETS:
            logger.warning(
                "Security Notice: Using development session secret placeholder. "
                "Configure a 32+ byte secret in AYURINTEL_SESSION_SECRET before deploying to production."
            )

    return sec or "ayur-intel-dev-fallback-secret-2026"


def get_signing_secret() -> str:
    """Return the active validated signing secret from settings."""
    return validate_session_secret()


EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email: str) -> bool:
    """Validate email format using regex."""
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


# ---------------------------------------------------------------------------
# Password Hashing (PBKDF2 HMAC-SHA256)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with salt."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verify a plain password against stored salt:hash string."""
    if not hashed_password or ":" not in hashed_password:
        return False
    try:
        salt_hex, key_hex = hashed_password.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(key, new_key)
    except Exception as e:
        logger.error("Password verification error: %s", e)
        return False


# ---------------------------------------------------------------------------
# HMAC Access Token Engine
# ---------------------------------------------------------------------------

def create_access_token(data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> str:
    """Create a signed HMAC-SHA256 token containing payload data."""
    payload = dict(data)
    effective_ttl = ttl_seconds if (ttl_seconds is not None and ttl_seconds > 0) else get_token_ttl_seconds()
    payload["exp"] = int(time.time()) + effective_ttl
    payload_bytes = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    
    secret = get_signing_secret()
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify signed access token and return payload if valid."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, signature = token.split(".", 1)
        secret = get_signing_secret()
        expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Pad base64 if needed
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        exp = payload.get("exp")
        if not isinstance(exp, (int, float)) or exp < int(time.time()):
            logger.warning("Token expired or missing exp for user: %s", payload.get("sub"))
            return None

        return payload
    except Exception as e:
        logger.error("Token verification exception: %s", e)
        return None


# ---------------------------------------------------------------------------
# User Auth Business Operations
# ---------------------------------------------------------------------------

def user_to_dict(user: User) -> Dict[str, Any]:
    """Convert User model to clean user dictionary for frontend API."""
    return {
        "id": user.public_id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "email": user.email or "",
        "role": getattr(user, "role", "user") or "user",
        "is_active": bool(getattr(user, "is_active", True)),
        "is_approved": bool(getattr(user, "is_approved", True)),
        "login_count": getattr(user, "login_count", 0) or 0,
        "avatar_url": getattr(user, "avatar_url", None) or "",
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }



def parse_device_info(user_agent: Optional[str]) -> str:
    """Extract human-readable device and browser summary from User-Agent string."""
    if not user_agent:
        return "Unknown Device"
    ua = user_agent.lower()

    # OS detection
    os_name = "Unknown OS"
    if "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua or "ipod" in ua:
        os_name = "iOS"
    elif "linux" in ua:
        os_name = "Linux"

    # Browser detection
    browser = "Unknown Browser"
    if "edg/" in ua or "edge" in ua:
        browser = "Edge"
    elif "chrome" in ua and "chromium" not in ua and "edg" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "curl" in ua or "postman" in ua or "python" in ua or "httpx" in ua:
        browser = "API Client"

    return f"{browser} on {os_name}"


def signup_user(
    db: Session,
    full_name: str,
    email: str,
    password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    """Register a new user account.

    By default (auto_approve=False), new accounts require administrator approval before
    accessing any protected resources. An access request is created and the administrator
    is notified via email.
    """
    clean_email = email.strip().lower()
    clean_name = full_name.strip()
    
    if not is_valid_email(clean_email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    # Check existing user by email
    existing_user = db.query(User).filter(User.email.ilike(clean_email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # Generate a username from email
    base_username = clean_email.split("@")[0]
    username = base_username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}_{counter}"
        counter += 1

    hashed = hash_password(password)
    user = User(
        username=username,
        display_name=clean_name or base_username.capitalize(),
        email=clean_email,
        hashed_password=hashed,
        role="user",
        token_version=1,
        is_active=bool(auto_approve),
        is_approved=bool(auto_approve),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    now_utc = datetime.now(timezone.utc)
    device_info = parse_device_info(user_agent)

    if not auto_approve:
        # Mandatory access approval workflow: record pending access request
        new_req = AccessRequest(
            user_id=user.id,
            user_email=user.email or clean_email,
            user_display_name=user.display_name or user.username,
            status="PENDING",
            request_type="NEW_USER",
            reason="New user registration approval request",
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now_utc,
        )
        db.add(new_req)
        db.commit()
        db.refresh(new_req)

        # Dispatch email notification to administrator (does not block registration if provider fails)
        try:
            ok, err = dispatch_admin_notification(
                applicant_name=user.display_name or user.username,
                applicant_email=user.email or clean_email,
                request_type="NEW_USER",
                created_at=new_req.created_at,
                device_info=new_req.device_info,
                reason=new_req.reason,
            )
            new_req.notification_sent = ok
            new_req.notification_error = err
            db.commit()
        except Exception as e:
            logger.warning("Exception dispatching admin notification email: %s", e)
            new_req.notification_sent = False
            new_req.notification_error = str(e)
            db.commit()

        try:
            log_action(
                db,
                action="SIGNUP",
                resource_type="AUTH",
                resource_id=new_req.public_id,
                user_id=user.id,
                user_public_id=user.public_id,
                username=user.username,
                ip_address=ip_address,
                user_agent=user_agent,
                status="SUCCESS",
                detail="User registered; pending administrator access approval",
                metadata={"request_id": new_req.public_id, "request_type": "NEW_USER"},
            )
            db.commit()
        except Exception as e:
            logger.debug("Failed to record signup audit log: %s", e)
            db.rollback()

        logger.info("New user registered (pending approval): %s (%s)", user.display_name, user.email)
        return {
            "user": user_to_dict(user),
            "status": "pending_approval",
            "message": "Approval pending by Admin. Your account has been registered and is pending administrator review. You will be able to sign in once access is approved.",
            "request_id": new_req.public_id,
        }

    # If auto_approve is True (internal/fixture use):
    idle_timeout_seconds, max_lifetime_seconds = parse_timeout_settings()
    expires_at = now_utc + timedelta(seconds=max_lifetime_seconds)

    session = UserSession(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info,
        is_revoked=False,
        idle_timeout_seconds=idle_timeout_seconds,
        max_lifetime_seconds=max_lifetime_seconds,
        created_at=now_utc,
        last_active_at=now_utc,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    token = create_access_token(
        {
            "sub": user.public_id,
            "email": user.email,
            "sid": session.public_id,
        },
        ttl_seconds=max_lifetime_seconds,
    )

    try:
        log_action(
            db,
            action="SIGNUP",
            resource_type="AUTH",
            resource_id=session.public_id,
            user_id=user.id,
            user_public_id=user.public_id,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail="User registered and session created (auto-approved)",
        )
        db.commit()
    except Exception as e:
        logger.debug("Failed to record signup audit log: %s", e)
        db.rollback()

    logger.info("User registered successfully (auto-approved): %s (%s)", user.display_name, user.email)
    return {
        "token": token,
        "user": user_to_dict(user),
    }


def login_user(
    db: Session,
    email_or_username: str,
    password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_timeout: Optional[str] = None,
    max_lifetime: Optional[str] = None,
    device_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Authenticate an existing user with email/username and password."""
    clean_identifier = email_or_username.strip().lower()
    
    user = (
        db.query(User)
        .filter(
            (User.email.ilike(clean_identifier)) | (User.username.ilike(clean_identifier))
        )
        .first()
    )

    # If account does not exist or has no password set:
    # run dummy password hash verification to minimize timing discrepancy, then fail.
    # An account without a configured password must NEVER become claimable through login.
    if not user or not user.hashed_password:
        verify_password(password, DUMMY_PASSWORD_HASH)
        try:
            log_action(
                db,
                action="LOGIN",
                resource_type="AUTH",
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILED",
                detail="Invalid credentials",
                metadata={"identifier": clean_identifier},
            )
            db.commit()
        except Exception as e:
            logger.debug("Failed to record login audit log: %s", e)
            db.rollback()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user.hashed_password):
        try:
            log_action(
                db,
                action="LOGIN",
                resource_type="AUTH",
                user_id=user.id,
                user_public_id=user.public_id,
                username=user.username,
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILED",
                detail="Invalid password",
                metadata={"identifier": clean_identifier},
            )
            db.commit()
        except Exception as e:
            logger.debug("Failed to record login audit log: %s", e)
            db.rollback()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # If password is correct but account is unapproved, deactivated, or rejected:
    # Do not issue token; record/retrieve access request and notify administrator on genuinely new request.
    if not user.is_active or not getattr(user, "is_approved", True):
        device_hash = hashlib.sha256(device_id.strip().encode("utf-8")).hexdigest() if device_id and device_id.strip() else None
        
        # 1. Reuse existing pending request to avoid duplicates and duplicate emails
        pending_req = (
            db.query(AccessRequest)
            .filter(AccessRequest.user_id == user.id, AccessRequest.status == "PENDING")
            .order_by(AccessRequest.created_at.desc())
            .first()
        )
        if pending_req:
            is_new = (pending_req.request_type == "NEW_USER") or not getattr(user, "is_approved", True)
            error_detail = (
                "Approval pending by Admin. Your account is pending administrator approval. You will be able to sign in once access is approved."
                if is_new
                else "Approval pending by Admin. Your account is currently deactivated. Your access request has been submitted for administrator review. You will be able to sign in once access is approved."
            )
            try:
                log_action(
                    db,
                    action="LOGIN_DENIED",
                    resource_type="AUTH",
                    user_id=user.id,
                    user_public_id=user.public_id,
                    username=user.username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="DENIED",
                    detail=error_detail,
                    metadata={"identifier": clean_identifier, "request_id": pending_req.public_id, "retry": True},
                )
                db.commit()
            except Exception as e:
                logger.debug("Failed to record login denied audit log: %s", e)
                db.rollback()

            raise HTTPException(status_code=403, detail=error_detail)

        # 2. Check if user's latest access request was REJECTED
        latest_req = (
            db.query(AccessRequest)
            .filter(AccessRequest.user_id == user.id)
            .order_by(AccessRequest.created_at.desc())
            .first()
        )
        if latest_req and latest_req.status == "REJECTED":
            reject_msg = "Access not approved. Your access request was not approved by an administrator. Please contact an administrator if you require access."
            try:
                log_action(
                    db,
                    action="LOGIN_DENIED",
                    resource_type="AUTH",
                    user_id=user.id,
                    user_public_id=user.public_id,
                    username=user.username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="DENIED",
                    detail=reject_msg,
                    metadata={"identifier": clean_identifier, "request_id": latest_req.public_id, "status": "REJECTED"},
                )
                db.commit()
            except Exception as e:
                logger.debug("Failed to record login denied audit log: %s", e)
                db.rollback()

            raise HTTPException(status_code=403, detail=reject_msg)

        # 3. Genuinely new access request (e.g. deactivated account without pending request)
        is_new_user = not getattr(user, "is_approved", True)
        req_type = "NEW_USER" if is_new_user else "REACTIVATION"
        pending_req = AccessRequest(
            user_id=user.id,
            user_email=user.email or "",
            user_display_name=user.display_name or user.username,
            status="PENDING",
            request_type=req_type,
            device_id=device_id.strip()[:100] if device_id and device_id.strip() else None,
            device_hash=device_hash,
            device_info=parse_device_info(user_agent),
            ip_address=ip_address,
            user_agent=user_agent,
            reason="Automatic access request on sign-in attempt",
        )
        db.add(pending_req)
        db.commit()
        db.refresh(pending_req)

        # Dispatch email notification for genuinely new request
        try:
            ok, err = dispatch_admin_notification(
                applicant_name=user.display_name or user.username,
                applicant_email=user.email or clean_identifier,
                request_type=req_type,
                created_at=pending_req.created_at,
                device_info=pending_req.device_info,
                reason=pending_req.reason,
            )
            pending_req.notification_sent = ok
            pending_req.notification_error = err
            db.commit()
        except Exception as e:
            logger.warning("Exception dispatching admin notification email: %s", e)
            pending_req.notification_sent = False
            pending_req.notification_error = str(e)
            db.commit()

        error_msg = (
            "Approval pending by Admin. Your account is pending administrator approval. You will be able to sign in once access is approved."
            if is_new_user
            else "Approval pending by Admin. Your account is currently deactivated. Your access request has been submitted for administrator review. You will be able to sign in once access is approved."
        )

        try:
            log_action(
                db,
                action="LOGIN_DENIED",
                resource_type="AUTH",
                user_id=user.id,
                user_public_id=user.public_id,
                username=user.username,
                ip_address=ip_address,
                user_agent=user_agent,
                status="DENIED",
                detail=error_msg,
                metadata={"identifier": clean_identifier, "request_id": pending_req.public_id},
            )
            db.commit()
        except Exception as e:
            logger.debug("Failed to record login denied audit log: %s", e)
            db.rollback()

        raise HTTPException(
            status_code=403,
            detail=error_msg,
        )

    # Successful login: track login count & create active session
    user.login_count = (getattr(user, "login_count", 0) or 0) + 1
    idle_timeout_seconds, max_lifetime_seconds = parse_timeout_settings(session_timeout, max_lifetime)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(seconds=max_lifetime_seconds)
    device_info = parse_device_info(user_agent)

    # For admin users: if a separate persistent Admin Console password has been configured,
    # the console starts strictly locked until unlocked via the separate console password.
    # If not yet configured (first-time setup or legacy test fixture), seed initial elevation.
    admin_unlocked = None
    if getattr(user, "role", "user") == "admin":
        if not getattr(user, "admin_console_password_hash", None):
            admin_unlocked = now_utc + timedelta(minutes=15)

    session = UserSession(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info,
        is_revoked=False,
        admin_unlocked_until=admin_unlocked,
        idle_timeout_seconds=idle_timeout_seconds,
        max_lifetime_seconds=max_lifetime_seconds,
        created_at=now_utc,
        last_active_at=now_utc,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)


    token = create_access_token(
        {
            "sub": user.public_id,
            "email": user.email,
            "sid": session.public_id,
        },
        ttl_seconds=max_lifetime_seconds,
    )

    try:
        log_action(
            db,
            action="LOGIN",
            resource_type="AUTH",
            resource_id=session.public_id,
            user_id=user.id,
            user_public_id=user.public_id,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail="User logged in successfully",
        )
        db.commit()
    except Exception as e:
        logger.debug("Failed to record login audit log: %s", e)
        db.rollback()

    logger.info("User logged in: %s (session: %s)", user.email or user.username, session.public_id)
    return {
        "token": token,
        "user": user_to_dict(user),
    }


def get_user_from_token(
    db: Session,
    token: str,
    request: Optional[Any] = None,
    is_background_request: bool = False,
) -> User:
    """Retrieve User model instance from authorization token and validate session."""
    payload = verify_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired authorization token")

    user = db.query(User).filter(User.public_id == payload["sub"]).first()
    if not user or not user.is_active or not getattr(user, "is_approved", True):
        raise HTTPException(status_code=401, detail="User account not found, inactive, or pending approval")

    sid = payload.get("sid")
    if not sid:
        # Admin accounts strictly require an active session and cannot use legacy tokens
        if getattr(user, "role", "user") == "admin":
            raise HTTPException(
                status_code=401,
                detail="Session identifier missing from token. Admin access requires an active session.",
            )

        # Deliberate legacy token policy:
        # If the user has any persisted session records in user_sessions, legacy tokens
        # without sid are strictly rejected to prevent session validation bypass.
        user_has_sessions = db.query(UserSession.id).filter(UserSession.user_id == user.id).first()
        if user_has_sessions:
            raise HTTPException(
                status_code=401,
                detail="Session identifier missing from token. Please sign in again.",
            )
        # If the user has no recorded sessions (e.g. synthetic test users in legacy test suites),
        # allow through only if token_version is default 1
        if getattr(user, "token_version", 1) > 1:
            raise HTTPException(
                status_code=401,
                detail="Session has been revoked. Please sign in again.",
            )
        return user

    # Session exists in token - validate against user_sessions table
    session = db.query(UserSession).filter(
        UserSession.public_id == sid,
        UserSession.user_id == user.id,
    ).first()

    if not session or session.is_revoked:
        raise HTTPException(
            status_code=401,
            detail="Session has been revoked or expired. Please sign in again.",
        )

    now_utc = datetime.now(timezone.utc)

    # 1. Absolute Maximum Session Lifetime check (enforced using trusted server-side creation time)
    created_at = session.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    max_life_sec = getattr(session, "max_lifetime_seconds", None) or DEFAULT_MAX_LIFETIME_SECONDS
    abs_expires_at = created_at + timedelta(seconds=max_life_sec)

    sess_exp = session.expires_at
    if sess_exp.tzinfo is None:
        sess_exp = sess_exp.replace(tzinfo=timezone.utc)

    effective_max_exp = min(abs_expires_at, sess_exp)
    if now_utc >= effective_max_exp:
        session.is_revoked = True
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=401,
            detail="Session has expired. Maximum session lifetime reached.",
        )

    # 2. Inactivity (Idle) Timeout check (enforced using server-side last_active_at)
    last_active = session.last_active_at
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    idle_sec = getattr(session, "idle_timeout_seconds", None) or DEFAULT_IDLE_TIMEOUT_SECONDS
    if now_utc >= last_active + timedelta(seconds=idle_sec):
        session.is_revoked = True
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=401,
            detail="Session has expired due to inactivity. Please sign in again.",
        )

    # 3. Activity tracking: update only for meaningful user activity (not background requests)
    if not is_background_request:
        if (now_utc - last_active).total_seconds() >= 10:
            session.last_active_at = now_utc
            try:
                db.commit()
            except Exception:
                db.rollback()

    user._current_session = session
    if request:
        try:
            request.state.current_session = session
            request.state.current_user = user
        except Exception:
            pass

    return user



def logout_user_session(
    db: Session,
    user: User,
    token: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Revoke only the current active session for the authenticated user."""
    sid = None
    if token:
        payload = verify_access_token(token)
        if payload:
            sid = payload.get("sid")

    if sid:
        session = db.query(UserSession).filter(
            UserSession.public_id == sid,
            UserSession.user_id == user.id,
        ).first()

        if session:
            session.is_revoked = True
            session.admin_unlocked_until = None
            db.commit()

        try:
            log_action(
                db,
                action="LOGOUT",
                resource_type="AUTH",
                resource_id=sid,
                user_id=user.id,
                user_public_id=user.public_id,
                username=user.username,
                ip_address=ip_address,
                user_agent=user_agent,
                status="SUCCESS",
                detail="User session logged out successfully",
            )
            db.commit()
        except Exception as e:
            logger.debug("Logout audit log note: %s", e)
            db.rollback()
    else:
        try:
            log_action(
                db,
                action="LOGOUT",
                resource_type="AUTH",
                user_id=user.id,
                user_public_id=user.public_id,
                username=user.username,
                ip_address=ip_address,
                user_agent=user_agent,
                status="SUCCESS",
                detail="User logged out",
            )
            db.commit()
        except Exception as e:
            logger.debug("Logout audit log note: %s", e)
            db.rollback()

    logger.info("User logged out: %s (session: %s)", user.username, sid or "legacy")
    return {"message": "Logged out successfully"}


def logout_all_user_sessions(
    db: Session,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Revoke all active sessions for a user across all devices."""
    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.is_revoked == False,
    ).update({"is_revoked": True, "admin_unlocked_until": None})

    user.token_version = (user.token_version or 1) + 1
    db.commit()

    try:
        log_action(
            db,
            action="LOGOUT_ALL",
            resource_type="AUTH",
            user_id=user.id,
            user_public_id=user.public_id,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail="All user sessions revoked successfully",
        )
        db.commit()
    except Exception as e:
        logger.debug("Logout all audit log note: %s", e)
        db.rollback()

    logger.info("All sessions revoked for user: %s", user.username)
    return {"message": "All sessions logged out successfully"}


def update_session_preferences(
    db: Session,
    user: User,
    token: Optional[str] = None,
    session_timeout: Optional[str] = None,
    max_session_lifetime: Optional[str] = None,
) -> Dict[str, Any]:
    """Update timeout preferences for the user's active session.

    Security Policies:
    - Rejects missing, revoked, or expired sessions.
    - Changing preferences must not silently grant a longer lifetime to an already-expired session.
    - Validates values against strictly allowed intervals.
    - Ensures token expiry never extends beyond max session lifetime.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    payload = verify_access_token(token)
    if not payload or not payload.get("sid"):
        raise HTTPException(status_code=401, detail="Active session required to update session settings")

    sid = payload["sid"]
    session = (
        db.query(UserSession)
        .filter(UserSession.public_id == sid, UserSession.user_id == user.id)
        .first()
    )

    if not session or session.is_revoked:
        raise HTTPException(status_code=401, detail="Session has been revoked or expired")

    now_utc = datetime.now(timezone.utc)
    created_at = session.created_at.replace(tzinfo=timezone.utc) if session.created_at.tzinfo is None else session.created_at
    last_active = session.last_active_at.replace(tzinfo=timezone.utc) if session.last_active_at.tzinfo is None else session.last_active_at

    current_max = getattr(session, "max_lifetime_seconds", None) or DEFAULT_MAX_LIFETIME_SECONDS
    if now_utc >= created_at + timedelta(seconds=current_max):
        session.is_revoked = True
        db.commit()
        raise HTTPException(status_code=401, detail="Session has expired. Maximum session lifetime reached.")

    current_idle = getattr(session, "idle_timeout_seconds", None) or DEFAULT_IDLE_TIMEOUT_SECONDS
    if now_utc >= last_active + timedelta(seconds=current_idle):
        session.is_revoked = True
        db.commit()
        raise HTTPException(status_code=401, detail="Session has expired due to inactivity")

    updated = False
    if session_timeout:
        clean_timeout = str(session_timeout).strip().lower()
        if clean_timeout not in IDLE_TIMEOUT_MAP:
            raise HTTPException(status_code=400, detail=f"Invalid session_timeout: {session_timeout}")
        session.idle_timeout_seconds = IDLE_TIMEOUT_MAP[clean_timeout]
        updated = True

    if max_session_lifetime:
        clean_max = str(max_session_lifetime).strip().lower()
        if clean_max not in MAX_LIFETIME_MAP:
            raise HTTPException(status_code=400, detail=f"Invalid max_session_lifetime: {max_session_lifetime}")
        new_max_sec = MAX_LIFETIME_MAP[clean_max]
        new_abs_exp = created_at + timedelta(seconds=new_max_sec)
        # Cannot extend already-expired lifetime; if new max lifetime is already in the past, revoke immediately
        if new_abs_exp <= now_utc:
            session.is_revoked = True
            db.commit()
            raise HTTPException(status_code=401, detail="Session has expired. Maximum session lifetime reached.")
        session.max_lifetime_seconds = new_max_sec
        session.expires_at = new_abs_exp
        updated = True

    if updated:
        db.commit()
        db.refresh(session)

    return {
        "status": "success",
        "idle_timeout_seconds": session.idle_timeout_seconds,
        "max_lifetime_seconds": session.max_lifetime_seconds,
    }


def update_user_profile(
    db: Session, user: User, full_name: Optional[str] = None, email: Optional[str] = None
) -> Dict[str, Any]:
    """Update user's display name and/or email address."""
    updated = False

    if full_name is not None and full_name.strip():
        user.display_name = full_name.strip()
        updated = True

    if email is not None and email.strip():
        clean_email = email.strip().lower()
        if not is_valid_email(clean_email):
            raise HTTPException(status_code=400, detail="Invalid email format")

        if clean_email != (user.email or "").lower():
            existing = db.query(User).filter(User.email.ilike(clean_email), User.id != user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Another account is already using this email address")
            user.email = clean_email
            updated = True

    if updated:
        db.commit()
        db.refresh(user)

    return {"message": "Profile updated successfully", "user": user_to_dict(user)}


def change_user_password(
    db: Session, user: User, old_password: str, new_password: str
) -> Dict[str, Any]:
    """Verify old password and change to new password."""
    if user.hashed_password and not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long")

    user.hashed_password = hash_password(new_password)
    db.commit()
    return {"message": "Password changed successfully"}


def update_user_avatar(db: Session, user: User, avatar_url: str) -> Dict[str, Any]:
    """Update user profile avatar image URL or preset color indicator."""
    user.avatar_url = (avatar_url or "").strip()
    db.commit()
    db.refresh(user)
    return {"message": "Avatar updated successfully", "user": user_to_dict(user)}


def delete_user_account(db: Session, user: User) -> Dict[str, Any]:
    """Permanently delete user account and associated session."""
    # Safeguard: Prevent deleting the sole active administrator account
    if getattr(user, "role", "user") == "admin":
        active_admins = (
            db.query(User)
            .filter(User.role == "admin", User.is_active == True)
            .count()
        )
        if active_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the sole active administrator account",
            )

    user_id = user.id
    display_name = user.display_name
    db.delete(user)
    db.commit()
    logger.info("Deleted user account #%s (%s)", user_id, display_name)
    return {"message": "Account deleted successfully"}


def submit_access_request(
    db: Session,
    email: str,
    password: str,
    reason: Optional[str] = None,
    device_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit or retrieve an access / reactivation request for a deactivated account."""
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email.ilike(clean_email)).first()
    if not user or not user.hashed_password:
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.is_active:
        return {
            "status": "already_active",
            "message": "Account is already active. Please sign in normally.",
            "is_active": True,
        }

    device_hash = hashlib.sha256(device_id.strip().encode("utf-8")).hexdigest() if device_id and device_id.strip() else None

    # Check for existing pending request to avoid duplicates
    pending = (
        db.query(AccessRequest)
        .filter(AccessRequest.user_id == user.id, AccessRequest.status == "PENDING")
        .order_by(AccessRequest.created_at.desc())
        .first()
    )
    if pending:
        if reason and reason.strip():
            pending.reason = reason.strip()
        if device_id and device_id.strip():
            pending.device_id = device_id.strip()[:100]
            pending.device_hash = device_hash
        db.commit()
        db.refresh(pending)
        return {
            "status": "pending",
            "request_id": pending.public_id,
            "message": "Approval pending by Admin. Your access request is currently pending administrator review.",
            "requested_at": pending.created_at.isoformat(),
            "device_info": pending.device_info,
        }

    is_new = not getattr(user, "is_approved", True)
    req_type = "NEW_USER" if is_new else "REACTIVATION"
    default_reason = "New user registration approval request" if is_new else "Reactivation requested"

    new_req = AccessRequest(
        user_id=user.id,
        user_email=user.email or "",
        user_display_name=user.display_name or user.username,
        status="PENDING",
        request_type=req_type,
        reason=reason.strip() if reason and reason.strip() else default_reason,
        device_id=device_id.strip()[:100] if device_id and device_id.strip() else None,
        device_hash=device_hash,
        device_info=parse_device_info(user_agent),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)

    # Dispatch email notification for genuinely new request
    try:
        ok, err = dispatch_admin_notification(
            applicant_name=user.display_name or user.username,
            applicant_email=user.email or clean_email,
            request_type=req_type,
            created_at=new_req.created_at,
            device_info=new_req.device_info,
            reason=new_req.reason,
        )
        new_req.notification_sent = ok
        new_req.notification_error = err
        db.commit()
    except Exception as e:
        logger.warning("Exception dispatching admin notification email: %s", e)
        new_req.notification_sent = False
        new_req.notification_error = str(e)
        db.commit()

    try:
        log_action(
            db,
            action="ACCESS_REQUEST_SUBMIT",
            resource_type="ACCESS_REQUEST",
            resource_id=new_req.public_id,
            user_id=user.id,
            user_public_id=user.public_id,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail=f"User submitted account {req_type.lower()} request",
            metadata={"email": clean_email, "device_info": new_req.device_info, "request_type": req_type},
        )
        db.commit()
    except Exception as e:
        logger.debug("Failed to record access request audit log: %s", e)
        db.rollback()
        raise

    return {
        "status": "pending",
        "request_id": new_req.public_id,
        "message": "Approval pending by Admin. Your access request has been submitted for administrator review. You will be able to sign in once access is approved.",
        "requested_at": new_req.created_at.isoformat(),
        "device_info": new_req.device_info,
    }


