"""AYUR-INTEL — Assistant API Schemas.

Pydantic models for the in-app RAG assistant.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AssistantAction(BaseModel):
    """Safe predefined navigation or workflow action."""

    id: str = Field(..., description="Predefined action ID, e.g. OPEN_PRODUCTS, OPEN_PATENT")
    label: str = Field(..., description="User-facing button label, e.g. 'View Products →'")
    target: str = Field(..., description="Target view or module name")
    product_id: Optional[str] = Field(None, description="Optional active product case ID for product-scoped views")


class ProductContextInfo(BaseModel):
    """Verified active product context."""

    active_product_id: Optional[str] = None
    active_product_name: Optional[str] = None
    verified: bool = False


class ChatMessageHistoryItem(BaseModel):
    """Single historical message turn for context and follow-up resolution."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., max_length=2000, description="Message text")


class AssistantChatRequest(BaseModel):
    """User message payload for the AYUR-INTEL assistant."""

    message: str = Field(..., min_length=1, max_length=2000, description="User question or prompt")
    history: Optional[List[ChatMessageHistoryItem]] = Field(default=None, description="Recent conversation turns for follow-ups")
    current_view: Optional[str] = Field("dashboard", description="Current frontend view identifier")
    active_product_id: Optional[str] = Field(None, description="Current active product case ID if selected")
    active_product_name: Optional[str] = Field(None, description="Current active product name from frontend state")


class AssistantChatResponse(BaseModel):
    """Assistant grounded response payload."""

    answer: str = Field(..., description="Grounded answer text in user's language")
    actions: List[AssistantAction] = Field(default_factory=list, description="Safe suggested navigation actions")
    sources: List[str] = Field(default_factory=list, description="Internal knowledge source labels")
    source_type: str = Field("GEMINI", description="'GEMINI' or 'FALLBACK'")
    product_context: Optional[ProductContextInfo] = Field(None, description="Active product verification status")
