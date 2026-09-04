"""AYUR-INTEL — Evidence & Citation API Routes (Phase 11)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User
from api.services.evidence_service import aggregate_case_evidence, get_evidence_detail
from api.services.audit_service import log_action

logger = logging.getLogger("ayur_intel.routers.evidence")

router = APIRouter(prefix="/api", tags=["Evidence & Citation"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/cases/{case_id}/evidence")
def get_case_evidence(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get aggregated evidence for a Product Case across all phases."""
    result = aggregate_case_evidence(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    log_action(db, action="ACCESS", resource_type="EVIDENCE",
               product_case_id=case_id, user_id=user.id,
               user_public_id=user.public_id, username=user.username)
    db.commit()
    return result


@router.get("/evidence/{evidence_id}")
def get_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed evidence record."""
    result = get_evidence_detail(db, user, evidence_id)
    if not result:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return result
