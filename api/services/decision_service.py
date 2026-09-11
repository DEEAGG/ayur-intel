"""AYUR-INTEL — Product Decision Dashboard Service (Phase 13).

Aggregates data from all 12 phases into a single decision-support dashboard.
Dynamically computed from existing entities — no data duplication.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    User, ProductCase,
    InnovationAnalysis, InnovationComponent,
    PatentSearch, PatentRelevance, PatentAnalysis,
    IPStrategy,
    RegulatoryProfile, RegulatoryRequirement,
)
from api.models.evidence import CaseFinding, UnifiedEvidence
from api.models.risk import Risk, SelfExtensionRequest
from api.services.evidence_service import aggregate_case_evidence
from api.services.ip_strategy_service import calculate_ip_readiness
from api.services.risk_service import (
    _detect_patent_risks, _detect_regulatory_risks, _detect_claims_risks,
    _detect_info_risks, _detect_jurisdiction_risks, _detect_self_extensions,
    _calculate_analysis_health,
)

logger = logging.getLogger("ayur_intel.decision_service")


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
# Product Completeness
# ---------------------------------------------------------------------------

def _calc_product_completeness(case: ProductCase) -> Tuple[float, List[dict]]:
    """Calculate product completeness and return checklist."""
    ingredients = _deserialize(case.ingredients)
    jurisdictions = _deserialize(case.jurisdictions)
    claims = _deserialize(case.claims)

    checks = [
        {"label": "Product Name", "status": "KNOWN" if case.name else "MISSING"},
        {"label": "Ingredients", "status": "KNOWN" if ingredients else "MISSING"},
        {"label": "Product Form", "status": "KNOWN" if case.form else "MISSING"},
        {"label": "Intended Use", "status": "KNOWN" if case.intended_use else "MISSING"},
        {"label": "Formulation", "status": "KNOWN" if case.formulation else "MISSING"},
        {"label": "Preparation Process", "status": "KNOWN" if case.process else "MISSING"},
        {"label": "Target Jurisdictions", "status": "KNOWN" if jurisdictions else "MISSING"},
        {"label": "Claims", "status": "KNOWN" if claims else "MISSING"},
        {"label": "Brand", "status": "KNOWN" if case.brand else "MISSING"},
    ]

    # Check for verification needs
    for ing in ingredients:
        if isinstance(ing, dict) and ing.get("status") == "NEEDS_VERIFICATION":
            checks.append({"label": f"Botanical Identity: {ing.get('name', 'Unknown')}", "status": "NEEDS_VERIFICATION"})

    known = sum(1 for c in checks if c["status"] == "KNOWN")
    total = len(checks)
    pct = round((known / total) * 100) if total > 0 else 0

    return pct, checks


# ---------------------------------------------------------------------------
# Readiness calculation
# ---------------------------------------------------------------------------

def _calc_readiness(
    case: ProductCase,
    completeness_pct: float,
    evidence_coverage: float,
    risk_dicts: List[dict],
    extension_dicts: List[dict],
    has_innovation: bool,
    has_patent_search: bool,
    has_regulatory: bool,
    jurisdictions: List[str],
) -> dict:
    """Calculate readiness level and explanation."""
    reasons = []
    next_steps = []

    # Check product completeness
    if completeness_pct < 40:
        reasons.append("Product information is largely incomplete.")
        next_steps.append("Complete the Product Passport with basic product details.")
    elif completeness_pct < 70:
        reasons.append("Product information is partially complete.")
        next_steps.append("Add missing Product Passport details.")

    # Check evidence
    if evidence_coverage < 50:
        reasons.append("Evidence coverage is limited.")
        next_steps.append("Generate analyses to build evidence base.")

    # Check high risks
    high_risks = [r for r in risk_dicts if r.get("level") == "HIGH"]
    if high_risks:
        reasons.append(f"{len(high_risks)} high-priority risk(s) require attention.")
        for r in high_risks[:2]:
            next_steps.append(r.get("next_action", "Review risk."))

    # Check missing analyses
    if not has_innovation and _deserialize(case.ingredients):
        reasons.append("Innovation analysis has not been performed.")
        next_steps.append("Run Innovation Analysis to identify differentiated components.")

    if not has_patent_search and _deserialize(case.ingredients):
        reasons.append("Patent search has not been performed.")
        next_steps.append("Run Patent Intelligence to check for relevant prior art.")

    if not has_regulatory and jurisdictions:
        reasons.append("Regulatory analysis has not been performed for target jurisdictions.")
        next_steps.append("Run Regulatory Intelligence for each target jurisdiction.")

    if not jurisdictions:
        reasons.append("No target jurisdictions selected.")
        next_steps.append("Select target market(s) in Product Passport.")

    # Check self-extensions
    high_exts = [e for e in extension_dicts if e.get("priority") == "HIGH"]
    if high_exts:
        reasons.append(f"{len(high_exts)} high-priority information gap(s) remain.")
        for e in high_exts[:2]:
            next_steps.append(e.get("suggested_action", "Address information gap."))

    # Determine readiness
    if not reasons:
        level = "READY_FOR_NEXT_STEP"
    elif high_risks or (completeness_pct < 40):
        level = "NOT_READY"
    elif completeness_pct >= 70 and evidence_coverage >= 60 and not high_risks:
        level = "READY_FOR_NEXT_STEP"
    elif completeness_pct >= 40:
        level = "REVIEW_REQUIRED"
    else:
        level = "PARTIALLY_READY"

    return {
        "level": level,
        "explanation": reasons[:5],
        "next_steps": next_steps[:5],
    }


# ---------------------------------------------------------------------------
# Main dashboard generation
# ---------------------------------------------------------------------------

def generate_decision_dashboard(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Generate the Product Decision Dashboard for a Product Case.

    Dynamically aggregates data from all 12 phases.
    """
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    ingredients = _deserialize(case.ingredients)
    jurisdictions = _deserialize(case.jurisdictions)
    claims = _deserialize(case.claims)

    # Product snapshot
    product_snapshot = {
        "name": case.name,
        "stage": case.stage,
        "status": case.status,
        "form": case.form,
        "intended_use": case.intended_use,
        "ingredients_count": len(ingredients),
        "jurisdictions": jurisdictions,
        "brand": case.brand,
    }

    # Product completeness
    completeness_pct, completeness_checks = _calc_product_completeness(case)

    # Innovation analysis
    innovation = db.query(InnovationAnalysis).filter(InnovationAnalysis.product_case_id == case.id).order_by(InnovationAnalysis.created_at.desc()).first()
    has_innovation = innovation is not None
    innovation_components = innovation.total_components if innovation else 0
    differentiated_count = innovation.differentiated_count if innovation else 0

    # Patent analysis
    patent_search = db.query(PatentSearch).filter(PatentSearch.product_case_id == case.id).order_by(PatentSearch.created_at.desc()).first()
    has_patent_search = patent_search is not None
    patent_analyses = db.query(PatentAnalysis).filter(PatentAnalysis.product_case_id == case.id).count()
    patent_relevances = db.query(PatentRelevance).filter(PatentRelevance.product_case_id == case.id).count()
    patent_review_status = "GOOD" if patent_analyses > 0 else ("PARTIAL" if has_patent_search else "LIMITED")

    # IP Strategy
    ip_strategy = db.query(IPStrategy).filter(IPStrategy.product_case_id == case.id).order_by(IPStrategy.created_at.desc()).first()
    ip_strategy_items = ip_strategy.total_items if ip_strategy else 0

    # Regulatory
    reg_profiles = db.query(RegulatoryProfile).filter(RegulatoryProfile.product_case_id == case.id).all()
    has_regulatory = len(reg_profiles) > 0
    reg_categories = [rp.potential_category for rp in reg_profiles if rp.potential_category]
    reg_total_reqs = sum(rp.total_requirements for rp in reg_profiles)
    reg_gaps = sum(rp.info_missing_count for rp in reg_profiles)
    regulatory_status = "GOOD" if len(reg_profiles) >= 2 else ("PARTIAL" if len(reg_profiles) >= 1 else "LIMITED")

    # Evidence
    ev_data = aggregate_case_evidence(db, user, case_public_id)
    evidence_coverage = ev_data.get("citation_coverage", 0) if ev_data else 0
    total_findings = ev_data.get("total_findings", 0) if ev_data else 0
    evidence_status = "GOOD" if evidence_coverage >= 80 else ("PARTIAL" if evidence_coverage >= 50 else "LIMITED")

    # Risks (from Phase 12 service)
    risk_dicts = []
    risk_dicts.extend(_detect_patent_risks(db, case))
    risk_dicts.extend(_detect_regulatory_risks(db, case))
    risk_dicts.extend(_detect_claims_risks(db, case))
    risk_dicts.extend(_detect_info_risks(db, case))
    risk_dicts.extend(_detect_jurisdiction_risks(db, case))

    high_risks = [r for r in risk_dicts if r.get("level") == "HIGH"]
    medium_risks = [r for r in risk_dicts if r.get("level") == "MEDIUM"]
    low_risks = [r for r in risk_dicts if r.get("level") == "LOW"]
    risk_status = "ATTENTION_REQUIRED" if high_risks else ("WATCH" if medium_risks else "CLEAR")

    # Self-extensions
    extension_dicts = _detect_self_extensions(db, case)

    # Decision summary
    ip_status = "REVIEW_REQUIRED" if patent_review_status != "GOOD" else "GOOD"
    ip_reason = "Potentially relevant patent identified." if patent_relevances > 0 else "Patent search completed." if has_patent_search else "Patent search not yet performed."

    reg_status = regulatory_status
    reg_reason = f"{len(reg_profiles)} jurisdiction(s) analyzed." if has_regulatory else "Regulatory analysis not yet performed."

    product_completeness_status = "GOOD" if completeness_pct >= 70 else ("PARTIAL" if completeness_pct >= 40 else "LIMITED")

    decision_summary = {
        "ip_status": ip_status,
        "ip_reason": ip_reason,
        "regulatory_status": reg_status,
        "regulatory_reason": reg_reason,
        "evidence_status": evidence_status,
        "evidence_coverage": evidence_coverage,
        "risk_status": risk_status,
        "high_risks": len(high_risks),
        "product_completeness_status": product_completeness_status,
        "product_completeness_pct": completeness_pct,
    }

    # Key findings
    key_findings = []
    if patent_relevances > 0:
        key_findings.append({
            "title": f"{patent_relevances} potentially relevant patent record(s) identified",
            "description": "Patent intelligence found records that may be relevant to your product.",
            "source_phase": "PHASE_6_PATENT",
            "evidence_available": True,
            "category": "PATENT",
        })
    if high_risks:
        key_findings.append({
            "title": f"{len(high_risks)} high-priority risk(s) detected",
            "description": high_risks[0].get("description", "Review required."),
            "source_phase": high_risks[0].get("source_phase"),
            "evidence_available": len(high_risks[0].get("evidence", [])) > 0,
            "category": "RISK",
        })
    if differentiated_count > 0:
        key_findings.append({
            "title": f"{differentiated_count} potentially differentiated component(s) identified",
            "description": "Innovation analysis found components that may warrant further investigation.",
            "source_phase": "PHASE_5_INNOVATION",
            "evidence_available": True,
            "category": "INNOVATION",
        })
    if reg_gaps > 0:
        key_findings.append({
            "title": f"{reg_gaps} regulatory information gap(s) identified",
            "description": "Regulatory analysis found missing information that should be addressed.",
            "source_phase": "PHASE_9_REGULATORY",
            "evidence_available": True,
            "category": "REGULATORY",
        })

    # Top risks (first 5)
    top_risks = []
    for r in (high_risks + medium_risks + low_risks)[:5]:
        top_risks.append({
            "level": r["level"],
            "title": r["title"],
            "description": r.get("description"),
            "category": r.get("category"),
        })

    # Information gaps
    info_gaps = []
    for ext in extension_dicts[:5]:
        info_gaps.append({
            "title": ext["title"],
            "description": ext.get("description"),
            "priority": ext.get("priority", "MEDIUM"),
            "suggested_action": ext.get("suggested_action"),
        })

    # Recommended actions
    recommended_actions = []
    for r in risk_dicts[:3]:
        if r.get("next_action"):
            recommended_actions.append({
                "priority": r.get("level", "MEDIUM"),
                "title": r["title"][:80],
                "description": r.get("next_action"),
                "action_label": "View Risk",
                "action_view": "risk",
            })
    for ext in extension_dicts[:3]:
        recommended_actions.append({
            "priority": ext.get("priority", "MEDIUM"),
            "title": ext["title"],
            "description": ext.get("suggested_action"),
            "action_label": "Resolve",
            "action_view": ext.get("resolve_url"),
        })

    ip_readiness = calculate_ip_readiness(case, db=db)

    # IP summary
    ip_summary = {
        "innovation_components": innovation_components,
        "differentiated_count": differentiated_count,
        "patent_review_status": patent_review_status,
        "ip_strategy_items": ip_strategy_items,
        "ip_readiness_score": ip_readiness["readiness_score"],
        "ip_readiness_level": ip_readiness["readiness_level"],
        "ip_readiness": ip_readiness,
    }

    # Regulatory summary
    reg_summary = {
        "jurisdictions_analyzed": len(reg_profiles),
        "categories": list(set(reg_categories)),
        "total_requirements": reg_total_reqs,
        "gaps": reg_gaps,
    }

    # Jurisdiction summary
    from api.services.regulatory_adapter import SUPPORTED_JURISDICTIONS
    jurisdiction_items = []
    for rp in reg_profiles:
        jur_info = SUPPORTED_JURISDICTIONS.get(rp.jurisdiction, {})
        jurisdiction_items.append({
            "jurisdiction": rp.jurisdiction,
            "flag": jur_info.get("flag", ""),
            "regulatory_coverage": "GOOD" if rp.relevant_count > 0 else ("PARTIAL" if rp.potentially_relevant_count > 0 else "LIMITED"),
            "evidence_coverage": "GOOD" if rp.sources_configured > 0 else "LIMITED",
            "key_issue": rp.information_gaps[0] if rp.information_gaps and _deserialize(rp.information_gaps) else None,
        })

    # Readiness
    readiness = _calc_readiness(
        case, completeness_pct, evidence_coverage, risk_dicts, extension_dicts,
        has_innovation, has_patent_search, has_regulatory, jurisdictions,
    )

    # Dashboard status
    if readiness["level"] == "READY_FOR_NEXT_STEP":
        dashboard_status = "READY_FOR_NEXT_STEP"
    elif readiness["level"] == "NOT_READY":
        dashboard_status = "DATA_INCOMPLETE"
    else:
        dashboard_status = "REVIEW_REQUIRED"

    return {
        "product_case_id": case.public_id,
        "product_name": case.name,
        "dashboard_status": dashboard_status,
        "last_updated": (case.updated_at or case.created_at).isoformat() if case.updated_at or case.created_at else "",

        "product_snapshot": product_snapshot,
        "decision_summary": decision_summary,
        "key_findings": key_findings,
        "top_risks": top_risks,
        "information_gaps": info_gaps,
        "recommended_actions": recommended_actions[:5],
        "ip_summary": ip_summary,
        "regulatory_summary": reg_summary,
        "jurisdictions": jurisdiction_items,
        "readiness": readiness,
    }
