"""AYUR-INTEL — Patent Intelligence Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Request schemas
# -------------------------------------------------------------------

class PatentSearchRequest(BaseModel):
    """Request to run a patent search for a Product Case."""
    jurisdictions: List[str] = Field(
        default_factory=lambda: ["IN", "US", "EU", "GLOBAL"],
        description="Jurisdictions to search",
    )
    limit: int = Field(default=20, ge=1, le=50)


class PatentSaveRequest(BaseModel):
    """Request to save a patent record to a Product Case."""
    patent_record_id: str
    relevance_level: Optional[str] = None
    explanation: Optional[str] = None
    overlap_component: Optional[str] = None
    overlap_description: Optional[str] = None
    user_notes: Optional[str] = None


# -------------------------------------------------------------------
# Response schemas
# -------------------------------------------------------------------

class PatentRecordResponse(BaseModel):
    id: str
    source_name: Optional[str] = None
    authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    publication_number: Optional[str] = None
    application_number: Optional[str] = None
    patent_type: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    applicant: Optional[str] = None
    inventors: Optional[List[str]] = None
    priority_date: Optional[str] = None
    filing_date: Optional[str] = None
    publication_date: Optional[str] = None
    status: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class PatentSearchResultResponse(BaseModel):
    """A single patent result with relevance info."""
    patent: PatentRecordResponse
    relevance_level: str = "LOW"
    relevance_score: int = 0
    explanation: Optional[str] = None
    overlap_component: Optional[str] = None
    overlap_description: Optional[str] = None


class PatentSearchResponse(BaseModel):
    """Response from a patent search."""
    search_id: str
    product_case_id: str
    search_concepts: List[str] = []
    jurisdictions_searched: List[str] = []
    sources_searched: int = 0
    sources_succeeded: int = 0
    total_results: int = 0
    results: List[PatentSearchResultResponse] = []
    source_messages: List[dict] = []
    created_at: datetime


class PatentSearchListResponse(BaseModel):
    searches: List[dict]
    total: int


class SavedPatentResponse(BaseModel):
    id: str
    patent: PatentRecordResponse
    relevance_level: str
    explanation: Optional[str] = None
    overlap_component: Optional[str] = None
    user_notes: Optional[str] = None
    saved_by_user: bool
    created_at: datetime

    model_config = {"from_attributes": True}
