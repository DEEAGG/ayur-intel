"""AYUR-INTEL — SQLAlchemy ORM Models.

Core entities:
- User: platform identity (Phase 1: minimal; Phase 19: full auth)
- ProductCase: the central persistent object of AYUR-INTEL
- CaseVersion: tracks material changes to a ProductCase

Phase 2: PlantDiscovery
Phase 3: Source, KnowledgeFinding, KnowledgeEvidence
Phase 4: Adaptive Product Passport (frontend wizard; no new model)
Phase 5: InnovationAnalysis, InnovationComponent
Future entities: WatchEvent, etc.
All connect to ProductCase.
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
    Boolean,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all AYUR-INTEL models."""
    pass


def _uuid() -> str:
    """Generate a prefixed UUID for use as a public ID."""
    return uuid.uuid4().hex[:12]


def _now_utc() -> datetime:
    """Current UTC time."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    """Platform user. Phase 1: minimal identity. Phase 19: full auth."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)
    username = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False, default="")
    email = Column(String(200), nullable=True)
    hashed_password = Column(String(300), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    product_cases = relationship("ProductCase", back_populates="owner", lazy="select")
    plant_discoveries = relationship("PlantDiscovery", back_populates="owner", lazy="select")
    knowledge_findings = relationship("KnowledgeFinding", back_populates="owner", lazy="select")


# ---------------------------------------------------------------------------
# Product Case — the central persistent object
# ---------------------------------------------------------------------------

class ProductCase(Base):
    """Product Case / Product Passport — the central object of AYUR-INTEL.

    Every future module (TK, Patent, Regulatory, Evidence, Risk, Watch)
    connects to this entity.
    """

    __tablename__ = "product_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid, index=True)

    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Product identity
    name = Column(String(300), nullable=False)
    stage = Column(String(50), nullable=False, default="IDEA")
    # Stages: IDEA, RND, PILOT, PRE_LAUNCH, COMMERCIAL

    # Jurisdictions (JSON string — list of jurisdiction codes like ["IN", "US"])
    jurisdictions = Column(Text, nullable=False, default="[]")

    # Status
    status = Column(String(50), nullable=False, default="DRAFT", index=True)
    # Statuses: DRAFT, ANALYZING, COMPLETED, ARCHIVED

    # Flag for pre-filled demo products (hidden from Active Products list)
    is_demo = Column(Boolean, nullable=False, default=False, index=True)

    # Product details (filled in Phase 1+; nullable in Phase 1)
    ingredients = Column(Text, nullable=True, default="[]")  # JSON
    form = Column(String(100), nullable=True)
    intended_use = Column(Text, nullable=True)
    claims = Column(Text, nullable=True, default="[]")  # JSON
    formulation = Column(Text, nullable=True)
    process = Column(Text, nullable=True)
    brand = Column(String(200), nullable=True)
    packaging = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_now_utc, index=True)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc, index=True)

    # Versioning
    current_version = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_product_cases_owner_demo_status", "owner_id", "is_demo", "status"),
        Index("ix_product_cases_created_at_desc", created_at.desc()),
        Index("ix_product_cases_updated_at_desc", updated_at.desc()),
    )

    # Relationships
    owner = relationship("User", back_populates="product_cases", lazy="joined")
    versions = relationship("CaseVersion", back_populates="case", lazy="select",
                            order_by="CaseVersion.version_number.desc()")
    plant_discoveries = relationship("PlantDiscovery", back_populates="product_case", lazy="select")
    knowledge_findings = relationship("KnowledgeFinding", back_populates="product_case", lazy="select")


# ---------------------------------------------------------------------------
# Case Version — tracks material changes
# ---------------------------------------------------------------------------

class CaseVersion(Base):
    """Snapshot of a ProductCase when material facts change.

    Enables analysis reproducibility: case_version + source_versions +
    evidence_ids + timestamp.
    """

    __tablename__ = "case_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)
    version_number = Column(Integer, nullable=False)

    # Snapshot of key fields at this version
    snapshot = Column(Text, nullable=False, default="{}")  # JSON

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    case = relationship("ProductCase", back_populates="versions")


# ---------------------------------------------------------------------------
# Plant Discovery — Phase 2
# ---------------------------------------------------------------------------

class PlantDiscovery(Base):
    """Plant Discovery record — preliminary plant identification from an image.

    Linked to a user and optionally to a ProductCase.
    Identification is ALWAYS preliminary — never guaranteed.
    """

    __tablename__ = "plant_discoveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Optional link to a Product Case
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=True)

    # Image
    image_filename = Column(String(300), nullable=True)
    image_path = Column(String(500), nullable=True)
    image_size_bytes = Column(Integer, nullable=True)
    image_content_type = Column(String(100), nullable=True)

    # Identification results
    candidate_name = Column(String(300), nullable=True)
    botanical_name = Column(String(300), nullable=True)
    confidence = Column(Integer, nullable=True)  # 0-100
    alternative_candidates = Column(Text, nullable=True, default="[]")  # JSON list
    identification_notes = Column(Text, nullable=True)
    verification_required = Column(Boolean, nullable=False, default=True)

    # Provider metadata
    provider = Column(String(100), nullable=True, default="none")
    provider_raw_result = Column(Text, nullable=True)  # JSON — raw provider response

    # Status
    status = Column(String(50), nullable=False, default="UPLOADED")
    # Statuses: UPLOADED, ANALYZING, IDENTIFIED, FAILED, SAVED

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")


# ---------------------------------------------------------------------------
# Source — registered knowledge source / authority
# ---------------------------------------------------------------------------

class Source(Base):
    """A registered knowledge source or authority.

    Each source adapter must register itself here so that evidence
    can be traced back to a specific authority, jurisdiction, and
    retrieval method.
    """

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Identity
    name = Column(String(200), nullable=False)
    authority = Column(String(300), nullable=True)  # e.g. "AYUSH", "WHO", "USPTO"
    source_type = Column(String(100), nullable=True)  # e.g. "TK", "GOV", "SCIENTIFIC"
    jurisdiction = Column(String(50), nullable=True)  # e.g. "IN", "US", "EU", "GLOBAL"
    url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    # Status
    is_configured = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # Metadata
    last_retrieved_at = Column(DateTime, nullable=True)
    capabilities = Column(Text, nullable=True, default="[]")  # JSON list

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    findings = relationship("KnowledgeFinding", back_populates="source", lazy="selectin")


# ---------------------------------------------------------------------------
# Knowledge Finding — a research finding saved to a Product Case
# ---------------------------------------------------------------------------

class KnowledgeFinding(Base):
    """A Traditional Knowledge or research finding.

    Each finding is backed by evidence from a source. Findings can be
    saved to a Product Case to build the research trail.
    """

    __tablename__ = "knowledge_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Links
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=True)
    plant_discovery_id = Column(Integer, ForeignKey("plant_discoveries.id"), nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)

    # Finding content
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # e.g. "TRADITIONAL_USE", "PREPARATION", "SAFETY"
    plant_name = Column(String(300), nullable=True)
    botanical_name = Column(String(300), nullable=True)
    traditional_name = Column(String(300), nullable=True)

    # Evidence metadata
    confidence = Column(String(20), nullable=True)  # HIGH, MODERATE, LOW, CONFLICTING, UNKNOWN
    relevance = Column(String(20), nullable=True)    # HIGH, MODERATE, LOW
    evidence_locator = Column(String(500), nullable=True)  # section, page, URL fragment
    evidence_excerpt = Column(Text, nullable=True)  # quoted excerpt if legally permitted
    publication_date = Column(String(50), nullable=True)
    retrieval_date = Column(String(50), nullable=True)

    # Jurisdiction & metadata
    jurisdiction = Column(String(50), nullable=True)
    source_name = Column(String(200), nullable=True)  # denormalized for quick display
    source_authority = Column(String(200), nullable=True)

    # Limitations & disclaimers
    limitations = Column(Text, nullable=True)
    is_conflicting = Column(Boolean, nullable=False, default=False)
    conflicting_details = Column(Text, nullable=True)  # JSON — other sources' positions

    # Status
    status = Column(String(50), nullable=False, default="RETRIEVED")
    # RETRIEVED, SAVED, FLAGGED

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    source = relationship("Source", back_populates="findings", lazy="selectin")


# ---------------------------------------------------------------------------
# Knowledge Evidence — individual evidence records attached to findings
# ---------------------------------------------------------------------------

class KnowledgeEvidence(Base):
    """A single piece of evidence supporting a Knowledge Finding.

    Evidence traces back to a source document, authority, section, and
    excerpt. Multiple evidence records can support one finding.
    """

    __tablename__ = "knowledge_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    finding_id = Column(Integer, ForeignKey("knowledge_findings.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)

    # Evidence content
    title = Column(String(500), nullable=True)
    source_identifier = Column(String(500), nullable=True)  # URL, DOI, patent number, etc.
    evidence_locator = Column(String(500), nullable=True)  # section, page, clause
    excerpt = Column(Text, nullable=True)  # quoted text if legally permitted
    confidence = Column(String(20), nullable=True)

    # Dates
    publication_date = Column(String(50), nullable=True)
    retrieval_date = Column(String(50), nullable=True)
    source_version = Column(String(100), nullable=True)

    # Provenance & Hash
    content_hash = Column(String(64), nullable=True, index=True)
    license_note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    finding = relationship("KnowledgeFinding", lazy="selectin")
    source = relationship("Source", lazy="selectin")


# ---------------------------------------------------------------------------
# Innovation Analysis — Phase 5
# ---------------------------------------------------------------------------

class InnovationAnalysis(Base):
    """An innovation decomposition analysis of a Product Case.

    Breaks the product into components and classifies each
    as traditional/known, potentially differentiated, or
    requiring investigation. This is DECISION SUPPORT, not
    a legal patentability opinion.
    """

    __tablename__ = "innovation_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Status
    status = Column(String(50), nullable=False, default="COMPLETED")
    # PENDING, COMPLETED, FAILED

    # Summary
    total_components = Column(Integer, nullable=False, default=0)
    traditional_count = Column(Integer, nullable=False, default=0)
    differentiated_count = Column(Integer, nullable=False, default=0)
    investigation_count = Column(Integer, nullable=False, default=0)
    insufficient_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    components = relationship("InnovationComponent", back_populates="analysis",
                              lazy="selectin", order_by="InnovationComponent.sort_order")


class InnovationComponent(Base):
    """A single decomposed component of a product, with classification.

    Each component represents one element of the product that has been
    analyzed for innovation potential. Classifications are preliminary
    research assessments, NOT legal conclusions.
    """

    __tablename__ = "innovation_components"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    analysis_id = Column(Integer, ForeignKey("innovation_analyses.id"), nullable=False)

    # Component identity
    component_type = Column(String(100), nullable=False)
    # INGREDIENT, COMBINATION, FORMULATION, PROCESS, EXTRACTION,
    # PRODUCT_FORM, INTENDED_USE, CLAIMS, BRAND, PACKAGING
    component_label = Column(String(200), nullable=False)
    component_value = Column(Text, nullable=True)  # The actual value/text
    sort_order = Column(Integer, nullable=False, default=0)

    # Classification
    classification = Column(String(50), nullable=False, default="INSUFFICIENT_INFORMATION")
    # TRADITIONAL_OR_KNOWN, POTENTIALLY_DIFFERENTIATED,
    # INSUFFICIENT_INFORMATION, REQUIRES_INVESTIGATION
    explanation = Column(Text, nullable=True)
    confidence = Column(String(20), nullable=True)  # LOW, MEDIUM, HIGH

    # Data origin
    data_origin = Column(String(50), nullable=True, default="UNKNOWN")
    # USER_PROVIDED, SOURCE_SUPPORTED, SYSTEM_DERIVED, UNKNOWN
    evidence_summary = Column(Text, nullable=True)  # Brief evidence/context note

    # IP route
    potential_ip_route = Column(String(200), nullable=True)
    investigation_required = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    analysis = relationship("InnovationAnalysis", back_populates="components")


# ---------------------------------------------------------------------------
# Patent Record — Phase 6
# ---------------------------------------------------------------------------

class PatentRecord(Base):
    """A normalized patent record from a patent source adapter.

    Stores patent/application information in a common structure
    regardless of which source it came from.
    """

    __tablename__ = "patent_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Source
    source_name = Column(String(200), nullable=True)
    authority = Column(String(200), nullable=True)
    jurisdiction = Column(String(50), nullable=True)
    source_url = Column(String(500), nullable=True)

    # Patent identifiers
    provider_record_id = Column(String(100), nullable=True)
    publication_number = Column(String(100), nullable=True)
    application_number = Column(String(100), nullable=True)
    patent_type = Column(String(50), nullable=True)  # APPLICATION, PUBLICATION, GRANTED

    # Content
    title = Column(String(500), nullable=True)
    abstract = Column(Text, nullable=True)
    applicant = Column(String(300), nullable=True)
    inventors = Column(Text, nullable=True)  # JSON list

    # Dates
    priority_date = Column(String(50), nullable=True)
    filing_date = Column(String(50), nullable=True)
    publication_date = Column(String(50), nullable=True)

    # Status
    status = Column(String(100), nullable=True)  # e.g. "Published", "Granted", "Pending"

    # Family
    family_id = Column(String(100), nullable=True)
    family_members_json = Column(Text, nullable=True)  # JSON list of family publication numbers

    # Retrieval
    retrieved_at = Column(DateTime, nullable=False, default=_now_utc)
    raw_metadata = Column(Text, nullable=True)  # JSON — raw source response

    created_at = Column(DateTime, nullable=False, default=_now_utc)


# ---------------------------------------------------------------------------
# Patent Search — stores a search session
# ---------------------------------------------------------------------------

class PatentSearch(Base):
    """A patent search session for a Product Case.

    Tracks what was searched, which sources were queried,
    and how many results were found.
    """

    __tablename__ = "patent_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Search details
    search_concepts = Column(Text, nullable=True, default="[]")  # JSON list of search query objects or strings
    jurisdictions_searched = Column(Text, nullable=True, default="[]")  # JSON list
    total_results = Column(Integer, nullable=False, default=0)
    raw_discovered_count = Column(Integer, nullable=True, default=0)
    unique_screened_count = Column(Integer, nullable=True, default=0)
    sources_searched = Column(Integer, nullable=False, default=0)
    sources_succeeded = Column(Integer, nullable=False, default=0)

    status = Column(String(50), nullable=False, default="COMPLETED")

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    relevances = relationship("PatentRelevance", back_populates="search", lazy="selectin")


# ---------------------------------------------------------------------------
# Patent Relevance — links a patent to a product case
# ---------------------------------------------------------------------------

class PatentRelevance(Base):
    """Links a patent record to a product case with relevance assessment.

    Created when a user saves a patent finding or when the system
    automatically flags potential overlap.
    """

    __tablename__ = "patent_relevances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)
    patent_record_id = Column(Integer, ForeignKey("patent_records.id"), nullable=False)
    search_id = Column(Integer, ForeignKey("patent_searches.id"), nullable=True)
    innovation_component_id = Column(Integer, ForeignKey("innovation_components.id"), nullable=True)

    # Relevance & Evidence Basis
    relevance_level = Column(String(30), nullable=False, default="LOW")  # VERY_HIGH, HIGH, MODERATE, LOW, NOT_ANALYZED
    relevance_score = Column(Integer, nullable=True)  # 0-100
    explanation = Column(Text, nullable=True)
    evidence_reference = Column(Text, nullable=True)
    overlap_component = Column(String(100), nullable=True)  # which component overlaps
    overlap_description = Column(Text, nullable=True)

    # Grounded evidence & score breakdown
    evidence_basis = Column(String(50), nullable=True, default="TITLE_ABSTRACT")  # TITLE_ONLY, TITLE_ABSTRACT, CLAIM_TEXT
    evidence_coverage = Column(String(50), nullable=True, default="STANDARD")  # LIMITED, STANDARD, ENHANCED
    score_breakdown_json = Column(Text, nullable=True)  # JSON dict of dimension scores
    matched_components_json = Column(Text, nullable=True)  # JSON list of matched terms
    matched_queries_json = Column(Text, nullable=True)  # JSON list of queries that matched
    why_relevant = Column(Text, nullable=True)
    important_difference = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)

    # User action
    saved_by_user = Column(Boolean, nullable=False, default=False)
    user_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    product_case = relationship("ProductCase", lazy="selectin")
    patent_record = relationship("PatentRecord", lazy="selectin")
    search = relationship("PatentSearch", back_populates="relevances")


# ---------------------------------------------------------------------------
# Patent Analysis — Phase 7: Deep Analysis of a specific patent vs product
# ---------------------------------------------------------------------------

class PatentAnalysis(Base):
    """Deep analysis of a single patent record against a Product Case.

    Compares Product Passport data and Innovation Components against
    patent metadata, abstract, and claims (where available).
    This is RESEARCH decision-support, NOT legal opinion.
    """

    __tablename__ = "patent_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)
    patent_record_id = Column(Integer, ForeignKey("patent_records.id"), nullable=False)

    # Overall result
    overall_relevance = Column(String(30), nullable=False, default="INSUFFICIENT_INFORMATION")
    # HIGH_POTENTIAL_OVERLAP, MEDIUM_POTENTIAL_OVERLAP,
    # LOW_POTENTIAL_OVERLAP, INSUFFICIENT_INFORMATION
    overall_confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    summary = Column(Text, nullable=True)
    recommended_next_step = Column(Text, nullable=True)

    # Missing information tracking
    missing_information = Column(Text, nullable=True)  # JSON list of missing fields

    # Status
    status = Column(String(30), nullable=False, default="COMPLETED")

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    patent_record = relationship("PatentRecord", lazy="selectin")
    comparisons = relationship("PatentComparison", back_populates="analysis", lazy="selectin")
    claim_elements = relationship("ClaimElement", back_populates="analysis", lazy="selectin")


class PatentComparison(Base):
    """A single feature-level comparison between a product element and patent element."""

    __tablename__ = "patent_comparisons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    analysis_id = Column(Integer, ForeignKey("patent_analyses.id"), nullable=False)

    # Product side
    product_component_type = Column(String(100), nullable=False)
    product_component_label = Column(String(200), nullable=False)
    product_component_value = Column(Text, nullable=True)

    # Patent side
    patent_element = Column(String(200), nullable=False)
    patent_element_detail = Column(Text, nullable=True)

    # Comparison result
    similarity_level = Column(String(20), nullable=False, default="UNKNOWN")
    # HIGH, MEDIUM, LOW, UNKNOWN
    explanation = Column(Text, nullable=True)
    confidence = Column(String(20), nullable=True)
    evidence_type = Column(String(50), nullable=True)  # ABSTRACT, CLAIM, METADATA
    evidence_reference = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    analysis = relationship("PatentAnalysis", back_populates="comparisons")


class ClaimElement(Base):
    """A decomposed patent claim element and its comparison status."""

    __tablename__ = "claim_elements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    analysis_id = Column(Integer, ForeignKey("patent_analyses.id"), nullable=False)

    # Claim info
    claim_reference = Column(String(100), nullable=True)  # e.g. "Claim 1", "Claim 3"
    element_text = Column(Text, nullable=True)  # The specific element text
    element_type = Column(String(50), nullable=True)  # INGREDIENT, FORMULATION, PROCESS, USE

    # Comparison
    comparison_status = Column(String(30), nullable=False, default="UNKNOWN")
    # MATCH, PARTIAL_MATCH, NO_MATCH, UNABLE_TO_COMPARE
    product_match = Column(Text, nullable=True)  # What in the product matches
    explanation = Column(Text, nullable=True)
    evidence_type = Column(String(50), nullable=True)
    evidence_reference = Column(Text, nullable=True)
    confidence = Column(String(20), nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    # Relationships
    analysis = relationship("PatentAnalysis", back_populates="claim_elements")


# ---------------------------------------------------------------------------
# IP Strategy — Phase 8: Visual IP roadmap derived from all prior phases
# ---------------------------------------------------------------------------

class IPStrategy(Base):
    """IP Strategy Map for a Product Case.

    Synthesizes Product Passport, Innovation Analysis, Patent Analysis,
    and Knowledge Findings into a visual IP investigation roadmap.
    This is RESEARCH decision-support, NOT legal advice.
    """

    __tablename__ = "ip_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Summary
    total_items = Column(Integer, nullable=False, default=0)
    high_priority_count = Column(Integer, nullable=False, default=0)
    medium_priority_count = Column(Integer, nullable=False, default=0)
    low_priority_count = Column(Integer, nullable=False, default=0)
    info_needed_count = Column(Integer, nullable=False, default=0)

    # Status
    status = Column(String(30), nullable=False, default="COMPLETED")

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    items = relationship("IPStrategyItem", back_populates="strategy", lazy="selectin")


class IPStrategyItem(Base):
    """A single IP strategy recommendation for a product component.

    Maps a product component to a potential IP category, with reason,
    evidence, priority, and recommended next action.
    """

    __tablename__ = "ip_strategy_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    strategy_id = Column(Integer, ForeignKey("ip_strategies.id"), nullable=False)
    innovation_component_id = Column(Integer, ForeignKey("innovation_components.id"), nullable=True)

    # Component mapping
    component_type = Column(String(100), nullable=False)
    component_label = Column(String(200), nullable=False)
    component_value = Column(Text, nullable=True)

    # IP category
    ip_category = Column(String(100), nullable=False)
    # PATENT_REVIEW, TRADE_SECRET, TRADEMARK, DESIGN_COPYRIGHT,
    # TK_PRIOR_ART, COMBINED_IP, INFORMATION_NEEDED
    ip_route_description = Column(String(300), nullable=True)

    # Reason and evidence
    reason = Column(Text, nullable=True)
    evidence_source = Column(String(200), nullable=True)  # e.g. "Phase 5 Innovation Analysis"
    evidence_detail = Column(Text, nullable=True)

    # Priority and status
    priority = Column(String(20), nullable=False, default="MEDIUM")
    # HIGH, MEDIUM, LOW, INFORMATION_NEEDED
    confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    status = Column(String(50), nullable=False, default="RECOMMENDED")
    # RECOMMENDED, IN_PROGRESS, COMPLETED, DEFERRED

    # Next action
    next_action = Column(Text, nullable=True)

    # Links to other analyses
    patent_analysis_id = Column(Integer, ForeignKey("patent_analyses.id"), nullable=True)
    innovation_analysis_id = Column(Integer, ForeignKey("innovation_analyses.id"), nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    strategy = relationship("IPStrategy", back_populates="items")


# ---------------------------------------------------------------------------
# Regulatory Intelligence — Phase 9: Global regulatory landscape analysis
# ---------------------------------------------------------------------------

class RegulatoryProfile(Base):
    """Regulatory intelligence profile for a Product Case in a specific jurisdiction.

    Synthesizes Product Passport data with regulatory source information
    to map the regulatory landscape. This is RESEARCH decision-support,
    NOT legal advice.
    """

    __tablename__ = "regulatory_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    # Jurisdiction & classification
    jurisdiction = Column(String(10), nullable=False)  # IN, US, EU, DE, etc.
    potential_category = Column(String(200), nullable=True)  # Herbal product, supplement, etc.
    category_confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    category_reasoning = Column(Text, nullable=True)

    # Summary counts
    total_requirements = Column(Integer, nullable=False, default=0)
    relevant_count = Column(Integer, nullable=False, default=0)
    potentially_relevant_count = Column(Integer, nullable=False, default=0)
    needs_verification_count = Column(Integer, nullable=False, default=0)
    info_missing_count = Column(Integer, nullable=False, default=0)

    # Sources consulted
    sources_consulted = Column(Text, nullable=True)  # JSON list of source names
    sources_configured = Column(Integer, nullable=False, default=0)
    sources_total = Column(Integer, nullable=False, default=0)

    # Missing information
    information_gaps = Column(Text, nullable=True)  # JSON list of gap descriptions
    document_checklist = Column(Text, nullable=True)  # JSON list of checklist items

    # Status
    status = Column(String(30), nullable=False, default="COMPLETED")

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    requirements = relationship("RegulatoryRequirement", back_populates="profile", lazy="selectin")


class RegulatoryRequirement(Base):
    """A single regulatory requirement or finding for a product in a jurisdiction.

    Each requirement is backed by source evidence and clearly shows
    its applicability, confidence, and limitations.
    """

    __tablename__ = "regulatory_requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Links
    profile_id = Column(Integer, ForeignKey("regulatory_profiles.id"), nullable=False)

    # Requirement details
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # CLASSIFICATION, INGREDIENT, CLAIMS, LABELLING, DOCUMENTATION, SAFETY
    subcategory = Column(String(100), nullable=True)

    # Jurisdiction & authority
    jurisdiction = Column(String(10), nullable=False)
    authority = Column(String(200), nullable=True)
    source_name = Column(String(200), nullable=True)
    source_reference = Column(Text, nullable=True)

    # Status & confidence
    applicability = Column(String(30), nullable=False, default="POTENTIALLY_RELEVANT")
    # RELEVANT, POTENTIALLY_RELEVANT, NEEDS_VERIFICATION, INFORMATION_MISSING, NOT_ENOUGH_EVIDENCE
    confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    status = Column(String(50), nullable=False, default="FOUND")
    # FOUND, NOT_CONFIGURED, PARTIAL, MISSING

    # Evidence
    evidence_type = Column(String(50), nullable=True)  # REGULATION, GUIDANCE, OFFICIAL_SOURCE
    evidence_detail = Column(Text, nullable=True)
    effective_date = Column(String(30), nullable=True)
    publication_date = Column(String(30), nullable=True)
    retrieval_date = Column(String(30), nullable=True)

    # Limitations
    limitations = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    profile = relationship("RegulatoryProfile", back_populates="requirements")
