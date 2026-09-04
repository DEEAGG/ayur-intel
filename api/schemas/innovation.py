"""AYUR-INTEL — Innovation Decomposition Pydantic schemas.

Request/response validation for the Innovation Analysis API.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

VALID_CLASSIFICATIONS = (
    "TRADITIONAL_OR_KNOWN",
    "POTENTIALLY_DIFFERENTIATED",
    "INSUFFICIENT_INFORMATION",
    "REQUIRES_INVESTIGATION",
)

VALID_CONFIDENCE = ("LOW", "MEDIUM", "HIGH")
VALID_DATA_ORIGINS = ("USER_PROVIDED", "SOURCE_SUPPORTED", "SYSTEM_DERIVED", "UNKNOWN")
VALID_COMPONENT_TYPES = (
    "INGREDIENT", "COMBINATION", "FORMULATION", "PROCESS", "EXTRACTION",
    "PRODUCT_FORM", "INTENDED_USE", "CLAIMS", "BRAND", "PACKAGING",
)


# -------------------------------------------------------------------
# Request schemas
# -------------------------------------------------------------------

class InnovationAnalysisCreate(BaseModel):
    """Request to create an innovation analysis for a Product Case."""
    pass  # No body needed — reads from existing case data


class InnovationComponentUpdate(BaseModel):
    """Update a single innovation component (e.g., mark as verified)."""
    classification: Optional[str] = None
    explanation: Optional[str] = None
    confidence: Optional[str] = None
    investigation_required: Optional[bool] = None


# -------------------------------------------------------------------
# Response schemas
# -------------------------------------------------------------------

class InnovationComponentResponse(BaseModel):
    """Schema for a single innovation component in API responses."""

    id: str
    component_type: str
    component_label: str
    component_value: Optional[str] = None
    sort_order: int = 0

    classification: str
    explanation: Optional[str] = None
    confidence: Optional[str] = None

    data_origin: Optional[str] = None
    evidence_summary: Optional[str] = None

    potential_ip_route: Optional[str] = None
    investigation_required: bool = False

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InnovationAnalysisResponse(BaseModel):
    """Schema for an innovation analysis in API responses."""

    id: str
    product_case_id: str
    status: str

    total_components: int
    traditional_count: int
    differentiated_count: int
    investigation_count: int
    insufficient_count: int

    components: List[InnovationComponentResponse] = []

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
