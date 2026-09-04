"""AYUR-INTEL — Product Case Service.

Business logic for Product Case CRUD. Keeps route handlers thin.
All database operations go through this service.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from api.models.models import ProductCase, User, CaseVersion

logger = logging.getLogger("ayur_intel.product_case_service")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_list(value) -> str:
    """Serialize a Python list to JSON string for storage."""
    if value is None:
        return "[]"
    return json.dumps(value)


def _deserialize_list(value: str) -> list:
    """Deserialize a JSON string to Python list."""
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _case_to_dict(case: ProductCase) -> dict:
    """Convert a ProductCase ORM object to a dict for API response."""
    return {
        "id": case.public_id,
        "name": case.name,
        "stage": case.stage,
        "jurisdictions": _deserialize_list(case.jurisdictions),
        "status": case.status,
        "owner_id": case.owner.public_id if case.owner else "",
        "ingredients": _deserialize_list(case.ingredients) if case.ingredients else None,
        "form": case.form,
        "intended_use": case.intended_use,
        "claims": _deserialize_list(case.claims) if case.claims else None,
        "formulation": case.formulation,
        "process": case.process,
        "brand": case.brand,
        "packaging": case.packaging,
        "notes": case.notes,
        "current_version": case.current_version,
        "created_at": case.created_at.isoformat() if case.created_at else "",
        "updated_at": case.updated_at.isoformat() if case.updated_at else "",
    }


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def get_or_create_demo_user(db: Session) -> User:
    """Get or create the demo user for development mode.

    In production, this would be replaced by real auth (Phase 19).
    """
    demo_user = db.query(User).filter(User.username == "demo").first()
    if demo_user is None:
        demo_user = User(
            username="demo",
            display_name="Demo User",
            email="demo@ayur-intel.local",
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        logger.info("Created demo user: %s", demo_user.public_id)
    return demo_user


def create_product_case(
    db: Session,
    owner: User,
    name: str,
    stage: str = "IDEA",
    jurisdictions: Optional[List[str]] = None,
    ingredients: Optional[List[dict]] = None,
    form: Optional[str] = None,
    intended_use: Optional[str] = None,
    claims: Optional[List[str]] = None,
    formulation: Optional[str] = None,
    process: Optional[str] = None,
    brand: Optional[str] = None,
    packaging: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Create a new Product Case and its initial version snapshot."""
    now = datetime.now(timezone.utc)

    case = ProductCase(
        owner_id=owner.id,
        name=name,
        stage=stage,
        jurisdictions=_serialize_list(jurisdictions or ["IN"]),
        status="DRAFT",
        ingredients=_serialize_list(ingredients) if ingredients else None,
        form=form,
        intended_use=intended_use,
        claims=_serialize_list(claims) if claims else None,
        formulation=formulation,
        process=process,
        brand=brand,
        packaging=packaging,
        notes=notes,
        current_version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Create initial version snapshot
    version = CaseVersion(
        case_id=case.id,
        version_number=1,
        snapshot=json.dumps({
            "name": name,
            "stage": stage,
            "jurisdictions": jurisdictions or ["IN"],
        }),
        created_at=now,
    )
    db.add(version)
    db.commit()

    logger.info("Created product case: %s (%s)", case.public_id, name)
    return _case_to_dict(case)


def list_product_cases(
    db: Session,
    owner: User,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    """List all Product Cases for a user."""
    query = db.query(ProductCase).filter(ProductCase.owner_id == owner.id)
    total = query.count()
    cases = (
        query
        .order_by(ProductCase.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "cases": [_case_to_dict(c) for c in cases],
        "total": total,
    }


def get_product_case(db: Session, owner: User, public_id: str) -> Optional[dict]:
    """Get a single Product Case by public ID, scoped to owner."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == public_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return None
    return _case_to_dict(case)


def update_product_case(
    db: Session,
    owner: User,
    public_id: str,
    updates: dict,
) -> Optional[dict]:
    """Update a Product Case. Creates a new version if material facts change."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == public_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return None

    # Track which material fields changed
    material_fields = {"name", "stage", "jurisdictions", "ingredients", "formulation", "process"}
    material_changed = False

    for field, value in updates.items():
        if value is not None and hasattr(case, field):
            old_value = getattr(case, field)
            if field in ("jurisdictions", "ingredients", "claims"):
                value = _serialize_list(value)
            setattr(case, field, value)
            if field in material_fields:
                material_changed = True

    case.updated_at = datetime.now(timezone.utc)

    # Create new version if material facts changed
    if material_changed:
        case.current_version += 1
        version = CaseVersion(
            case_id=case.id,
            version_number=case.current_version,
            snapshot=json.dumps({
                "name": case.name,
                "stage": case.stage,
                "jurisdictions": _deserialize_list(case.jurisdictions),
            }),
            created_at=case.updated_at,
        )
        db.add(version)

    db.commit()
    db.refresh(case)
    logger.info("Updated product case: %s (v%d)", case.public_id, case.current_version)
    return _case_to_dict(case)


def delete_product_case(db: Session, owner: User, public_id: str) -> bool:
    """Delete a Product Case and its versions."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == public_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return False

    # Delete versions first
    db.query(CaseVersion).filter(CaseVersion.case_id == case.id).delete()
    db.delete(case)
    db.commit()
    logger.info("Deleted product case: %s", public_id)
    return True
