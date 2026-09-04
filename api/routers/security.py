"""AYUR-INTEL — Security API Routes (Phase 17).

Audit log viewing and security status endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User
from api.services.audit_service import get_audit_logs
from api.services.product_case_service import get_or_create_demo_user
from api.core.config import settings

logger = logging.getLogger("ayur_intel.routers.security")

router = APIRouter(prefix="/api/security", tags=["Security"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


@router.get("/audit-logs")
def list_audit_logs(
    case_id: str = Query(None, alias="case_id"),
    action: str = Query(None),
    resource_type: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get audit logs for the current user.

    Filters by case_id, action, resource_type, and status.
    """
    result = get_audit_logs(
        db,
        user_id=user.id,
        product_case_id=case_id,
        action=action,
        resource_type=resource_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/status")
def security_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current security configuration status.

    Shows authentication mode, CORS settings, and security features.
    """
    from api.core.config import settings

    return {
        "authentication": {
            "mode": "demo" if settings.AYURINTEL_DEMO_MODE else "session",
            "session_ttl_seconds": settings.AYURINTEL_SESSION_TTL_SECONDS,
        },
        "security_features": {
            "audit_logging": True,
            "input_validation": True,
            "security_headers": True,
            "idor_protection": True,
            "product_case_isolation": True,
            "rate_limiting": True,
            "secret_protection": True,
        },
        "cors": {
            "allowed_origins": settings.AYURINTEL_CORS_ALLOW_ORIGINS,
        },
        "user": {
            "id": user.public_id,
            "username": user.username,
        },
    }
