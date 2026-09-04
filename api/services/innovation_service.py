"""AYUR-INTEL — Innovation Decomposition Service.

Breaks a product into meaningful components and classifies each
as traditional/known, potentially differentiated, or requiring
investigation. This is DECISION SUPPORT, not a legal opinion.

No AI provider is required — uses deterministic rule-based analysis.
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
    KnowledgeFinding,
    ProductCase,
    User,
)

logger = logging.getLogger("ayur_intel.innovation_service")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _deserialize_list(value: str) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _analysis_to_dict(analysis: InnovationAnalysis) -> dict:
    components = []
    for comp in analysis.components:
        components.append({
            "id": comp.public_id,
            "component_type": comp.component_type,
            "component_label": comp.component_label,
            "component_value": comp.component_value,
            "sort_order": comp.sort_order,
            "classification": comp.classification,
            "explanation": comp.explanation,
            "confidence": comp.confidence,
            "data_origin": comp.data_origin,
            "evidence_summary": comp.evidence_summary,
            "potential_ip_route": comp.potential_ip_route,
            "investigation_required": comp.investigation_required,
            "created_at": comp.created_at.isoformat() if comp.created_at else "",
            "updated_at": comp.updated_at.isoformat() if comp.updated_at else "",
        })

    return {
        "id": analysis.public_id,
        "product_case_id": analysis.product_case.public_id if analysis.product_case else "",
        "status": analysis.status,
        "total_components": analysis.total_components,
        "traditional_count": analysis.traditional_count,
        "differentiated_count": analysis.differentiated_count,
        "investigation_count": analysis.investigation_count,
        "insufficient_count": analysis.insufficient_count,
        "components": components,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else "",
        "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else "",
    }


# -------------------------------------------------------------------
# Decomposition rules
# -------------------------------------------------------------------

# Well-known Ayurvedic ingredients (simplified list for rule-based classification)
KNOWN_INGREDIENTS = {
    "ashwagandha", "withania somnifera", "brahmi", "bacopa monnieri",
    "tulsi", "holy basil", "ocimum tenuiflorum", "triphala", "amla",
    "ashoka", "shatavari", "guduchi", "giloy", "neem", "turmeric",
    "haridra", "curcuma longa", "mulethi", "licorice", "ginger",
    "cardamom", "cinnamon", "fenugreek", "cumin", "coriander",
    "ajwain", "fennel", "black pepper", "pippali", "vidanga",
    "musta", "kiratatikta", "kalmegh", "bhumyamalaki",
}

KNOWN_FORMS = {
    "powder", "tablet", "capsule", "oil", "liquid", "tea", "decoction",
    "cream", "ointment", "syrup", "granules",
}

# IP route mapping by component type
IP_ROUTE_MAP = {
    "FORMULATION": "Patent review",
    "PROCESS": "Patent / Trade Secret review",
    "EXTRACTION": "Patent / Trade Secret review",
    "COMBINATION": "Prior-art / Patent investigation",
    "PRODUCT_FORM": "Patent / Design review",
    "INTENDED_USE": "Patent / Regulatory review",
    "CLAIMS": "Regulatory review",
    "BRAND": "Trademark review",
    "PACKAGING": "Design / Copyright review",
    "INGREDIENT": "Prior-art / TK context",
}


def _classify_ingredient(name: str, knowledge_titles: List[str]) -> dict:
    """Classify a single ingredient."""
    name_lower = name.lower().strip()

    # Check if it's a known ingredient
    is_known = any(kw in name_lower for kw in KNOWN_INGREDIENTS)

    # Check if there's knowledge evidence for it
    has_evidence = any(name_lower in t.lower() for t in knowledge_titles)

    if is_known and has_evidence:
        return {
            "classification": "TRADITIONAL_OR_KNOWN",
            "explanation": f"'{name}' is a documented ingredient with knowledge findings supporting its traditional use.",
            "confidence": "HIGH",
            "data_origin": "SOURCE_SUPPORTED",
            "evidence_summary": "Matches known traditional ingredient with supporting knowledge findings.",
            "investigation_required": False,
            "potential_ip_route": "Prior-art / TK context",
        }
    elif is_known:
        return {
            "classification": "TRADITIONAL_OR_KNOWN",
            "explanation": f"'{name}' is a well-documented Ayurvedic ingredient with extensive traditional use.",
            "confidence": "HIGH",
            "data_origin": "SYSTEM_DERIVED",
            "evidence_summary": "Recognized as a well-known traditional ingredient.",
            "investigation_required": False,
            "potential_ip_route": "Prior-art / TK context",
        }
    else:
        return {
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": f"'{name}' could not be matched to known traditional ingredients. Further research needed.",
            "confidence": "LOW",
            "data_origin": "USER_PROVIDED",
            "evidence_summary": "No traditional knowledge evidence found for this ingredient.",
            "investigation_required": True,
            "potential_ip_route": "Prior-art / Patent investigation",
        }


def _decompose_and_classify(case: ProductCase, findings: List[KnowledgeFinding]) -> List[dict]:
    """Decompose a Product Case into innovation components and classify each."""

    components = []
    sort_order = 0
    now = datetime.now(timezone.utc)

    # Gather knowledge finding titles for evidence matching
    knowledge_titles = [f.title for f in findings] if findings else []

    # --- Ingredients ---
    ingredients = _deserialize_list(case.ingredients) if case.ingredients else []
    ingredient_names = []
    for ing in ingredients:
        if isinstance(ing, dict):
            name = ing.get("name", "")
        elif isinstance(ing, str):
            name = ing
        else:
            continue
        if not name.strip():
            continue
        ingredient_names.append(name.strip())

        cls = _classify_ingredient(name, knowledge_titles)
        components.append({
            "component_type": "INGREDIENT",
            "component_label": f"Ingredient: {name}",
            "component_value": name,
            "sort_order": sort_order,
            **cls,
        })
        sort_order += 1

    # --- Combination (if 2+ ingredients) ---
    if len(ingredient_names) >= 2:
        combo_name = " + ".join(ingredient_names)
        # Check if this specific combination is well-known
        is_known_combo = len(ingredient_names) == 2 and all(
            any(kw in n.lower() for kw in KNOWN_INGREDIENTS) for n in ingredient_names
        )
        if is_known_combo:
            components.append({
                "component_type": "COMBINATION",
                "component_label": f"Combination: {combo_name}",
                "component_value": combo_name,
                "sort_order": sort_order,
                "classification": "TRADITIONAL_OR_KNOWN",
                "explanation": f"The combination of {combo_name} is found in traditional formulations. However, specific ratios and proportions may require investigation.",
                "confidence": "MEDIUM",
                "data_origin": "SYSTEM_DERIVED",
                "evidence_summary": "Both ingredients are individually well-documented; combination context requires review.",
                "investigation_required": False,
                "potential_ip_route": "Prior-art / TK context",
            })
        else:
            components.append({
                "component_type": "COMBINATION",
                "component_label": f"Combination: {combo_name}",
                "component_value": combo_name,
                "sort_order": sort_order,
                "classification": "POTENTIALLY_DIFFERENTIATED",
                "explanation": f"The specific combination of {combo_name} may be differentiated. Prior-art investigation recommended to assess novelty.",
                "confidence": "MEDIUM",
                "data_origin": "SYSTEM_DERIVED",
                "evidence_summary": "Combination novelty requires prior-art investigation.",
                "investigation_required": True,
                "potential_ip_route": "Prior-art / Patent investigation",
            })
        sort_order += 1

    # --- Formulation ---
    if case.formulation:
        components.append({
            "component_type": "FORMULATION",
            "component_label": "Formulation",
            "component_value": case.formulation,
            "sort_order": sort_order,
            "classification": "POTENTIALLY_DIFFERENTIATED",
            "explanation": "Specific formulation parameters (ratios, concentrations, excipients) may be differentiated. Patent investigation recommended.",
            "confidence": "MEDIUM",
            "data_origin": "USER_PROVIDED",
            "evidence_summary": "User-provided formulation details.",
            "investigation_required": True,
            "potential_ip_route": "Patent review",
        })
    else:
        components.append({
            "component_type": "FORMULATION",
            "component_label": "Formulation",
            "component_value": None,
            "sort_order": sort_order,
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": "No formulation information provided. Cannot assess innovation potential without formulation details.",
            "confidence": "LOW",
            "data_origin": "UNKNOWN",
            "evidence_summary": None,
            "investigation_required": False,
            "potential_ip_route": "Patent review",
        })
    sort_order += 1

    # --- Process / Preparation ---
    if case.process:
        # Check if process mentions common extraction methods
        process_lower = case.process.lower()
        common_methods = ["simple mixing", "grinding", "mixing", "drying"]
        is_common = any(m in process_lower for m in common_methods)

        if is_common:
            components.append({
                "component_type": "PROCESS",
                "component_label": "Preparation Process",
                "component_value": case.process,
                "sort_order": sort_order,
                "classification": "TRADITIONAL_OR_KNOWN",
                "explanation": "The described process appears to use conventional/traditional preparation methods.",
                "confidence": "MEDIUM",
                "data_origin": "USER_PROVIDED",
                "evidence_summary": "User-described process appears conventional.",
                "investigation_required": False,
                "potential_ip_route": "Patent / Trade Secret review",
            })
        else:
            components.append({
                "component_type": "PROCESS",
                "component_label": "Preparation Process",
                "component_value": case.process,
                "sort_order": sort_order,
                "classification": "POTENTIALLY_DIFFERENTIATED",
                "explanation": "The described process may involve non-conventional methods. Patent / Trade Secret investigation recommended.",
                "confidence": "MEDIUM",
                "data_origin": "USER_PROVIDED",
                "evidence_summary": "User-described process may be differentiated.",
                "investigation_required": True,
                "potential_ip_route": "Patent / Trade Secret review",
            })
    else:
        components.append({
            "component_type": "PROCESS",
            "component_label": "Preparation Process",
            "component_value": None,
            "sort_order": sort_order,
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": "No preparation process provided. Cannot assess innovation potential.",
            "confidence": "LOW",
            "data_origin": "UNKNOWN",
            "evidence_summary": None,
            "investigation_required": False,
            "potential_ip_route": "Patent / Trade Secret review",
        })
    sort_order += 1

    # --- Product Form / Delivery ---
    if case.form:
        form_lower = case.form.lower().strip()
        is_known_form = any(kw in form_lower for kw in KNOWN_FORMS)

        if is_known_form:
            components.append({
                "component_type": "PRODUCT_FORM",
                "component_label": "Product Form / Delivery",
                "component_value": case.form,
                "sort_order": sort_order,
                "classification": "TRADITIONAL_OR_KNOWN",
                "explanation": f"'{case.form}' is a common product form. However, novel delivery mechanisms within this form may be differentiated.",
                "confidence": "MEDIUM",
                "data_origin": "USER_PROVIDED",
                "evidence_summary": "Common product form.",
                "investigation_required": False,
                "potential_ip_route": "Patent / Design review",
            })
        else:
            components.append({
                "component_type": "PRODUCT_FORM",
                "component_label": "Product Form / Delivery",
                "component_value": case.form,
                "sort_order": sort_order,
                "classification": "POTENTIALLY_DIFFERENTIATED",
                "explanation": f"'{case.form}' appears to be a non-standard product form. This may represent a differentiated delivery mechanism.",
                "confidence": "MEDIUM",
                "data_origin": "USER_PROVIDED",
                "evidence_summary": "Non-standard product form.",
                "investigation_required": True,
                "potential_ip_route": "Patent / Design review",
            })
    else:
        components.append({
            "component_type": "PRODUCT_FORM",
            "component_label": "Product Form / Delivery",
            "component_value": None,
            "sort_order": sort_order,
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": "No product form specified.",
            "confidence": "LOW",
            "data_origin": "UNKNOWN",
            "evidence_summary": None,
            "investigation_required": False,
            "potential_ip_route": "Patent / Design review",
        })
    sort_order += 1

    # --- Intended Use ---
    if case.intended_use:
        components.append({
            "component_type": "INTENDED_USE",
            "component_label": "Intended Use",
            "component_value": case.intended_use,
            "sort_order": sort_order,
            "classification": "POTENTIALLY_DIFFERENTIATED",
            "explanation": "Specific intended use claims may be differentiated but require regulatory and prior-art review.",
            "confidence": "MEDIUM",
            "data_origin": "USER_PROVIDED",
            "evidence_summary": "User-proposed intended use (labeled as proposed).",
            "investigation_required": True,
            "potential_ip_route": "Patent / Regulatory review",
        })
    else:
        components.append({
            "component_type": "INTENDED_USE",
            "component_label": "Intended Use",
            "component_value": None,
            "sort_order": sort_order,
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": "No intended use specified.",
            "confidence": "LOW",
            "data_origin": "UNKNOWN",
            "evidence_summary": None,
            "investigation_required": False,
            "potential_ip_route": "Patent / Regulatory review",
        })
    sort_order += 1

    # --- Claims ---
    claims = _deserialize_list(case.claims) if case.claims else []
    if claims:
        claims_text = "; ".join(claims)
        components.append({
            "component_type": "CLAIMS",
            "component_label": "Proposed Claims",
            "component_value": claims_text,
            "sort_order": sort_order,
            "classification": "REQUIRES_INVESTIGATION",
            "explanation": "Proposed claims require regulatory and prior-art review. Claims must be substantiated and comply with jurisdiction-specific regulations.",
            "confidence": "LOW",
            "data_origin": "USER_PROVIDED",
            "evidence_summary": "User-proposed claims (not substantiated).",
            "investigation_required": True,
            "potential_ip_route": "Regulatory review",
        })
    else:
        components.append({
            "component_type": "CLAIMS",
            "component_label": "Proposed Claims",
            "component_value": None,
            "sort_order": sort_order,
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": "No claims specified.",
            "confidence": "LOW",
            "data_origin": "UNKNOWN",
            "evidence_summary": None,
            "investigation_required": False,
            "potential_ip_route": "Regulatory review",
        })
    sort_order += 1

    # --- Brand ---
    if case.brand:
        components.append({
            "component_type": "BRAND",
            "component_label": "Brand",
            "component_value": case.brand,
            "sort_order": sort_order,
            "classification": "POTENTIALLY_DIFFERENTIATED",
            "explanation": f"The brand '{case.brand}' should be reviewed for trademark availability and conflicts.",
            "confidence": "MEDIUM",
            "data_origin": "USER_PROVIDED",
            "evidence_summary": "User-provided brand name.",
            "investigation_required": True,
            "potential_ip_route": "Trademark review",
        })
    else:
        components.append({
            "component_type": "BRAND",
            "component_label": "Brand",
            "component_value": None,
            "sort_order": sort_order,
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": "No brand specified.",
            "confidence": "LOW",
            "data_origin": "UNKNOWN",
            "evidence_summary": None,
            "investigation_required": False,
            "potential_ip_route": "Trademark review",
        })
    sort_order += 1

    # --- Packaging ---
    if case.packaging:
        components.append({
            "component_type": "PACKAGING",
            "component_label": "Packaging",
            "component_value": case.packaging,
            "sort_order": sort_order,
            "classification": "POTENTIALLY_DIFFERENTIATED",
            "explanation": "Packaging design may be eligible for design protection or copyright review.",
            "confidence": "LOW",
            "data_origin": "USER_PROVIDED",
            "evidence_summary": "User-provided packaging details.",
            "investigation_required": True,
            "potential_ip_route": "Design / Copyright review",
        })
    else:
        components.append({
            "component_type": "PACKAGING",
            "component_label": "Packaging",
            "component_value": None,
            "sort_order": sort_order,
            "classification": "INSUFFICIENT_INFORMATION",
            "explanation": "No packaging information provided.",
            "confidence": "LOW",
            "data_origin": "UNKNOWN",
            "evidence_summary": None,
            "investigation_required": False,
            "potential_ip_route": "Design / Copyright review",
        })
    sort_order += 1

    return components


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def create_analysis(
    db: Session,
    owner: User,
    case_public_id: str,
) -> Optional[dict]:
    """Create an innovation analysis for a Product Case.

    Reads the case data, decomposes into components, classifies each,
    and persists the results.
    """
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

    # Get existing knowledge findings for evidence matching
    from api.models.models import KnowledgeFinding
    findings = (
        db.query(KnowledgeFinding)
        .filter(KnowledgeFinding.product_case_id == case.id)
        .all()
    )

    # Decompose and classify
    component_data = _decompose_and_classify(case, findings)

    now = datetime.now(timezone.utc)

    # Create analysis record
    analysis = InnovationAnalysis(
        owner_id=owner.id,
        product_case_id=case.id,
        status="COMPLETED",
        total_components=len(component_data),
        traditional_count=sum(1 for c in component_data if c["classification"] == "TRADITIONAL_OR_KNOWN"),
        differentiated_count=sum(1 for c in component_data if c["classification"] == "POTENTIALLY_DIFFERENTIATED"),
        investigation_count=sum(1 for c in component_data if c["classification"] == "REQUIRES_INVESTIGATION"),
        insufficient_count=sum(1 for c in component_data if c["classification"] == "INSUFFICIENT_INFORMATION"),
        created_at=now,
        updated_at=now,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Create component records
    for cdata in component_data:
        comp = InnovationComponent(
            analysis_id=analysis.id,
            component_type=cdata["component_type"],
            component_label=cdata["component_label"],
            component_value=cdata.get("component_value"),
            sort_order=cdata["sort_order"],
            classification=cdata["classification"],
            explanation=cdata.get("explanation"),
            confidence=cdata.get("confidence"),
            data_origin=cdata.get("data_origin"),
            evidence_summary=cdata.get("evidence_summary"),
            potential_ip_route=cdata.get("potential_ip_route"),
            investigation_required=cdata.get("investigation_required", False),
            created_at=now,
            updated_at=now,
        )
        db.add(comp)

    db.commit()
    db.refresh(analysis)

    logger.info(
        "Created innovation analysis %s for case %s (%d components)",
        analysis.public_id, case_public_id, len(component_data),
    )
    return _analysis_to_dict(analysis)


def get_analysis(
    db: Session,
    owner: User,
    case_public_id: str,
) -> Optional[dict]:
    """Get the latest innovation analysis for a Product Case."""
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

    analysis = (
        db.query(InnovationAnalysis)
        .filter(InnovationAnalysis.product_case_id == case.id)
        .order_by(InnovationAnalysis.created_at.desc())
        .first()
    )
    if analysis is None:
        return None

    return _analysis_to_dict(analysis)


def update_component(
    db: Session,
    owner: User,
    component_public_id: str,
    updates: dict,
) -> Optional[dict]:
    """Update a single innovation component."""
    comp = (
        db.query(InnovationComponent)
        .join(InnovationAnalysis)
        .filter(
            InnovationComponent.public_id == component_public_id,
            InnovationAnalysis.owner_id == owner.id,
        )
        .first()
    )
    if comp is None:
        return None

    for field, value in updates.items():
        if value is not None and hasattr(comp, field):
            setattr(comp, field, value)

    comp.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comp)

    return {
        "id": comp.public_id,
        "component_type": comp.component_type,
        "component_label": comp.component_label,
        "classification": comp.classification,
        "explanation": comp.explanation,
        "confidence": comp.confidence,
        "investigation_required": comp.investigation_required,
    }
