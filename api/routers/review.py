"""AYUR-INTEL — Human-in-the-Loop Review API Routes (Phase 18)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User
from api.services.product_case_service import get_or_create_demo_user
from api.services.review_service import (
    assign_reviewer,
    auto_create_reviews_from_risks,
    get_review_detail,
    get_review_queue,
    make_decision,
    create_review_request,
)
from api.core.config import settings

logger = logging.getLogger("ayur_intel.routers.review")

router = APIRouter(prefix="/api", tags=["Human Review"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


# --- Request bodies ---

class ReviewCreateRequest(BaseModel):
    case_id: str
    trigger_type: str = "USER_REQUESTED"
    title: str
    description: str = ""
    priority: str = "MEDIUM"
    related_risk_id: int = None
    related_entity_type: str = None
    related_entity_id: str = None


class ReviewAssignRequest(BaseModel):
    assignee: str = "demo"


class ReviewDecisionRequest(BaseModel):
    decision: str  # CONFIRMED, REJECTED, MORE_INFORMATION_REQUIRED, ESCALATED, NO_ACTION
    comment: str = ""
    missing_info_description: str = ""


# --- Routes ---

@router.get("/reviews")
def list_reviews(
    case_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the review queue."""
    result = get_review_queue(
        db, user=user, case_public_id=case_id,
        status=status, limit=limit, offset=offset,
    )
    return result


@router.get("/reviews/{review_id}")
def get_review(
    review_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed review information."""
    result = get_review_detail(db, user=user, review_public_id=review_id)
    if not result:
        raise HTTPException(status_code=404, detail="Review not found")
    return result


@router.post("/reviews", status_code=201)
def create_review(
    body: ReviewCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new review request."""
    result = create_review_request(
        db, user=user, case_public_id=body.case_id,
        trigger_type=body.trigger_type, title=body.title,
        description=body.description, priority=body.priority,
        related_risk_id=body.related_risk_id,
        related_entity_type=body.related_entity_type,
        related_entity_id=body.related_entity_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.post("/reviews/{review_id}/assign")
def assign(
    review_id: str,
    body: ReviewAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Assign a reviewer."""
    result = assign_reviewer(
        db, user=user, review_public_id=review_id,
        assignee_username=body.assignee,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review not found")
    return result


@router.post("/reviews/{review_id}/decision")
def decide(
    review_id: str,
    body: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record a review decision."""
    result = make_decision(
        db, user=user, review_public_id=review_id,
        decision=body.decision, comment=body.comment,
        missing_info_description=body.missing_info_description,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review not found")
    return result


@router.post("/cases/{case_id}/reviews/auto-create")
def auto_create(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Auto-create review requests from HIGH risks."""
    created = auto_create_reviews_from_risks(db, user=user, case_public_id=case_id)
    return {"created": len(created), "reviews": created}
