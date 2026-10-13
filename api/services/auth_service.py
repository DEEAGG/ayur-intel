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
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from api.models.models import User
from api.core.config import settings

logger = logging.getLogger("ayur_intel.auth")

DEFAULT_TOKEN_EXPIRE_SECONDS = 86400      # 24 hours default
MIN_TOKEN_EXPIRE_SECONDS = 60              # 1 minute minimum
MAX_TOKEN_EXPIRE_SECONDS = 30 * 24 * 3600  # 30 days maximum


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
        "avatar_url": getattr(user, "avatar_url", None) or "",
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }


def signup_user(db: Session, full_name: str, email: str, password: str) -> Dict[str, Any]:
    """Register a new user account."""
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
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.public_id, "email": user.email})
    logger.info("User registered successfully: %s (%s)", user.display_name, user.email)
    return {
        "token": token,
        "user": user_to_dict(user),
    }


def login_user(db: Session, email_or_username: str, password: str) -> Dict[str, Any]:
    """Authenticate an existing user with email/username and password."""
    clean_identifier = email_or_username.strip().lower()
    
    user = (
        db.query(User)
        .filter(
            (User.email.ilike(clean_identifier)) | (User.username.ilike(clean_identifier))
        )
        .first()
    )

    # If account does not exist, has no password set, or is inactive:
    # run dummy password hash verification to minimize timing discrepancy, then fail.
    # An account without a configured password must NEVER become claimable through login.
    if not user or not user.hashed_password or not user.is_active:
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": user.public_id, "email": user.email})
    logger.info("User logged in: %s", user.email or user.username)
    return {
        "token": token,
        "user": user_to_dict(user),
    }


def get_user_from_token(db: Session, token: str) -> User:
    """Retrieve User model instance from authorization token."""
    payload = verify_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired authorization token")

    user = db.query(User).filter(User.public_id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account not found or inactive")

    return user


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
    user_id = user.id
    display_name = user.display_name
    db.delete(user)
    db.commit()
    logger.info("Deleted user account #%s (%s)", user_id, display_name)
    return {"message": "Account deleted successfully"}

