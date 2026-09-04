"""AYUR-INTEL — Regulatory Intelligence API Routes (Phase 9).

Provides endpoints for generating, retrieving, and updating Regulatory Profiles.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import RegulatoryProfile, RegulatoryRequirement, ProductCase, User
from api.schemas.regulatory import (
    RegulatoryAnalysisRequest,
    RegulatoryProfileResponse,
    RegulatoryRequirementUpdateRequest,
)
from api.services.regulatory_service import generate_regulatory_analysis, profile_to_dict
from api.services.regulatory_adapter import SUPPORTED_JURISDICTIONS

logger = logging.getLogger("ayur_intel.routers.regulatory")

router = APIRouter(prefix="/api", tags=["Regulatory Intelligence"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Get or create demo user. Phase 1: minimal auth."""
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/regulatory/jurisdictions")
def list_jurisdictions():
    """List supported jurisdictions."""
    return {
        "jurisdictions": [
            {"code": code, "name": info["name"], "flag": info["flag"]}
            for code, info in SUPPORTED_JURISDICTIONS.items()
        ]
    }


@router.post("/cases/{case_id}/regulatory-analysis")
def create_regulatory_analysis(
    case_id: str,
    body: RegulatoryAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate regulatory intelligence analysis for a Product Case.

    Takes a jurisdiction code and analyzes the Product Passport data
    against regulatory sources for that jurisdiction.
    """
    if body.jurisdiction not in SUPPORTED_JURISDICTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported jurisdiction: {body.jurisdiction}. Supported: {', '.join(SUPPORTED_JURISDICTIONS.keys())}",
        )

    profile = generate_regulatory_analysis(db, user, case_id, body.jurisdiction)
    if not profile:
        raise HTTPException(status_code=404, detail="Product Case not found")

    result = profile_to_dict(profile)
    result["message"] = "Regulatory analysis generated successfully"
    return result


@router.get("/cases/{case_id}/regulatory-analysis")
def get_regulatory_analysis(
    case_id: str,
    jurisdiction: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the latest Regulatory Profile for a Product Case."""
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

    query = (
        db.query(RegulatoryProfile)
        .filter(
            RegulatoryProfile.product_case_id == case.id,
            RegulatoryProfile.owner_id == user.id,
        )
    )
    if jurisdiction:
        query = query.filter(RegulatoryProfile.jurisdiction == jurisdiction)

    profile = query.order_by(RegulatoryProfile.created_at.desc()).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No Regulatory Profile found. Generate one first.")

    return profile_to_dict(profile)


@router.patch("/regulatory-requirements/{req_id}")
def update_requirement(
    req_id: str,
    body: RegulatoryRequirementUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a regulatory requirement (e.g. mark status)."""
    req = (
        db.query(RegulatoryRequirement)
        .filter(RegulatoryRequirement.public_id == req_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    # Verify ownership
    profile = req.profile
    if not profile or profile.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if body.status:
        req.status = body.status
    if body.applicability:
        req.applicability = body.applicability

    db.commit()
    db.refresh(req)

    return {
        "id": req.public_id,
        "status": req.status,
        "applicability": req.applicability,
        "message": "Requirement updated successfully",
    }
