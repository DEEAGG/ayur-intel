"""AYUR-INTEL — Patent Deep Analysis Service (Phase 7).

Compares a Product Case's passport data and innovation components
against a specific patent record. This is RESEARCH decision-support,
NOT legal opinion or infringement analysis.

If no AI provider is configured, uses deterministic rule-based comparison.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    ClaimElement,
    InnovationAnalysis,
    InnovationComponent,
    PatentAnalysis,
    PatentComparison,
    PatentRecord,
    ProductCase,
    User,
)

logger = logging.getLogger("ayur_intel.patent_analysis_service")


# -------------------------------------------------------------------
# Known ingredient keywords for comparison
# -------------------------------------------------------------------

KNOWN_AYURVEDIC_INGREDIENTS = {
    "ashwagandha", "withania somnifera", "brahmi", "bacopa monnieri",
    "turmeric", "curcuma longa", "tulsi", "ocimum sanctum",
    "shatavari", "asparagus racemosus", "amla", "emblica officinalis",
    "guduchi", "tinospora cordifolia", "neem", "azadirachta indica",
    "triphala", "haritaki", "bibhitaki", "fenugreek", "trigonella foenum",
    "moringa", "moringa oleifera", "ginger", "zingiber officinale",
    "boswellia", "shallaki", "guggul", "commiphora mukul",
    "arjuna", "terminalia arjuna", "manjistha", "rubia cordifolia",
    "licorice", "glycyrrhiza glabra", "cardamom", "elettaria cardamomum",
    "cinnamon", "cinnamomum verum", "clove", "syzygium aromaticum",
    "cumin", "cuminum cyminum", "coriander", "coriandrum sativum",
    "fennel", "foeniculum vulgare", "black pepper", "piper nigrum",
    "long pepper", "piper longum", "pippali", "nutmeg", "myristica fragrans",
    "saffron", "crocus sativus", "sandalwood", "santalum album",
    "gotu kola", "centella asiatica", "jatamansi", "nardostachys jatamansi",
    "tagara", "valeriana wallichii", "musta", "cyperus rotundus",
    "kiratatikta", "swertia chirata", "bhumyamalaki", "phyllanthus niruri",
    "kalmegh", "andrographis paniculata", "gudmar", "gymnema sylvestre",
    "shilajit", "岩白菜", "selenium", "zinc", "magnesium",
}

KNOWN_PRODUCT_FORMS = {
    "powder", "tablet", "capsule", "oil", "liquid", "tea", "decoction",
    "cream", "ointment", "syrup", "granules", "drops", "tincture",
    "extract", "suppository", "inhaler", "spray", "gel", "lotion",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_loads(value: Optional[str], default=None):
    if not value:
        return default
    try:
        result = json.loads(value)
        return result if result is not None else default
    except (json.JSONDecodeError, TypeError):
        return default


# -------------------------------------------------------------------
# Feature extraction from Product Case
# -------------------------------------------------------------------

def _extract_product_features(case: ProductCase) -> Dict[str, List[str]]:
    """Extract structured features from a Product Case for comparison."""
    features = {
        "ingredients": [],
        "product_form": [],
        "process": [],
        "intended_use": [],
        "claims": [],
        "combination": [],
    }

    # Ingredients
    if case.ingredients:
        for ing in case.ingredients:
            if isinstance(ing, dict):
                name = ing.get("name", "").strip().lower()
            else:
                name = str(ing).strip().lower()
            if name:
                features["ingredients"].append(name)

    # Product form
    if case.form:
        features["product_form"].append(case.form.lower().strip())

    # Process / preparation
    if case.process:
        features["process"].append(case.process.lower().strip())

    # Intended use
    if case.intended_use:
        features["intended_use"].append(case.intended_use.lower().strip())

    # Claims
    if case.claims:
        for claim in case.claims:
            if isinstance(claim, dict):
                text = claim.get("text", "").strip().lower()
            else:
                text = str(claim).strip().lower()
            if text:
                features["claims"].append(text)

    # Combination (auto-generated for 2+ ingredients)
    if len(features["ingredients"]) >= 2:
        features["combination"].append(
            " + ".join(features["ingredients"][:5])
        )

    return features


def _extract_patent_features(record: PatentRecord) -> Dict[str, List[str]]:
    """Extract features from a patent record for comparison."""
    features = {
        "ingredients": [],
        "product_form": [],
        "process": [],
        "title_concepts": [],
        "abstract_concepts": [],
    }

    text_pool = ""

    # Title
    if record.title:
        text_pool += " " + record.title.lower()

    # Abstract
    if record.abstract:
        text_pool += " " + record.abstract.lower()

    # Title concepts (words longer than 3 chars, not common)
    common_words = {
        "the", "and", "for", "with", "from", "that", "this", "which",
        "method", "comprising", "having", "containing", "related", "using",
        "present", "invention", "disclosed", "herein", "product", "novel",
        "improved", "composition", "formulation", "pharmaceutical", "herbal",
        "natural", "plant", "extract", "preparation", "process", "between",
        "thereof", "wherein", "group", "selected", "optionally", "also",
    }
    if text_pool:
        words = set()
        for word in text_pool.split():
            cleaned = word.strip(".,;:()[]{}\"'!?")
            if len(cleaned) > 3 and cleaned not in common_words:
                words.add(cleaned)
        features["title_concepts"] = list(words)[:30]

    # Check for known ingredients in patent text
    for ingredient in KNOWN_AYURVEDIC_INGREDIENTS:
        if ingredient in text_pool:
            features["ingredients"].append(ingredient)

    # Check for product forms in patent text
    for form in KNOWN_PRODUCT_FORMS:
        if form in text_pool:
            features["product_form"].append(form)

    # Process keywords
    process_keywords = [
        "extraction", "decoction", "fermentation", "distillation",
        "supercritical", "cold press", "steam", "maceration",
        "standardization", "purification", "concentration",
        "solvent", "aqueous", "ethanol", "hydroalcoholic",
    ]
    for kw in process_keywords:
        if kw in text_pool:
            features["process"].append(kw)

    return features


# -------------------------------------------------------------------
# Similarity comparison
# -------------------------------------------------------------------

def _compare_ingredient_lists(
    product_ingredients: List[str],
    patent_ingredients: List[str],
) -> Tuple[str, str, str]:
    """Compare ingredient lists. Returns (level, explanation, confidence)."""
    if not product_ingredients or not patent_ingredients:
        return (
            "UNKNOWN",
            "Insufficient data for ingredient comparison.",
            "LOW",
        )

    # Check overlap
    product_set = set(product_ingredients)
    patent_set = set(patent_ingredients)

    # Direct overlap
    direct_matches = product_set & patent_set

    # Partial matches (word-level)
    partial_matches = []
    for pi in product_ingredients:
        for pt in patent_ingredients:
            if pi != pt and (pi in pt or pt in pi):
                partial_matches.append((pi, pt))

    total_product = len(product_set)
    overlap_count = len(direct_matches) + len(partial_matches)

    if overlap_count == 0:
        return (
            "LOW",
            "No matching ingredients identified between product and patent.",
            "MEDIUM",
        )

    if direct_matches and overlap_count >= total_product * 0.5:
        match_str = ", ".join(direct_matches) if direct_matches else ", ".join(
            f"{a}≈{b}" for a, b in partial_matches[:3]
        )
        return (
            "HIGH",
            f"Significant ingredient overlap detected: {match_str}.",
            "HIGH",
        )

    if direct_matches or partial_matches:
        match_str = ", ".join(direct_matches) if direct_matches else ", ".join(
            f"{a}≈{b}" for a, b in partial_matches[:2]
        )
        return (
            "MEDIUM",
            f"Partial ingredient similarity detected: {match_str}.",
            "MEDIUM",
        )

    return (
        "LOW",
        "Minimal ingredient overlap.",
        "MEDIUM",
    )


def _compare_text_features(
    product_texts: List[str],
    patent_texts: List[str],
    feature_name: str,
) -> Tuple[str, str, str]:
    """Compare text features. Returns (level, explanation, confidence)."""
    if not product_texts:
        return (
            "UNKNOWN",
            f"Product {feature_name} information not available for comparison.",
            "LOW",
        )
    if not patent_texts:
        return (
            "UNKNOWN",
            f"Patent {feature_name} information not available.",
            "LOW",
        )

    # Join all texts into a single string for keyword matching
    product_combined = " ".join(product_texts).lower()
    patent_combined = " ".join(patent_texts).lower()

    # Check for keyword overlap
    product_words = set(product_combined.split())
    patent_words = set(patent_combined.split())
    common = product_words & patent_words
    # Filter out very common words
    common -= {"the", "and", "for", "with", "from", "that", "this", "is", "are", "was", "were"}

    if len(common) >= 5:
        return (
            "HIGH",
            f"Strong conceptual overlap in {feature_name}.",
            "MEDIUM",
        )
    if len(common) >= 2:
        return (
            "MEDIUM",
            f"Moderate conceptual overlap in {feature_name}.",
            "LOW",
        )

    return (
        "LOW",
        f"Limited conceptual overlap in {feature_name}.",
        "LOW",
    )


# -------------------------------------------------------------------
# Main analysis engine
# -------------------------------------------------------------------

def run_deep_analysis(
    db: Session,
    owner: User,
    case_public_id: str,
    patent_record_id: str,
    recalculate: bool = False,
) -> Optional[dict]:
    """Run a deep analysis of a patent record against a Product Case."""

    # 1. Load the product case
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

    # 2. Load the patent record
    patent = (
        db.query(PatentRecord)
        .filter(PatentRecord.public_id == patent_record_id)
        .first()
    )
    if patent is None:
        return None

    # 3. Check for existing analysis
    existing = (
        db.query(PatentAnalysis)
        .filter(
            PatentAnalysis.product_case_id == case.id,
            PatentAnalysis.patent_record_id == patent.id,
        )
        .first()
    )
    if existing and not recalculate:
        return _analysis_to_dict(existing, case, patent)

    # 4. If recalculating, delete old analysis
    if existing:
        for comp in existing.comparisons:
            db.delete(comp)
        for ce in existing.claim_elements:
            db.delete(ce)
        db.delete(existing)
        db.flush()

    # 5. Extract features
    product_features = _extract_product_features(case)
    patent_features = _extract_patent_features(patent)

    # 6. Run comparisons
    comparisons = []
    missing_info = []

    # Ingredients
    sim, expl, conf = _compare_ingredient_lists(
        product_features["ingredients"],
        patent_features["ingredients"],
    )
    comparisons.append({
        "product_component_type": "INGREDIENT",
        "product_component_label": "Ingredient Combination",
        "product_component_value": ", ".join(product_features["ingredients"]) or "Not specified",
        "patent_element": "Ingredient/compound disclosure",
        "patent_element_detail": ", ".join(patent_features["ingredients"]) if patent_features["ingredients"] else None,
        "similarity_level": sim,
        "explanation": expl,
        "confidence": conf,
        "evidence_type": "ABSTRACT" if patent.abstract else "METADATA",
        "evidence_reference": patent.publication_number,
    })

    # Combination
    if product_features["combination"]:
        if patent_features["ingredients"] and len(patent_features["ingredients"]) >= 2:
            combo_sim, combo_expl, combo_conf = "MEDIUM", "Patent discloses multiple ingredients similar to product combination.", "MEDIUM"
        elif patent_features["ingredients"]:
            combo_sim, combo_expl, combo_conf = "LOW", "Patent references some overlapping ingredients.", "LOW"
        else:
            combo_sim, combo_expl, combo_conf = "UNKNOWN", "Insufficient patent data for combination comparison.", "LOW"
        comparisons.append({
            "product_component_type": "COMBINATION",
            "product_component_label": "Ingredient Combination",
            "product_component_value": product_features["combination"][0],
            "patent_element": "Multi-ingredient composition",
            "patent_element_detail": None,
            "similarity_level": combo_sim,
            "explanation": combo_expl,
            "confidence": combo_conf,
            "evidence_type": "ABSTRACT" if patent.abstract else "METADATA",
            "evidence_reference": patent.publication_number,
        })

    # Process
    proc_sim, proc_expl, proc_conf = _compare_text_features(
        product_features["process"],
        patent_features["process"],
        "preparation process",
    )
    comparisons.append({
        "product_component_type": "PROCESS",
        "product_component_label": "Preparation Process",
        "product_component_value": case.process or "Not specified",
        "patent_element": "Process/method disclosure",
        "patent_element_detail": ", ".join(patent_features["process"]) if patent_features["process"] else None,
        "similarity_level": proc_sim,
        "explanation": proc_expl,
        "confidence": proc_conf,
        "evidence_type": "ABSTRACT" if patent.abstract else "METADATA",
        "evidence_reference": patent.publication_number,
    })

    # Form
    form_sim, form_expl, form_conf = _compare_text_features(
        product_features["product_form"],
        patent_features["product_form"],
        "product form",
    )
    comparisons.append({
        "product_component_type": "FORM",
        "product_component_label": "Product Form/Delivery",
        "product_component_value": case.form or "Not specified",
        "patent_element": "Dosage form disclosure",
        "patent_element_detail": ", ".join(patent_features["product_form"]) if patent_features["product_form"] else None,
        "similarity_level": form_sim,
        "explanation": form_expl,
        "confidence": form_conf,
        "evidence_type": "ABSTRACT" if patent.abstract else "METADATA",
        "evidence_reference": patent.publication_number,
    })

    # Intended Use
    use_sim, use_expl, use_conf = _compare_text_features(
        product_features["intended_use"],
        patent_features["title_concepts"],
        "intended use",
    )
    comparisons.append({
        "product_component_type": "INTENDED_USE",
        "product_component_label": "Intended Use",
        "product_component_value": case.intended_use or "Not specified",
        "patent_element": "Indication/use disclosure",
        "patent_element_detail": None,
        "similarity_level": use_sim,
        "explanation": use_expl,
        "confidence": use_conf,
        "evidence_type": "ABSTRACT" if patent.abstract else "METADATA",
        "evidence_reference": patent.publication_number,
    })

    # 7. Calculate overall result
    sim_levels = [c["similarity_level"] for c in comparisons]
    high_count = sim_levels.count("HIGH")
    medium_count = sim_levels.count("MEDIUM")

    if high_count >= 2:
        overall_relevance = "HIGH_POTENTIAL_OVERLAP"
        overall_confidence = "MEDIUM"
    elif high_count >= 1 or medium_count >= 2:
        overall_relevance = "MEDIUM_POTENTIAL_OVERLAP"
        overall_confidence = "MEDIUM"
    elif medium_count >= 1:
        overall_relevance = "LOW_POTENTIAL_OVERLAP"
        overall_confidence = "LOW"
    else:
        overall_relevance = "INSUFFICIENT_INFORMATION"
        overall_confidence = "LOW"

    # Determine missing info
    if not case.process:
        missing_info.append("Preparation process")
    if not case.form:
        missing_info.append("Product form/delivery")
    if not case.intended_use:
        missing_info.append("Intended use")
    if not case.ingredients:
        missing_info.append("Ingredients")
    if not patent.abstract:
        missing_info.append("Patent abstract (unavailable)")
    if not patent.status:
        missing_info.append("Patent legal status")

    # Build summary
    overlap_areas = []
    for c in comparisons:
        if c["similarity_level"] in ("HIGH", "MEDIUM"):
            overlap_areas.append(c["product_component_label"])

    if overlap_areas:
        summary = (
            f"Potential similarity detected in: {', '.join(overlap_areas)}. "
            "This is a preliminary research comparison, not a legal conclusion."
        )
    else:
        summary = (
            "Limited or no significant similarity detected between the product "
            "and this patent record based on available information. "
            "This is a preliminary research comparison, not a legal conclusion."
        )

    # Recommended next step
    if overall_relevance == "HIGH_POTENTIAL_OVERLAP":
        next_step = "Review relevant patent claims in detail. Professional IP review recommended."
    elif overall_relevance == "MEDIUM_POTENTIAL_OVERLAP":
        next_step = "Verify product details and compare with patent claims. Consider professional review."
    else:
        next_step = "Continue research. Patent claims review may be informative."

    # 8. Save analysis
    analysis = PatentAnalysis(
        owner_id=owner.id,
        product_case_id=case.id,
        patent_record_id=patent.id,
        overall_relevance=overall_relevance,
        overall_confidence=overall_confidence,
        summary=summary,
        recommended_next_step=next_step,
        missing_information=json.dumps(missing_info) if missing_info else None,
        status="COMPLETED",
    )
    db.add(analysis)
    db.flush()

    # Save comparisons
    for c_data in comparisons:
        comp = PatentComparison(
            analysis_id=analysis.id,
            product_component_type=c_data["product_component_type"],
            product_component_label=c_data["product_component_label"],
            product_component_value=c_data["product_component_value"],
            patent_element=c_data["patent_element"],
            patent_element_detail=c_data["patent_element_detail"],
            similarity_level=c_data["similarity_level"],
            explanation=c_data["explanation"],
            confidence=c_data["confidence"],
            evidence_type=c_data["evidence_type"],
            evidence_reference=c_data["evidence_reference"],
        )
        db.add(comp)

    # Save claim elements (placeholder — claims not available from unconfigured sources)
    claim_elements_data = []
    if patent.abstract:
        # Extract simple claim-like elements from abstract
        abstract_sentences = patent.abstract.split(".")
        for i, sentence in enumerate(abstract_sentences[:5]):
            sentence = sentence.strip()
            if len(sentence) > 10:
                # Determine element type
                element_type = "METADATA"
                lower_s = sentence.lower()
                if any(kw in lower_s for kw in ["comprising", "containing", "mixture", "combination"]):
                    element_type = "INGREDIENT"
                elif any(kw in lower_s for kw in ["process", "method", "extraction", "preparation"]):
                    element_type = "PROCESS"
                elif any(kw in lower_s for kw in ["dosage", "form", "tablet", "capsule", "powder"]):
                    element_type = "FORMULATION"
                elif any(kw in lower_s for kw in ["use", "treatment", "method of"]):
                    element_type = "USE"

                claim_elements_data.append({
                    "claim_reference": f"Abstract element {i + 1}",
                    "element_text": sentence,
                    "element_type": element_type,
                })

    for ce_data in claim_elements_data:
        ce = ClaimElement(
            analysis_id=analysis.id,
            claim_reference=ce_data["claim_reference"],
            element_text=ce_data["element_text"],
            element_type=ce_data["element_type"],
            comparison_status="UNABLE_TO_COMPARE",  # No claim text available
            explanation="Claim-level analysis unavailable. Analysis based on abstract/metadata only.",
            evidence_type="ABSTRACT",
            confidence="LOW",
        )
        db.add(ce)

    db.commit()
    db.refresh(analysis)

    return _analysis_to_dict(analysis, case, patent)


# -------------------------------------------------------------------
# Serialization
# -------------------------------------------------------------------

def _analysis_to_dict(
    analysis: PatentAnalysis,
    case: ProductCase,
    patent: PatentRecord,
) -> dict:
    """Convert a PatentAnalysis to a response dict."""
    missing = _safe_json_loads(analysis.missing_information, [])

    comparisons = []
    for c in analysis.comparisons:
        comparisons.append({
            "id": c.public_id,
            "product_component_type": c.product_component_type,
            "product_component_label": c.product_component_label,
            "product_component_value": c.product_component_value,
            "patent_element": c.patent_element,
            "patent_element_detail": c.patent_element_detail,
            "similarity_level": c.similarity_level,
            "explanation": c.explanation,
            "confidence": c.confidence,
            "evidence_type": c.evidence_type,
            "evidence_reference": c.evidence_reference,
        })

    claim_elements = []
    for ce in analysis.claim_elements:
        claim_elements.append({
            "id": ce.public_id,
            "claim_reference": ce.claim_reference,
            "element_text": ce.element_text,
            "element_type": ce.element_type,
            "comparison_status": ce.comparison_status,
            "product_match": ce.product_match,
            "explanation": ce.explanation,
            "evidence_type": ce.evidence_type,
            "evidence_reference": ce.evidence_reference,
            "confidence": ce.confidence,
        })

    return {
        "id": analysis.public_id,
        "product_case_id": case.public_id,
        "patent_record_id": patent.public_id,
        "overall_relevance": analysis.overall_relevance,
        "overall_confidence": analysis.overall_confidence,
        "summary": analysis.summary,
        "recommended_next_step": analysis.recommended_next_step,
        "missing_information": missing,
        "comparisons": comparisons,
        "claim_elements": claim_elements,
        "patent_title": patent.title,
        "patent_number": patent.publication_number,
        "patent_jurisdiction": patent.jurisdiction,
        "patent_status": patent.status,
        "patent_abstract": patent.abstract,
        "patent_applicant": patent.applicant,
        "product_name": case.name,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else "",
        "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else "",
    }


def get_case_analyses(
    db: Session,
    owner: User,
    case_public_id: str,
) -> List[dict]:
    """Get all patent analyses for a Product Case."""
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

    analyses = (
        db.query(PatentAnalysis)
        .filter(PatentAnalysis.product_case_id == case.id)
        .order_by(PatentAnalysis.created_at.desc())
        .all()
    )

    results = []
    for a in analyses:
        patent = a.patent_record
        if patent:
            results.append(_analysis_to_dict(a, case, patent))
    return results


def get_analysis(
    db: Session,
    owner: User,
    analysis_public_id: str,
) -> Optional[dict]:
    """Get a single patent analysis by ID."""
    analysis = (
        db.query(PatentAnalysis)
        .filter(PatentAnalysis.public_id == analysis_public_id)
        .first()
    )
    if analysis is None:
        return None

    # Verify access
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.id == analysis.product_case_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return None

    patent = analysis.patent_record
    if patent is None:
        return None

    return _analysis_to_dict(analysis, case, patent)
