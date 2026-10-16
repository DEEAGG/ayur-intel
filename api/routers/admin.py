"""AYUR-INTEL — Admin Console API Router.

Protected endpoints for administrative management:
- GET  /api/admin/users
- GET  /api/admin/users/{user_id}
- PUT  /api/admin/users/{user_id}/status
- GET  /api/admin/users/{user_id}/sessions
- POST /api/admin/users/{user_id}/sessions/{session_id}/revoke
- POST /api/admin/users/{user_id}/logout-all
- GET  /api/admin/audit-logs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.security import get_client_ip, require_admin, require_admin_unlocked
from api.models.models import User
from api.services.admin_service import (
    get_admin_audit_logs,
    get_admin_metrics,
    get_admin_user_detail,
    get_admin_users,
    get_user_sessions,
    revoke_all_user_sessions_admin,
    revoke_user_session_admin,
    update_user_status,
    get_admin_access_requests,
    get_admin_access_request_detail,
    approve_access_request_admin,
    reject_access_request_admin,
    unlock_admin_console,
    setup_admin_console_password,
    change_admin_console_password,
    recover_admin_console_password,
    lock_admin_console,
    get_admin_unlock_status,
    get_all_active_sessions_admin,
)

logger = logging.getLogger("ayur_intel.routers.admin")

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class UpdateUserStatusRequest(BaseModel):
    is_active: bool = Field(..., description="Active status of the user account")


class AdminUnlockRequest(BaseModel):
    password: str = Field(..., min_length=1, description="Admin Console password")


class SetupConsolePasswordRequest(BaseModel):
    account_password: str = Field(..., min_length=1, description="Current administrator account password")
    console_password: str = Field(..., min_length=12, description="New Admin Console password (min 12 chars)")
    confirm_password: str = Field(..., min_length=12, description="Confirm Admin Console password")


class ChangeConsolePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="Current Admin Console password")
    new_password: str = Field(..., min_length=12, description="New Admin Console password (min 12 chars)")
    confirm_password: str = Field(..., min_length=12, description="Confirm new Admin Console password")


class RecoverConsolePasswordRequest(BaseModel):
    account_password: str = Field(..., min_length=1, description="Current administrator account password")
    new_console_password: str = Field(..., min_length=12, description="New Admin Console password (min 12 chars)")
    confirm_console_password: str = Field(..., min_length=12, description="Confirm new Admin Console password")


class AccessRequestDecision(BaseModel):
    review_notes: Optional[str] = Field(None, max_length=500, description="Optional review decision notes")


# ---------------------------------------------------------------------------
# Admin Console Elevated Unlock Endpoints
# ---------------------------------------------------------------------------

@router.post("/unlock", summary="Re-authenticate administrator and unlock console")
def unlock_console(
    req: AdminUnlockRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Verify administrator password and issue elevated console unlock token."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    session = getattr(admin, "_current_session", None)
    if not session and hasattr(request, "state") and hasattr(request.state, "current_session"):
        session = request.state.current_session

    return unlock_admin_console(
        db=db,
        admin=admin,
        session=session,
        password=req.password,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post("/setup-password", summary="First-time setup of persistent Admin Console password")
def setup_console_password(
    req: SetupConsolePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Verify administrator account password and initialize isolated Admin Console password."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    session = getattr(admin, "_current_session", None)
    if not session and hasattr(request, "state") and hasattr(request.state, "current_session"):
        session = request.state.current_session

    return setup_admin_console_password(
        db=db,
        admin=admin,
        session=session,
        account_password=req.account_password,
        console_password=req.console_password,
        confirm_password=req.confirm_password,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post("/change-console-password", summary="Change persistent Admin Console password")
def change_console_password(
    req: ChangeConsolePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Change the Admin Console password requiring verification of current console password."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    session = getattr(admin, "_current_session", None)
    if not session and hasattr(request, "state") and hasattr(request.state, "current_session"):
        session = request.state.current_session

    return change_admin_console_password(
        db=db,
        admin=admin,
        session=session,
        current_password=req.current_password,
        new_password=req.new_password,
        confirm_password=req.confirm_password,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post("/recover-console-password", summary="Recover Admin Console password with account credentials")
def recover_console_password(
    req: RecoverConsolePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Reset the Admin Console password using primary account credentials."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    session = getattr(admin, "_current_session", None)
    if not session and hasattr(request, "state") and hasattr(request.state, "current_session"):
        session = request.state.current_session

    return recover_admin_console_password(
        db=db,
        admin=admin,
        session=session,
        account_password=req.account_password,
        new_console_password=req.new_console_password,
        confirm_console_password=req.confirm_console_password,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post("/lock", summary="Explicitly lock the administrator console")
def lock_console(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Explicitly terminate elevated unlock state for the current administrative session."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    session = getattr(admin, "_current_session", None)
    if not session and hasattr(request, "state") and hasattr(request.state, "current_session"):
        session = request.state.current_session

    return lock_admin_console(
        db=db,
        admin=admin,
        session=session,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.get("/unlock-status", summary="Check administrator console unlock state")
def unlock_status(
    request: Request,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Retrieve current unlock status and expiry for the active administrative session."""
    session = getattr(admin, "_current_session", None)
    if not session and hasattr(request, "state") and hasattr(request.state, "current_session"):
        session = request.state.current_session

    return get_admin_unlock_status(session=session, admin=admin)


@router.get("/all-sessions", summary="List all active sessions system-wide (Admin only)")
def list_all_sessions(
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Retrieve all active concurrent user sessions across the platform."""
    return get_all_active_sessions_admin(db=db, limit=limit, offset=offset)


@router.get("/metrics", summary="System security and presence metrics (Admin only)")
def get_metrics(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Retrieve system-wide KPIs: user presence, active accounts, and session counts."""
    return get_admin_metrics(db=db)


@router.get("/users", summary="List users (Admin only)")
def list_users(
    query: Optional[str] = Query(None, max_length=100, description="Search term for username, email, display name"),
    status: Optional[str] = Query(None, max_length=20, description="Filter by status: all, active, inactive"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Retrieve paginated list of users with active session counts. Safe fields only."""
    return get_admin_users(db=db, query=query, limit=limit, offset=offset, status=status)


@router.get("/users/{user_id}", summary="Get user details and sessions (Admin only)")
def get_user_detail(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Retrieve safe user details and recent session history."""
    return get_admin_user_detail(db=db, user_id=user_id)


@router.put("/users/{user_id}/status", summary="Activate or deactivate user account (Admin only)")
def set_user_status(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    req: UpdateUserStatusRequest = ...,
    request: Request = ...,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Activate or deactivate a user account with safeguards against self and sole-admin lockouts."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    return update_user_status(
        db=db,
        admin=admin,
        user_id=user_id,
        is_active=req.is_active,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.get("/users/{user_id}/sessions", summary="List user sessions (Admin only)")
def list_user_sessions(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> List[Dict[str, Any]]:
    """Retrieve complete session history for a specific user."""
    return get_user_sessions(db=db, user_id=user_id)


@router.post("/users/{user_id}/sessions/{session_id}/revoke", summary="Revoke individual user session (Admin only)")
def revoke_session(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    session_id: str = Path(..., min_length=1, max_length=64, description="Session public ID"),
    request: Request = ...,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Remotely terminate an individual user session."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    return revoke_user_session_admin(
        db=db,
        admin=admin,
        user_id=user_id,
        session_id=session_id,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post("/users/{user_id}/logout-all", summary="Revoke all sessions for user (Admin only)")
def logout_all_sessions(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    request: Request = ...,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Revoke all active sessions for a user across all devices."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    return revoke_all_user_sessions_admin(
        db=db,
        admin=admin,
        user_id=user_id,
        ip_address=client_ip,
        user_agent=user_agent,
    )


# ---------------------------------------------------------------------------
# Access Requests Endpoints
# ---------------------------------------------------------------------------

@router.get("/requests", summary="List access / reactivation requests (Admin only)")
def list_access_requests(
    status: Optional[str] = Query(None, max_length=20, description="Filter by status: all, pending, approved, rejected"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Retrieve paginated user reactivation requests with device contexts."""
    return get_admin_access_requests(db=db, status=status, limit=limit, offset=offset)


@router.get("/requests/{request_id}", summary="Get access request details (Admin only)")
def get_request_detail(
    request_id: str = Path(..., min_length=1, max_length=64, description="Access request public ID"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Retrieve full request context including device hash and review notes."""
    return get_admin_access_request_detail(db=db, request_id=request_id)


@router.post("/requests/{request_id}/approve", summary="Approve reactivation request (Admin only)")
def approve_request(
    request_id: str = Path(..., min_length=1, max_length=64, description="Access request public ID"),
    decision: Optional[AccessRequestDecision] = None,
    request: Request = ...,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Approve access request, reactivate account, bind approved device, and record decision."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    notes = decision.review_notes if decision else None

    return approve_access_request_admin(
        db=db,
        admin=admin,
        request_id=request_id,
        review_notes=notes,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post("/requests/{request_id}/reject", summary="Reject reactivation request (Admin only)")
def reject_request(
    request_id: str = Path(..., min_length=1, max_length=64, description="Access request public ID"),
    decision: Optional[AccessRequestDecision] = None,
    request: Request = ...,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Reject access request and retain account deactivation."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    notes = decision.review_notes if decision else None

    return reject_access_request_admin(
        db=db,
        admin=admin,
        request_id=request_id,
        review_notes=notes,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.get("/audit-logs", summary="List system-wide audit logs (Admin only)")
def list_audit_logs(
    user_query: Optional[str] = Query(None, max_length=100, description="Filter by username or public user ID"),
    action: Optional[str] = Query(None, max_length=50, description="Filter by audit action"),
    resource_type: Optional[str] = Query(None, max_length=50, description="Filter by resource type"),
    status: Optional[str] = Query(None, max_length=20, description="Filter by operation status"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_unlocked),
) -> Dict[str, Any]:
    """Retrieve paginated system audit logs with administrative filtering."""
    return get_admin_audit_logs(
        db=db,
        user_query=user_query,
        action=action,
        resource_type=resource_type,
        status=status,
        limit=limit,
        offset=offset,
    )

