"""AYUR-INTEL — In-App RAG Assistant API Router.

Provides conversational intelligence, feature guidance, and safe navigation actions.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from api.services.assistant_service import process_assistant_chat

logger = logging.getLogger("ayur_intel.routers.assistant")

router = APIRouter(prefix="/api/assistant", tags=["Assistant"])


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with AYUR-INTEL In-App RAG Assistant",
)
def chat_with_assistant(
    request: AssistantChatRequest,
    db: Session = Depends(get_db),
) -> AssistantChatResponse:
    """Process a user query, retrieve relevant AYUR-INTEL knowledge chunks,

    and return a grounded response with safe navigation actions.
    """
    try:
        result = process_assistant_chat(
            db=db,
            message=request.message,
            history=request.history,
            current_view=request.current_view or "dashboard",
            active_product_id=request.active_product_id,
            active_product_name=request.active_product_name,
        )
        return AssistantChatResponse(**result)
    except Exception as e:
        logger.error("Error processing assistant chat: %s", e, exc_info=True)
        # Return graceful fallback on any unexpected error
        return AssistantChatResponse(
            answer="AYUR-INTEL Assistant is currently operating in offline mode. You can explore products, run patent searches, or view monitoring via the sidebar.",
            actions=[],
            sources=["AYUR-INTEL Platform & Mission"],
            source_type="FALLBACK",
            product_context=None,
        )
