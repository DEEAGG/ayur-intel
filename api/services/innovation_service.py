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
from typing import Any, Dict, List, Optional

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


# ===================================================================
# Combined Innovation Analysis & Professional Report Service
# ===================================================================

TRADITIONAL_INGREDIENTS = {
    "ashwagandha": {"traditional_uses": ["stress relief", "adaptogen", "vitality"], "classical_text": "Charaka Samhita"},
    "brahmi": {"traditional_uses": ["memory", "cognition", "brain health"], "classical_text": "Charaka Samhita"},
    "tulsi": {"traditional_uses": ["immunity", "respiratory", "stress"], "classical_text": "Sushruta Samhita"},
    "turmeric": {"traditional_uses": ["anti-inflammatory", "wound healing"], "classical_text": "Sushruta Samhita"},
    "amla": {"traditional_uses": ["immunity", "digestion", "rejuvenation"], "classical_text": "Charaka Samhita"},
    "triphala": {"traditional_uses": ["digestion", "detox", "rejuvenation"], "classical_text": "Charaka Samhita"},
    "shatavari": {"traditional_uses": ["women's health", "hormonal balance"], "classical_text": "Charaka Samhita"},
    "giloy": {"traditional_uses": ["immunity", "fever", "general wellness"], "classical_text": "Sushruta Samhita"},
    "neem": {"traditional_uses": ["skin health", "blood purification"], "classical_text": "Sushruta Samhita"},
    "jatamansi": {"traditional_uses": ["nervine", "sleep", "mental clarity"], "classical_text": "Ashtanga Hridaya"},
    "mulethi": {"traditional_uses": ["respiratory", "digestion", "soothing"], "classical_text": "Charaka Samhita"},
    "haritaki": {"traditional_uses": ["digestion", "detox", "rejuvenation"], "classical_text": "Charaka Samhita"},
    "bibhitaki": {"traditional_uses": ["respiratory", "vision", "digestion"], "classical_text": "Charaka Samhita"},
    "shankhpushpi": {"traditional_uses": ["brain health", "memory", "sleep"], "classical_text": "Charaka Samhita"},
    "guggul": {"traditional_uses": ["joint health", "lipid metabolism"], "classical_text": "Sushruta Samhita"},
    "ginger": {"traditional_uses": ["digestion", "circulation", "nausea"], "classical_text": "Charaka Samhita"},
}


def analyze_innovation(case_data: Any) -> dict:
    """Analyze product formulation and generate combined professional report"""
    if isinstance(case_data, dict):
        ingredients = case_data.get('ingredients', [])
        form = case_data.get('form', '') or case_data.get('dosage_form', '') or case_data.get('formulation', '')
        process = case_data.get('process', '')
        intended_use = case_data.get('intended_use', '')
        claims = case_data.get('claims', [])
        name = case_data.get('name', 'Unnamed Product')
    else:
        ingredients = getattr(case_data, 'ingredients', [])
        form = getattr(case_data, 'form', '') or getattr(case_data, 'formulation', '')
        process = getattr(case_data, 'process', '')
        intended_use = getattr(case_data, 'intended_use', '')
        claims = getattr(case_data, 'claims', [])
        name = getattr(case_data, 'name', 'Unnamed Product')

    if isinstance(ingredients, str):
        try:
            ingredients = json.loads(ingredients)
        except Exception:
            ingredients = []
    if not isinstance(ingredients, list):
        ingredients = []

    # Parse ingredients
    ingredient_names = []
    for ing in ingredients:
        if isinstance(ing, dict):
            ing_name = ing.get('name') or ing.get('input_name') or ''
            if ing_name:
                ingredient_names.append(ing_name.lower())
        elif isinstance(ing, str):
            ingredient_names.append(ing.lower())

    # Identify traditional vs innovative
    traditional_elements = []
    innovative_elements = []
    unique_combinations = []
    all_findings = []

    # Check each ingredient
    for ing_name in ingredient_names:
        matched = False
        for key, data in TRADITIONAL_INGREDIENTS.items():
            if key in ing_name or ing_name in key:
                traditional_elements.append({
                    "name": ing_name.title(),
                    "reason": f"Classical Ayurvedic ingredient used in {data['classical_text']} for {data['traditional_uses'][0]}",
                    "classical_text": data['classical_text']
                })
                all_findings.append({
                    "type": "traditional",
                    "name": ing_name.title(),
                    "detail": f"Classical ingredient from {data['classical_text']} used for {data['traditional_uses'][0]}"
                })
                matched = True
                break
        if not matched:
            innovative_elements.append({
                "name": ing_name.title(),
                "reason": "Less commonly used or novel ingredient in Ayurvedic formulations"
            })
            all_findings.append({
                "type": "innovative",
                "name": ing_name.title(),
                "detail": "Novel ingredient with potential for differentiation"
            })

    # Check formulation
    if form:
        form_str = str(form).strip()
        if any(f in form_str.lower() for f in ['capsule', 'tablet', 'extract', 'liquid extract', 'nano', 'liposomal', 'serum', 'gel']):
            innovative_elements.append({
                "name": f"Modern {form_str} Format",
                "reason": "Traditional Ayurvedic formulations were typically powders, decoctions, or medicated oils. Modern dosage forms like capsules/extracts are contemporary innovations."
            })
            all_findings.append({
                "type": "innovative",
                "name": f"Modern {form_str} Format",
                "detail": "Contemporary dosage form innovation"
            })
        else:
            traditional_elements.append({
                "name": f"Traditional {form_str} Format",
                "reason": "Classical Ayurvedic delivery form"
            })
            all_findings.append({
                "type": "traditional",
                "name": f"Traditional {form_str} Format",
                "detail": "Classical Ayurvedic delivery form"
            })

    # Check process
    if process:
        process_str = str(process).strip()
        if any(word in process_str.lower() for word in ['extract', 'standardized', 'hplc', 'modern', 'supercritical', 'co2', 'spray dry']):
            innovative_elements.append({
                "name": "Modern Extraction Process",
                "reason": "Use of standardized/modern extraction methods represents technical innovation"
            })
            all_findings.append({
                "type": "innovative",
                "name": "Modern Extraction Process",
                "detail": "Technical innovation in processing"
            })
        else:
            traditional_elements.append({
                "name": "Traditional Preparation",
                "reason": "Follows classical Ayurvedic preparation methods"
            })
            all_findings.append({
                "type": "traditional",
                "name": "Traditional Preparation",
                "detail": "Classical preparation method"
            })

    # Check unique combinations
    if len(ingredient_names) >= 2:
        traditional_pairs = [
            ('ashwagandha', 'brahmi'),
            ('triphala', 'amla'),
            ('tulsi', 'giloy'),
            ('shatavari', 'ashwagandha'),
            ('turmeric', 'neem'),
        ]

        is_traditional_pair = False
        for pair in traditional_pairs:
            if pair[0] in ingredient_names and pair[1] in ingredient_names:
                is_traditional_pair = True
                break

        if not is_traditional_pair:
            unique_combinations.append({
                "name": "Unique Ingredient Combination",
                "reason": f"This combination of {', '.join([i.title() for i in ingredient_names[:3]])} is not a traditional classical combination, potentially novel"
            })
            all_findings.append({
                "type": "innovative",
                "name": "Unique Ingredient Combination",
                "detail": f"Novel combination of {', '.join([i.title() for i in ingredient_names[:3]])}"
            })

    return {
        "product_name": name,
        "total_ingredients": len(ingredients),
        "traditional_elements": traditional_elements,
        "innovative_elements": innovative_elements,
        "unique_combinations": unique_combinations,
        "confidence": "High" if len(ingredients) >= 3 else "Medium" if len(ingredients) >= 1 else "Low",
        "innovation_insights": generate_innovation_insights(traditional_elements, innovative_elements, ingredients, form, process, intended_use),
        "enhancement_suggestions": generate_enhancement_suggestions(traditional_elements, innovative_elements, unique_combinations, ingredients, form, process),
        "recommendations": [
            "Review traditional elements for prior art",
            "Focus IP strategy on innovative elements",
            "Consider patent search for unique combinations",
            "Consult with patent attorney for novelty assessment"
        ]
    }


def generate_enhancement_suggestions(traditional_elements, innovative_elements, unique_combinations, ingredients, form=None, process=None):
    """Generate actionable enhancement suggestions with detailed reasons"""
    suggestions = []

    # Based on traditional elements
    if traditional_elements:
        classical_text = traditional_elements[0].get('classical_text', 'Ayurvedic texts')
        ingredients_list = ', '.join([el.get('name', '') for el in traditional_elements[:2]])
        suggestions.append({
            "title": "Build on Traditional Knowledge",
            "description": "Your formulation uses classical ingredients. Consider adding more herbs from the same classical text for synergistic effects.",
            "icon": "📜",
            "action": "Research other ingredients",
            "detail": f"Your product uses {ingredients_list} which are mentioned in {classical_text}. Adding complementary ingredients from the same text could create a more complete formulation with better efficacy and credibility.",
            "full_detail": f"The classical texts describe these ingredients in specific combinations. Researching and adding more ingredients from {classical_text} could enhance both efficacy and market credibility."
        })

    # Based on innovative elements
    if not innovative_elements:
        suggestions.append({
            "title": "Add Modern Delivery Format",
            "description": "Consider using modern formats like capsules, liquid extracts, or transdermal patches to differentiate your product.",
            "icon": "💊",
            "action": "Explore modern delivery",
            "detail": "Currently using traditional delivery format. Modern formats offer better dosing accuracy, convenience, and consumer appeal.",
            "full_detail": "Traditional Ayurvedic products typically use powders or decoctions. Modern formats like capsules, tablets, or extracts improve consumer convenience and allow for more precise dosing. This differentiation can be valuable for IP protection."
        })
    else:
        suggestions.append({
            "title": "Enhance Your Innovation",
            "description": "Your modern delivery format is a good start. Consider adding standardized extracts or novel combinations.",
            "icon": "🚀",
            "action": "Explore novel combinations",
            "detail": "Your use of modern formats is a good foundation. Adding standardized extracts or novel combinations could further enhance differentiation.",
            "full_detail": "Standardized extracts ensure consistent potency and quality. Combining multiple innovative elements creates a stronger IP position."
        })

    # Based on unique combinations
    if unique_combinations:
        combo_ingredients = unique_combinations[0].get('name', 'unique combination')
        suggestions.append({
            "title": "Strengthen Your Unique Combination",
            "description": "Your unique ingredient combination is promising. Consider adding supporting ingredients or clinical validation.",
            "icon": "🔗",
            "action": "Explore clinical validation",
            "detail": f"The combination of ingredients in your product is unique and not found in classical texts. This creates an opportunity for IP protection.",
            "full_detail": f"Your unique combination of {combo_ingredients} represents a novel formulation. Supporting this with clinical validation could strengthen both market claims and IP protection."
        })
    else:
        suggestions.append({
            "title": "Create Unique Combinations",
            "description": "Consider combining ingredients in novel ways that aren't found in classical texts for differentiation.",
            "icon": "✨",
            "action": "Research unique combinations",
            "detail": "Classical texts describe many ingredient combinations. Combining ingredients in novel ways creates differentiation.",
            "full_detail": "Researching different ingredient combinations that aren't found in classical texts could create unique formulations with IP protection potential."
        })

    # Based on ingredients count
    if len(ingredients) < 3:
        suggestions.append({
            "title": "Add More Ingredients",
            "description": "Consider adding 1-2 more supporting herbs to create a more complete formulation.",
            "icon": "🌿",
            "action": "Research complementary ingredients",
            "detail": f"Your current formulation has {len(ingredients)} ingredients. Adding 1-2 more supporting herbs could create a more comprehensive product.",
            "full_detail": f"With {len(ingredients)} ingredients, your product addresses a limited scope. Adding complementary herbs could broaden efficacy and appeal."
        })

    # General suggestions
    suggestions.append({
        "title": "Document Your Process",
        "description": "Document your manufacturing process in detail. This can be valuable for IP protection.",
        "icon": "📝",
        "action": "Start documenting process",
        "detail": "Well-documented processes can support trade secret protection and enhance patent applications.",
        "full_detail": "Documentation of manufacturing processes, including critical parameters and quality controls, can support IP protection strategies."
    })

    return suggestions


def generate_innovation_insights(traditional_elements, innovative_elements, ingredients, form=None, process=None, intended_use=None):
    """Generate insights with detailed reasons"""
    insights = []

    # Check formulation strength
    if len(ingredients) >= 3 and innovative_elements:
        insights.append({
            "title": "Strong Formulation",
            "description": "Your product has a good balance of traditional and innovative elements.",
            "type": "positive",
            "detail": "This product combines multiple classical ingredients with modern innovative elements. The balance suggests a formulation that respects traditional knowledge while incorporating contemporary advances, potentially increasing market appeal and IP protection opportunities.",
            "icon": "✅"
        })
    elif innovative_elements:
        insights.append({
            "title": "Innovative Approach",
            "description": "Your product shows clear innovation in formulation or processing.",
            "type": "positive",
            "detail": "The presence of innovative elements indicates that this product moves beyond traditional formulations. This is a strong foundation for differentiation in the market and potential IP protection.",
            "icon": "✅"
        })
    else:
        insights.append({
            "title": "Traditional Foundation",
            "description": "Your product is well-grounded in traditional knowledge. Consider adding innovative elements for differentiation.",
            "type": "neutral",
            "detail": "Your formulation uses only classical Ayurvedic ingredients with traditional processing methods. While this provides credibility and safety, adding innovative elements could help differentiate your product in the market and create IP protection opportunities.",
            "icon": "💡"
        })

    # Check market potential
    if len(ingredients) >= 3:
        insights.append({
            "title": "Good Market Potential",
            "description": "With multiple ingredients and some innovative elements, your product has strong market potential.",
            "type": "positive",
            "detail": "Products with 3+ ingredients typically offer more comprehensive benefits. Combined with the innovative elements, this formulation has strong market differentiation potential.",
            "icon": "✅"
        })
    else:
        insights.append({
            "title": "Consider Expanding Formulation",
            "description": "With more ingredients, you could create a more comprehensive product.",
            "type": "neutral",
            "detail": f"Your product currently has {len(ingredients)} ingredients. Consider adding 1-2 more supporting herbs to create a more complete formulation that addresses multiple aspects of the intended use.",
            "icon": "💡"
        })

    # Check if modern form is used
    if form and str(form).lower() in ['capsule', 'tablet', 'liquid extract', 'extract', 'serum', 'gel']:
        insights.append({
            "title": "Modern Delivery Format",
            "description": f"Using {form} format shows innovation in product delivery.",
            "type": "positive",
            "detail": f"The {form} format represents a departure from traditional Ayurvedic delivery methods (powders, decoctions). This modern approach improves convenience and may appeal to contemporary consumers.",
            "icon": "✅"
        })

    return insights

