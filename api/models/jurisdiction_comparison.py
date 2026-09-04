"""AYUR-INTEL — Jurisdiction Comparison Models (Phase 10).

Cross-jurisdiction regulatory comparison. Compares regulatory requirements
across multiple jurisdictions for a single Product Case.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


# We import Base from the main models module
from api.models.models import Base, _uuid, _now_utc


# ---------------------------------------------------------------------------
# Jurisdiction Comparison — Phase 10
# ---------------------------------------------------------------------------

class JurisdictionComparison(Base):
    """A cross-jurisdiction comparison for a Product Case.

    Stores the comparison metadata, jurisdictions selected, and summary.
    """

    __tablename__ = "jurisdiction_comparisons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Summary counts
    total_items = Column(Integer, nullable=False, default=0)
    jurisdictions_count = Column(Integer, nullable=False, default=0)
    differences_found = Column(Integer, nullable=False, default=0)
    information_gaps_total = Column(Integer, nullable=False, default=0)

    # Summary text
    key_differences = Column(Text, nullable=True)  # JSON list of difference strings
    decision_support_notes = Column(Text, nullable=True)

    # Status
    status = Column(String(30), nullable=False, default="COMPLETED")
    # COMPLETED, FAILED, PARTIAL

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    jurisdictions = relationship("ComparisonJurisdiction", back_populates="comparison", lazy="selectin")
    items = relationship("ComparisonItem", back_populates="comparison", lazy="selectin")


class ComparisonJurisdiction(Base):
    """A single jurisdiction within a comparison.

    Links to the RegulatoryProfile that was used for this jurisdiction.
    """

    __tablename__ = "comparison_jurisdictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    comparison_id = Column(Integer, ForeignKey("jurisdiction_comparisons.id"), nullable=False)
    regulatory_profile_id = Column(Integer, ForeignKey("regulatory_profiles.id"), nullable=True)

    # Jurisdiction info
    jurisdiction = Column(String(10), nullable=False)  # IN, US, EU, DE
    jurisdiction_name = Column(String(100), nullable=True)
    flag = Column(String(10), nullable=True)

    # Confidence and coverage
    confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW, INSUFFICIENT_DATA
    source_coverage = Column(String(20), nullable=True)  # FULL, PARTIAL, NONE
    sources_configured = Column(Integer, nullable=False, default=0)
    sources_total = Column(Integer, nullable=False, default=0)
    requirements_count = Column(Integer, nullable=False, default=0)
    category = Column(String(200), nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    comparison = relationship("JurisdictionComparison", back_populates="jurisdictions")
    regulatory_profile = relationship("RegulatoryProfile", lazy="selectin")
    values = relationship("ComparisonValue", back_populates="jurisdiction", lazy="selectin")


class ComparisonItem(Base):
    """A normalized comparison category (e.g. CLAIMS, INGREDIENTS, LABELLING)."""

    __tablename__ = "comparison_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    comparison_id = Column(Integer, ForeignKey("jurisdiction_comparisons.id"), nullable=False)

    # Item info
    category = Column(String(100), nullable=False)  # CLASSIFICATION, INGREDIENTS, CLAIMS, LABELLING, etc.
    normalized_label = Column(String(200), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_difference = Column(String(10), nullable=False, default="false")  # "true" if values differ
    difference_description = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    comparison = relationship("JurisdictionComparison", back_populates="items")
    values = relationship("ComparisonValue", back_populates="item", lazy="selectin")


class ComparisonValue(Base):
    """A single value for a ComparisonItem in a specific ComparisonJurisdiction."""

    __tablename__ = "comparison_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    comparison_item_id = Column(Integer, ForeignKey("comparison_items.id"), nullable=False)
    comparison_jurisdiction_id = Column(Integer, ForeignKey("comparison_jurisdictions.id"), nullable=False)

    # Value
    value = Column(Text, nullable=True)  # The comparison value/text
    status = Column(String(30), nullable=False, default="UNKNOWN")
    # FOUND, NOT_CONFIGURED, PARTIAL, MISSING, DIFFERENT
    confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    source_name = Column(String(200), nullable=True)
    evidence_detail = Column(Text, nullable=True)
    evidence_type = Column(String(50), nullable=True)
    authority = Column(String(200), nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    item = relationship("ComparisonItem", back_populates="values")
    jurisdiction = relationship("ComparisonJurisdiction", back_populates="values")
