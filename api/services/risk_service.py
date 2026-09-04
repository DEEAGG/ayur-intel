"""AYUR-INTEL — Risk + Self-Extension Service (Phase 12).

Detects risks from all prior phases, generates self-extension
requests for missing information, and calculates analysis health.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    User, ProductCase,
    InnovationComponent, PatentRelevance, PatentAnalysis, PatentComparison,
    PatentRecord,
    IPStrategyItem,
    RegulatoryProfile, RegulatoryRequirement,
)
from api.models.evidence import UnifiedEvidence
from api.models.risk import Risk, RiskEvidence, SelfExtensionRequest
from api.services.evidence_service import create_or_find_evidence

logger = logging.getLogger("ayur_intel.risk_service")


def _deserialize(value) -> list:
    if not value:
        return []
    try:
        result = json.loads(value) if isinstance(value, str) else value
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _get_case(db: Session, user: User, case_public_id: str) -> Optional[ProductCase]:
    return (
        db.query(ProductCase)
        .filter(ProductCase.public_id == case_public_id, ProductCase.owner_id == user.id)
        .first()
    )


# ---------------------------------------------------------------------------
# Risk detection helpers
# ---------------------------------------------------------------------------

def _detect_patent_risks(db: Session, case: ProductCase) -> List[dict]:
    """Detect patent/IP risks from Phase 6-7-8 outputs."""
    risks = []

    # Check patent analysis results
    analyses = db.query(PatentAnalysis).filter(PatentAnalysis.product_case_id == case.id).all()
    for analysis in analyses:
        if analysis.overall_relevance in ("HIGH_POTENTIAL_OVERLAP", "MEDIUM_POTENTIAL_OVERLAP"):
            pr = analysis.patent_record
            level = "HIGH" if "HIGH" in analysis.overall_relevance else "MEDIUM"
            risks.append({
                "category": "PATENT_IP",
                "level": level,
                "title": f"Potential patent overlap: {pr.title if pr else 'Unknown'}",
                "description": f"Patent analysis detected {analysis.overall_relevance.replace('_', ' ').lower()} with patent record {pr.publication_number if pr else 'Unknown'}.",
                "affected_component_type": "FORMULATION",
                "affected_component_label": "Product formulation",
                "confidence": analysis.overall_confidence or "MEDIUM",
                "data_origin": "INFERENCE",
                "evidence_summary": analysis.summary,
                "missing_information": "Complete formulation ratio and detailed process parameters",
                "next_action": "Review relevant patent claims and verify product details.",
                "source_phase": "PHASE_7_PATENT_DEEP",
                "evidence": [{
                    "evidence_type": "PATENT_PUBLICATION",
                    "evidence_title": pr.title if pr else "Patent Record",
                    "evidence_reference": pr.publication_number if pr else None,
                    "evidence_description": f"Patent from {pr.authority or 'Unknown'} ({pr.jurisdiction or 'Unknown'})",
                    "evidence_source_name": pr.source_name if pr else None,
                    "evidence_authority": pr.authority if pr else None,
                    "evidence_jurisdiction": pr.jurisdiction if pr else None,
                }]
            })

    # Check patent relevances
    relevances = db.query(PatentRelevance).filter(PatentRelevance.product_case_id == case.id).all()
    high_relevances = [r for r in relevances if r.relevance_level == "HIGH"]
    if high_relevances:
        pr = high_relevances[0].patent_record
        risks.append({
            "category": "PATENT_IP",
            "level": "MEDIUM",
            "title": f"{len(high_relevances)} high-relevance patent record(s) found",
            "description": f"Multiple patent records show high relevance to your product components.",
            "affected_component_type": "MIXED",
            "affected_component_label": "Multiple product components",
            "confidence": "MEDIUM",
            "data_origin": "INFERENCE",
            "evidence_summary": f"Patent search found {len(high_relevances)} high-relevance records.",
            "missing_information": "Claim-level analysis for all relevant patents",
            "next_action": "Review patent claims for each high-relevance record.",
            "source_phase": "PHASE_6_PATENT",
            "evidence": [{
                "evidence_type": "PATENT_PUBLICATION",
                "evidence_title": pr.title if pr else "Patent Record",
                "evidence_reference": pr.publication_number if pr else None,
                "evidence_description": f"High relevance patent from {pr.authority or 'Unknown'}",
                "evidence_source_name": pr.source_name if pr else None,
                "evidence_authority": pr.authority if pr else None,
                "evidence_jurisdiction": pr.jurisdiction if pr else None,
            }]
        })

    return risks


def _detect_regulatory_risks(db: Session, case: ProductCase) -> List[dict]:
    """Detect regulatory risks from Phase 9-10 outputs."""
    risks = []
    profiles = db.query(RegulatoryProfile).filter(RegulatoryProfile.product_case_id == case.id).all()

    for profile in profiles:
        # Check for classification uncertainty
        if profile.category_confidence in ("LOW", None):
            risks.append({
                "category": "REGULATORY",
                "level": "MEDIUM",
                "title": f"Product classification uncertain for {profile.jurisdiction}",
                "description": f"Regulatory category could not be confirmed with high confidence for {profile.jurisdiction}.",
                "affected_component_type": "CLASSIFICATION",
                "affected_component_label": "Product classification",
                "confidence": profile.category_confidence or "LOW",
                "data_origin": "INFERENCE",
                "evidence_summary": profile.category_reasoning,
                "missing_information": "Official product classification verification",
                "next_action": f"Verify product category with relevant {profile.jurisdiction} authority.",
                "source_phase": "PHASE_9_REGULATORY",
                "evidence": [{
                    "evidence_type": "REGULATORY_GUIDANCE",
                    "evidence_title": f"Regulatory profile: {profile.potential_category or 'Unclassified'}",
                    "evidence_reference": None,
                    "evidence_description": f"Regulatory analysis for {profile.jurisdiction}",
                    "evidence_source_name": "AYUR-INTEL Regulatory Engine",
                    "evidence_authority": "Regulatory Authority",
                    "evidence_jurisdiction": profile.jurisdiction,
                }]
            })

        # Check for missing regulatory sources
        if profile.sources_configured == 0:
            risks.append({
                "category": "DATA_EVIDENCE_GAP",
                "level": "MEDIUM",
                "title": f"No regulatory sources configured for {profile.jurisdiction}",
                "description": f"Regulatory analysis for {profile.jurisdiction} was performed without configured external sources.",
                "affected_component_type": "REGULATORY_SOURCE",
                "affected_component_label": f"Regulatory source — {profile.jurisdiction}",
                "confidence": "LOW",
                "data_origin": "UNKNOWN",
                "evidence_summary": "No external regulatory sources configured.",
                "missing_information": f"Configured regulatory source for {profile.jurisdiction}",
                "next_action": f"Configure regulatory source adapter for {profile.jurisdiction}.",
                "source_phase": "PHASE_9_REGULATORY",
                "evidence": []
            })

    return risks


def _detect_claims_risks(db: Session, case: ProductCase) -> List[dict]:
    """Detect claims-related risks from Product Passport."""
    risks = []
    claims = _deserialize(case.claims)

    if claims:
        for claim in claims[:3]:  # limit to first 3
            claim_text = claim if isinstance(claim, str) else str(claim)
            # Check if claim contains disease-treatment language
            treatment_keywords = ["treat", "cure", "heal", "prevent", "diagnose", "remedy"]
            is_treatment_claim = any(kw in claim_text.lower() for kw in treatment_keywords)

            if is_treatment_claim:
                risks.append({
                    "category": "CLAIMS",
                    "level": "HIGH",
                    "title": f"Potential treatment claim detected: \"{claim_text[:80]}\"",
                    "description": "Claim language suggests treatment/disease claims which may require additional regulatory review.",
                    "affected_component_type": "CLAIMS",
                    "affected_component_label": "Proposed claims",
                    "confidence": "MEDIUM",
                    "data_origin": "USER_INPUT",
                    "evidence_summary": "User-provided claim text analyzed for regulatory implications.",
                    "missing_information": "Jurisdiction-specific claims compliance review",
                    "next_action": "Review claim against jurisdiction-specific advertising and labeling standards.",
                    "source_phase": "USER_INPUT",
                    "evidence": []
                })
            else:
                risks.append({
                    "category": "CLAIMS",
                    "level": "LOW",
                    "title": f"Claims review needed: \"{claim_text[:80]}\"",
                    "description": "Proposed claim requires verification against jurisdiction-specific requirements.",
                    "affected_component_type": "CLAIMS",
                    "affected_component_label": "Proposed claims",
                    "confidence": "MEDIUM",
                    "data_origin": "USER_INPUT",
                    "evidence_summary": "User-provided claim.",
                    "missing_information": "Claims compliance verification for target jurisdictions",
                    "next_action": "Verify claim compliance with applicable advertising standards.",
                    "source_phase": "USER_INPUT",
                    "evidence": []
                })

    return risks


def _detect_info_risks(db: Session, case: ProductCase) -> List[dict]:
    """Detect ingredient/product information risks from Product Passport."""
    risks = []
    ingredients = _deserialize(case.ingredients)

    # Check for missing ingredients
    if not ingredients:
        risks.append({
            "category": "INGREDIENT_PRODUCT_INFO",
            "level": "HIGH",
            "title": "No ingredients specified",
            "description": "Product Passport does not contain any ingredients. Patent and regulatory analysis may be incomplete.",
            "affected_component_type": "INGREDIENTS",
            "affected_component_label": "Product ingredients",
            "confidence": "HIGH",
            "data_origin": "USER_INPUT",
            "evidence_summary": "Product Passport ingredients field is empty.",
            "missing_information": "Product ingredients with botanical names",
            "next_action": "Add ingredients to Product Passport.",
            "source_phase": "USER_INPUT",
            "evidence": []
        })
    else:
        # Check for botanical identity verification
        for ing in ingredients:
            name = ing.get("name", "") if isinstance(ing, dict) else str(ing)
            status = ing.get("status", "") if isinstance(ing, dict) else ""
            if status == "NEEDS_VERIFICATION":
                risks.append({
                    "category": "INGREDIENT_PRODUCT_INFO",
                    "level": "MEDIUM",
                    "title": f"Botanical identity needs verification: {name}",
                    "description": f"Ingredient \"{name}\" has been flagged as needing identity verification.",
                    "affected_component_type": "INGREDIENT",
                    "affected_component_label": name,
                    "confidence": "MEDIUM",
                    "data_origin": "USER_INPUT",
                    "evidence_summary": "User-provided ingredient with verification flag.",
                    "missing_information": "Verified botanical identity",
                    "next_action": "Verify botanical identity of this ingredient.",
                    "source_phase": "USER_INPUT",
                    "evidence": []
                })

    # Check missing formulation
    if not case.formulation:
        risks.append({
            "category": "INGREDIENT_PRODUCT_INFO",
            "level": "MEDIUM",
            "title": "Formulation details missing",
            "description": "No formulation ratio or dosage form details provided. Patent comparison may be limited.",
            "affected_component_type": "FORMULATION",
            "affected_component_label": "Product formulation",
            "confidence": "HIGH",
            "data_origin": "USER_INPUT",
            "evidence_summary": "Product Passport formulation field is empty.",
            "missing_information": "Formulation ratio and dosage details",
            "next_action": "Add formulation details to Product Passport.",
            "source_phase": "USER_INPUT",
            "evidence": []
        })

    # Check missing intended use
    if not case.intended_use:
        risks.append({
            "category": "INGREDIENT_PRODUCT_INFO",
            "level": "LOW",
            "title": "Intended use not specified",
            "description": "No intended use provided. Regulatory analysis may be limited.",
            "affected_component_type": "INTENDED_USE",
            "affected_component_label": "Intended use",
            "confidence": "HIGH",
            "data_origin": "USER_INPUT",
            "evidence_summary": "Product Passport intended_use field is empty.",
            "missing_information": "Product intended use description",
            "next_action": "Add intended use to Product Passport.",
            "source_phase": "USER_INPUT",
            "evidence": []
        })

    return risks


def _detect_jurisdiction_risks(db: Session, case: ProductCase) -> List[dict]:
    """Detect jurisdiction-specific uncertainty risks."""
    risks = []
    jurisdictions = _deserialize(case.jurisdictions)

    if not jurisdictions:
        risks.append({
            "category": "JURISDICTION_UNCERTAINTY",
            "level": "MEDIUM",
            "title": "No target jurisdictions specified",
            "description": "No target markets selected. Regulatory and jurisdiction-specific analysis is limited.",
            "affected_component_type": "JURISDICTIONS",
            "affected_component_label": "Target markets",
            "confidence": "HIGH",
            "data_origin": "USER_INPUT",
            "evidence_summary": "Product Passport jurisdictions field is empty.",
            "missing_information": "Target jurisdiction(s)",
            "next_action": "Select target market(s) in Product Passport.",
            "source_phase": "USER_INPUT",
            "evidence": []
        })

    return risks


# ---------------------------------------------------------------------------
# Self-extension detection
# ---------------------------------------------------------------------------

def _detect_self_extensions(db: Session, case: ProductCase) -> List[dict]:
    """Detect missing information and generate self-extension requests."""
    extensions = []
    ingredients = _deserialize(case.ingredients)
    jurisdictions = _deserialize(case.jurisdictions)
    claims = _deserialize(case.claims)

    # Missing user information
    if not case.formulation:
        extensions.append({
            "type": "MISSING_USER_INFORMATION",
            "title": "Add formulation ratio",
            "description": "Complete formulation details are needed for deeper patent comparison.",
            "why_needed": "Patent and regulatory analysis cannot fully compare your product without formulation data.",
            "priority": "HIGH",
            "suggested_action": "Open Product Passport and add formulation details.",
            "resolve_url": "/passport",
        })

    if not case.process:
        extensions.append({
            "type": "MISSING_USER_INFORMATION",
            "title": "Add preparation process",
            "description": "Manufacturing/preparation process details help assess patent and regulatory implications.",
            "why_needed": "Process-related patent analysis requires knowing how the product is prepared.",
            "priority": "MEDIUM",
            "suggested_action": "Open Product Passport and describe the preparation process.",
            "resolve_url": "/passport",
        })

    if not ingredients:
        extensions.append({
            "type": "MISSING_USER_INFORMATION",
            "title": "Add product ingredients",
            "description": "Ingredients are needed for comprehensive patent, regulatory, and TK analysis.",
            "why_needed": "All intelligence modules depend on knowing what the product contains.",
            "priority": "HIGH",
            "suggested_action": "Open Product Passport and add ingredients.",
            "resolve_url": "/passport",
        })

    if not jurisdictions:
        extensions.append({
            "type": "MISSING_USER_INFORMATION",
            "title": "Select target jurisdictions",
            "description": "Target markets are needed for jurisdiction-specific regulatory analysis.",
            "why_needed": "Regulatory and IP analysis are jurisdiction-dependent.",
            "priority": "HIGH",
            "suggested_action": "Open Product Passport and select target markets.",
            "resolve_url": "/passport",
        })

    if not claims:
        extensions.append({
            "type": "MISSING_USER_INFORMATION",
            "title": "Add proposed claims",
            "description": "Claims are needed to assess regulatory and advertising compliance.",
            "why_needed": "Claims analysis requires knowing what the product is intended to do.",
            "priority": "MEDIUM",
            "suggested_action": "Open Product Passport and add proposed claims.",
            "resolve_url": "/passport",
        })

    # Missing evidence / source configuration
    from api.models.models import Source
    configured_sources = db.query(Source).filter(Source.is_configured == True, Source.is_active == True).count()
    if configured_sources == 0:
        extensions.append({
            "type": "SOURCE_CONFIGURATION_REQUIRED",
            "title": "Configure external data sources",
            "description": "No external patent, regulatory, or TK sources are configured.",
            "why_needed": "Without configured sources, intelligence analysis is limited to rule-based inferences.",
            "priority": "HIGH",
            "suggested_action": "Configure at least one patent or regulatory source adapter.",
            "resolve_url": None,
        })

    # Missing analysis
    from api.models.models import InnovationAnalysis, PatentSearch, IPStrategy
    has_innovation = db.query(InnovationAnalysis).filter(InnovationAnalysis.product_case_id == case.id).count() > 0
    has_patent_search = db.query(PatentSearch).filter(PatentSearch.product_case_id == case.id).count() > 0
    has_ip_strategy = db.query(IPStrategy).filter(IPStrategy.product_case_id == case.id).count() > 0
    has_regulatory = db.query(RegulatoryProfile).filter(RegulatoryProfile.product_case_id == case.id).count() > 0

    if not has_innovation and ingredients:
        extensions.append({
            "type": "MISSING_ANALYSIS",
            "title": "Run Innovation Analysis",
            "description": "Innovation decomposition has not been performed yet.",
            "why_needed": "Innovation analysis identifies potentially differentiated components and IP opportunities.",
            "priority": "MEDIUM",
            "suggested_action": "Open case detail and click 'Analyze Innovation'.",
            "resolve_url": None,
        })

    if not has_patent_search and ingredients:
        extensions.append({
            "type": "MISSING_ANALYSIS",
            "title": "Run Patent Search",
            "description": "Patent intelligence search has not been performed yet.",
            "why_needed": "Patent search identifies potentially relevant prior art and IP considerations.",
            "priority": "MEDIUM",
            "suggested_action": "Open case detail and click 'Patent Intel'.",
            "resolve_url": None,
        })

    if not has_ip_strategy:
        extensions.append({
            "type": "MISSING_ANALYSIS",
            "title": "Generate IP Strategy Map",
            "description": "IP strategy analysis has not been generated yet.",
            "why_needed": "IP strategy maps components to potential protection routes.",
            "priority": "LOW",
            "suggested_action": "Open case detail and click 'IP Strategy'.",
            "resolve_url": None,
        })

    if not has_regulatory and jurisdictions:
        extensions.append({
            "type": "MISSING_ANALYSIS",
            "title": "Run Regulatory Analysis",
            "description": "Regulatory intelligence has not been generated for target jurisdictions.",
            "why_needed": "Regulatory analysis identifies jurisdiction-specific requirements.",
            "priority": "MEDIUM",
            "suggested_action": "Open case detail and click 'Regulatory Intel'.",
            "resolve_url": None,
        })

    # Verification required
    for ing in ingredients:
        if isinstance(ing, dict) and ing.get("status") == "NEEDS_VERIFICATION":
            extensions.append({
                "type": "VERIFICATION_REQUIRED",
                "title": f"Verify botanical identity: {ing.get('name', 'Unknown')}",
                "description": f"Ingredient '{ing.get('name', 'Unknown')}' requires identity verification.",
                "why_needed": "Accurate botanical identity is essential for patent, regulatory, and TK analysis.",
                "priority": "HIGH",
                "suggested_action": "Verify the botanical name and source of this ingredient.",
                "resolve_url": None,
            })

    return extensions


# ---------------------------------------------------------------------------
# Analysis Health
# ---------------------------------------------------------------------------

def _calculate_analysis_health(
    db: Session,
    case: ProductCase,
    extensions: List[dict],
) -> dict:
    """Calculate analysis health metrics."""
    ingredients = _deserialize(case.ingredients)
    jurisdictions = _deserialize(case.jurisdictions)

    # Product completeness
    fields = [case.name, case.form, case.intended_use, case.formulation, case.process, case.brand]
    filled = sum(1 for f in fields if f)
    ingredient_score = 1 if ingredients else 0
    jurisdiction_score = 1 if jurisdictions else 0
    completeness_score = (filled + ingredient_score + jurisdiction_score) / (len(fields) + 2)

    if completeness_score >= 0.7:
        product_completeness = "GOOD"
    elif completeness_score >= 0.4:
        product_completeness = "PARTIAL"
    else:
        product_completeness = "LIMITED"

    # Evidence coverage
    from api.models.evidence import CaseFinding
    total_findings = db.query(CaseFinding).filter(CaseFinding.product_case_id == case.id).count()
    from api.services.evidence_service import aggregate_case_evidence
    ev_data = aggregate_case_evidence(db, case.owner, case.public_id)
    evidence_coverage = ev_data.get("citation_coverage", 0) if ev_data else 0

    # Patent analysis
    from api.models.models import PatentAnalysis
    has_patent_analysis = db.query(PatentAnalysis).filter(PatentAnalysis.product_case_id == case.id).count() > 0
    patent_analysis = "GOOD" if has_patent_analysis else "LIMITED"

    # Regulatory coverage
    from api.models.models import RegulatoryProfile
    reg_profiles = db.query(RegulatoryProfile).filter(RegulatoryProfile.product_case_id == case.id).count()
    if reg_profiles >= 2:
        regulatory_coverage = "GOOD"
    elif reg_profiles >= 1:
        regulatory_coverage = "PARTIAL"
    else:
        regulatory_coverage = "LIMITED"

    # Jurisdiction coverage
    if len(jurisdictions) >= 2:
        jurisdiction_coverage = "GOOD"
    elif len(jurisdictions) == 1:
        jurisdiction_coverage = "PARTIAL"
    else:
        jurisdiction_coverage = "LIMITED"

    # Overall
    scores = {
        "GOOD": 3, "PARTIAL": 2, "LIMITED": 1
    }
    avg = (scores[product_completeness] + scores[patent_analysis] + scores[regulatory_coverage] + scores[jurisdiction_coverage]) / 4
    if avg >= 2.5:
        overall = "GOOD"
    elif avg >= 1.5:
        overall = "PARTIAL"
    else:
        overall = "LIMITED"

    return {
        "product_completeness": product_completeness,
        "evidence_coverage": evidence_coverage,
        "patent_analysis": patent_analysis,
        "regulatory_coverage": regulatory_coverage,
        "jurisdiction_coverage": jurisdiction_coverage,
        "overall_health": overall,
    }


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def generate_risk_analysis(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Generate comprehensive risk analysis and self-extension for a Product Case."""
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    # Detect risks from all phases
    all_risk_dicts = []
    all_risk_dicts.extend(_detect_patent_risks(db, case))
    all_risk_dicts.extend(_detect_regulatory_risks(db, case))
    all_risk_dicts.extend(_detect_claims_risks(db, case))
    all_risk_dicts.extend(_detect_info_risks(db, case))
    all_risk_dicts.extend(_detect_jurisdiction_risks(db, case))

    # Build set of existing risk titles for deduplication
    existing_risks = (
        db.query(Risk)
        .filter(Risk.product_case_id == case.id, Risk.status != "DELETED")
        .all()
    )
    existing_titles = {r.title for r in existing_risks}

    # Create risk records
    risk_records = []
    for rd in all_risk_dicts:
        # Skip if a risk with this exact title already exists
        if rd["title"] in existing_titles:
            continue
        # Create risk
        risk = Risk(
            owner_id=user.id,
            product_case_id=case.id,
            category=rd["category"],
            level=rd["level"],
            title=rd["title"],
            description=rd.get("description"),
            affected_component_type=rd.get("affected_component_type"),
            affected_component_label=rd.get("affected_component_label"),
            confidence=rd.get("confidence"),
            data_origin=rd.get("data_origin"),
            evidence_summary=rd.get("evidence_summary"),
            missing_information=rd.get("missing_information"),
            next_action=rd.get("next_action"),
            source_phase=rd.get("source_phase"),
        )
        db.add(risk)
        db.flush()

        # Create evidence links
        for ev_data in rd.get("evidence", []):
            risk_ev = RiskEvidence(
                risk_id=risk.id,
                evidence_type=ev_data.get("evidence_type"),
                evidence_title=ev_data.get("evidence_title"),
                evidence_reference=ev_data.get("evidence_reference"),
                evidence_description=ev_data.get("evidence_description"),
                evidence_source_name=ev_data.get("evidence_source_name"),
                evidence_authority=ev_data.get("evidence_authority"),
                evidence_jurisdiction=ev_data.get("evidence_jurisdiction"),
            )
            db.add(risk_ev)

        risk_records.append(risk)

    # Detect self-extensions
    extension_dicts = _detect_self_extensions(db, case)
    extension_records = []
    for ed in extension_dicts:
        ext = SelfExtensionRequest(
            owner_id=user.id,
            product_case_id=case.id,
            type=ed["type"],
            title=ed["title"],
            description=ed.get("description"),
            why_needed=ed.get("why_needed"),
            priority=ed.get("priority", "MEDIUM"),
            suggested_action=ed.get("suggested_action"),
            resolve_url=ed.get("resolve_url"),
        )
        db.add(ext)
        extension_records.append(ext)

    db.flush()

    # Calculate analysis health
    health = _calculate_analysis_health(db, case, extension_dicts)

    # Build response
    risk_responses = []
    for r in risk_records:
        evidence_responses = []
        for re in r.evidence_links:
            evidence_responses.append({
                "id": re.public_id,
                "evidence_type": re.evidence_type,
                "evidence_title": re.evidence_title,
                "evidence_reference": re.evidence_reference,
                "evidence_description": re.evidence_description,
                "evidence_source_name": re.evidence_source_name,
                "evidence_authority": re.evidence_authority,
                "evidence_jurisdiction": re.evidence_jurisdiction,
                "relationship_type": "SUPPORTS",
            })
        risk_responses.append({
            "id": r.public_id,
            "category": r.category,
            "level": r.level,
            "title": r.title,
            "description": r.description,
            "affected_component_type": r.affected_component_type,
            "affected_component_label": r.affected_component_label,
            "confidence": r.confidence,
            "data_origin": r.data_origin,
            "evidence_summary": r.evidence_summary,
            "missing_information": r.missing_information,
            "next_action": r.next_action,
            "source_phase": r.source_phase,
            "status": r.status,
            "evidence": evidence_responses,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        })

    ext_responses = []
    for ext in extension_records:
        ext_responses.append({
            "id": ext.public_id,
            "type": ext.type,
            "title": ext.title,
            "description": ext.description,
            "why_needed": ext.why_needed,
            "priority": ext.priority,
            "status": ext.status,
            "related_component_type": ext.related_component_type,
            "suggested_action": ext.suggested_action,
            "resolve_url": ext.resolve_url,
            "created_at": ext.created_at.isoformat() if ext.created_at else "",
        })

    high_count = sum(1 for r in risk_records if r.level == "HIGH")
    medium_count = sum(1 for r in risk_records if r.level == "MEDIUM")
    low_count = sum(1 for r in risk_records if r.level == "LOW")
    unknown_count = sum(1 for r in risk_records if r.level == "UNKNOWN")
    open_count = sum(1 for r in risk_records if r.status == "OPEN")

    return {
        "product_case_id": case.public_id,
        "product_name": case.name,
        "risks": risk_responses,
        "self_extensions": ext_responses,
        "analysis_health": health,
        "total_risks": len(risk_records),
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "unknown_count": unknown_count,
        "open_count": open_count,
        "total_extensions": len(extension_records),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def update_risk_status(db: Session, user: User, risk_public_id: str, status: str, note: str = None) -> Optional[dict]:
    """Update a risk's status and record resolution history."""
    risk = db.query(Risk).filter(Risk.public_id == risk_public_id).first()
    if not risk:
        return None
    if risk.owner_id != user.id:
        return None

    old_status = risk.status
    risk.status = status
    risk.updated_at = datetime.now(timezone.utc)

    resolution = RiskResolution(
        risk_id=risk.id,
        status=status,
        note=note,
    )
    db.add(resolution)
    db.commit()

    return {"id": risk.public_id, "status": risk.status, "message": f"Risk status updated from {old_status} to {status}"}


def update_extension_status(db: Session, user: User, ext_public_id: str, status: str) -> Optional[dict]:
    """Update a self-extension request's status."""
    ext = db.query(SelfExtensionRequest).filter(SelfExtensionRequest.public_id == ext_public_id).first()
    if not ext:
        return None
    if ext.owner_id != user.id:
        return None

    ext.status = status
    ext.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"id": ext.public_id, "status": ext.status, "message": f"Extension status updated to {status}"}
