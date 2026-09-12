"""AYUR-INTEL — Knowledge Engine Pydantic schemas.

Request/response validation for the Knowledge & Traditional Knowledge API.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Knowledge categories
# ---------------------------------------------------------------------------

VALID_CATEGORIES = (
    "TRADITIONAL_USE",
    "PREPARATION",
    "BOTANICAL",
    "SAFETY",
    "DOSAGE",
    "INTERACTION",
    "HISTORY",
    "CULTURAL",
    "PHARMACOLOGY",
    "OTHER",
)

CONFIDENCE_LEVELS = ("HIGH", "MODERATE", "LOW", "CONFLICTING", "UNKNOWN")
RELEVANCE_LEVELS = ("HIGH", "MODERATE", "LOW")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class KnowledgeSearchRequest(BaseModel):
    """Schema for knowledge search requests."""

    query: Optional[str] = Field(default="", max_length=500, description="Search query")
    plant_name: Optional[str] = Field(None, max_length=300, description="Common plant name")
    botanical_name: Optional[str] = Field(None, max_length=300, description="Scientific name")
    category: Optional[str] = Field(None, description="Knowledge category filter")
    jurisdiction: Optional[str] = Field(None, max_length=50, description="Jurisdiction filter")
    limit: int = Field(default=20, ge=1, le=50, description="Max results per source")


class KnowledgeSaveRequest(BaseModel):
    """Schema for saving a finding to a Product Case."""

    product_case_id: str = Field(..., description="Public ID of the Product Case")
    plant_discovery_id: Optional[str] = Field(None, description="Public ID of a Plant Discovery")

    # Finding data
    title: str = Field(..., min_length=1, max_length=500)
    summary: Optional[str] = None
    category: Optional[str] = None
    plant_name: Optional[str] = None
    botanical_name: Optional[str] = None
    traditional_name: Optional[str] = None
    source_name: Optional[str] = None
    source_authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    confidence: Optional[str] = None
    relevance: Optional[str] = None
    evidence_locator: Optional[str] = None
    excerpt: Optional[str] = None
    source_identifier: Optional[str] = None
    publication_date: Optional[str] = None
    retrieval_date: Optional[str] = None
    source_version: Optional[str] = None
    limitations: Optional[str] = None
    is_conflicting: bool = False
    conflicting_details: Optional[str] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SourceResponse(BaseModel):
    """Schema for a source in API responses."""

    id: str
    name: str
    authority: Optional[str] = None
    source_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    is_configured: bool = False
    is_active: bool = True
    capabilities: List[str] = []

    model_config = {"from_attributes": True}


class EvidenceResponse(BaseModel):
    """Schema for a single evidence record."""

    id: str
    title: Optional[str] = None
    source_identifier: Optional[str] = None
    evidence_locator: Optional[str] = None
    excerpt: Optional[str] = None
    confidence: Optional[str] = None
    publication_date: Optional[str] = None
    retrieval_date: Optional[str] = None
    source_version: Optional[str] = None

    model_config = {"from_attributes": True}


class KnowledgeFindingResponse(BaseModel):
    """Schema for returning a Knowledge Finding in API responses."""

    id: str
    title: str
    summary: Optional[str] = None
    category: Optional[str] = None
    plant_name: Optional[str] = None
    botanical_name: Optional[str] = None
    traditional_name: Optional[str] = None

    # Source
    source_name: Optional[str] = None
    source_authority: Optional[str] = None
    jurisdiction: Optional[str] = None

    # Evidence
    confidence: Optional[str] = None
    relevance: Optional[str] = None
    evidence_locator: Optional[str] = None
    evidence_excerpt: Optional[str] = None
    publication_date: Optional[str] = None
    retrieval_date: Optional[str] = None

    # Conflict info
    is_conflicting: bool = False
    conflicting_details: Optional[str] = None
    limitations: Optional[str] = None

    # Links
    product_case_id: Optional[str] = None
    plant_discovery_id: Optional[str] = None
    source_id: Optional[str] = None
    evidence: List[EvidenceResponse] = []

    # Status
    status: str = "RETRIEVED"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceSearchResultResponse(BaseModel):
    """Schema for a search result from a source adapter."""

    title: str
    summary: Optional[str] = None
    plant_name: Optional[str] = None
    botanical_name: Optional[str] = None
    traditional_name: Optional[str] = None
    category: Optional[str] = None
    source_name: str = ""
    source_authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    confidence: str = "UNKNOWN"
    relevance: str = "MODERATE"
    evidence_locator: Optional[str] = None
    excerpt: Optional[str] = None
    publication_date: Optional[str] = None
    limitations: Optional[str] = None
    is_conflicting: bool = False
    conflicting_details: Optional[str] = None


class SourceSearchResponseSchema(BaseModel):
    """Schema for a source adapter search response."""

    source_name: str
    source_authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    is_configured: bool = True
    message: Optional[str] = None
    total: int = 0
    results: List[SourceSearchResultResponse] = []
    retrieval_date: str = ""


class KnowledgeSearchResponse(BaseModel):
    """Schema for the aggregated knowledge search response."""

    query: str
    sources: List[SourceSearchResponseSchema] = []
    total_results: int = 0
    has_configured_sources: bool = False


class KnowledgeFindingListResponse(BaseModel):
    """Schema for listing Knowledge Findings."""

    findings: List[KnowledgeFindingResponse]
    total: int


class SourceListResponse(BaseModel):
    """Schema for listing Sources."""

    sources: List[SourceResponse]
    total: int
