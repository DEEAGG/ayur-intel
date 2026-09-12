"""AYUR-INTEL — Product Case Service.

Business logic for Product Case CRUD. Keeps route handlers thin.
All database operations go through this service.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
import time
from typing import List, Optional

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.models import (
    ProductCase, User, CaseVersion,
    RegulatoryProfile, RegulatoryRequirement,
    PatentAnalysis, PatentComparison, ClaimElement, PatentSearch, PatentRelevance, PatentRecord,
    PlantDiscovery, ReviewHistory, KnowledgeFinding,
    JurisdictionComparison, ComparisonJurisdiction, ComparisonItem, ComparisonValue,
)

logger = logging.getLogger("ayur_intel.product_case_service")

# ---------------------------------------------------------------------------
# In-Memory Product List Cache
# ---------------------------------------------------------------------------
_PRODUCT_LIST_CACHE: dict = {}
CACHE_TTL_SECONDS = 30


def _invalidate_product_cache(owner_id: Optional[int] = None) -> None:
    """Invalidate product list cache for a user or all users."""
    global _PRODUCT_LIST_CACHE
    if owner_id is None:
        _PRODUCT_LIST_CACHE.clear()
    else:
        prefix = f"{owner_id}_"
        keys_to_del = [k for k in _PRODUCT_LIST_CACHE if k.startswith(prefix)]
        for k in keys_to_del:
            _PRODUCT_LIST_CACHE.pop(k, None)


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
        "is_demo": bool(getattr(case, "is_demo", False)),
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
    is_demo: bool = False,
) -> dict:
    """Create a new Product Case or reuse existing to prevent duplicates."""
    clean_name = name.strip()

    # 1. Duplicate Check
    if is_demo:
        existing_demo = (
            db.query(ProductCase)
            .filter(
                (ProductCase.is_demo == True) | (ProductCase.public_id == "demo-001"),
                func.lower(func.trim(ProductCase.name)) == clean_name.lower(),
            )
            .first()
        )
        if existing_demo:
            logger.info("Reusing existing demo product case: %s", existing_demo.public_id)
            return _case_to_dict(existing_demo)
    else:
        existing_case = (
            db.query(ProductCase)
            .filter(
                ProductCase.owner_id == owner.id,
                ProductCase.is_demo == False,
                func.lower(func.trim(ProductCase.name)) == clean_name.lower(),
            )
            .first()
        )
        if existing_case:
            logger.info("Product case with name '%s' already exists (%s), returning existing.", clean_name, existing_case.public_id)
            return _case_to_dict(existing_case)

    now = datetime.now(timezone.utc)

    case = ProductCase(
        owner_id=owner.id,
        name=clean_name,
        stage=stage,
        jurisdictions=json.dumps(jurisdictions or ["IN"]),
        status="DRAFT",
        is_demo=is_demo,
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

    # Atomic insert with race condition fallback
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # Concurrent insert occurred: fetch and return canonical record
        if is_demo:
            canonical = (
                db.query(ProductCase)
                .filter(
                    (ProductCase.is_demo == True) | (ProductCase.public_id == "demo-001"),
                    func.lower(func.trim(ProductCase.name)) == clean_name.lower(),
                )
                .first()
            )
        else:
            canonical = (
                db.query(ProductCase)
                .filter(
                    ProductCase.owner_id == owner.id,
                    ProductCase.is_demo == False,
                    func.lower(func.trim(ProductCase.name)) == clean_name.lower(),
                )
                .first()
            )
        if canonical:
            logger.info("Concurrent insert handled: returning canonical product case %s", canonical.public_id)
            return _case_to_dict(canonical)
        raise

    # Create initial version snapshot
    version = CaseVersion(
        case_id=case.id,
        version_number=1,
        snapshot=json.dumps({
            "name": clean_name,
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

    try:
        db.commit()
        db.refresh(case)
    except IntegrityError:
        db.rollback()
        if is_demo:
            canonical = (
                db.query(ProductCase)
                .filter(
                    (ProductCase.is_demo == True) | (ProductCase.public_id == "demo-001"),
                    func.lower(func.trim(ProductCase.name)) == clean_name.lower(),
                )
                .first()
            )
        else:
            canonical = (
                db.query(ProductCase)
                .filter(
                    ProductCase.owner_id == owner.id,
                    ProductCase.is_demo == False,
                    func.lower(func.trim(ProductCase.name)) == clean_name.lower(),
                )
                .first()
            )
        if canonical:
            logger.info("Concurrent commit handled: returning canonical product case %s", canonical.public_id)
            return _case_to_dict(canonical)
        raise

    _invalidate_product_cache(owner.id)
    logger.info("Created product case: %s (%s, is_demo=%s)", case.public_id, clean_name, is_demo)
    return _case_to_dict(case)


def list_product_cases(
    db: Session,
    owner: User,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """List all Product Cases for a user, excluding demo products, with 30s cache."""
    cache_key = f"{owner.id}_{skip}_{limit}"
    now_ts = time.time()
    if cache_key in _PRODUCT_LIST_CACHE:
        cached_ts, cached_data = _PRODUCT_LIST_CACHE[cache_key]
        if now_ts - cached_ts < CACHE_TTL_SECONDS:
            return cached_data

    query = (
        db.query(ProductCase)
        .filter(
            ProductCase.owner_id == owner.id,
            ProductCase.is_demo == False,
        )
    )
    total = query.count()
    cases = (
        query
        .order_by(ProductCase.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = {
        "cases": [_case_to_dict(c) for c in cases],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
    _PRODUCT_LIST_CACHE[cache_key] = (now_ts, result)
    return result


def get_product_case(db: Session, owner: User, public_id: str) -> Optional[dict]:
    """Get a single Product Case by public ID, scoped to owner or demo."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == public_id,
            (ProductCase.owner_id == owner.id) | (ProductCase.is_demo == True),
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
    _invalidate_product_cache(owner.id)
    logger.info("Updated product case: %s (v%d)", case.public_id, case.current_version)
    return _case_to_dict(case)


def delete_product_case(db: Session, owner: User, public_id: str) -> bool:
    """Delete a Product Case and all associated child entities (demo cases protected)."""
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

    # Block deletion of demo products
    if getattr(case, "is_demo", False) or case.public_id == "demo-001":
        logger.warning("Blocked attempt to delete demo case: %s", public_id)
        return False

    cid = case.id
    db.expire_all()

    child_deletes = [
        # Decision snapshots
        "DELETE FROM decision_dashboard_snapshots WHERE product_case_id = :cid",
        # Monitoring
        "DELETE FROM monitoring_sources WHERE config_id IN (SELECT id FROM monitoring_configs WHERE product_case_id = :cid)",
        "DELETE FROM monitoring_alerts WHERE product_case_id = :cid",
        "DELETE FROM change_records WHERE product_case_id = :cid",
        "DELETE FROM monitoring_runs WHERE product_case_id = :cid",
        "DELETE FROM monitoring_configs WHERE product_case_id = :cid",
        # Review
        "DELETE FROM review_history WHERE review_request_id IN (SELECT id FROM review_requests WHERE product_case_id = :cid)",
        "DELETE FROM review_decisions WHERE review_request_id IN (SELECT id FROM review_requests WHERE product_case_id = :cid)",
        "DELETE FROM review_items WHERE review_request_id IN (SELECT id FROM review_requests WHERE product_case_id = :cid)",
        "DELETE FROM review_requests WHERE product_case_id = :cid",
        # Unified Evidence & Findings
        "DELETE FROM case_finding_evidence WHERE finding_id IN (SELECT id FROM case_findings WHERE product_case_id = :cid)",
        "DELETE FROM case_findings WHERE product_case_id = :cid",
        # Risks & Self Extension
        "DELETE FROM risk_assessments WHERE product_case_id = :cid",
        "DELETE FROM risk_evidence WHERE risk_id IN (SELECT id FROM risks WHERE product_case_id = :cid)",
        "DELETE FROM risk_resolutions WHERE risk_id IN (SELECT id FROM risks WHERE product_case_id = :cid)",
        "DELETE FROM risks WHERE product_case_id = :cid",
        "DELETE FROM self_extension_requests WHERE product_case_id = :cid",
        # Regulatory
        "DELETE FROM regulatory_requirements WHERE profile_id IN (SELECT id FROM regulatory_profiles WHERE product_case_id = :cid)",
        "DELETE FROM regulatory_profiles WHERE product_case_id = :cid",
        # Patents
        "DELETE FROM claim_elements WHERE analysis_id IN (SELECT id FROM patent_analyses WHERE product_case_id = :cid)",
        "DELETE FROM patent_comparisons WHERE analysis_id IN (SELECT id FROM patent_analyses WHERE product_case_id = :cid)",
        "DELETE FROM patent_analyses WHERE product_case_id = :cid",
        "DELETE FROM patent_relevances WHERE product_case_id = :cid",
        "DELETE FROM patent_searches WHERE product_case_id = :cid",
        # IP Strategy
        "DELETE FROM ip_strategy_items WHERE strategy_id IN (SELECT id FROM ip_strategies WHERE product_case_id = :cid)",
        "DELETE FROM ip_strategies WHERE product_case_id = :cid",
        # Innovation
        "DELETE FROM innovation_components WHERE analysis_id IN (SELECT id FROM innovation_analyses WHERE product_case_id = :cid)",
        "DELETE FROM innovation_analyses WHERE product_case_id = :cid",
        # Jurisdiction Comparisons
        "DELETE FROM comparison_values WHERE comparison_item_id IN (SELECT id FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid))",
        "DELETE FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
        "DELETE FROM comparison_jurisdictions WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
        "DELETE FROM jurisdiction_comparisons WHERE product_case_id = :cid",
        # Plant Discoveries & Knowledge Findings
        "DELETE FROM knowledge_evidence WHERE finding_id IN (SELECT id FROM knowledge_findings WHERE product_case_id = :cid)",
        "DELETE FROM knowledge_findings WHERE product_case_id = :cid",
        "DELETE FROM plant_discoveries WHERE product_case_id = :cid",
        # Case Versions
        "DELETE FROM case_versions WHERE case_id = :cid",
        # The Product Case itself
        "DELETE FROM product_cases WHERE id = :cid",
    ]

    try:
        for stmt in child_deletes:
            db.execute(text(stmt), {"cid": cid})
        db.commit()
        _invalidate_product_cache(owner.id)
        logger.info("Deleted product case: %s (id=%d)", public_id, cid)
        return True
    except Exception as e:
        db.rollback()
        logger.error("Failed to delete product case %s (id=%d), rolled back: %s", public_id, cid, e)
        return False


def get_or_create_demo_case(db: Session, owner: User) -> dict:
    """Get or create/migrate the pre-filled official Ayurvedic Demo Product Case."""
    demo_ingredients = [
        {
            "name": "Ashwagandha",
            "botanical": "Withania somnifera",
            "quantity": "175 mg",
            "standardization": "5% Withanolides (HPLC)",
            "status": "VERIFIED",
            "source": "Charaka Samhita Chikitsa Sthana Rasayana",
            "verification_status": "VERIFIED",
            "therapeutic_indication": "Adaptogenic stress & neuro-calming support",
        },
        {
            "name": "Jatamansi",
            "botanical": "Nardostachys jatamansi",
            "quantity": "125 mg",
            "standardization": "10% Valeranone / Jatamansone",
            "status": "VERIFIED",
            "source": "Charaka Samhita Sutra Sthana & Chikitsa Sthana",
            "verification_status": "VERIFIED",
            "therapeutic_indication": "Restorative sleep, anxiety relief & mental calm",
        },
        {
            "name": "Brahmi",
            "botanical": "Bacopa monnieri",
            "quantity": "100 mg",
            "standardization": "20% Bacosides (HPLC)",
            "status": "VERIFIED",
            "source": "Charaka Samhita Sutra Sthana Medhya",
            "verification_status": "VERIFIED",
            "therapeutic_indication": "Cognitive wellness & nocturnal stress resilience",
        },
        {
            "name": "Mandukaparni",
            "botanical": "Centella asiatica",
            "quantity": "55 mg",
            "standardization": "10% Asiaticosides",
            "status": "VERIFIED",
            "source": "Sushruta Samhita Sutra Sthana",
            "verification_status": "VERIFIED",
            "therapeutic_indication": "Nootropic calm & cellular resilience support",
        },
        {
            "name": "Shankhpushpi",
            "botanical": "Convolvulus pluricaulis",
            "quantity": "45 mg",
            "standardization": "5% Flavonoids",
            "status": "VERIFIED",
            "source": "Charaka Samhita & Astanga Hridaya",
            "verification_status": "VERIFIED",
            "therapeutic_indication": "Sleep-inducing neuro-relaxation support",
        },
    ]

    demo_claims = [
        "Sleep wellness & relaxation support",
        "Adaptogenic night-time stress support",
        "Restorative sleep & mental calm support",
    ]

    demo_process = (
        "Standardized botanical extract fractions prepared using controlled extraction "
        "and phytochemical standardization parameters, followed by staged dry blending and encapsulation "
        "into a defined 500 mg oral hard gelatin capsule. The formulation process combines hydro-ethanolic "
        "extraction, HPLC phytochemical fingerprinting, dry granulation, and uniform capsule shell filling "
        "of standardized Withania somnifera, Nardostachys jatamansi, Bacopa monnieri, Centella asiatica, "
        "and Convolvulus pluricaulis extracts."
    )

    demo_notes = (
        "A quantitative multi-botanical oral capsule formulation combining standardized extract fractions "
        "of adaptogenic, calming, and cognitive-support botanicals (Ashwagandha, Jatamansi, Brahmi, "
        "Mandukaparni, Shankhpushpi), differentiated by oral solid-dose capsule architecture, marker "
        "standardization, and formulation ratios."
    )

    demo_case = (
        db.query(ProductCase)
        .filter(
            (ProductCase.is_demo == True) | (ProductCase.public_id == "demo-001")
        )
        .first()
    )

    now = datetime.now(timezone.utc)

    if demo_case is not None:
        try:
            curr_ings = json.loads(demo_case.ingredients) if demo_case.ingredients else []
        except Exception:
            curr_ings = []

        # Check if already updated to 5-ingredient sleep showcase concept
        if len(curr_ings) == 5 and demo_case.name == "AYUR-INTEL NidraAdapt Botanical Complex":
            ensure_demo_patent_snapshot(db, demo_case)
            return _case_to_dict(demo_case)

        # Stale demo case found — Perform IN-PLACE MIGRATION of canonical demo-001
        logger.info("Migrating existing stale demo-001 case to approved showcase product specifications...")
        cid = demo_case.id

        # Invalidate stale dependent intelligence for demo-001 ONLY
        queries = [
            "DELETE FROM monitoring_alerts WHERE product_case_id = :cid",
            "DELETE FROM monitoring_configs WHERE product_case_id = :cid",
            "DELETE FROM monitoring_change_records WHERE product_case_id = :cid",
            "DELETE FROM risk_mitigation_actions WHERE risk_id IN (SELECT id FROM risks WHERE product_case_id = :cid)",
            "DELETE FROM risk_matrix_entries WHERE risk_id IN (SELECT id FROM risks WHERE product_case_id = :cid)",
            "DELETE FROM risk_assessments WHERE product_case_id = :cid",
            "DELETE FROM risks WHERE product_case_id = :cid",
            "DELETE FROM patent_relevances WHERE product_case_id = :cid",
            "DELETE FROM patent_searches WHERE product_case_id = :cid",
            "DELETE FROM patent_analyses WHERE product_case_id = :cid",
            "DELETE FROM ip_strategy_items WHERE strategy_id IN (SELECT id FROM ip_strategies WHERE product_case_id = :cid)",
            "DELETE FROM ip_strategies WHERE product_case_id = :cid",
            "DELETE FROM innovation_components WHERE analysis_id IN (SELECT id FROM innovation_analyses WHERE product_case_id = :cid)",
            "DELETE FROM innovation_analyses WHERE product_case_id = :cid",
            "DELETE FROM regulatory_profiles WHERE product_case_id = :cid",
            "DELETE FROM case_finding_evidence WHERE finding_id IN (SELECT id FROM case_findings WHERE product_case_id = :cid)",
            "DELETE FROM case_findings WHERE product_case_id = :cid",
            "DELETE FROM comparison_values WHERE comparison_item_id IN (SELECT id FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid))",
            "DELETE FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
            "DELETE FROM comparison_jurisdictions WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
            "DELETE FROM jurisdiction_comparisons WHERE product_case_id = :cid",
            "DELETE FROM knowledge_evidence WHERE finding_id IN (SELECT id FROM knowledge_findings WHERE product_case_id = :cid)",
            "DELETE FROM knowledge_findings WHERE product_case_id = :cid",
            "DELETE FROM plant_discoveries WHERE product_case_id = :cid",
            "DELETE FROM case_versions WHERE case_id = :cid",
        ]
        for q in queries:
            try:
                db.execute(text(q), {"cid": cid})
            except Exception as e:
                logger.debug("Stale demo migration cleanup note (%s): %s", q[:30], e)
        db.commit()

        # Update canonical demo-001 IN-PLACE
        demo_case.public_id = "demo-001"
        demo_case.owner_id = owner.id
        demo_case.name = "AYUR-INTEL NidraAdapt Botanical Complex"
        demo_case.stage = "IDEA"
        demo_case.jurisdictions = json.dumps(["IN"])
        demo_case.status = "DRAFT"
        demo_case.is_demo = True
        demo_case.ingredients = json.dumps(demo_ingredients)
        demo_case.form = "Hard Gelatin Capsule"
        demo_case.formulation = "Ayurvedic Proprietary Medicine"
        demo_case.intended_use = "Sleep wellness & relaxation support\nAdaptogenic night-time stress support\nRestorative sleep & mental calm support"
        demo_case.claims = json.dumps(demo_claims)
        demo_case.process = demo_process
        demo_case.brand = "AYUR-INTEL Showcase"
        demo_case.packaging = "Blister pack in outer carton with moisture barrier (500 mg per capsule)"
        demo_case.notes = demo_notes
        demo_case.current_version = 1
        demo_case.updated_at = now
        db.commit()
        db.refresh(demo_case)

        # Update initial version snapshot
        version = CaseVersion(
            case_id=demo_case.id,
            version_number=1,
            snapshot=json.dumps({
                "name": demo_case.name,
                "stage": demo_case.stage,
                "jurisdictions": ["IN"],
                "ingredients": demo_ingredients,
                "form": demo_case.form,
                "intended_use": demo_case.intended_use,
                "process": demo_case.process,
                "claims": demo_claims,
            }),
            created_at=now,
        )
        db.add(version)
        db.commit()

        logger.info("Successfully migrated demo-001 to approved showcase product specifications (in-place ID %s)", demo_case.id)
        return _case_to_dict(demo_case)

    # Create new demo-001 case if non-existent
    demo_case = ProductCase(
        public_id="demo-001",
        owner_id=owner.id,
        name="AYUR-INTEL NidraAdapt Botanical Complex",
        stage="IDEA",
        jurisdictions=json.dumps(["IN"]),
        status="DRAFT",
        is_demo=True,
        ingredients=json.dumps(demo_ingredients),
        form="Hard Gelatin Capsule",
        formulation="Ayurvedic Proprietary Medicine",
        intended_use="Sleep wellness & relaxation support\nAdaptogenic night-time stress support\nRestorative sleep & mental calm support",
        claims=json.dumps(demo_claims),
        process=demo_process,
        brand="AYUR-INTEL Showcase",
        packaging="Blister pack in outer carton with moisture barrier (500 mg per capsule)",
        notes=demo_notes,
        current_version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(demo_case)
    db.commit()
    db.refresh(demo_case)

    version = CaseVersion(
        case_id=demo_case.id,
        version_number=1,
        snapshot=json.dumps({
            "name": demo_case.name,
            "stage": demo_case.stage,
            "jurisdictions": ["IN"],
            "ingredients": demo_ingredients,
            "form": demo_case.form,
            "intended_use": demo_case.intended_use,
            "process": demo_case.process,
            "claims": demo_claims,
        }),
        created_at=now,
    )
    db.add(version)
    db.commit()

    logger.info("Successfully created demo product case: %s", demo_case.public_id)
    ensure_demo_patent_snapshot(db, demo_case)
    return _case_to_dict(demo_case)


DEMO_SHOWCASE_VERSION = "DEMO_SHOWCASE_V3_PRECOMPUTED"

def ensure_demo_patent_snapshot(db: Session, demo_case: ProductCase) -> None:
    """Seed precomputed verified showcase patent intelligence snapshot for demo-001 at startup (0 external calls)."""
    try:
        existing = (
            db.query(PatentSearch)
            .filter(PatentSearch.product_case_id == demo_case.id)
            .order_by(PatentSearch.created_at.desc())
            .first()
        )
        if existing:
            sc_raw = existing.search_concepts or ""
            if DEMO_SHOWCASE_VERSION in sc_raw:
                return

        db.execute(text("DELETE FROM patent_relevances WHERE product_case_id = :cid"), {"cid": demo_case.id})
        db.execute(text("DELETE FROM patent_searches WHERE product_case_id = :cid"), {"cid": demo_case.id})
        db.commit()
        db.expire_all()

        now = datetime.now(timezone.utc)
        query_plan = [
            {"category": "FORMULATION_OVERLAP", "query": "Withania somnifera Nardostachys jatamansi sleep", "purpose": "Search sleep compositions combining Ashwagandha and Jatamansi"},
            {"category": "ACTIVE_FRACTIONS", "query": "Withania somnifera standardized withanolides extract", "purpose": "Search standardized Ashwagandha extract literature"},
            {"category": "ANXIOLYTIC_SEDATIVE", "query": "Bacopa monnieri Convolvulus pluricaulis anxiolytic", "purpose": "Search Brahmi & Shankhpushpi neuro-functional literature"},
            {"category": "ADAPTOGENIC_RELAXATION", "query": "Centella asiatica adaptogen restorative sleep", "purpose": "Search Mandukaparni stress reduction prior-art"},
            {"category": "PROCESS_STABILITY", "query": "herbal composition enteric microencapsulation stability", "purpose": "Search capsule formulation & delivery literature"}
        ]

        query_plan_envelope = {
            "version": DEMO_SHOWCASE_VERSION,
            "analysis_mode": "VERIFIED_DEMO_SNAPSHOT",
            "source_disclosure": "Verified showcase snapshot · Built from real patent evidence retrieved through Europe PMC Patent Index",
            "plan": query_plan,
        }

        search = PatentSearch(
            public_id="srch-demo-001-v3",
            owner_id=demo_case.owner_id,
            product_case_id=demo_case.id,
            search_concepts=json.dumps(query_plan_envelope),
            jurisdictions_searched=json.dumps(["IN", "US", "EP", "WO", "GLOBAL"]),
            total_results=20,
            raw_discovered_count=73,
            unique_screened_count=54,
            sources_searched=2,
            sources_succeeded=2,
            status="COMPLETED",
            created_at=now,
        )
        db.add(search)
        db.commit()
        db.refresh(search)

        from api.services.patent_adapter import VERIFIED_PUBLIC_PATENT_CORPUS
        scores_and_explanations = [
            (85, "VERY_HIGH", "Direct formulation overlap comprising standardized extract fractions of Withania somnifera (Ashwagandha) and Nardostachys jatamansi (Jatamansi) for sleep induction and stress relief.", "WO2019016717A1 claims topical gel/oil/cream embodiments and coolant/botanical vehicle systems. AYUR-INTEL NidraAdapt is an oral hard gelatin capsule containing a 500 mg standardized dry extract matrix (Ashwagandha, Jatamansi, Brahmi, Mandukaparni, Shankhpushpi).", ["Ashwagandha (Withania somnifera)", "Jatamansi (Nardostachys jatamansi)"]),
            (82, "VERY_HIGH", "Standardized Withania somnifera extract preparation with validated anti-stress and neuroprotective bio-activity originating from Indian priority application 1775/DEL/2008.", "Patent covers single-herb Withania somnifera selective extraction method. NidraAdapt is a 5-botanical oral capsule complex combining standardized Ashwagandha with Jatamansi, Brahmi, Mandukaparni, and Shankhpushpi at defined unit dosage ratios.", ["Ashwagandha (Withania somnifera)"]),
            (78, "HIGH", "3-herb botanical combination of Withania somnifera, Nardostachys jatamansi, and Bacopa monnieri for non-narcotic sleep and anxiolytic support.", "NidraAdapt includes Mandukaparni and Shankhpushpi to form a 5-ingredient Medhya Rasayana complex with specified mg ratios.", ["Ashwagandha (Withania somnifera)", "Jatamansi (Nardostachys jatamansi)", "Brahmi (Bacopa monnieri)"]),
            (72, "HIGH", "Nanoformulation of Withania somnifera and Bacopa monnieri for enhanced oral bioavailability and central nervous system penetration.", "NidraAdapt relies on standardized dry extract ratios rather than nanoemulsion processing.", ["Ashwagandha (Withania somnifera)", "Brahmi (Bacopa monnieri)"]),
            (60, "MODERATE", "Microencapsulation process for enteric protection of sensitive botanical extract active constituents including withanolides.", "Covers delivery vessel technology rather than specific botanical active combination.", ["Ashwagandha (Withania somnifera)"]),
            (58, "MODERATE", "Supercritical fluid extraction methodology for isolating active withanolides and saponins.", "Covers solvent extraction technique rather than final oral finished dosage form.", ["Ashwagandha (Withania somnifera)", "Brahmi (Bacopa monnieri)"]),
            (55, "MODERATE", "Standardized Bacopa monnieri bio-active fraction for cognitive support.", "Focused on memory enhancement rather than sleep induction and stress adaptogen support.", ["Brahmi (Bacopa monnieri)"]),
            (52, "MODERATE", "Aqueous extract fraction of Centella asiatica for neuroprotection.", "Covers single-herb Centella extract rather than multi-botanical sleep matrix.", ["Mandukaparni (Centella asiatica)"]),
            (48, "MODERATE", "Convolvulus pluricaulis fraction for anxiolytic activity.", "Single-herb Shankhpushpi extract study.", ["Shankhpushpi (Convolvulus pluricaulis)"]),
            (45, "MODERATE", "Herbal anti-stress composition comprising Withania somnifera.", "Generic anti-stress formulation.", ["Ashwagandha (Withania somnifera)"]),
            (40, "LOW", "Method for stabilizing botanical powders.", "General excipient processing method.", []),
            (38, "LOW", "Ayurvedic herbal tea composition.", "Beverage dosage form rather than hard gelatin capsule.", []),
            (35, "LOW", "Plant extract formulation for topical application.", "Topical route of administration.", []),
            (32, "LOW", "Botanical composition for metabolic health.", "Distant therapeutic indication.", []),
            (30, "LOW", "Phytochemical isolation apparatus.", "Manufacturing equipment patent.", []),
            (28, "LOW", "Herbal dietary supplement packaging.", "Packaging design patent.", []),
            (25, "LOW", "Method for testing botanical purity.", "Analytical method patent.", []),
            (22, "LOW", "Plant tissue culture propagation.", "Agricultural propagation patent.", []),
            (20, "LOW", "Herbal syrup formulation.", "Liquid syrup dosage form.", []),
            (18, "LOW", "Fermented botanical composition.", "Fermentation process patent.", []),
        ]

        for idx, seed in enumerate(VERIFIED_PUBLIC_PATENT_CORPUS):
            pub_num = seed.get("publication_number")
            rec = db.query(PatentRecord).filter(PatentRecord.publication_number == pub_num).first()
            if not rec:
                rec = PatentRecord(
                    provider_record_id=pub_num,
                    source_name=seed.get("source_name", "VERIFIED_PATENT_CORPUS"),
                    authority=seed.get("authority", "Verified Public Patent Corpus"),
                    jurisdiction=seed.get("jurisdiction", "GLOBAL"),
                    publication_number=pub_num,
                    application_number=seed.get("application_number"),
                    patent_type=seed.get("status", "PUBLICATION"),
                    title=seed.get("title"),
                    abstract=seed.get("abstract"),
                    applicant=seed.get("applicant"),
                    inventors=json.dumps(seed.get("inventors")) if seed.get("inventors") else None,
                    priority_date=seed.get("priority_date"),
                    filing_date=seed.get("filing_date"),
                    publication_date=seed.get("publication_date"),
                    status=seed.get("status"),
                    family_id=seed.get("family_id"),
                    family_members_json=json.dumps(seed.get("family_members")) if seed.get("family_members") else None,
                    retrieved_at=now,
                    created_at=now,
                )
                db.add(rec)
                db.commit()
                db.refresh(rec)
            else:
                rec.title = seed.get("title")
                rec.applicant = seed.get("applicant")
                rec.inventors = json.dumps(seed.get("inventors")) if seed.get("inventors") else None
                rec.application_number = seed.get("application_number")
                rec.priority_date = seed.get("priority_date")
                rec.filing_date = seed.get("filing_date")
                rec.source_name = seed.get("source_name", "VERIFIED_PATENT_CORPUS")
                rec.authority = seed.get("authority", "Verified Public Patent Corpus")
                if seed.get("family_members"):
                    rec.family_members_json = json.dumps(seed.get("family_members"))
                db.commit()

            score_info = scores_and_explanations[idx] if idx < len(scores_and_explanations) else (20, "LOW", "General prior art", "Different composition", [])

            rel = PatentRelevance(
                product_case_id=demo_case.id,
                patent_record_id=rec.id,
                search_id=search.id,
                relevance_level=score_info[1],
                relevance_score=score_info[0],
                explanation=score_info[2],
                why_relevant=score_info[2],
                important_difference=score_info[3],
                evidence_basis="ABSTRACT-LEVEL SCREENING",
                evidence_coverage="STANDARD",
                score_breakdown_json=json.dumps({
                    "technological_overlap": int(score_info[0] * 0.9),
                    "ingredient_overlap": int(score_info[0] * 0.95),
                    "formulation_process_overlap": int(score_info[0] * 0.85),
                    "claim_concept_overlap": int(score_info[0] * 0.88),
                }),
                matched_components_json=json.dumps(score_info[4]),
                matched_queries_json=json.dumps(["Withania somnifera sleep adaptogen"]),
                created_at=now,
                updated_at=now,
            )
            db.add(rel)

        db.commit()
        logger.info("Successfully seeded precomputed verified demo patent snapshot for case %s", demo_case.public_id)
    except Exception as e:
        logger.warning("Demo patent snapshot seeding error: %s", e)
        db.rollback()

