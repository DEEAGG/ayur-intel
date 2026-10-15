"""AYUR-INTEL — Authentication API Router.

Endpoints:
- POST /api/auth/signup
- POST /api/auth/login
- GET /api/auth/me
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.security import (
    check_auth_rate_limit,
    get_authenticated_user as _get_authenticated_user,
    get_client_ip,
)
from api.services.auth_service import (
    signup_user,
    login_user,
    get_user_from_token,
    verify_access_token,
    user_to_dict,
    update_user_profile,
    change_user_password,
    update_user_avatar,
    delete_user_account,
    logout_user_session,
    logout_all_user_sessions,
    update_session_preferences,
)

logger = logging.getLogger("ayur_intel.routers.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class SignUpRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150, description="Full Name")
    email: str = Field(..., description="Valid Email Address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 characters)")


class LoginRequest(BaseModel):
    email: str = Field(..., description="Email Address or Username")
    password: str = Field(..., min_length=1, description="Password")
    session_timeout: Optional[str] = Field(None, description="Inactivity timeout: 5m, 15m, 30m, 1h, 2h, 4h")
    max_lifetime: Optional[str] = Field(None, description="Max session lifetime: 8h, 12h, 24h")


class SessionSettingsRequest(BaseModel):
    session_timeout: Optional[str] = Field(None, description="Inactivity timeout: 5m, 15m, 30m, 1h, 2h, 4h")
    max_session_lifetime: Optional[str] = Field(None, description="Max session lifetime: 8h, 12h, 24h")


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, description="Updated Full Name")
    email: Optional[str] = Field(None, description="Updated Email Address")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Current Password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New Password (min 8 characters)")


class UpdateAvatarRequest(BaseModel):
    avatar_url: str = Field(..., description="Avatar Image URL or Base64 or Preset Color")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", summary="Register new user account")
def signup(
    req: SignUpRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new user with full name, email, and password."""
    client_ip = get_client_ip(request)
    check_auth_rate_limit(ip=client_ip, action="signup")
    user_agent = request.headers.get("User-Agent")

    return signup_user(
        db=db,
        full_name=req.full_name,
        email=req.email,
        password=req.password,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post("/login", summary="Sign in existing user")
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Authenticate user credentials and return access token."""
    client_ip = get_client_ip(request)
    check_auth_rate_limit(ip=client_ip, identifier=req.email, action="login")
    user_agent = request.headers.get("User-Agent")

    return login_user(
        db=db,
        email_or_username=req.email,
        password=req.password,
        ip_address=client_ip,
        user_agent=user_agent,
        session_timeout=req.session_timeout,
        max_lifetime=req.max_lifetime,
    )


@router.post("/logout", summary="Log out current user session")
def logout(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    user: Any = Depends(_get_authenticated_user),
) -> Dict[str, Any]:
    """Revoke only the current active session for the authenticated user."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    return logout_user_session(
        db=db,
        user=user,
        token=token,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.get("/me", summary="Get current authenticated user profile")
def get_me(
    authorization: Optional[str] = Header(None),
    user: Any = Depends(_get_authenticated_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return currently authenticated user profile and active session parameters."""
    sess_info = None
    if authorization and authorization.startswith("Bearer "):
        tok = authorization[7:].strip()
        payload = verify_access_token(tok)
        if payload and payload.get("sid"):
            from api.models.security import UserSession
            sess = (
                db.query(UserSession)
                .filter(UserSession.public_id == payload["sid"], UserSession.user_id == user.id)
                .first()
            )
            if sess:
                sess_info = {
                    "idle_timeout_seconds": getattr(sess, "idle_timeout_seconds", 1800) or 1800,
                    "max_lifetime_seconds": getattr(sess, "max_lifetime_seconds", 43200) or 43200,
                    "created_at": sess.created_at.isoformat() if sess.created_at else None,
                }

    return {
        "user": user_to_dict(user),
        "authenticated": True,
        "mode": "user",
        "session": sess_info,
    }


@router.put("/session/settings", summary="Update session timeout preferences for active session")
def set_session_settings(
    req: SessionSettingsRequest,
    authorization: Optional[str] = Header(None),
    user: Any = Depends(_get_authenticated_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update inactivity timeout and max session lifetime for the active session."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    return update_session_preferences(
        db=db,
        user=user,
        token=token,
        session_timeout=req.session_timeout,
        max_session_lifetime=req.max_session_lifetime,
    )


@router.put("/profile", summary="Update user display name and email")
def update_profile(
    req: UpdateProfileRequest,
    user: Any = Depends(_get_authenticated_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update user profile info."""
    return update_user_profile(
        db=db,
        user=user,
        full_name=req.full_name,
        email=req.email,
    )


@router.put("/password", summary="Change user password")
def change_password(
    req: ChangePasswordRequest,
    user: Any = Depends(_get_authenticated_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Change user account password."""
    return change_user_password(
        db=db,
        user=user,
        old_password=req.old_password,
        new_password=req.new_password,
    )


@router.put("/avatar", summary="Update user avatar image or preset")
def update_avatar(
    req: UpdateAvatarRequest,
    user: Any = Depends(_get_authenticated_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update user avatar."""
    return update_user_avatar(
        db=db,
        user=user,
        avatar_url=req.avatar_url,
    )


@router.delete("/account", summary="Delete user account")
def delete_account(
    user: Any = Depends(_get_authenticated_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete current user account."""
    return delete_user_account(db=db, user=user)

