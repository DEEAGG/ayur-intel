"""AYUR-INTEL — Product Decision Dashboard Models (Phase 13).

Lightweight snapshot model for persisting dashboard state.
The dashboard itself is dynamically computed from existing phase data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from api.models.models import Base, _uuid, _now_utc


class DecisionDashboardSnapshot(Base):
    """Lightweight snapshot of the decision dashboard state."""

    __tablename__ = "decision_dashboard_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Status
    status = Column(String(30), nullable=False, default="ANALYSIS_IN_PROGRESS")
    # ANALYSIS_NOT_STARTED, DATA_INCOMPLETE, ANALYSIS_IN_PROGRESS,
    # REVIEW_REQUIRED, READY_FOR_NEXT_STEP

    readiness_level = Column(String(30), nullable=False, default="NOT_READY")
    # NOT_READY, PARTIALLY_READY, REVIEW_REQUIRED, READY_FOR_NEXT_STEP

    # Summary counts
    total_risks = Column(Integer, nullable=False, default=0)
    high_risks = Column(Integer, nullable=False, default=0)
    medium_risks = Column(Integer, nullable=False, default=0)
    low_risks = Column(Integer, nullable=False, default=0)
    total_extensions = Column(Integer, nullable=False, default=0)
    evidence_coverage = Column(Integer, nullable=False, default=0)  # 0-100
    product_completeness = Column(Integer, nullable=False, default=0)  # 0-100

    # JSON summaries (for quick retrieval without recomputation)
    readiness_reasons = Column(Text, nullable=True)  # JSON list
    recommended_actions = Column(Text, nullable=True)  # JSON list

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
