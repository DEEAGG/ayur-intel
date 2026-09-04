"""AYUR-INTEL — Innovation Decomposition API routes.

Handles creating, retrieving, and updating innovation analyses.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.schemas.innovation import (
    InnovationAnalysisCreate,
    InnovationAnalysisResponse,
    InnovationComponentUpdate,
)
from api.services.innovation_service import (
    create_analysis,
    get_analysis,
    update_component,
)
from api.services.product_case_service import get_or_create_demo_user

logger = logging.getLogger("ayur_intel.routers.innovation")

router = APIRouter(prefix="/api/cases", tags=["Innovation Decomposition"])


# -------------------------------------------------------------------
# Dependency: get current user
# -------------------------------------------------------------------

def get_current_user(db: Session = Depends(get_db)) -> User:
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@router.post(
    "/{case_id}/innovation-analysis",
    status_code=201,
    responses={404: {"description": "Product Case not found"}},
    summary="Create an innovation analysis for a Product Case",
)
def create_innovation_analysis(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Decompose a Product Case into innovation components and classify each.

    This is a decision-support tool. Classifications are preliminary
    research assessments, NOT legal conclusions.
    """
    result = create_analysis(db=db, owner=user, case_public_id=case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.get(
    "/{case_id}/innovation-analysis",
    responses={404: {"description": "No analysis found"}},
    summary="Get the latest innovation analysis for a Product Case",
)
def get_innovation_analysis(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the latest innovation analysis. Returns 404 if no analysis exists."""
    result = get_analysis(db=db, owner=user, case_public_id=case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No innovation analysis found for this case")
    return result


@router.patch(
    "/innovation-components/{component_id}",
    responses={404: {"description": "Component not found"}},
    summary="Update a single innovation component",
)
def update_innovation_component(
    component_id: str,
    payload: InnovationComponentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a component's classification, explanation, or investigation status."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = update_component(db=db, owner=user, component_public_id=component_id, updates=updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Component not found")
    return result
