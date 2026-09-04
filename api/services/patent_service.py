"""AYUR-INTEL — Patent Intelligence Service.

Searches patent sources, normalizes results, ranks relevance,
and saves findings to Product Cases. This is PATENT DISCOVERY,
not patentability determination.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from api.models.models import (
    InnovationAnalysis,
    InnovationComponent,
    PatentRecord,
    PatentRelevance,
    PatentSearch,
    ProductCase,
    User,
)
from api.services.patent_adapter import (
    PatentResult,
    PatentSourceRegistry,
    get_patent_registry,
)

logger = logging.getLogger("ayur_intel.patent_service")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _deserialize_list(value: str) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _record_to_dict(rec: PatentRecord) -> dict:
    inventors = None
    if rec.inventors:
        try:
            inventors = json.loads(rec.inventors)
        except (json.JSONDecodeError, TypeError):
            inventors = [rec.inventors] if rec.inventors else None

    return {
        "id": rec.public_id,
        "source_name": rec.source_name,
        "authority": rec.authority,
        "jurisdiction": rec.jurisdiction,
        "publication_number": rec.publication_number,
        "application_number": rec.application_number,
        "patent_type": rec.patent_type,
        "title": rec.title,
        "abstract": rec.abstract,
        "applicant": rec.applicant,
        "inventors": inventors,
        "priority_date": rec.priority_date,
        "filing_date": rec.filing_date,
        "publication_date": rec.publication_date,
        "status": rec.status,
        "source_url": rec.source_url,
        "retrieved_at": rec.retrieved_at.isoformat() if rec.retrieved_at else "",
        "created_at": rec.created_at.isoformat() if rec.created_at else "",
    }


# -------------------------------------------------------------------
# Search concept generation
# -------------------------------------------------------------------

def _generate_search_concepts(case: ProductCase, components: List[InnovationComponent]) -> List[str]:
    """Generate patent search concepts from Product Case + Innovation Components."""
    concepts = []

    # Product name
    if case.name:
        concepts.append(case.name)

    # Ingredients
    ingredients = _deserialize_list(case.ingredients) if case.ingredients else []
    for ing in ingredients:
        name = ing.get("name", "") if isinstance(ing, dict) else str(ing)
        if name.strip():
            concepts.append(name.strip())
            # Also search botanical name if in parentheses
            if "(" in name and ")" in name:
                botanical = name.split("(")[1].split(")")[0].strip()
                if botanical:
                    concepts.append(botanical)

    # Combination of ingredients
    ing_names = []
    for ing in ingredients:
        name = ing.get("name", "") if isinstance(ing, dict) else str(ing)
        if name.strip():
            # Use just the common name part
            simple = name.split("(")[0].strip()
            ing_names.append(simple)
    if len(ing_names) >= 2:
        concepts.append(" + ".join(ing_names))

    # Formulation
    if case.formulation:
        concepts.append(case.formulation)

    # Process
    if case.process:
        concepts.append(case.process)

    # Product form
    if case.form:
        concepts.append(case.form)

    # Innovation components that are differentiated or need investigation
    if components:
        for comp in components:
            if comp.classification in ("POTENTIALLY_DIFFERENTIATED", "REQUIRES_INVESTIGATION"):
                if comp.component_value and comp.component_value not in concepts:
                    concepts.append(comp.component_value)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in concepts:
        c_lower = c.lower().strip()
        if c_lower not in seen and len(c_lower) > 1:
            seen.add(c_lower)
            unique.append(c.strip())

    return unique[:15]  # Cap at 15 concepts


# -------------------------------------------------------------------
# Relevance ranking
# -------------------------------------------------------------------

def _rank_relevance(
    patent: PatentResult,
    case: ProductCase,
    concepts: List[str],
) -> dict:
    """Rank a patent result's relevance to the product case."""
    score = 0
    reasons = []

    title_lower = (patent.title or "").lower()
    abstract_lower = (patent.abstract or "").lower()
    combined_text = title_lower + " " + abstract_lower

    # Check ingredient overlap
    ingredients = _deserialize_list(case.ingredients) if case.ingredients else []
    for ing in ingredients:
        name = (ing.get("name", "") if isinstance(ing, dict) else str(ing)).lower()
        simple_name = name.split("(")[0].strip()
        if simple_name and simple_name in combined_text:
            score += 30
            reasons.append(f"Ingredient '{simple_name}' mentioned in patent")

    # Check formulation overlap
    if case.formulation and case.formulation.lower() in combined_text:
        score += 25
        reasons.append("Formulation concept matches")

    # Check process overlap
    if case.process:
        process_words = [w.strip().lower() for w in case.process.split() if len(w.strip()) > 3]
        process_matches = sum(1 for w in process_words if w in combined_text)
        if process_matches > 0:
            score += min(20, process_matches * 10)
            reasons.append(f"Process concept overlap ({process_matches} terms matched)")

    # Check product form overlap
    if case.form and case.form.lower() in combined_text:
        score += 10
        reasons.append("Product form matches")

    # Check concept overlap
    for concept in concepts:
        concept_lower = concept.lower()
        if len(concept_lower) > 3 and concept_lower in combined_text:
            score += 5
            reasons.append(f"Concept '{concept}' matches")

    # Jurisdiction relevance
    jurisdictions = _deserialize_list(case.jurisdictions) if case.jurisdictions else []
    if patent.jurisdiction in jurisdictions:
        score += 5
        reasons.append(f"Jurisdiction {patent.jurisdiction} matches target market")

    # Determine level
    if score >= 40:
        level = "HIGH"
    elif score >= 20:
        level = "MEDIUM"
    else:
        level = "LOW"

    explanation = "; ".join(reasons[:3]) if reasons else "Limited direct overlap detected."

    return {
        "relevance_level": level,
        "relevance_score": min(100, score),
        "explanation": explanation,
    }


# -------------------------------------------------------------------
# Normalize and persist
# -------------------------------------------------------------------

def _normalize_and_persist(
    db: Session,
    results: List[PatentResult],
    case: ProductCase,
    concepts: List[str],
    search_id: int,
) -> List[dict]:
    """Normalize patent results, rank relevance, and persist to database."""
    persisted = []
    seen_numbers = set()

    for result in results:
        # Deduplicate by publication number
        pub_num = result.publication_number or result.application_number
        if pub_num and pub_num in seen_numbers:
            continue
        if pub_num:
            seen_numbers.add(pub_num)

        # Rank relevance
        ranking = _rank_relevance(result, case, concepts)

        now = datetime.now(timezone.utc)

        # Create patent record
        record = PatentRecord(
            source_name=result.source_name,
            authority=result.authority,
            jurisdiction=result.jurisdiction,
            source_url=result.source_url,
            publication_number=result.publication_number,
            application_number=result.application_number,
            patent_type=result.patent_type,
            title=result.title,
            abstract=result.abstract,
            applicant=result.applicant,
            inventors=json.dumps(result.inventors) if result.inventors else None,
            priority_date=result.priority_date,
            filing_date=result.filing_date,
            publication_date=result.publication_date,
            status=result.status,
            retrieved_at=now,
            created_at=now,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # Create relevance record
        relevance = PatentRelevance(
            product_case_id=case.id,
            patent_record_id=record.id,
            search_id=search_id,
            relevance_level=ranking["relevance_level"],
            relevance_score=ranking["relevance_score"],
            explanation=ranking["explanation"],
            overlap_component=None,
            overlap_description=ranking["explanation"],
            saved_by_user=False,
            created_at=now,
            updated_at=now,
        )
        db.add(relevance)
        db.commit()

        persisted.append({
            "patent": _record_to_dict(record),
            "relevance_level": ranking["relevance_level"],
            "relevance_score": ranking["relevance_score"],
            "explanation": ranking["explanation"],
            "overlap_component": None,
            "overlap_description": ranking["explanation"],
        })

    # Sort by relevance score descending
    persisted.sort(key=lambda x: x["relevance_score"], reverse=True)
    return persisted


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def run_patent_search(
    db: Session,
    owner: User,
    case_public_id: str,
    jurisdictions: Optional[List[str]] = None,
    limit: int = 20,
) -> Optional[dict]:
    """Run a patent search for a Product Case."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == case_public_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return None

    # Get innovation components
    analysis = (
        db.query(InnovationAnalysis)
        .filter(InnovationAnalysis.product_case_id == case.id)
        .order_by(InnovationAnalysis.created_at.desc())
        .first()
    )
    components = list(analysis.components) if analysis else []

    # Generate search concepts
    concepts = _generate_search_concepts(case, components)

    # Get patent registry
    registry = get_patent_registry()

    # Search all relevant adapters
    search_jurisdictions = jurisdictions or ["IN", "US", "EU", "GLOBAL"]
    responses = registry.search_all(
        query=case.name,
        keywords=concepts,
        jurisdictions=search_jurisdictions,
        limit=limit,
    )

    # Create search record
    now = datetime.now(timezone.utc)
    sources_searched = len(responses)
    sources_succeeded = sum(1 for r in responses if r.is_configured)
    total_raw = sum(r.total for r in responses)

    search = PatentSearch(
        owner_id=owner.id,
        product_case_id=case.id,
        search_concepts=json.dumps(concepts),
        jurisdictions_searched=json.dumps(search_jurisdictions),
        total_results=0,  # Updated after normalization
        sources_searched=sources_searched,
        sources_succeeded=sources_succeeded,
        status="COMPLETED",
        created_at=now,
    )
    db.add(search)
    db.commit()
    db.refresh(search)

    # Collect all results from all sources
    all_results = []
    source_messages = []
    for resp in responses:
        all_results.extend(resp.results)
        if resp.message:
            source_messages.append({
                "source_name": resp.source_name,
                "jurisdiction": resp.jurisdiction,
                "is_configured": resp.is_configured,
                "message": resp.message,
            })

    # Normalize, rank, and persist
    persisted = _normalize_and_persist(db, all_results, case, concepts, search.id)

    # Update search total
    search.total_results = len(persisted)
    db.commit()

    return {
        "search_id": search.public_id,
        "product_case_id": case.public_id,
        "search_concepts": concepts,
        "jurisdictions_searched": search_jurisdictions,
        "sources_searched": sources_searched,
        "sources_succeeded": sources_succeeded,
        "total_results": len(persisted),
        "results": persisted,
        "source_messages": source_messages,
        "created_at": now.isoformat(),
    }


def get_saved_patents(
    db: Session,
    owner: User,
    case_public_id: str,
) -> List[dict]:
    """Get all saved patent relevances for a Product Case."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == case_public_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return []

    relevances = (
        db.query(PatentRelevance)
        .filter(
            PatentRelevance.product_case_id == case.id,
            PatentRelevance.saved_by_user == True,
        )
        .order_by(PatentRelevance.created_at.desc())
        .all()
    )

    results = []
    for rel in relevances:
        rec = rel.patent_record
        results.append({
            "id": rel.public_id,
            "patent": _record_to_dict(rec) if rec else {},
            "relevance_level": rel.relevance_level,
            "explanation": rel.explanation,
            "overlap_component": rel.overlap_component,
            "user_notes": rel.user_notes,
            "saved_by_user": rel.saved_by_user,
            "created_at": rel.created_at.isoformat() if rel.created_at else "",
        })

    return results


def save_patent(
    db: Session,
    owner: User,
    case_public_id: str,
    patent_record_id: str,
    relevance_level: Optional[str] = None,
    explanation: Optional[str] = None,
    overlap_component: Optional[str] = None,
    overlap_description: Optional[str] = None,
    user_notes: Optional[str] = None,
) -> Optional[dict]:
    """Save a patent record to a Product Case."""
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == case_public_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return None

    # Find or create the patent record
    record = (
        db.query(PatentRecord)
        .filter(PatentRecord.public_id == patent_record_id)
        .first()
    )
    if record is None:
        return None

    # Check if already saved
    existing = (
        db.query(PatentRelevance)
        .filter(
            PatentRelevance.product_case_id == case.id,
            PatentRelevance.patent_record_id == record.id,
            PatentRelevance.saved_by_user == True,
        )
        .first()
    )
    if existing:
        # Update
        if relevance_level:
            existing.relevance_level = relevance_level
        if explanation:
            existing.explanation = explanation
        if user_notes:
            existing.user_notes = user_notes
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return {
            "id": existing.public_id,
            "patent": _record_to_dict(record),
            "relevance_level": existing.relevance_level,
            "explanation": existing.explanation,
            "saved_by_user": True,
            "created_at": existing.created_at.isoformat() if existing.created_at else "",
        }

    now = datetime.now(timezone.utc)
    relevance = PatentRelevance(
        product_case_id=case.id,
        patent_record_id=record.id,
        relevance_level=relevance_level or "MEDIUM",
        explanation=explanation,
        overlap_component=overlap_component,
        overlap_description=overlap_description,
        saved_by_user=True,
        user_notes=user_notes,
        created_at=now,
        updated_at=now,
    )
    db.add(relevance)
    db.commit()
    db.refresh(relevance)

    return {
        "id": relevance.public_id,
        "patent": _record_to_dict(record),
        "relevance_level": relevance.relevance_level,
        "explanation": relevance.explanation,
        "saved_by_user": True,
        "created_at": relevance.created_at.isoformat() if relevance.created_at else "",
    }
