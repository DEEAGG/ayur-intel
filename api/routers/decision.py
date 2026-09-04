"""AYUR-INTEL — Product Decision Dashboard API Routes (Phase 13)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User
from api.services.decision_service import generate_decision_dashboard

logger = logging.getLogger("ayur_intel.routers.decision")

router = APIRouter(prefix="/api", tags=["Decision Dashboard"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/cases/{case_id}/decision-dashboard")
def get_decision_dashboard(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the Product Decision Dashboard for a Product Case."""
    result = generate_decision_dashboard(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.post("/cases/{case_id}/decision-dashboard/refresh")
def refresh_decision_dashboard(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Refresh/regenerate the Product Decision Dashboard."""
    result = generate_decision_dashboard(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result
