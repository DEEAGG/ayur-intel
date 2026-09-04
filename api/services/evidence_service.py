"""AYUR-INTEL — Evidence & Citation Service (Phase 11).

Aggregates evidence from all phases, provides citation tracking,
coverage metrics, and cross-phase finding→evidence→source traceability.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    User, ProductCase, Source,
    InnovationComponent, PatentRecord, PatentRelevance, PatentComparison,
    PatentAnalysis, ClaimElement,
    IPStrategyItem,
    RegulatoryRequirement,
)
from api.models.evidence import (
    UnifiedEvidence, CaseFinding, CaseFindingEvidence,
)

logger = logging.getLogger("ayur_intel.evidence_service")


def _deserialize(value) -> list:
    if not value:
        return []
    try:
        result = json.loads(value) if isinstance(value, str) else value
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _hash_evidence(source_name: str, reference: str, excerpt: str) -> str:
    """Create a dedup hash for evidence."""
    raw = f"{source_name}|{reference}|{excerpt}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _get_case(db: Session, user: User, case_public_id: str) -> Optional[ProductCase]:
    return (
        db.query(ProductCase)
        .filter(ProductCase.public_id == case_public_id, ProductCase.owner_id == user.id)
        .first()
    )


# ---------------------------------------------------------------------------
# Evidence creation helpers
# ---------------------------------------------------------------------------

def create_or_find_evidence(
    db: Session,
    evidence_type: str,
    title: str = None,
    reference: str = None,
    excerpt: str = None,
    description: str = None,
    source_name: str = None,
    authority: str = None,
    jurisdiction: str = None,
    quality: str = None,
    confidence: str = None,
    data_origin: str = None,
    publication_date: str = None,
    version: str = None,
    effective_date: str = None,
    retrieved_at: datetime = None,
    source_id: int = None,
) -> UnifiedEvidence:
    """Create or find an existing evidence record (deduplication)."""
    # Try dedup via hash
    if source_name and reference:
        evidence_hash = _hash_evidence(source_name, reference, excerpt or "")
        existing = (
            db.query(UnifiedEvidence)
            .filter(UnifiedEvidence.evidence_hash == evidence_hash)
            .first()
        )
        if existing:
            return existing

    ev = UnifiedEvidence(
        evidence_type=evidence_type,
        title=title,
        reference=reference,
        excerpt=excerpt,
        description=description,
        source_name=source_name,
        authority=authority,
        jurisdiction=jurisdiction,
        quality=quality,
        confidence=confidence,
        data_origin=data_origin,
        publication_date=publication_date,
        version=version,
        effective_date=effective_date,
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
        source_id=source_id,
    )
    if source_name and reference:
        ev.evidence_hash = _hash_evidence(source_name, reference, excerpt or "")
    db.add(ev)
    db.flush()
    return ev


def link_finding_evidence(
    db: Session,
    finding_id: int,
    evidence_id: int,
    relationship_type: str = "SUPPORTS",
) -> CaseFindingEvidence:
    """Link a finding to evidence. Avoids duplicates."""
    existing = (
        db.query(CaseFindingEvidence)
        .filter(
            CaseFindingEvidence.finding_id == finding_id,
            CaseFindingEvidence.evidence_id == evidence_id,
        )
        .first()
    )
    if existing:
        return existing

    link = CaseFindingEvidence(
        finding_id=finding_id,
        evidence_id=evidence_id,
        relationship_type=relationship_type,
    )
    db.add(link)
    db.flush()
    return link


def create_finding(
    db: Session,
    owner_id: int,
    product_case_id: int,
    finding_type: str,
    source_phase: str,
    title: str,
    content: str = None,
    reference_type: str = None,
    reference_id: str = None,
    data_origin: str = None,
    confidence: str = None,
) -> CaseFinding:
    """Create a new case finding."""
    finding = CaseFinding(
        owner_id=owner_id,
        product_case_id=product_case_id,
        finding_type=finding_type,
        source_phase=source_phase,
        title=title,
        content=content,
        reference_type=reference_type,
        reference_id=reference_id,
        data_origin=data_origin,
        confidence=confidence,
    )
    db.add(finding)
    db.flush()
    return finding


# ---------------------------------------------------------------------------
# Cross-phase evidence aggregation
# ---------------------------------------------------------------------------

def _extract_patent_evidence(db: Session, case: ProductCase) -> List[dict]:
    """Extract evidence from patent records linked to this case."""
    relevances = (
        db.query(PatentRelevance)
        .filter(PatentRelevance.product_case_id == case.id)
        .all()
    )
    evidence_items = []
    for rel in relevances:
        pr = rel.patent_record
        if pr:
            evidence_items.append({
                "evidence_type": "PATENT_PUBLICATION",
                "title": pr.title or "Patent Record",
                "reference": pr.publication_number or pr.application_number,
                "description": f"Patent from {pr.authority or pr.source_name or 'Unknown'} ({pr.jurisdiction or 'Unknown'})",
                "source_name": pr.source_name or pr.authority,
                "authority": pr.authority,
                "jurisdiction": pr.jurisdiction,
                "publication_date": pr.publication_date,
                "data_origin": "FACT",
                "quality": "MEDIUM",
                "confidence": rel.relevance_level,
                "finding_type": "PATENT_RELEVANCE",
                "source_phase": "PHASE_6_PATENT",
                "finding_title": f"Patent relevance: {pr.title or pr.publication_number or 'Unknown'}",
                "finding_content": rel.explanation or rel.overlap_description,
                "reference_type": "patent_record",
                "reference_id": str(pr.public_id) if pr.public_id else None,
            })
    return evidence_items


def _extract_patent_analysis_evidence(db: Session, case: ProductCase) -> List[dict]:
    """Extract evidence from patent deep analyses."""
    analyses = (
        db.query(PatentAnalysis)
        .filter(PatentAnalysis.product_case_id == case.id)
        .all()
    )
    evidence_items = []
    for analysis in analyses:
        pr = analysis.patent_record
        evidence_items.append({
            "evidence_type": "PATENT_CLAIM" if analysis.overall_relevance != "INSUFFICIENT_INFORMATION" else "PATENT_METADATA",
            "title": f"Patent analysis: {pr.title if pr else 'Unknown'}",
            "reference": pr.publication_number if pr else None,
            "description": analysis.summary,
            "source_name": pr.source_name if pr else None,
            "authority": pr.authority if pr else None,
            "jurisdiction": pr.jurisdiction if pr else None,
            "publication_date": pr.publication_date if pr else None,
            "data_origin": "INFERENCE",
            "quality": "MEDIUM",
            "confidence": analysis.overall_confidence,
            "finding_type": "PATENT_COMPARISON",
            "source_phase": "PHASE_7_PATENT_DEEP",
            "finding_title": f"Patent overlap analysis: {analysis.overall_relevance.replace('_', ' ').title()}",
            "finding_content": analysis.summary,
            "reference_type": "patent_analysis",
            "reference_id": str(analysis.public_id) if analysis.public_id else None,
        })
    return evidence_items


def _extract_regulatory_evidence(db: Session, case: ProductCase) -> List[dict]:
    """Extract evidence from regulatory requirements."""
    from api.models.models import RegulatoryProfile
    profiles = (
        db.query(RegulatoryProfile)
        .filter(RegulatoryProfile.product_case_id == case.id)
        .all()
    )
    evidence_items = []
    for profile in profiles:
        for req in profile.requirements:
            if req.applicability in ("RELEVANT", "POTENTIALLY_RELEVANT"):
                evidence_items.append({
                    "evidence_type": req.evidence_type or "REGULATORY_GUIDANCE",
                    "title": req.title,
                    "reference": req.source_reference,
                    "description": req.description,
                    "source_name": req.source_name,
                    "authority": req.authority,
                    "jurisdiction": req.jurisdiction,
                    "publication_date": req.publication_date,
                    "data_origin": "SYSTEM_DERIVED" if req.evidence_type == "SYSTEM_DERIVED" else "FACT",
                    "quality": "MEDIUM",
                    "confidence": req.confidence,
                    "finding_type": "REGULATORY_REQUIREMENT",
                    "source_phase": "PHASE_9_REGULATORY",
                    "finding_title": f"Regulatory requirement: {req.title}",
                    "finding_content": req.description,
                    "reference_type": "regulatory_requirement",
                    "reference_id": str(req.public_id),
                })
    return evidence_items


def _extract_innovation_evidence(db: Session, case: ProductCase) -> List[dict]:
    """Extract evidence from innovation components."""
    from api.models.models import InnovationAnalysis
    analyses = (
        db.query(InnovationAnalysis)
        .filter(InnovationAnalysis.product_case_id == case.id)
        .all()
    )
    evidence_items = []
    for analysis in analyses:
        for comp in analysis.components:
            if comp.classification in ("POTENTIALLY_DIFFERENTIATED", "REQUIRES_INVESTIGATION"):
                evidence_items.append({
                    "evidence_type": "INNOVATION_ANALYSIS",
                    "title": f"Innovation component: {comp.component_label}",
                    "reference": None,
                    "description": comp.explanation,
                    "source_name": "AYUR-INTEL Innovation Engine",
                    "authority": "AYUR-INTEL Rule Engine",
                    "jurisdiction": None,
                    "data_origin": "SYSTEM_DERIVED",
                    "quality": "MEDIUM",
                    "confidence": comp.confidence,
                    "finding_type": "INNOVATION_COMPONENT",
                    "source_phase": "PHASE_5_INNOVATION",
                    "finding_title": f"Innovation: {comp.component_label} — {comp.classification.replace('_', ' ').title()}",
                    "finding_content": comp.explanation or comp.evidence_summary,
                    "reference_type": "innovation_component",
                    "reference_id": str(comp.public_id),
                })
    return evidence_items


def _extract_ip_strategy_evidence(db: Session, case: ProductCase) -> List[dict]:
    """Extract evidence from IP strategy items."""
    from api.models.models import IPStrategy
    strategies = (
        db.query(IPStrategy)
        .filter(IPStrategy.product_case_id == case.id)
        .all()
    )
    evidence_items = []
    for strategy in strategies:
        for item in strategy.items:
            evidence_items.append({
                "evidence_type": "IP_STRATEGY",
                "title": f"IP Route: {item.ip_category.replace('_', ' ')}",
                "reference": None,
                "description": item.reason,
                "source_name": item.evidence_source,
                "authority": "AYUR-INTEL IP Strategy Engine",
                "jurisdiction": None,
                "data_origin": "SYSTEM_DERIVED",
                "quality": "MEDIUM",
                "confidence": item.confidence,
                "finding_type": "IP_STRATEGY_ITEM",
                "source_phase": "PHASE_8_IP_STRATEGY",
                "finding_title": f"IP Strategy: {item.component_label} → {item.ip_category.replace('_', ' ')}",
                "finding_content": item.reason,
                "reference_type": "ip_strategy_item",
                "reference_id": str(item.public_id),
            })
    return evidence_items


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------

def aggregate_case_evidence(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Aggregate all evidence for a Product Case across all phases.

    Returns a structured summary with findings, evidence, and coverage.
    """
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    # Collect evidence items from all phases
    all_items = []
    all_items.extend(_extract_patent_evidence(db, case))
    all_items.extend(_extract_patent_analysis_evidence(db, case))
    all_items.extend(_extract_regulatory_evidence(db, case))
    all_items.extend(_extract_innovation_evidence(db, case))
    all_items.extend(_extract_ip_strategy_evidence(db, case))

    # Create findings and evidence records
    findings = []
    seen_finding_refs = set()

    for item in all_items:
        ref_key = f"{item['finding_type']}:{item.get('reference_id', '')}:{item['finding_title']}"
        if ref_key in seen_finding_refs:
            continue
        seen_finding_refs.add(ref_key)

        # Create or find evidence
        evidence = create_or_find_evidence(
            db,
            evidence_type=item["evidence_type"],
            title=item.get("title"),
            reference=item.get("reference"),
            description=item.get("description"),
            source_name=item.get("source_name"),
            authority=item.get("authority"),
            jurisdiction=item.get("jurisdiction"),
            quality=item.get("quality"),
            confidence=item.get("confidence"),
            data_origin=item.get("data_origin"),
            publication_date=item.get("publication_date"),
        )

        # Create finding
        finding = create_finding(
            db,
            owner_id=case.owner_id,
            product_case_id=case.id,
            finding_type=item["finding_type"],
            source_phase=item["source_phase"],
            title=item["finding_title"],
            content=item.get("finding_content"),
            reference_type=item.get("reference_type"),
            reference_id=item.get("reference_id"),
            data_origin=item.get("data_origin"),
            confidence=item.get("confidence"),
        )

        # Link finding → evidence
        link = link_finding_evidence(db, finding.id, evidence.id, "SUPPORTS")
        finding.evidence_count = 1
        db.flush()

        findings.append({
            "finding": finding,
            "evidence": evidence,
        })

    # Calculate coverage
    total_findings = len(findings)
    findings_with_evidence = sum(1 for f in findings if f["finding"].evidence_count > 0)
    coverage = (findings_with_evidence / total_findings * 100) if total_findings > 0 else 0.0

    # Build response
    finding_responses = []
    for f in findings:
        finding = f["finding"]
        evidence = f["evidence"]
        finding_responses.append({
            "id": finding.public_id,
            "finding_type": finding.finding_type,
            "source_phase": finding.source_phase,
            "title": finding.title,
            "content": finding.content,
            "reference_type": finding.reference_type,
            "reference_id": finding.reference_id,
            "status": finding.status,
            "confidence": finding.confidence,
            "data_origin": finding.data_origin,
            "evidence_count": finding.evidence_count,
            "has_conflicts": finding.has_conflicts,
            "is_unsupported": finding.is_unsupported,
            "citations": [{
                "id": f"cite-{evidence.public_id}",
                "evidence_id": evidence.public_id,
                "relationship_type": "SUPPORTS",
                "evidence": {
                    "id": evidence.public_id,
                    "evidence_type": evidence.evidence_type,
                    "title": evidence.title,
                    "reference": evidence.reference,
                    "excerpt": evidence.excerpt,
                    "description": evidence.description,
                    "source_name": evidence.source_name,
                    "authority": evidence.authority,
                    "jurisdiction": evidence.jurisdiction,
                    "quality": evidence.quality,
                    "confidence": evidence.confidence,
                    "data_origin": evidence.data_origin,
                    "publication_date": evidence.publication_date,
                    "version": evidence.version,
                    "retrieved_at": evidence.retrieved_at.isoformat() if evidence.retrieved_at else None,
                    "source_url": None,
                    "created_at": evidence.created_at.isoformat() if evidence.created_at else "",
                }
            }],
            "created_at": finding.created_at.isoformat() if finding.created_at else "",
        })

    return {
        "product_case_id": case.public_id,
        "product_name": case.name,
        "total_findings": total_findings,
        "findings_with_evidence": findings_with_evidence,
        "citation_coverage": round(coverage, 1),
        "total_evidence": len(set(f["evidence"].id for f in findings)),
        "unsupported_count": 0,
        "conflicting_count": 0,
        "findings": finding_responses,
    }


def get_evidence_detail(db: Session, user: User, evidence_public_id: str) -> Optional[dict]:
    """Get detailed evidence record."""
    evidence = (
        db.query(UnifiedEvidence)
        .filter(UnifiedEvidence.public_id == evidence_public_id)
        .first()
    )
    if not evidence:
        return None

    return {
        "id": evidence.public_id,
        "evidence_type": evidence.evidence_type,
        "title": evidence.title,
        "reference": evidence.reference,
        "excerpt": evidence.excerpt,
        "description": evidence.description,
        "source_name": evidence.source_name,
        "authority": evidence.authority,
        "jurisdiction": evidence.jurisdiction,
        "quality": evidence.quality,
        "confidence": evidence.confidence,
        "data_origin": evidence.data_origin,
        "publication_date": evidence.publication_date,
        "version": evidence.version,
        "effective_date": evidence.effective_date,
        "retrieved_at": evidence.retrieved_at.isoformat() if evidence.retrieved_at else None,
        "source_url": None,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else "",
    }
