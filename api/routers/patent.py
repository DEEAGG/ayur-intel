"""AYUR-INTEL — Patent Intelligence API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.schemas.patent import (
    PatentRecordResponse,
    PatentSaveRequest,
    PatentSearchListResponse,
    PatentSearchRequest,
    PatentSearchResponse,
)
from api.services.patent_service import (
    get_saved_patents,
    run_patent_search,
    save_patent,
)
from api.services.product_case_service import get_or_create_demo_user

logger = logging.getLogger("ayur_intel.routers.patent")

router = APIRouter(prefix="/api/cases", tags=["Patent Intelligence"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


@router.post(
    "/{case_id}/patent-search",
    responses={404: {"description": "Product Case not found"}},
    summary="Run a patent search for a Product Case",
)
def search_patents(
    case_id: str,
    payload: PatentSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search patent sources for relevant records. This is patent DISCOVERY,
    not patentability determination."""
    result = run_patent_search(
        db=db, owner=user, case_public_id=case_id,
        jurisdictions=payload.jurisdictions, limit=payload.limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.get(
    "/{case_id}/patents",
    summary="Get saved patent findings for a Product Case",
)
def get_patents(
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
