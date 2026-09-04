"""AYUR-INTEL — Evidence & Citation Engine Models (Phase 11).

Unified evidence and finding models that connect across all phases:
Patent, Regulatory, IP Strategy, Knowledge, Innovation.

Provides traceability: Finding → Evidence → Source → Original Reference.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from api.models.models import Base, _uuid, _now_utc


# ---------------------------------------------------------------------------
# Unified Evidence — a single evidence record across all phases
# ---------------------------------------------------------------------------

class UnifiedEvidence(Base):
    """A single piece of evidence that can be cited by any finding.

    Unlike KnowledgeEvidence (Phase 3), this is a unified evidence record
    that works across patents, regulations, IP strategy, and knowledge.
    """

    __tablename__ = "unified_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Source reference (reuses existing Source model)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)

    # Evidence type classification
    evidence_type = Column(String(50), nullable=False)
    # PATENT_PUBLICATION, PATENT_CLAIM, PATENT_ABSTRACT, PATENT_METADATA,
    # REGULATION, REGULATORY_GUIDANCE, OFFICIAL_SOURCE,
    # TK_DOCUMENT, SCIENTIFIC_PAPER,
    # USER_PROVIDED, SYSTEM_DERIVED, INNOVATION_ANALYSIS,
    # PATENT_ANALYSIS, IP_STRATEGY, REGULATORY_PROFILE,
    # JURISDICTION_COMPARISON, PRODUCT_PASSPORT

    # Content
    title = Column(String(500), nullable=True)
    reference = Column(String(500), nullable=True)  # URL, DOI, patent number, section ref
    excerpt = Column(Text, nullable=True)  # quoted text if legally permitted
    description = Column(Text, nullable=True)  # human-readable summary of the evidence

    # Source metadata (denormalized for quick display)
    source_name = Column(String(200), nullable=True)
    authority = Column(String(200), nullable=True)
    jurisdiction = Column(String(50), nullable=True)

    # Quality / confidence
    quality = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW, INSUFFICIENT
    confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    data_origin = Column(String(30), nullable=True)  # FACT, INFERENCE, USER_INPUT, UNKNOWN

    # Dates
    publication_date = Column(String(50), nullable=True)
    version = Column(String(100), nullable=True)
    effective_date = Column(String(50), nullable=True)
    retrieved_at = Column(DateTime, nullable=True)

    # Deduplication
    evidence_hash = Column(String(64), nullable=True)  # SHA-256 of source+reference+excerpt

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    source = relationship("Source", lazy="selectin")
    finding_links = relationship("CaseFindingEvidence", back_populates="evidence", lazy="selectin")


# ---------------------------------------------------------------------------
# Case Finding — a finding linked to a Product Case (any phase)
# ---------------------------------------------------------------------------

class CaseFinding(Base):
    """A finding that can be traced to evidence.

    Unlike KnowledgeFinding (Phase 3), this is a unified finding model
    that works across all analysis phases.
    """

    __tablename__ = "case_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Finding classification
    finding_type = Column(String(50), nullable=False)
    # INNOVATION_COMPONENT, PATENT_RELEVANCE, PATENT_COMPARISON,
    # IP_STRATEGY_ITEM, REGULATORY_REQUIREMENT,
    # JURISDICTION_DIFFERENCE, KNOWLEDGE_FINDING,
    # USER_CLAIM, SYSTEM_INFERENCE

    # Phase origin
    source_phase = Column(String(20), nullable=False)
    # PHASE_5_INNOVATION, PHASE_6_PATENT, PHASE_7_PATENT_DEEP,
    # PHASE_8_IP_STRATEGY, PHASE_9_REGULATORY, PHASE_10_JURISDICTION,
    # PHASE_3_KNOWLEDGE, USER_INPUT

    # Content
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)

    # Reference to source entity (e.g., patent_record_id, innovation_component_id)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(String(100), nullable=True)

    # Status & confidence
    status = Column(String(30), nullable=False, default="ACTIVE")
    # ACTIVE, FLAGGED_UNSUPPORTED, CONFLICTING, VERIFIED, RETRACTED
    confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    data_origin = Column(String(30), nullable=True)
    # FACT, INFERENCE, USER_INPUT, UNKNOWN, SYSTEM_DERIVED

    # Citation tracking
    evidence_count = Column(Integer, nullable=False, default=0)
    has_conflicts = Column(Boolean, nullable=False, default=False)
    is_unsupported = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    evidence_links = relationship("CaseFindingEvidence", back_populates="finding", lazy="selectin")


# ---------------------------------------------------------------------------
# Finding ↔ Evidence junction
# ---------------------------------------------------------------------------

class CaseFindingEvidence(Base):
    """Links a CaseFinding to a UnifiedEvidence with relationship type."""

    __tablename__ = "case_finding_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    finding_id = Column(Integer, ForeignKey("case_findings.id"), nullable=False)
    evidence_id = Column(Integer, ForeignKey("unified_evidence.id"), nullable=False)

    # Relationship type
    relationship_type = Column(String(30), nullable=False, default="SUPPORTS")
    # SUPPORTS, CONTEXT, CONTRADICTS, USER_PROVIDED, INFERRED_FROM

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    finding = relationship("CaseFinding", back_populates="evidence_links")
    evidence = relationship("UnifiedEvidence", back_populates="finding_links")
