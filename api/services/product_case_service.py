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

from api.models import (
    ProductCase, User, CaseVersion,
    RegulatoryProfile, RegulatoryRequirement,
    PatentAnalysis, PatentComparison, ClaimElement,
    PlantDiscovery, ReviewHistory, KnowledgeFinding,
    JurisdictionComparison, ComparisonJurisdiction, ComparisonItem, ComparisonValue,
)



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
        jurisdictions=json.dumps(jurisdictions or ["IN"]),
        status="DRAFT",
        ingredients=json.dumps(ingredients) if ingredients else None,
        form=form,
        intended_use=intended_use,
        claims=json.dumps(claims) if claims else None,
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
            "ingredients": ingredients,
            "form": form,
            "intended_use": intended_use,
            "process": process,
            "claims": claims,
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
    material_fields = {"name", "stage", "jurisdictions", "ingredients", "formulation", "process", "form", "intended_use", "claims"}
    material_changed = False

    for field, value in updates.items():
        if hasattr(case, field):
            if field in ("jurisdictions", "ingredients", "claims"):
                if value is not None and not isinstance(value, str):
                    value = json.dumps(value)
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
                "ingredients": _deserialize_list(case.ingredients),
                "form": case.form,
                "intended_use": case.intended_use,
                "process": case.process,
            }),
            created_at=case.updated_at,
        )
        db.add(version)

    db.commit()
    db.refresh(case)
    logger.info("Updated product case: %s (v%d)", case.public_id, case.current_version)
    return _case_to_dict(case)


def delete_product_case(db: Session, owner: User, public_id: str) -> bool:
    """Delete a Product Case and all associated child entities."""
    from sqlalchemy import text
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
    cid = case.id
    db.expire_all()



    child_deletes = [
        "DELETE FROM regulatory_requirements WHERE profile_id IN (SELECT id FROM regulatory_profiles WHERE product_case_id = :cid)",
        "DELETE FROM regulatory_profiles WHERE product_case_id = :cid",
        "DELETE FROM claim_elements WHERE analysis_id IN (SELECT id FROM patent_analyses WHERE product_case_id = :cid)",
        "DELETE FROM patent_comparisons WHERE analysis_id IN (SELECT id FROM patent_analyses WHERE product_case_id = :cid)",
        "DELETE FROM patent_analyses WHERE product_case_id = :cid",
        "DELETE FROM comparison_jurisdictions WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
        "DELETE FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
        "DELETE FROM comparison_values WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
        "DELETE FROM jurisdiction_comparisons WHERE product_case_id = :cid",
        "DELETE FROM plant_discoveries WHERE product_case_id = :cid",
        "DELETE FROM knowledge_findings WHERE product_case_id = :cid",
        "DELETE FROM case_versions WHERE case_id = :cid",
        "DELETE FROM product_cases WHERE id = :cid",
    ]

    for stmt in child_deletes:
        try:
            db.execute(text(stmt), {"cid": cid})
        except Exception as e:
            logger.debug("Cascade delete query exception: %s", e)

    db.commit()
    logger.info("Deleted product case: %s (id=%d)", public_id, cid)
    return True

