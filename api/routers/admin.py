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
from api.core.security import get_client_ip, require_admin
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
)

logger = logging.getLogger("ayur_intel.routers.admin")

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class UpdateUserStatusRequest(BaseModel):
    is_active: bool = Field(..., description="Active status of the user account")


@router.get("/metrics", summary="System security and presence metrics (Admin only)")
def get_metrics(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
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
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Retrieve paginated list of users with active session counts. Safe fields only."""
    return get_admin_users(db=db, query=query, limit=limit, offset=offset, status=status)


@router.get("/users/{user_id}", summary="Get user details and sessions (Admin only)")
def get_user_detail(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Retrieve safe user details and recent session history."""
    return get_admin_user_detail(db=db, user_id=user_id)


@router.put("/users/{user_id}/status", summary="Activate or deactivate user account (Admin only)")
def set_user_status(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    req: UpdateUserStatusRequest = ...,
    request: Request = ...,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
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
    admin: User = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Retrieve complete session history for a specific user."""
    return get_user_sessions(db=db, user_id=user_id)


@router.post("/users/{user_id}/sessions/{session_id}/revoke", summary="Revoke individual user session (Admin only)")
def revoke_session(
    user_id: str = Path(..., min_length=1, max_length=64, description="User public ID"),
    session_id: str = Path(..., min_length=1, max_length=64, description="Session public ID"),
    request: Request = ...,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
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
    admin: User = Depends(require_admin),
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


@router.get("/audit-logs", summary="List system-wide audit logs (Admin only)")
def list_audit_logs(
    user_query: Optional[str] = Query(None, max_length=100, description="Filter by username or public user ID"),
    action: Optional[str] = Query(None, max_length=50, description="Filter by audit action"),
    resource_type: Optional[str] = Query(None, max_length=50, description="Filter by resource type"),
    status: Optional[str] = Query(None, max_length=20, description="Filter by operation status"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
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
