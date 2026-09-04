"""AYUR-INTEL — IP Strategy Map Schemas (Phase 8).

Request/response schemas for the IP Strategy endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# -------------------------------------------------------------------
# Request
# -------------------------------------------------------------------

class IPStrategyCreateRequest(BaseModel):
    """Request to generate an IP strategy for a product case."""
    product_case_id: str


# -------------------------------------------------------------------
# Response — IP Strategy Item
# -------------------------------------------------------------------

class IPStrategyItemResponse(BaseModel):
    id: str
    component_type: str
    component_label: str
    component_value: Optional[str] = None
    ip_category: str
    ip_route_description: Optional[str] = None
    reason: Optional[str] = None
    evidence_source: Optional[str] = None
    evidence_detail: Optional[str] = None
    priority: str  # HIGH, MEDIUM, LOW, INFORMATION_NEEDED
    confidence: Optional[str] = None
    status: str
    next_action: Optional[str] = None
    created_at: str


# -------------------------------------------------------------------
# Response — IP Strategy
# -------------------------------------------------------------------

class IPStrategyResponse(BaseModel):
    id: str
    product_case_id: str
    product_name: Optional[str] = None
    total_items: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    info_needed_count: int
    status: str
    items: List[IPStrategyItemResponse]
    created_at: str
    updated_at: str


class IPStrategyItemUpdateRequest(BaseModel):
    """Update a single IP strategy item (e.g. mark status)."""
    status: Optional[str] = None
    notes: Optional[str] = None
