"""AYUR-INTEL — IP Strategy Map Service (Phase 8).

Synthesizes Product Passport, Innovation Analysis, Patent Analysis,
and Knowledge Findings into a visual IP investigation roadmap.

This is RESEARCH decision-support, NOT legal advice.
Uses deterministic rule-based mapping — no AI provider required.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    IPStrategy,
    IPStrategyItem,
    InnovationAnalysis,
    InnovationComponent,
    KnowledgeFinding,
    PatentAnalysis,
    PatentRecord,
    ProductCase,
    User,
)

logger = logging.getLogger("ayur_intel.ip_strategy_service")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _deserialize_list(value: Optional[str]) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _get_case(db: Session, user: User, case_public_id: str) -> Optional[ProductCase]:
    return (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == case_public_id,
            ProductCase.owner_id == user.id,
        )
        .first()
    )


def _get_innovation_analysis(db: Session, case: ProductCase) -> Optional[InnovationAnalysis]:
    return (
        db.query(InnovationAnalysis)
        .filter(InnovationAnalysis.product_case_id == case.id)
        .order_by(InnovationAnalysis.created_at.desc())
        .first()
    )


def _get_patent_analysis(db: Session, case: ProductCase) -> Optional[PatentAnalysis]:
    return (
        db.query(PatentAnalysis)
        .filter(PatentAnalysis.product_case_id == case.id)
        .order_by(PatentAnalysis.created_at.desc())
        .first()
    )


def _get_knowledge_findings(db: Session, case: ProductCase) -> List[KnowledgeFinding]:
    return (
        db.query(KnowledgeFinding)
        .filter(KnowledgeFinding.product_case_id == case.id)
        .all()
    )


# -------------------------------------------------------------------
# IP Category Mapping Rules
# -------------------------------------------------------------------

# Maps component_type → (ip_category, ip_route_description, next_action)
IP_CATEGORY_MAP: Dict[str, Tuple[str, str, str]] = {
    "FORMULATION": (
        "PATENT_REVIEW",
        "Potential Patent Review",
        "Review relevant claims and prior art for formulation novelty.",
    ),
    "PROCESS": (
        "COMBINED_IP",
        "Potential Patent / Trade Secret Review",
        "Evaluate whether the process can be protected via patent or kept confidential as trade secret.",
    ),
    "PRODUCT_FORM": (
        "PATENT_REVIEW",
        "Potential Patent Review",
        "Review prior art for similar dosage forms or delivery mechanisms.",
    ),
    "INTENDED_USE": (
        "PATENT_REVIEW",
        "Potential Patent Review",
        "Review relevant claim scope and regulatory considerations.",
    ),
    "CLAIMS": (
        "COMBINED_IP",
        "Potential Patent / Regulatory Review",
        "Review proposed claims against existing prior art and regulatory requirements.",
    ),
    "BRAND": (
        "TRADEMARK",
        "Potential Trademark Review",
        "Conduct trademark availability and conflict review.",
    ),
    "PACKAGING": (
        "DESIGN_COPYRIGHT",
        "Potential Design / Copyright Review",
        "Review design protection options for packaging and visual elements.",
    ),
    "INGREDIENT": (
        "TK_PRIOR_ART",
        "Prior-Art / Traditional Knowledge Context",
        "Review documented Traditional Knowledge context for this ingredient.",
    ),
    "COMBINATION": (
        "PATENT_REVIEW",
        "Potential Patent Review",
        "Review prior art for similar ingredient combinations and formulations.",
    ),
}


# -------------------------------------------------------------------
# Strategy Generation
# -------------------------------------------------------------------

def _classify_innovation_component(
    component: InnovationComponent,
    knowledge_findings: List[KnowledgeFinding],
    patent_analysis: Optional[PatentAnalysis],
) -> Tuple[str, str, str, str, str]:
    """Classify an innovation component into an IP category with priority.

    Returns: (ip_category, ip_route_description, reason, priority, next_action)
    """
    comp_type = component.component_type
    classification = component.classification or ""
    comp_value = component.component_value or ""

    # Get base mapping
    if comp_type in IP_CATEGORY_MAP:
        ip_cat, ip_desc, base_next = IP_CATEGORY_MAP[comp_type]
    else:
        ip_cat = "PATENT_REVIEW"
        ip_desc = "Potential IP Review"
        base_next = "Further investigation recommended."

    # Determine priority based on classification
    priority = "MEDIUM"
    reason = component.explanation or ""

    if classification == "POTENTIALLY_DIFFERENTIATED":
        priority = "HIGH"
        reason = reason or "Potentially differentiated element identified."
    elif classification == "REQUIRES_INVESTIGATION":
        priority = "HIGH"
        reason = reason or "Element requires further investigation."
    elif classification == "TRADITIONAL_OR_KNOWN":
        priority = "LOW"
        reason = reason or "Documented traditional/known element."
    elif classification == "INSUFFICIENT_INFORMATION":
        priority = "INFORMATION_NEEDED"
        reason = "More product information needed to assess IP relevance."
        base_next = "Provide additional product details before detailed IP assessment."

    # If patent analysis shows overlap, boost priority
    if patent_analysis and patent_analysis.overall_relevance in ("HIGH_POTENTIAL_OVERLAP", "MEDIUM_POTENTIAL_OVERLAP"):
        if comp_type in ("FORMULATION", "PROCESS", "COMBINATION"):
            priority = "HIGH"
            reason += " Potentially relevant patent records identified."

    # Check for TK knowledge findings
    has_tk = any(
        (kf.category or "").upper() in ("TRADITIONAL_USE", "TRADITIONAL_KNOWLEDGE", "AYURVEDA")
        for kf in knowledge_findings
    )
    if comp_type == "INGREDIENT" and has_tk:
        ip_cat = "TK_PRIOR_ART"
        ip_desc = "Prior-Art / Traditional Knowledge Context"
        priority = "MEDIUM"
        reason = "Traditional Knowledge documentation available for this ingredient."
        base_next = "Review documented TK/prior-art context."

    return ip_cat, ip_desc, reason, priority, base_next


def generate_ip_strategy(
    db: Session,
    user: User,
    case_public_id: str,
) -> Optional[IPStrategy]:
    """Generate an IP Strategy Map for a Product Case.

    Reads data from:
    - Product Case / Passport
    - Innovation Analysis (Phase 5)
    - Patent Analysis (Phase 7)
    - Knowledge Findings (Phase 3)

    Returns the saved IPStrategy or None if inputs are missing.
    """
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    # Gather existing analyses
    innovation_analysis = _get_innovation_analysis(db, case)
    patent_analysis = _get_patent_analysis(db, case)
    knowledge_findings = _get_knowledge_findings(db, case)

    # Create or update strategy
    existing = (
        db.query(IPStrategy)
        .filter(IPStrategy.product_case_id == case.id, IPStrategy.owner_id == user.id)
        .order_by(IPStrategy.created_at.desc())
        .first()
    )
    if existing:
        # Delete old items
        for item in existing.items:
            db.delete(item)
        db.flush()
        strategy = existing
        strategy.updated_at = datetime.now(timezone.utc)
    else:
        strategy = IPStrategy(
            owner_id=user.id,
            product_case_id=case.id,
        )
        db.add(strategy)
        db.flush()

    # Build items from innovation components
    items: List[IPStrategyItem] = []

    if innovation_analysis and innovation_analysis.components:
        for comp in innovation_analysis.components:
            ip_cat, ip_desc, reason, priority, next_action = _classify_innovation_component(
                comp, knowledge_findings, patent_analysis
            )

            # Determine confidence
            confidence = comp.confidence or "MEDIUM"
            if priority == "INFORMATION_NEEDED":
                confidence = "LOW"

            # Determine evidence source
            evidence_source = "Phase 5: Innovation Analysis"
            evidence_detail = comp.evidence_summary or comp.explanation

            # If patent analysis exists and relates to this component type
            if patent_analysis:
                for comparison in patent_analysis.comparisons:
                    if comparison.product_component_type == comp.component_type:
                        evidence_source = "Phase 5: Innovation Analysis + Phase 7: Patent Analysis"
                        evidence_detail = (evidence_detail or "") + (
                            f" Patent analysis: {comparison.similarity_level} similarity — "
                            f"{comparison.explanation or 'No detail available.'}"
                        )
                        break

            item = IPStrategyItem(
                strategy_id=strategy.id,
                innovation_component_id=comp.id,
                component_type= comp.component_type,
                component_label=comp.component_label or comp.component_type,
                component_value=comp.component_value,
                ip_category=ip_cat,
                ip_route_description=ip_desc,
                reason=reason,
                evidence_source=evidence_source,
                evidence_detail=evidence_detail,
                priority=priority,
                confidence=confidence,
                status="RECOMMENDED",
                next_action=next_action,
                patent_analysis_id=patent_analysis.id if patent_analysis else None,
                innovation_analysis_id=innovation_analysis.id if innovation_analysis else None,
            )
            items.append(item)
    else:
        # No innovation analysis — create info-needed items for basic components
        basic_components = [
            ("FORMULATION", "Formulation"),
            ("PROCESS", "Preparation Process"),
            ("BRAND", "Brand"),
            ("PACKAGING", "Packaging"),
        ]
        for comp_type, comp_label in basic_components:
            ip_cat, ip_desc, _, _, next_action = IP_CATEGORY_MAP.get(
                comp_type, ("PATENT_REVIEW", "Potential IP Review", "Investigate further.")
            )
            item = IPStrategyItem(
                strategy_id=strategy.id,
                component_type=comp_type,
                component_label=comp_label,
                component_value=None,
                ip_category=ip_cat,
                ip_route_description=ip_desc,
                reason="No Innovation Analysis available. Basic mapping applied.",
                evidence_source="System default mapping",
                evidence_detail=None,
                priority="INFORMATION_NEEDED",
                confidence="LOW",
                status="RECOMMENDED",
                next_action=f"Complete Innovation Analysis before detailed {comp_label} assessment.",
            )
            items.append(item)

    # Add brand trademark item if brand exists on the case
    brand = case.brand or ""
    if brand and not any(i.component_type == "BRAND" for i in items):
        item = IPStrategyItem(
            strategy_id=strategy.id,
            component_type="BRAND",
            component_label="Brand Name",
            component_value=brand,
            ip_category="TRADEMARK",
            ip_route_description="Potential Trademark Review",
            reason=f"Brand name '{brand}' identified in Product Passport.",
            evidence_source="Phase 4: Product Passport",
            evidence_detail=brand,
            priority="MEDIUM",
            confidence="MEDIUM",
            status="RECOMMENDED",
            next_action="Conduct trademark availability and conflict review.",
        )
        items.append(item)

    # Add packaging item if packaging exists
    packaging = case.packaging or ""
    if packaging and not any(i.component_type == "PACKAGING" for i in items):
        item = IPStrategyItem(
            strategy_id=strategy.id,
            component_type="PACKAGING",
            component_label="Packaging / Visual Design",
            component_value=packaging,
            ip_category="DESIGN_COPYRIGHT",
            ip_route_description="Potential Design / Copyright Review",
            reason=f"Packaging described: '{packaging}'.",
            evidence_source="Phase 4: Product Passport",
            evidence_detail=packaging,
            priority="LOW",
            confidence="MEDIUM",
            status="RECOMMENDED",
            next_action="Review design protection options for packaging.",
        )
        items.append(item)

    # Save all items
    for item in items:
        db.add(item)

    # Update strategy counts
    strategy.total_items = len(items)
    strategy.high_priority_count = sum(1 for i in items if i.priority == "HIGH")
    strategy.medium_priority_count = sum(1 for i in items if i.priority == "MEDIUM")
    strategy.low_priority_count = sum(1 for i in items if i.priority == "LOW")
    strategy.info_needed_count = sum(1 for i in items if i.priority == "INFORMATION_NEEDED")

    db.commit()
    db.refresh(strategy)

    return strategy


# -------------------------------------------------------------------
# Serialization
# -------------------------------------------------------------------

def strategy_to_dict(strategy: IPStrategy) -> dict:
    """Serialize an IPStrategy to a JSON-safe dict."""
    items = []
    for item in strategy.items:
        items.append({
            "id": item.public_id,
            "component_type": item.component_type,
            "component_label": item.component_label,
            "component_value": item.component_value,
            "ip_category": item.ip_category,
            "ip_route_description": item.ip_route_description,
            "reason": item.reason,
            "evidence_source": item.evidence_source,
            "evidence_detail": item.evidence_detail,
            "priority": item.priority,
            "confidence": item.confidence,
            "status": item.status,
            "next_action": item.next_action,
            "created_at": item.created_at.isoformat() if item.created_at else "",
        })

    return {
        "id": strategy.public_id,
        "product_case_id": strategy.product_case.public_id if strategy.product_case else "",
        "product_name": strategy.product_case.name if strategy.product_case else "",
        "total_items": strategy.total_items,
        "high_priority_count": strategy.high_priority_count,
        "medium_priority_count": strategy.medium_priority_count,
        "low_priority_count": strategy.low_priority_count,
        "info_needed_count": strategy.info_needed_count,
        "status": strategy.status,
        "items": items,
        "created_at": strategy.created_at.isoformat() if strategy.created_at else "",
        "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else "",
    }
