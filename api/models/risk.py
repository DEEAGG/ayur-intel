"""AYUR-INTEL — Risk + Self-Extension Engine Models (Phase 12).

Risk detection and self-extension (missing information) tracking
across all analysis phases.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, Float
from sqlalchemy.orm import relationship

from api.models.models import Base, _uuid, _now_utc


class Risk(Base):
    """A detected risk or concern for a Product Case."""

    __tablename__ = "risks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Risk classification
    category = Column(String(50), nullable=False)
    # PATENT_IP, REGULATORY, INGREDIENT_PRODUCT_INFO, CLAIMS,
    # TK_PRIOR_ART, DATA_EVIDENCE_GAP, JURISDICTION_UNCERTAINTY
    level = Column(String(20), nullable=False, default="MEDIUM")
    # HIGH, MEDIUM, LOW, UNKNOWN
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)

    # Affected component
    affected_component_type = Column(String(100), nullable=True)
    affected_component_label = Column(String(200), nullable=True)
    affected_component_id = Column(String(100), nullable=True)

    # Evidence & confidence
    confidence = Column(String(20), nullable=True)
    data_origin = Column(String(30), nullable=True)
    # FACT, INFERENCE, USER_INPUT, UNKNOWN
    evidence_summary = Column(Text, nullable=True)

    # Missing information & next action
    missing_information = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)

    # Source phase origin
    source_phase = Column(String(20), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="OPEN")
    # OPEN, IN_REVIEW, RESOLVED, DISMISSED, UNKNOWN

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    evidence_links = relationship("RiskEvidence", back_populates="risk", lazy="selectin")
    resolutions = relationship("RiskResolution", back_populates="risk", lazy="selectin")


class RiskEvidence(Base):
    """Links a Risk to a UnifiedEvidence record."""

    __tablename__ = "risk_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    risk_id = Column(Integer, ForeignKey("risks.id"), nullable=False)
    evidence_id = Column(Integer, ForeignKey("unified_evidence.id"), nullable=True)

    # For evidence not yet in unified_evidence (inline evidence)
    evidence_type = Column(String(50), nullable=True)
    evidence_title = Column(String(500), nullable=True)
    evidence_reference = Column(String(500), nullable=True)
    evidence_description = Column(Text, nullable=True)
    evidence_source_name = Column(String(200), nullable=True)
    evidence_authority = Column(String(200), nullable=True)
    evidence_jurisdiction = Column(String(50), nullable=True)

    relationship_type = Column(String(30), nullable=False, default="SUPPORTS")

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    risk = relationship("Risk", back_populates="evidence_links")


class RiskResolution(Base):
    """Tracks resolution history for a Risk."""

    __tablename__ = "risk_resolutions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    risk_id = Column(Integer, ForeignKey("risks.id"), nullable=False)
    status = Column(String(20), nullable=False)
    note = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True, default="demo")

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    risk = relationship("Risk", back_populates="resolutions")


class SelfExtensionRequest(Base):
    """A self-extension request — missing information or next investigation step."""

    __tablename__ = "self_extension_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Classification
    type = Column(String(50), nullable=False)
    # MISSING_USER_INFORMATION, MISSING_EVIDENCE, MISSING_SOURCE,
    # MISSING_ANALYSIS, SOURCE_CONFIGURATION_REQUIRED, VERIFICATION_REQUIRED

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    why_needed = Column(Text, nullable=True)

    # Priority
    priority = Column(String(10), nullable=False, default="MEDIUM")
    # HIGH, MEDIUM, LOW

    # Status
    status = Column(String(20), nullable=False, default="OPEN")
    # OPEN, IN_PROGRESS, RESOLVED, SKIPPED

    # Related references
    related_component_type = Column(String(100), nullable=True)
    related_component_id = Column(String(100), nullable=True)
    related_risk_id = Column(String(100), nullable=True)

    # Suggested action
    suggested_action = Column(Text, nullable=True)
    resolve_url = Column(String(300), nullable=True)  # deep link to resolve

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")


class RiskAssessment(Base):
    """Complete, canonical AI / Rule-based Risk Assessment for a Product Case."""

    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False, index=True)

    # Assessment provenance
    assessment_source = Column(String(30), nullable=False, default="GEMINI")  # GEMINI | RULE_ENGINE
    model_used = Column(String(50), nullable=True)  # e.g. gemini-2.5-flash or None
    schema_version = Column(Integer, nullable=False, default=1)

    # Core scores & summary
    overall_score = Column(Integer, nullable=False, default=0)  # 0-100
    overall_level = Column(String(20), nullable=False, default="MODERATE")  # LOW, MODERATE, HIGH, CRITICAL
    overall_confidence = Column(Float, nullable=False, default=0.80)  # 0.0 - 1.0
    overall_summary = Column(Text, nullable=True)

    # Structured JSON payloads
    domain_scores_json = Column(Text, nullable=False, default="[]")
    top_risks_json = Column(Text, nullable=False, default="[]")
    mitigation_plan_json = Column(Text, nullable=False, default="{}")
    evidence_gaps_json = Column(Text, nullable=False, default="[]")
    evidence_coverage_json = Column(Text, nullable=False, default="{}")
    raw_response_json = Column(Text, nullable=False, default="{}")

    # Transparency disclaimer
    disclaimer = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
