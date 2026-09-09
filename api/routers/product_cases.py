"""AYUR-INTEL — Product Case API routes.

Handles CRUD for Product Cases.
All routes are scoped to the authenticated user.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.schemas.product_case import (
    ErrorResponse,
    ProductCaseCreate,
    ProductCaseListResponse,
    ProductCaseResponse,
    ProductCaseUpdate,
)
from api.services.knowledge_service import get_case_findings as _get_case_findings
from api.services.product_case_service import (
    create_product_case,
    delete_product_case,
    get_or_create_demo_user,
    get_product_case,
    list_product_cases,
    update_product_case,
)
from api.services.audit_service import log_action

logger = logging.getLogger("ayur_intel.routers.product_cases")

router = APIRouter(prefix="/api/cases", tags=["Product Cases"])


# ---------------------------------------------------------------------------
# Dependency: get current user
# ---------------------------------------------------------------------------

def get_current_user(db: Session = Depends(get_db)) -> User:
    """Get the current authenticated user.

    Phase 1: returns the demo user in demo mode.
    Phase 19: will implement full auth with session cookies.
    """
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    # TODO (Phase 19): implement real session-based auth
    raise HTTPException(status_code=401, detail="Authentication required")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ProductCaseResponse,
    status_code=201,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Create a new Product Case",
)
def create_case(
    payload: ProductCaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new Product Case for the authenticated user."""
    try:
        case = create_product_case(
            db=db,
            owner=user,
            name=payload.name,
            stage=payload.stage,
            jurisdictions=payload.jurisdictions,
            ingredients=payload.ingredients,
            form=payload.form,
            intended_use=payload.intended_use,
            claims=payload.claims,
            formulation=payload.formulation,
            process=payload.process,
            brand=payload.brand,
            packaging=payload.packaging,
            notes=payload.notes,
            is_demo=bool(payload.is_demo),
        )
        log_action(
            db, action="CREATE", resource_type="PRODUCT_CASE",
            resource_id=case.get("id"), user_id=user.id,
            user_public_id=user.public_id, username=user.username,
        )
        db.commit()
        return case
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create product case: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create product case")


@router.get(
    "",
    response_model=ProductCaseListResponse,
    summary="List all Product Cases for the current user",
)
def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all Product Cases owned by the authenticated user."""
    return list_product_cases(db=db, owner=user, skip=skip, limit=limit)


from pydantic import BaseModel
from typing import Any, Dict, List

class NormalizeProductRequest(BaseModel):
    description: Optional[str] = None
    name: Optional[str] = None
    product_type: Optional[str] = None
    ingredients_text: Optional[str] = None
    ingredients: Optional[List[dict]] = None
    form: Optional[str] = None
    intended_use: Optional[str] = None
    intended_use_list: Optional[List[str]] = None
    process: Optional[str] = None
    claims: Optional[List[str]] = None
    claims_text: Optional[str] = None
    jurisdictions: Optional[List[str]] = None
    notes: Optional[str] = None


@router.post(
    "/normalize",
    summary="Normalize natural language product details into structured Product Passport",
)
def normalize_case(
    payload: NormalizeProductRequest,
    user: User = Depends(get_current_user),
):
    """Normalize user input using Gemini AI or local Ayurvedic rule engine."""
    from api.services.ai_normalization_service import normalize_product_passport
    explicit_data = payload.model_dump(exclude_unset=True)
    raw_text = payload.description or ""
    return normalize_product_passport(raw_text=raw_text, explicit_data=explicit_data)


@router.get(
    "/demo",
    response_model=ProductCaseResponse,
    summary="Get or initialize pre-filled Demo Product Case",
)
def get_demo_case_route(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the pre-filled official Ayurvedic Demo Product Case."""
    from api.services.product_case_service import get_or_create_demo_case
    return get_or_create_demo_case(db=db, owner=user)


@router.get(
    "/{case_id}",
    response_model=ProductCaseResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a Product Case by ID",
)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single Product Case. Scoped to the authenticated user."""
    case = get_product_case(db=db, owner=user, public_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return case


@router.put(
    "/{case_id}",
    response_model=ProductCaseResponse,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
    summary="Update a Product Case",
)
def update_case(
    case_id: str,
    payload: ProductCaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a Product Case. Material changes create a new version."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    case = update_product_case(db=db, owner=user, public_id=case_id, updates=updates)
    if case is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    log_action(
        db, action="UPDATE", resource_type="PRODUCT_CASE",
        resource_id=case_id, user_id=user.id,
        user_public_id=user.public_id, username=user.username,
    )
    db.commit()
    return case


@router.delete(
    "/{case_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a Product Case",
)
def delete_case(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a Product Case and all its versions."""
    deleted = delete_product_case(db=db, owner=user, public_id=case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Product Case not found")
    log_action(
        db, action="DELETE", resource_type="PRODUCT_CASE",
        resource_id=case_id, user_id=user.id,
        user_public_id=user.public_id, username=user.username,
    )
    db.commit()
    return None


@router.get(
    "/{case_id}/knowledge-findings",
    summary="Get knowledge findings for a Product Case",
)
def get_knowledge_findings(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all saved knowledge findings for a Product Case."""
    result = _get_case_findings(db=db, owner=user, case_public_id=case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result

