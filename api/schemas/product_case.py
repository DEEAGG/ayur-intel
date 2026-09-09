"""AYUR-INTEL — Product Case Pydantic schemas.

Request/response validation for the Product Case API.
Follows the data_contract.md ProductCase structure.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums (as string constants — Pydantic v2 style)
# ---------------------------------------------------------------------------

VALID_STAGES = ("IDEA", "RND", "PILOT", "PRE_LAUNCH", "COMMERCIAL")
VALID_STATUSES = ("DRAFT", "ANALYZING", "COMPLETED", "ARCHIVED")

# Common jurisdiction codes (not exhaustive)
KNOWN_JURISDICTIONS = ("IN", "US", "EU", "DE", "GB", "JP", "AU", "CA", "BR")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ProductCaseCreate(BaseModel):
    """Schema for creating a new Product Case."""

    name: str = Field(..., min_length=1, max_length=300, description="Product name")
    stage: str = Field(
        default="IDEA",
        description="Development stage",
    )
    jurisdictions: List[str] = Field(
        default_factory=lambda: ["IN"],
        description="Target jurisdiction codes",
    )
    # Optional fields (can be filled later)
    ingredients: Optional[List[dict]] = None
    form: Optional[str] = None
    intended_use: Optional[str] = None
    claims: Optional[List[str]] = None
    formulation: Optional[str] = None
    process: Optional[str] = None
    brand: Optional[str] = None
    packaging: Optional[str] = None
    notes: Optional[str] = None

    def model_post_init(self, __context) -> None:
        """Validate stage and jurisdictions after initialization."""
        if self.stage not in VALID_STAGES:
            raise ValueError(
                f"Invalid stage '{self.stage}'. Must be one of: {', '.join(VALID_STAGES)}"
            )
        for j in self.jurisdictions:
            if j not in KNOWN_JURISDICTIONS:
                raise ValueError(
                    f"Unknown jurisdiction '{j}'. Known: {', '.join(KNOWN_JURISDICTIONS)}"
                )


class ProductCaseUpdate(BaseModel):
    """Schema for updating an existing Product Case."""

    name: Optional[str] = Field(None, min_length=1, max_length=300)
    stage: Optional[str] = None
    jurisdictions: Optional[List[str]] = None
    status: Optional[str] = None
    ingredients: Optional[List[dict]] = None
    form: Optional[str] = None
    intended_use: Optional[str] = None
    claims: Optional[List[str]] = None
    formulation: Optional[str] = None
    process: Optional[str] = None
    brand: Optional[str] = None
    packaging: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ProductCaseResponse(BaseModel):
    """Schema for returning a Product Case in API responses."""

    id: str = Field(..., description="Public case ID")
    name: str
    stage: str
    jurisdictions: List[str]
    status: str
    is_demo: bool = False
    owner_id: str
    ingredients: Optional[List[dict]] = None
    form: Optional[str] = None
    intended_use: Optional[str] = None
    claims: Optional[List[str]] = None
    formulation: Optional[str] = None
    process: Optional[str] = None
    brand: Optional[str] = None
    packaging: Optional[str] = None
    notes: Optional[str] = None
    current_version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductCaseListResponse(BaseModel):
    """Schema for listing Product Cases."""

    cases: List[ProductCaseResponse]
    total: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
