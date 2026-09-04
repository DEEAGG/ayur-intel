"""AYUR-INTEL — Analytics + Impact Intelligence Routes (Phase 19)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.services.product_case_service import get_or_create_demo_user
from api.services.analytics_service import (
    get_product_analytics,
    get_platform_analytics,
    get_funnel_analytics,
    get_trend_analytics,
    get_risk_analytics,
    get_review_analytics,
)

logger = logging.getLogger("ayur_intel.routers.analytics")

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


@router.get("/product-cases/{case_id}")
def product_analytics(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get analytics for a specific Product Case."""
    result = get_product_analytics(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.get("/platform")
def platform_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get platform-wide aggregated analytics."""
    return get_platform_analytics(db, user)


@router.get("/funnel")
def funnel_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get workflow funnel analytics."""
    return get_funnel_analytics(db, user)


@router.get("/trends")
def trend_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get trend analytics over a date range."""
    return get_trend_analytics(db, user, days=days)


@router.get("/risks")
def risk_analytics(
    case_id: str = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get risk analytics, optionally for a specific case."""
    return get_risk_analytics(db, user, case_public_id=case_id)


@router.get("/reviews")
def review_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get review analytics."""
    return get_review_analytics(db, user)
