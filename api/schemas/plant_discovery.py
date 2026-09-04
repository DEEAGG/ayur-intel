"""AYUR-INTEL — Plant Discovery Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

class CandidateResponse(BaseModel):
    """A single candidate plant identification."""
    name: str
    scientific_name: Optional[str] = None
    confidence: int = Field(..., ge=0, le=100)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class PlantDiscoveryAnalyze(BaseModel):
    """Request to analyze an uploaded plant image."""
    pass  # Analysis is triggered on the uploaded image; no extra body needed


class PlantDiscoveryLinkCase(BaseModel):
    """Request to link a plant discovery to a Product Case."""
    product_case_id: str = Field(..., description="Public ID of the Product Case to link")


class PlantDiscoveryUpdate(BaseModel):
    """Request to update a plant discovery (e.g., notes)."""
    identification_notes: Optional[str] = None
    verification_required: Optional[bool] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class PlantDiscoveryResponse(BaseModel):
    """Schema for returning a Plant Discovery in API responses."""

    id: str = Field(..., description="Public discovery ID")
    owner_id: str
    product_case_id: Optional[str] = None
    image_filename: Optional[str] = None
    image_url: Optional[str] = None  # URL to fetch the image
    candidate_name: Optional[str] = None
    botanical_name: Optional[str] = None
    confidence: Optional[int] = None
    alternative_candidates: List[CandidateResponse] = []
    identification_notes: Optional[str] = None
    verification_required: bool = True
    provider: str = "none"
    provider_used: str = "none"  # 'plantnet', 'demo', 'unconfigured'
    fallback_reason: Optional[str] = None  # Why fallback to demo occurred
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_provider(cls, data: dict):
        """Create response with provider_used field."""
        data = dict(data)
        data['provider_used'] = data.get('provider', 'none')
        return cls(**data)


class PlantDiscoveryListResponse(BaseModel):
    """Schema for listing Plant Discoveries."""
    discoveries: List[PlantDiscoveryResponse]
    total: int


class AnalysisStatusResponse(BaseModel):
    """Schema for analysis status updates."""
    discovery_id: str
    status: str
    message: Optional[str] = None
