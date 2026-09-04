"""AYUR-INTEL — Human-in-the-Loop Review Models (Phase 18).

ReviewRequest, ReviewItem, ReviewDecision, ReviewHistory.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from api.models.models import Base, _uuid, _now_utc


class ReviewRequest(Base):
    """A human review request triggered by AI analysis or user action."""

    __tablename__ = "review_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Trigger
    trigger_type = Column(String(50), nullable=False)
    # HIGH_RISK, LOW_CONFIDENCE, SOURCE_CONFLICT, CRITICAL_EVIDENCE_GAP,
    # IMPORTANT_REGULATORY_CHANGE, IMPORTANT_PATENT_FINDING, USER_REQUESTED

    priority = Column(String(10), nullable=False, default="MEDIUM")
    # HIGH, MEDIUM, LOW

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="PENDING")
    # PENDING, ASSIGNED, IN_REVIEW, COMPLETED, CANCELLED

    # Assignment
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Related references
    related_risk_id = Column(Integer, nullable=True)
    related_evidence_id = Column(Integer, nullable=True)
    related_entity_type = Column(String(100), nullable=True)
    related_entity_id = Column(String(100), nullable=True)

    # AI context shown to reviewer
    ai_assessment = Column(Text, nullable=True)
    ai_confidence = Column(String(20), nullable=True)
    ai_evidence_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    product_case = relationship("ProductCase", lazy="selectin")
    created_by = relationship("User", foreign_keys=[created_by_id], lazy="selectin")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], lazy="selectin")
    items = relationship("ReviewItem", back_populates="review_request", lazy="selectin")
    decisions = relationship("ReviewDecision", back_populates="review_request",
                            lazy="selectin", order_by="ReviewDecision.created_at.desc()")
    history = relationship("ReviewHistory", back_populates="review_request",
                          lazy="selectin", order_by="ReviewHistory.created_at.desc()")


class ReviewItem(Base):
    """A specific item within a review request (references existing entities)."""

    __tablename__ = "review_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    review_request_id = Column(Integer, ForeignKey("review_requests.id"), nullable=False)

    entity_type = Column(String(100), nullable=False)
    # RISK, EVIDENCE, PATENT_FINDING, REGULATORY_FINDING, MONITORING_ALERT, RECOMMENDATION
    entity_id = Column(String(100), nullable=False)  # public_id of the referenced entity
    entity_title = Column(String(300), nullable=True)  # denormalized for display

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    review_request = relationship("ReviewRequest", back_populates="items")


class ReviewDecision(Base):
    """A reviewer's decision on a review request."""

    __tablename__ = "review_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    review_request_id = Column(Integer, ForeignKey("review_requests.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    decision = Column(String(30), nullable=False)
    # CONFIRMED, REJECTED, MORE_INFORMATION_REQUIRED, ESCALATED, NO_ACTION

    comment = Column(Text, nullable=True)

    # For MORE_INFORMATION_REQUIRED
    missing_info_description = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    review_request = relationship("ReviewRequest", back_populates="decisions")
    reviewer = relationship("User", lazy="selectin")


class ReviewHistory(Base):
    """Tracks status changes for a review request."""

    __tablename__ = "review_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    review_request_id = Column(Integer, ForeignKey("review_requests.id"), nullable=False)
    old_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    review_request = relationship("ReviewRequest", back_populates="history")
    changed_by = relationship("User", lazy="selectin")
