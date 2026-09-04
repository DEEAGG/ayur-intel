"""AYUR-INTEL — Patent Deep Analysis API routes (Phase 7)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.schemas.patent_analysis import (
    PatentAnalysisListResponse,
    PatentAnalysisRequest,
    PatentAnalysisResponse,
)
from api.services.patent_analysis_service import (
    get_analysis,
    get_case_analyses,
    run_deep_analysis,
)
from api.services.product_case_service import get_or_create_demo_user

logger = logging.getLogger("ayur_intel.routers.patent_analysis")

router = APIRouter(prefix="/api/cases", tags=["Patent Deep Analysis"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


@router.post(
    "/{case_id}/patent-analyses",
    responses={404: {"description": "Product Case or Patent not found"}},
    summary="Run deep analysis of a patent against a Product Case",
)
def create_analysis(
    case_id: str,
    payload: PatentAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a deep analysis comparing a specific patent record against
    the Product Case's passport and innovation components.

    This is RESEARCH decision-support, NOT legal opinion.
    """
    result = run_deep_analysis(
        db=db, owner=user, case_public_id=case_id,
        patent_record_id=payload.patent_record_id,
        recalculate=payload.recalculate,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case or Patent Record not found")
    return result


@router.get(
    "/{case_id}/patent-analyses",
    summary="Get all patent analyses for a Product Case",
)
def list_analyses(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all deep patent analyses saved for this Product Case."""
    analyses = get_case_analyses(db=db, owner=user, case_public_id=case_id)
    return {"analyses": analyses, "total": len(analyses)}
