"""AYUR-INTEL — AI Source Router API Routes (Phase 16)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User
from api.services.source_router_service import (
    route_question,
    get_source_registry,
)

logger = logging.getLogger("ayur_intel.routers.source_router")

router = APIRouter(prefix="/api", tags=["Source Router"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


class RouteQuestionRequest(BaseModel):
    question: str
    case_id: Optional[str] = None


@router.post("/source-router/route")
def route(
    body: RouteQuestionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Route a question to appropriate sources."""
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    result = route_question(db, user, body.question.strip(), body.case_id)
    return result


@router.get("/source-router/sources")
def get_sources(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the complete source registry."""
    return get_source_registry(db)
