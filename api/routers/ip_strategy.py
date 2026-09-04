"""AYUR-INTEL — IP Strategy Map API Routes (Phase 8).

Provides endpoints for generating, retrieving, and updating IP Strategy Maps.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import IPStrategy, IPStrategyItem, ProductCase, User
from api.schemas.ip_strategy import (
    IPStrategyCreateRequest,
    IPStrategyItemUpdateRequest,
    IPStrategyResponse,
)
from api.services.ip_strategy_service import generate_ip_strategy, strategy_to_dict

logger = logging.getLogger("ayur_intel.routers.ip_strategy")

router = APIRouter(prefix="/api", tags=["IP Strategy"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Get or create demo user. Phase 1: minimal auth."""
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/cases/{case_id}/ip-strategy")
def create_ip_strategy(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate an IP Strategy Map for a Product Case.

    Reads data from Product Passport, Innovation Analysis, Patent Analysis,
    and Knowledge Findings to produce a visual IP investigation roadmap.
    """
    strategy = generate_ip_strategy(db, user, case_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Product Case not found")

    result = strategy_to_dict(strategy)
    result["message"] = "IP Strategy generated successfully"
    return result


@router.get("/cases/{case_id}/ip-strategy")
def get_ip_strategy(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the latest IP Strategy for a Product Case."""
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

    strategy = (
        db.query(IPStrategy)
        .filter(
            IPStrategy.product_case_id == case.id,
            IPStrategy.owner_id == user.id,
        )
        .order_by(IPStrategy.created_at.desc())
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="No IP Strategy found. Generate one first.")

    return strategy_to_dict(strategy)


@router.patch("/ip-strategy-items/{item_id}")
def update_strategy_item(
    item_id: str,
    body: IPStrategyItemUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update an IP Strategy Item (e.g. mark status)."""
    item = (
        db.query(IPStrategyItem)
        .filter(IPStrategyItem.public_id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Strategy item not found")

    # Verify ownership via strategy → product_case → owner
    strategy = item.strategy
    if not strategy or strategy.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if body.status:
        item.status = body.status

    db.commit()
    db.refresh(item)

    return {
        "id": item.public_id,
        "status": item.status,
        "message": "Item updated successfully",
    }
