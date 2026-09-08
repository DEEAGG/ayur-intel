"""AYUR-INTEL — Authentication API Router.

Endpoints:
- POST /api/auth/signup
- POST /api/auth/login
- GET /api/auth/me
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.services.auth_service import (
    signup_user,
    login_user,
    get_user_from_token,
    user_to_dict,
    update_user_profile,
    change_user_password,
    update_user_avatar,
    delete_user_account,
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


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, description="Updated Full Name")
    email: Optional[str] = Field(None, description="Updated Email Address")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Current Password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New Password (min 8 characters)")


class UpdateAvatarRequest(BaseModel):
    avatar_url: str = Field(..., description="Avatar Image URL or Base64 or Preset Color")


def _get_authenticated_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    authToken = None
    if authorization and authorization.startswith("Bearer "):
        authToken = authorization[7:].strip()
    elif token:
        authToken = token.strip()

    if not authToken:
        raise HTTPException(status_code=401, detail="Authentication token required")

    return get_user_from_token(db, authToken)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", summary="Register new user account")
def signup(req: SignUpRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Register a new user with full name, email, and password."""
    return signup_user(
        db=db,
        full_name=req.full_name,
        email=req.email,
        password=req.password,
    )


@router.post("/login", summary="Sign in existing user")
def login(req: LoginRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Authenticate user credentials and return access token."""
    return login_user(
        db=db,
        email_or_username=req.email,
        password=req.password,
    )


@router.get("/me", summary="Get current authenticated user profile")
def get_me(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return currently authenticated user profile."""
    authToken = None
    if authorization and authorization.startswith("Bearer "):
        authToken = authorization[7:].strip()
    elif token:
        authToken = token.strip()

    if not authToken:
        # Fallback to demo user if no token provided
        from api.core.security import get_current_user
        user = get_current_user(db)
        return {"user": user_to_dict(user), "authenticated": True, "mode": "demo"}

    user = get_user_from_token(db, authToken)
    return {"user": user_to_dict(user), "authenticated": True, "mode": "user"}


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

