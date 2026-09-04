"""AYUR-INTEL — Human-in-the-Loop Review Service (Phase 18).

Creates review requests, assigns reviewers, processes decisions,
and generates the review queue from risk analysis results.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.models import ProductCase, User
from api.models.risk import Risk
from api.models.review import ReviewRequest, ReviewItem, ReviewDecision, ReviewHistory
from api.services.audit_service import log_action

logger = logging.getLogger("ayur_intel.review")


def create_review_request(
    db: Session,
    *,
    user: User,
    case_public_id: str,
    trigger_type: str,
    title: str,
    description: Optional[str] = None,
    priority: str = "MEDIUM",
    related_risk_id: Optional[int] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    ai_assessment: Optional[str] = None,
    ai_confidence: Optional[str] = None,
    ai_evidence_summary: Optional[str] = None,
) -> Optional[dict]:
    """Create a new review request for a Product Case."""
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_public_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        return None

    request = ReviewRequest(
        product_case_id=case.id,
        created_by_id=user.id,
        trigger_type=trigger_type,
        priority=priority,
        title=title,
        description=description,
        status="PENDING",
        related_risk_id=related_risk_id,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        ai_assessment=ai_assessment,
        ai_confidence=ai_confidence,
        ai_evidence_summary=ai_evidence_summary,
    )
    db.add(request)
    db.flush()

    # Add history entry
    history = ReviewHistory(
        review_request_id=request.id,
        old_status=None,
        new_status="PENDING",
        changed_by_id=user.id,
        note="Review request created",
    )
    db.add(history)

    log_action(
        db, action="CREATE", resource_type="REVIEW_REQUEST",
        resource_id=request.public_id, product_case_id=case_public_id,
        user_id=user.id, user_public_id=user.public_id, username=user.username,
        detail=f"Trigger: {trigger_type}, Priority: {priority}",
    )
    db.commit()
    db.refresh(request)

    return _review_to_dict(request, case)


def assign_reviewer(
    db: Session,
    *,
    user: User,
    review_public_id: str,
    assignee_username: str,
) -> Optional[dict]:
    """Assign a reviewer to a review request."""
    request = db.query(ReviewRequest).filter(
        ReviewRequest.public_id == review_public_id,
    ).first()
    if not request:
        return None

    # Check case ownership
    case = db.query(ProductCase).filter(
        ProductCase.id == request.product_case_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        return None

    assignee = db.query(User).filter(User.username == assignee_username).first()
    if not assignee:
        # Use the current user in demo mode
        assignee = user

    old_status = request.status
    request.assigned_to_id = assignee.id
    request.status = "ASSIGNED"
    request.updated_at = datetime.now(timezone.utc)

    history = ReviewHistory(
        review_request_id=request.id,
        old_status=old_status,
        new_status="ASSIGNED",
        changed_by_id=user.id,
        note=f"Assigned to {assignee.username}",
    )
    db.add(history)

    log_action(
        db, action="ASSIGN", resource_type="REVIEW_REQUEST",
        resource_id=review_public_id, product_case_id=case.public_id,
        user_id=user.id, user_public_id=user.public_id, username=user.username,
    )
    db.commit()
    db.refresh(request)

    return _review_to_dict(request, case)


def make_decision(
    db: Session,
    *,
    user: User,
    review_public_id: str,
    decision: str,
    comment: Optional[str] = None,
    missing_info_description: Optional[str] = None,
) -> Optional[dict]:
    """Record a reviewer's decision on a review request."""
    request = db.query(ReviewRequest).filter(
        ReviewRequest.public_id == review_public_id,
    ).first()
    if not request:
        return None

    # Check case ownership
    case = db.query(ProductCase).filter(
        ProductCase.id == request.product_case_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        return None

    # Record decision
    review_decision = ReviewDecision(
        review_request_id=request.id,
        reviewer_id=user.id,
        decision=decision,
        comment=comment,
        missing_info_description=missing_info_description,
    )
    db.add(review_decision)

    # Update request status
    old_status = request.status
    new_status = "COMPLETED" if decision in ("CONFIRMED", "REJECTED", "NO_ACTION") else request.status
    if decision == "MORE_INFORMATION_REQUIRED":
        new_status = "IN_REVIEW"
    elif decision == "ESCALATED":
        new_status = "IN_REVIEW"

    request.status = new_status
    request.updated_at = datetime.now(timezone.utc)

    history = ReviewHistory(
        review_request_id=request.id,
        old_status=old_status,
        new_status=new_status,
        changed_by_id=user.id,
        note=f"Decision: {decision}",
    )
    db.add(history)

    log_action(
        db, action="DECISION", resource_type="REVIEW_REQUEST",
        resource_id=review_public_id, product_case_id=case.public_id,
        user_id=user.id, user_public_id=user.public_id, username=user.username,
        detail=f"Decision: {decision}",
    )
    db.commit()
    db.refresh(request)

    return _review_to_dict(request, case)


def get_review_queue(
    db: Session,
    *,
    user: User,
    case_public_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Get the review queue for a user."""
    query = db.query(ReviewRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    )

    if case_public_id:
        case = db.query(ProductCase).filter(
            ProductCase.public_id == case_public_id,
            ProductCase.owner_id == user.id,
        ).first()
        if case:
            query = query.filter(ReviewRequest.product_case_id == case.id)

    if status:
        query = query.filter(ReviewRequest.status == status)

    total = query.count()
    requests = query.order_by(
        ReviewRequest.priority.desc(),
        ReviewRequest.created_at.desc(),
    ).offset(offset).limit(limit).all()

    return {
        "reviews": [_review_summary(r) for r in requests],
        "total": total,
        "pending": db.query(ReviewRequest).join(ProductCase).filter(
            ProductCase.owner_id == user.id,
            ReviewRequest.status.in_(["PENDING", "ASSIGNED"]),
        ).count(),
        "in_review": db.query(ReviewRequest).join(ProductCase).filter(
            ProductCase.owner_id == user.id,
            ReviewRequest.status == "IN_REVIEW",
        ).count(),
        "completed": db.query(ReviewRequest).join(ProductCase).filter(
            ProductCase.owner_id == user.id,
            ReviewRequest.status == "COMPLETED",
        ).count(),
    }


def get_review_detail(
    db: Session,
    *,
    user: User,
    review_public_id: str,
) -> Optional[dict]:
    """Get detailed review information."""
    request = db.query(ReviewRequest).filter(
        ReviewRequest.public_id == review_public_id,
    ).first()
    if not request:
        return None

    case = db.query(ProductCase).filter(
        ProductCase.id == request.product_case_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        return None

    result = _review_to_dict(request, case)

    # Include risk details if linked
    if request.related_risk_id:
        risk = db.query(Risk).filter(Risk.id == request.related_risk_id).first()
        if risk:
            result["linked_risk"] = {
                "id": risk.public_id,
                "category": risk.category,
                "level": risk.level,
                "title": risk.title,
                "description": risk.description,
                "confidence": risk.confidence,
                "evidence_summary": risk.evidence_summary,
                "next_action": risk.next_action,
            }

    return result


def auto_create_reviews_from_risks(
    db: Session,
    *,
    user: User,
    case_public_id: str,
) -> list:
    """Auto-create review requests for HIGH risks in a Product Case."""
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_public_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        return []

    # Find HIGH risks that don't already have a review request
    high_risks = db.query(Risk).filter(
        Risk.product_case_id == case.id,
        Risk.level == "HIGH",
        Risk.status == "OPEN",
    ).all()

    created = []
    for risk in high_risks:
        # Check if review already exists for this risk
        existing = db.query(ReviewRequest).filter(
            ReviewRequest.product_case_id == case.id,
            ReviewRequest.related_risk_id == risk.id,
        ).first()
        if existing:
            continue

        result = create_review_request(
            db,
            user=user,
            case_public_id=case_public_id,
            trigger_type="HIGH_RISK",
            title=f"Review: {risk.title}",
            description=risk.description or f"High-risk finding in {risk.category} category requires review.",
            priority="HIGH",
            related_risk_id=risk.id,
            related_entity_type="RISK",
            related_entity_id=risk.public_id,
            ai_assessment=risk.description,
            ai_confidence=risk.confidence,
            ai_evidence_summary=risk.evidence_summary,
        )
        if result:
            created.append(result)

    return created


def _review_to_dict(request: ReviewRequest, case: ProductCase) -> dict:
    """Convert a ReviewRequest to a dict for API response."""
    return {
        "id": request.public_id,
        "case_id": case.public_id,
        "case_name": case.name,
        "trigger_type": request.trigger_type,
        "priority": request.priority,
        "title": request.title,
        "description": request.description,
        "status": request.status,
        "created_by": request.created_by.username if request.created_by else None,
        "assigned_to": request.assigned_to.username if request.assigned_to else None,
        "related_risk_id": request.related_risk_id,
        "related_entity_type": request.related_entity_type,
        "related_entity_id": request.related_entity_id,
        "ai_assessment": request.ai_assessment,
        "ai_confidence": request.ai_confidence,
        "ai_evidence_summary": request.ai_evidence_summary,
        "decisions": [
            {
                "id": d.public_id,
                "decision": d.decision,
                "comment": d.comment,
                "reviewer": d.reviewer.username if d.reviewer else None,
                "created_at": d.created_at.isoformat() if d.created_at else "",
            }
            for d in (request.decisions or [])
        ],
        "history": [
            {
                "old_status": h.old_status,
                "new_status": h.new_status,
                "changed_by": h.changed_by.username if h.changed_by else None,
                "note": h.note,
                "created_at": h.created_at.isoformat() if h.created_at else "",
            }
            for h in (request.history or [])
        ],
        "created_at": request.created_at.isoformat() if request.created_at else "",
        "updated_at": request.updated_at.isoformat() if request.updated_at else "",
    }


def _review_summary(request: ReviewRequest) -> dict:
    """Convert a ReviewRequest to a summary dict for queue display."""
    case = None
    if request.product_case:
        case = request.product_case

    return {
        "id": request.public_id,
        "case_id": case.public_id if case else None,
        "case_name": case.name if case else None,
        "trigger_type": request.trigger_type,
        "priority": request.priority,
        "title": request.title,
        "status": request.status,
        "assigned_to": request.assigned_to.username if request.assigned_to else None,
        "created_at": request.created_at.isoformat() if request.created_at else "",
    }
