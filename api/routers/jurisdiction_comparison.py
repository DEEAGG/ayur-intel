"""AYUR-INTEL — Jurisdiction Comparison API Routes (Phase 10).

Provides endpoints for generating and retrieving cross-jurisdiction comparisons.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import ProductCase, User
from api.models.jurisdiction_comparison import JurisdictionComparison
from api.schemas.jurisdiction_comparison import (
    JurisdictionComparisonRequest,
    JurisdictionComparisonResponse,
)
from api.services.jurisdiction_comparison_service import (
    generate_jurisdiction_comparison,
    comparison_to_dict,
)
from api.services.regulatory_adapter import SUPPORTED_JURISDICTIONS

logger = logging.getLogger("ayur_intel.routers.jurisdiction_comparison")

router = APIRouter(prefix="/api", tags=["Jurisdiction Comparison"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Get or create demo user. Phase 1: minimal auth."""
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/cases/{case_id}/jurisdiction-comparison")
def create_jurisdiction_comparison(
    case_id: str,
    body: JurisdictionComparisonRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a cross-jurisdiction regulatory comparison.

    Requires at least 2 jurisdiction codes. Generates Regulatory Profiles
    for each (if not already available) and then compares them.
    """
    if len(body.jurisdictions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 jurisdictions required for comparison.",
        )

    # Validate all jurisdictions
    invalid = [j for j in body.jurisdictions if j not in SUPPORTED_JURISDICTIONS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported jurisdiction(s): {', '.join(invalid)}. Supported: {', '.join(SUPPORTED_JURISDICTIONS.keys())}",
        )

    comparison = generate_jurisdiction_comparison(db, user, case_id, body.jurisdictions)
    if not comparison:
        raise HTTPException(status_code=404, detail="Product Case not found or comparison could not be generated.")

    result = comparison_to_dict(comparison)
    result["message"] = "Jurisdiction comparison generated successfully"
    return result


@router.get("/cases/{case_id}/jurisdiction-comparisons")
def list_jurisdiction_comparisons(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all jurisdiction comparisons for a Product Case."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == case_id,
            ProductCase.owner_id == user.id,
        )
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Product Case not found")

    comparisons = (
        db.query(JurisdictionComparison)
        .filter(
            JurisdictionComparison.product_case_id == case.id,
            JurisdictionComparison.owner_id == user.id,
        )
        .order_by(JurisdictionComparison.created_at.desc())
        .all()
    )

    return {
        "comparisons": [
            {
                "id": c.public_id,
                "jurisdictions_count": c.jurisdictions_count,
                "differences_found": c.differences_found,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in comparisons
        ]
    }


@router.get("/jurisdiction-comparisons/{comparison_id}")
def get_jurisdiction_comparison(
    comparison_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific jurisdiction comparison with all details."""
    comparison = (
        db.query(JurisdictionComparison)
        .filter(
            JurisdictionComparison.public_id == comparison_id,
            JurisdictionComparison.owner_id == user.id,
        )
        .first()
    )
    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    return comparison_to_dict(comparison)
