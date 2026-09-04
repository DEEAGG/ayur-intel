"""AYUR-INTEL — Knowledge Engine Service.

Business logic for the Knowledge & Traditional Knowledge Engine:
- Search across registered sources
- Save findings to Product Cases
- Manage evidence records
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from api.models.models import (
    KnowledgeEvidence,
    KnowledgeFinding,
    PlantDiscovery,
    ProductCase,
    Source,
    User,
)
from api.services.source_adapter import (
    SourceRegistry,
    SourceResult,
    SourceSearchResponse,
    get_source_registry,
)

logger = logging.getLogger("ayur_intel.knowledge_service")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _finding_to_dict(finding: KnowledgeFinding) -> dict:
    """Convert a KnowledgeFinding ORM object to a dict for API response."""
    evidence_list = []
    if hasattr(finding, "evidence_records") and finding.evidence_records:
        for ev in finding.evidence_records:
            evidence_list.append({
                "id": ev.public_id,
                "title": ev.title,
                "source_identifier": ev.source_identifier,
                "evidence_locator": ev.evidence_locator,
                "excerpt": ev.excerpt,
                "confidence": ev.confidence,
                "publication_date": ev.publication_date,
                "retrieval_date": ev.retrieval_date,
                "source_version": ev.source_version,
            })

    return {
        "id": finding.public_id,
        "title": finding.title,
        "summary": finding.summary,
        "category": finding.category,
        "plant_name": finding.plant_name,
        "botanical_name": finding.botanical_name,
        "traditional_name": finding.traditional_name,
        "source_name": finding.source_name,
        "source_authority": finding.source_authority,
        "jurisdiction": finding.jurisdiction,
        "confidence": finding.confidence,
        "relevance": finding.relevance,
        "evidence_locator": finding.evidence_locator,
        "evidence_excerpt": finding.evidence_excerpt,
        "publication_date": finding.publication_date,
        "retrieval_date": finding.retrieval_date,
        "is_conflicting": finding.is_conflicting,
        "conflicting_details": finding.conflicting_details,
        "limitations": finding.limitations,
        "product_case_id": finding.product_case.public_id if finding.product_case else None,
        "plant_discovery_id": None,  # would need relationship
        "source_id": finding.source.public_id if finding.source else None,
        "evidence": evidence_list,
        "status": finding.status,
        "created_at": finding.created_at.isoformat() if finding.created_at else "",
        "updated_at": finding.updated_at.isoformat() if finding.updated_at else "",
    }


def _source_to_dict(src: Source) -> dict:
    """Convert a Source ORM object to a dict."""
    caps = []
    if src.capabilities:
        try:
            caps = json.loads(src.capabilities)
        except (json.JSONDecodeError, TypeError):
            caps = []

    return {
        "id": src.public_id,
        "name": src.name,
        "authority": src.authority,
        "source_type": src.source_type,
        "jurisdiction": src.jurisdiction,
        "url": src.url,
        "description": src.description,
        "is_configured": src.is_configured,
        "is_active": src.is_active,
        "capabilities": caps,
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_knowledge(
    db: Session,
    query: str,
    plant_name: Optional[str] = None,
    botanical_name: Optional[str] = None,
    category: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Search across all registered source adapters.

    Returns aggregated results from all sources, each clearly labeled
    with authority, jurisdiction, and confidence.
    """
    registry = get_source_registry()
    responses: List[SourceSearchResponse] = registry.search_all(
        query=query,
        plant_name=plant_name,
        botanical_name=botanical_name,
        category=category,
        jurisdiction=jurisdiction,
        limit=limit,
    )

    has_configured = any(r.is_configured for r in responses)
    total = sum(r.total for r in responses)

    # Ensure sources exist in the database
    _sync_sources(db, registry)

    # Build response
    sources = []
    for resp in responses:
        results = []
        for r in resp.results:
            results.append({
                "title": r.title,
                "summary": r.summary,
                "plant_name": r.plant_name,
                "botanical_name": r.botanical_name,
                "traditional_name": r.traditional_name,
                "category": r.category,
                "source_name": r.source_name,
                "source_authority": r.source_authority,
                "jurisdiction": r.jurisdiction,
                "confidence": r.confidence,
                "relevance": r.relevance,
                "evidence_locator": r.evidence_locator,
                "excerpt": r.excerpt,
                "publication_date": r.publication_date,
                "limitations": r.limitations,
                "is_conflicting": r.is_conflicting,
                "conflicting_details": r.conflicting_details,
            })

        sources.append({
            "source_name": resp.source_name,
            "source_authority": resp.source_authority,
            "jurisdiction": resp.jurisdiction,
            "is_configured": resp.is_configured,
            "message": resp.message,
            "total": resp.total,
            "results": results,
            "retrieval_date": resp.retrieval_date,
        })

    return {
        "query": query,
        "sources": sources,
        "total_results": total,
        "has_configured_sources": has_configured,
    }


def _sync_sources(db: Session, registry: SourceRegistry) -> None:
    """Ensure all registered adapters have corresponding Source records in DB."""
    for adapter in registry.get_all():
        existing = db.query(Source).filter(Source.name == adapter.name).first()
        if existing is None:
            now = datetime.now(timezone.utc)
            src = Source(
                name=adapter.name,
                authority=adapter.authority,
                source_type=adapter.source_type,
                jurisdiction=adapter.jurisdiction,
                description=adapter.description(),
                is_configured=adapter.is_configured(),
                is_active=True,
                capabilities=json.dumps(adapter.capabilities),
                created_at=now,
                updated_at=now,
            )
            db.add(src)
        else:
            existing.is_configured = adapter.is_configured()
            existing.updated_at = datetime.now(timezone.utc)
    db.commit()


# ---------------------------------------------------------------------------
# Save finding to Product Case
# ---------------------------------------------------------------------------

def save_finding(
    db: Session,
    owner: User,
    finding_data: dict,
    product_case_id: str,
    plant_discovery_id: Optional[str] = None,
) -> Optional[dict]:
    """Save a knowledge finding to a Product Case.

    Creates the KnowledgeFinding record, and optionally creates
    evidence records from the source adapter results.
    """
    # Verify the Product Case belongs to this user
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == product_case_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return None

    # Find the Source record if source_name is provided
    source = None
    source_name = finding_data.get("source_name")
    if source_name:
        source = db.query(Source).filter(Source.name == source_name).first()

    now = datetime.now(timezone.utc)

    # Create the finding
    finding = KnowledgeFinding(
        owner_id=owner.id,
        product_case_id=case.id,
        source_id=source.id if source else None,
        title=finding_data.get("title", "Untitled Finding"),
        summary=finding_data.get("summary"),
        category=finding_data.get("category"),
        plant_name=finding_data.get("plant_name"),
        botanical_name=finding_data.get("botanical_name"),
        traditional_name=finding_data.get("traditional_name"),
        confidence=finding_data.get("confidence", "UNKNOWN"),
        relevance=finding_data.get("relevance", "MODERATE"),
        evidence_locator=finding_data.get("evidence_locator"),
        evidence_excerpt=finding_data.get("excerpt"),
        publication_date=finding_data.get("publication_date"),
        retrieval_date=finding_data.get("retrieval_date") or _now_iso(),
        jurisdiction=finding_data.get("jurisdiction"),
        source_name=source_name,
        source_authority=finding_data.get("source_authority"),
        limitations=finding_data.get("limitations"),
        is_conflicting=finding_data.get("is_conflicting", False),
        conflicting_details=finding_data.get("conflicting_details"),
        status="SAVED",
        created_at=now,
        updated_at=now,
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    # Create evidence record if we have source data
    if source and finding_data.get("evidence_locator"):
        evidence = KnowledgeEvidence(
            finding_id=finding.id,
            source_id=source.id,
            title=finding_data.get("title"),
            source_identifier=finding_data.get("source_identifier"),
            evidence_locator=finding_data.get("evidence_locator"),
            excerpt=finding_data.get("excerpt"),
            confidence=finding_data.get("confidence"),
            publication_date=finding_data.get("publication_date"),
            retrieval_date=finding_data.get("retrieval_date") or _now_iso(),
            source_version=finding_data.get("source_version"),
            created_at=now,
        )
        db.add(evidence)
        db.commit()

    logger.info("Saved knowledge finding %s to case %s", finding.public_id, product_case_id)
    return _finding_to_dict(finding)


# ---------------------------------------------------------------------------
# Get saved findings for a Product Case
# ---------------------------------------------------------------------------

def get_case_findings(
    db: Session,
    owner: User,
    case_public_id: str,
) -> Optional[List[dict]]:
    """Get all saved knowledge findings for a Product Case."""
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

    findings = (
        db.query(KnowledgeFinding)
        .filter(KnowledgeFinding.product_case_id == case.id)
        .order_by(KnowledgeFinding.created_at.desc())
        .all()
    )

    return [_finding_to_dict(f) for f in findings]


# ---------------------------------------------------------------------------
# Get a single finding
# ---------------------------------------------------------------------------

def get_finding(
    db: Session,
    owner: User,
    finding_public_id: str,
) -> Optional[dict]:
    """Get a single Knowledge Finding by public ID, scoped to owner."""
    finding = (
        db.query(KnowledgeFinding)
        .filter(
            KnowledgeFinding.public_id == finding_public_id,
            KnowledgeFinding.owner_id == owner.id,
        )
        .first()
    )
    if finding is None:
        return None
    return _finding_to_dict(finding)


# ---------------------------------------------------------------------------
# List sources
# ---------------------------------------------------------------------------

def list_sources(db: Session) -> dict:
    """List all registered sources."""
    _sync_sources(db, get_source_registry())
    sources = db.query(Source).filter(Source.is_active == True).all()
    return {
        "sources": [_source_to_dict(s) for s in sources],
        "total": len(sources),
    }


# ---------------------------------------------------------------------------
# Get a single source
# ---------------------------------------------------------------------------

def get_source(db: Session, public_id: str) -> Optional[dict]:
    """Get a single Source by public ID."""
    src = db.query(Source).filter(Source.public_id == public_id).first()
    if src is None:
        return None
    return _source_to_dict(src)
