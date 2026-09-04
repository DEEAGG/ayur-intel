"""AYUR-INTEL — Regulatory Intelligence Schemas (Phase 9).

Request/response schemas for the Regulatory Intelligence endpoint.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


# -------------------------------------------------------------------
# Request
# -------------------------------------------------------------------

class RegulatoryAnalysisRequest(BaseModel):
    """Request to generate regulatory analysis for a product case."""
    jurisdiction: str  # IN, US, EU, DE


# -------------------------------------------------------------------
# Response — Regulatory Requirement
# -------------------------------------------------------------------

class RegulatoryRequirementResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    jurisdiction: str
    authority: Optional[str] = None
    source_name: Optional[str] = None
    source_reference: Optional[str] = None
    applicability: str
    confidence: Optional[str] = None
    status: str
    evidence_type: Optional[str] = None
    evidence_detail: Optional[str] = None
    effective_date: Optional[str] = None
    publication_date: Optional[str] = None
    limitations: Optional[str] = None
    next_action: Optional[str] = None
    created_at: str


# -------------------------------------------------------------------
# Response — Regulatory Profile
# -------------------------------------------------------------------

class RegulatoryProfileResponse(BaseModel):
    id: str
    product_case_id: str
    product_name: Optional[str] = None
    jurisdiction: str
    potential_category: Optional[str] = None
    category_confidence: Optional[str] = None
    category_reasoning: Optional[str] = None
    total_requirements: int
    relevant_count: int
    potentially_relevant_count: int
    needs_verification_count: int
    info_missing_count: int
    sources_consulted: Optional[List[str]] = None
    sources_configured: int
    sources_total: int
    information_gaps: Optional[List[str]] = None
    document_checklist: Optional[List[dict]] = None
    status: str
    requirements: List[RegulatoryRequirementResponse]
    created_at: str
    updated_at: str


class RegulatoryRequirementUpdateRequest(BaseModel):
    """Update a regulatory requirement (e.g. mark status)."""
    status: Optional[str] = None
    applicability: Optional[str] = None
    notes: Optional[str] = None
