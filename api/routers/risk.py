"""AYUR-INTEL — Risk + Self-Extension API Routes (Phase 12)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User
from api.models.risk import Risk, SelfExtensionRequest
from api.schemas.risk import (
    RiskAnalysisResponse,
    UpdateRiskStatusRequest,
    UpdateExtensionStatusRequest,
)
from api.services.risk_service import (
    generate_risk_analysis,
    update_risk_status,
    update_extension_status,
)
from api.services.audit_service import log_action

logger = logging.getLogger("ayur_intel.routers.risk")

router = APIRouter(prefix="/api", tags=["Risk & Self-Extension"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/cases/{case_id}/risk-analysis")
def create_risk_analysis(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate risk analysis and self-extension for a Product Case."""
    result = generate_risk_analysis(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    log_action(db, action="CREATE", resource_type="RISK_ANALYSIS",
               product_case_id=case_id, user_id=user.id,
               user_public_id=user.public_id, username=user.username)
    db.commit()
    return result


@router.get("/cases/{case_id}/risks")
def list_risks(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all risks for a Product Case."""
    from api.models.models import ProductCase
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Product Case not found")

    risks = db.query(Risk).filter(Risk.product_case_id == case.id).order_by(Risk.created_at.desc()).all()
    return {
        "risks": [{
            "id": r.public_id,
            "category": r.category,
            "level": r.level,
            "title": r.title,
            "status": r.status,
            "source_phase": r.source_phase,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        } for r in risks]
    }


@router.patch("/risks/{risk_id}")
def patch_risk(
    risk_id: str,
    body: UpdateRiskStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a risk's status."""
    result = update_risk_status(db, user, risk_id, body.status, body.note)
    if not result:
        raise HTTPException(status_code=404, detail="Risk not found")
    return result


@router.patch("/self-extension/{ext_id}")
def patch_extension(
    ext_id: str,
    body: UpdateExtensionStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a self-extension request's status."""
    result = update_extension_status(db, user, ext_id, body.status)
    if not result:
        raise HTTPException(status_code=404, detail="Extension request not found")
    return result
