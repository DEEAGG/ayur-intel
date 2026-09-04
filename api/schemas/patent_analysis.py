"""AYUR-INTEL — Patent Deep Analysis Pydantic schemas (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Request schemas
# -------------------------------------------------------------------

class PatentAnalysisRequest(BaseModel):
    """Request to run a deep analysis of a patent against a Product Case."""
    patent_record_id: str
    recalculate: bool = Field(default=False, description="Force recalculation")


# -------------------------------------------------------------------
# Response schemas
# -------------------------------------------------------------------

class PatentComparisonResponse(BaseModel):
    id: str
    product_component_type: str
    product_component_label: str
    product_component_value: Optional[str] = None
    patent_element: str
    patent_element_detail: Optional[str] = None
    similarity_level: str = "UNKNOWN"
    explanation: Optional[str] = None
    confidence: Optional[str] = None
    evidence_type: Optional[str] = None
    evidence_reference: Optional[str] = None

    model_config = {"from_attributes": True}


class ClaimElementResponse(BaseModel):
    id: str
    claim_reference: Optional[str] = None
    element_text: Optional[str] = None
    element_type: Optional[str] = None
    comparison_status: str = "UNKNOWN"
    product_match: Optional[str] = None
    explanation: Optional[str] = None
    evidence_type: Optional[str] = None
    evidence_reference: Optional[str] = None
    confidence: Optional[str] = None

    model_config = {"from_attributes": True}


class PatentAnalysisResponse(BaseModel):
    id: str
    product_case_id: str
    patent_record_id: str
    overall_relevance: str = "INSUFFICIENT_INFORMATION"
    overall_confidence: Optional[str] = None
    summary: Optional[str] = None
    recommended_next_step: Optional[str] = None
    missing_information: Optional[List[str]] = None
    comparisons: List[PatentComparisonResponse] = []
    claim_elements: List[ClaimElementResponse] = []
    # Patent metadata for display
    patent_title: Optional[str] = None
    patent_number: Optional[str] = None
    patent_jurisdiction: Optional[str] = None
    patent_status: Optional[str] = None
    patent_abstract: Optional[str] = None
    patent_applicant: Optional[str] = None
    # Product context
    product_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatentAnalysisListResponse(BaseModel):
    analyses: List[PatentAnalysisResponse] = []
    total: int = 0
