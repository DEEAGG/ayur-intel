"""AYUR-INTEL — Patent Intelligence API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.schemas.patent import (
    PatentSaveRequest,
    PatentSearchRequest,
)
from api.services.patent_service import (
    get_or_run_patent_intelligence,
    get_saved_patents,
    save_patent,
)
from api.services.product_case_service import get_or_create_demo_user

logger = logging.getLogger("ayur_intel.routers.patent")

router = APIRouter(prefix="/api/cases", tags=["Patent Intelligence"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


@router.get(
    "/{case_id}/patents",
    summary="Get Patent Intelligence analysis for a Product Case (GET-First)",
)
def get_patent_intelligence(
    case_id: str,
    force_rerun: bool = Query(False, description="Set True to force new search re-run"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve persisted Patent Intelligence for a Product Case, or run initial screening if none exists."""
    result = get_or_run_patent_intelligence(
        db=db, owner=user, case_public_id=case_id, force_rerun=force_rerun
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.post(
    "/{case_id}/patent-search",
    responses={404: {"description": "Product Case not found"}},
    summary="Run or force re-run a patent prior-art search for a Product Case",
)
def search_patents(
    case_id: str,
    payload: Optional[PatentSearchRequest] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Explicitly trigger or re-run a patent discovery search."""
    result = get_or_run_patent_intelligence(
        db=db, owner=user, case_public_id=case_id, force_rerun=True
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.get(
    "/{case_id}/saved-patents",
    summary="Get saved patent findings for a Product Case",
)
def list_saved_patents(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all patents the user has saved to this Product Case."""
    results = get_saved_patents(db=db, owner=user, case_public_id=case_id)
    return {"patents": results, "total": len(results)}


@router.post(
    "/{case_id}/patents/save",
    responses={404: {"description": "Product Case or Patent not found"}},
    summary="Save a patent record to a Product Case",
)
def save_patent_to_case(
    case_id: str,
    payload: PatentSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save a patent record to a Product Case for future reference."""
    result = save_patent(
        db=db, owner=user, case_public_id=case_id,
        patent_record_id=payload.patent_record_id,
        relevance_level=payload.relevance_level,
        explanation=payload.explanation,
        overlap_component=payload.overlap_component,
        overlap_description=payload.overlap_description,
        user_notes=payload.user_notes,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case or Patent not found")
    return result
