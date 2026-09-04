"""AYUR-INTEL — Jurisdiction Comparison Schemas (Phase 10).

Request/response schemas for the Jurisdiction Comparison endpoint.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


# -------------------------------------------------------------------
# Request
# -------------------------------------------------------------------

class JurisdictionComparisonRequest(BaseModel):
    """Request to generate a jurisdiction comparison for a Product Case."""
    jurisdictions: List[str]  # e.g. ["IN", "US", "EU"]


# -------------------------------------------------------------------
# Response — Comparison Value
# -------------------------------------------------------------------

class ComparisonValueResponse(BaseModel):
    id: str
    value: Optional[str] = None
    status: str
    confidence: Optional[str] = None
    source_name: Optional[str] = None
    evidence_detail: Optional[str] = None
    evidence_type: Optional[str] = None
    authority: Optional[str] = None
    jurisdiction: str


# -------------------------------------------------------------------
# Response — Comparison Item
# -------------------------------------------------------------------

class ComparisonItemResponse(BaseModel):
    id: str
    category: str
    normalized_label: str
    sort_order: int
    is_difference: bool
    difference_description: Optional[str] = None
    values: List[ComparisonValueResponse]


# -------------------------------------------------------------------
# Response — Comparison Jurisdiction
# -------------------------------------------------------------------

class ComparisonJurisdictionResponse(BaseModel):
    id: str
    jurisdiction: str
    jurisdiction_name: Optional[str] = None
    flag: Optional[str] = None
    confidence: Optional[str] = None
    source_coverage: Optional[str] = None
    sources_configured: int
    sources_total: int
    requirements_count: int
    category: Optional[str] = None


# -------------------------------------------------------------------
# Response — Jurisdiction Comparison
# -------------------------------------------------------------------

class JurisdictionComparisonResponse(BaseModel):
    id: str
    product_case_id: str
    product_name: Optional[str] = None
    jurisdictions: List[ComparisonJurisdictionResponse]
    items: List[ComparisonItemResponse]
    total_items: int
    jurisdictions_count: int
    differences_found: int
    information_gaps_total: int
    key_differences: Optional[List[str]] = None
    decision_support_notes: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
