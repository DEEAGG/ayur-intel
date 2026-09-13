"""AYUR-INTEL — Continuous Monitoring API Routes (Phase 14)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User, ProductCase
from api.schemas.monitoring import (
    MonitoringConfigResponse,
    UpdateMonitoringConfigRequest,
    AlertResponse,
    UpdateAlertRequest,
)
from api.services.monitoring_service import (
    get_or_create_config,
    update_config,
    run_monitoring_check,
    get_monitoring_summary,
    get_monitoring_history,
    update_alert_status,
)
from api.services.audit_service import log_action

logger = logging.getLogger("ayur_intel.routers.monitoring")

router = APIRouter(prefix="/api", tags=["Continuous Monitoring"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/cases/{case_id}/monitoring")
def get_monitoring(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get monitoring summary for a Product Case."""
    result = get_monitoring_summary(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.post("/cases/{case_id}/monitoring")
def create_monitoring(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create or get monitoring configuration."""
    conds = [ProductCase.public_id == case_id]
    if str(case_id).isdigit():
        conds.append(ProductCase.id == int(case_id))
    case = db.query(ProductCase).filter(
        or_(*conds),
        or_(
            ProductCase.owner_id == user.id,
            ProductCase.is_demo == True,
            ProductCase.public_id == "demo-001",
        ),
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Product Case not found")

    config = get_or_create_config(db, user, case)
    db.commit()
    return {
        "id": config.public_id,
        "message": "Monitoring configuration created/loaded",
    }


@router.patch("/cases/{case_id}/monitoring")
def patch_monitoring(
    case_id: str,
    body: UpdateMonitoringConfigRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update monitoring configuration."""
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    result = update_config(db, user, case_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.post("/cases/{case_id}/monitoring/run")
def run_monitoring(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a manual monitoring check."""
    result = run_monitoring_check(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    log_action(db, action="RUN_CHECK", resource_type="MONITORING",
               product_case_id=case_id, user_id=user.id,
               user_public_id=user.public_id, username=user.username,
               detail=f"Sources checked: {result.get('sources_checked', 0)}")
    db.commit()
    return result


@router.get("/cases/{case_id}/monitoring/history")
def get_history(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get monitoring history for a Product Case."""
    result = get_monitoring_history(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.patch("/monitoring/alerts/{alert_id}")
def patch_alert(
    alert_id: str,
    body: UpdateAlertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update an alert's status."""
    if not body.status:
        raise HTTPException(status_code=400, detail="Status is required")
    result = update_alert_status(db, user, alert_id, body.status)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result
