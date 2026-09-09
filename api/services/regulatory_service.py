"""AYUR-INTEL — Regulatory Intelligence Service (Phase 9).

Synthesizes Product Passport data with jurisdiction-specific regulatory
source adapters to map the regulatory landscape.

This is RESEARCH decision-support, NOT legal advice.
Uses deterministic rule-based classification — no AI provider required.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    RegulatoryProfile,
    RegulatoryRequirement,
    ProductCase,
    User,
)
from api.services.regulatory_adapter import (
    RegulatoryFinding,
    RegulatorySearchResult,
    SUPPORTED_JURISDICTIONS,
    get_sources_for_jurisdiction,
)

logger = logging.getLogger("ayur_intel.regulatory_service")


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


# -------------------------------------------------------------------
# Product Classification Rules
# -------------------------------------------------------------------

def classify_product(form: Optional[str], ingredients: list, intended_use: Optional[str], claims: list, jurisdiction: str) -> Tuple[str, str, str]:
    """Determine potential regulatory product category.

    Returns: (category, confidence, reasoning)
    """
    form_lower = (form or "").lower()
    intended_lower = (intended_use or "").lower()
    claims_lower = " ".join(c.lower() if isinstance(c, str) else "" for c in claims)

    # India-specific categories
    if jurisdiction == "IN":
        med_terms = ["treat", "cure", "prevent", "relieve", "disease", "therapeutic", "medicinal", "remedy", "healing", "anti-inflammatory", "analgesic", "management"]
        food_terms = ["food", "supplement", "wellness", "immunity", "energy", "vitality", "digestive health", "gut health", "daily", "nutrition", "aahara"]

        has_med = any(kw in intended_lower or kw in claims_lower for kw in med_terms)
        has_food = any(kw in intended_lower or kw in claims_lower for kw in food_terms)
        has_ayush = any(kw in intended_lower or kw in claims_lower for kw in ["ayurved", "traditional", "herbal", "rasayana", "bhasma", "kashayam", "churn", "churna"])

        if has_med or (has_ayush and not has_food):
            return ("AYUSH Drug License (Ayurvedic Medicine)", "HIGH",
                    "Product contains therapeutic/medicinal claims or traditional Ayurvedic formulation requiring licensing under Drugs & Cosmetics Act 1940.")
        elif has_food and not has_med:
            return ("FSSAI Ayurveda Aahara (Food Category)", "HIGH",
                    "Product is positioned for daily wellness, dietary support, or nutrition under FSSAI Ayurveda Aahara Regulations 2022.")
        else:
            return ("Dual Pathway (AYUSH Drug & FSSAI Ayurveda Aahara)", "HIGH",
                    "Product encompasses both therapeutic traditional elements and daily dietary supplement features under Indian regulations.")

    # EU/Germany categories
    if jurisdiction in ("EU", "DE"):
        if any(kw in intended_lower for kw in ["traditional", "herbal", "medicinal", "therapy"]):
            return ("Traditional Herbal Medicinal Product", "MEDIUM",
                    "Product uses terminology consistent with EU Traditional Herbal Directive.")
        if form_lower in ("tea", "decoction", "infusion"):
            return ("Herbal Food Product", "MEDIUM",
                    "Product form (tea/decoction) may fall under food regulations.")
        if form_lower in ("powder", "tablet", "capsule"):
            return ("Herbal Product — Category pending", "LOW",
                    "Product form requires further classification. May be food, supplement, or herbal medicine.")

    # US categories
    if jurisdiction == "US":
        if any(kw in intended_lower for kw in ["supplement", "dietary", "nutrient"]):
            return ("Dietary Supplement (DSHEA)", "MEDIUM",
                    "Product intended use suggests dietary supplement category under DSHEA.")
        if any(kw in claims_lower for kw in ["treat", "cure", "prevent", "diagnose"]):
            return ("Potential Drug — Requires FDA Evaluation", "MEDIUM",
                    "Product claims may require drug classification review.")
        if form_lower in ("powder", "tablet", "capsule", "liquid"):
            return ("Dietary Supplement / Herbal Product", "LOW",
                    "Product form is consistent with dietary supplement. Classification requires verification.")

    # Default
    return ("Product Category Requires Verification", "LOW",
            "Insufficient information to determine regulatory category. Manual classification recommended.")


# -------------------------------------------------------------------
# Requirements Generation (Rule-based)
# -------------------------------------------------------------------

def _generate_requirements(
    product_data: dict,
    jurisdiction: str,
    category: str,
    search_results: List[RegulatorySearchResult],
) -> List[dict]:
    """Generate regulatory requirements based on product data and source results.

    Combines deterministic rules with source findings.
    """
    requirements = []
    form = product_data.get("form", "")
    intended_use = product_data.get("intended_use", "")
    claims = product_data.get("claims", [])
    ingredients = product_data.get("ingredients", [])

    # --- Source-based requirements ---
    for result in search_results:
        for finding in result.findings:
            requirements.append({
                "title": finding.title,
                "description": finding.description,
                "category": finding.category,
                "jurisdiction": jurisdiction,
                "authority": finding.authority,
                "source_name": finding.source_name,
                "source_reference": finding.source_reference,
                "applicability": finding.applicability,
                "confidence": finding.confidence,
                "status": "FOUND",
                "evidence_type": finding.evidence_type,
                "evidence_detail": finding.description,
                "limitations": finding.limitations,
                "next_action": finding.next_action,
            })

    # --- Rule-based requirements (always shown, clearly labelled as system-derived) ---

    # 1. Product Classification
    requirements.append({
        "title": "Product Classification",
        "description": f"Potential category: {category}. This is an automated suggestion — verify with official classification.",
        "category": "CLASSIFICATION",
        "jurisdiction": jurisdiction,
        "authority": "System classification (requires verification)",
        "source_name": "AYUR-INTEL Rule Engine",
        "source_reference": None,
        "applicability": "NEEDS_VERIFICATION",
        "confidence": "MEDIUM",
        "status": "FOUND",
        "evidence_type": "SYSTEM_DERIVED",
        "evidence_detail": "Automated classification based on product form, ingredients, and intended use.",
        "limitations": "This is a preliminary classification. Official regulatory classification must be verified with the relevant authority.",
        "next_action": "Verify product classification with relevant regulatory authority.",
    })

    # 2. Ingredient requirements
    if ingredients:
        ingredient_names = []
        for ing in ingredients:
            if isinstance(ing, dict):
                ingredient_names.append(ing.get("name", "Unknown"))
            elif isinstance(ing, str):
                ingredient_names.append(ing)

        if jurisdiction == "IN":
            requirements.append({
                "title": "Ingredient Eligibility — India",
                "description": f"Verify that ingredients ({', '.join(ingredient_names[:3])}{'...' if len(ingredient_names) > 3 else ''}) are listed in applicable schedules/rules for the identified product category.",
                "category": "INGREDIENT",
                "jurisdiction": "IN",
                "authority": "Ministry of Ayush / FSSAI (as applicable)",
                "source_name": "AYUR-INTEL Rule Engine",
                "source_reference": None,
                "applicability": "RELEVANT",
                "confidence": "HIGH",
                "status": "FOUND",
                "evidence_type": "SYSTEM_DERIVED",
                "evidence_detail": "Ingredients must be verified against applicable Indian regulatory schedules.",
                "limitations": "Ingredient identity must be confirmed. Traditional/synonym names must be mapped to official botanical names.",
                "next_action": "Verify each ingredient against applicable regulatory schedules.",
            })
        elif jurisdiction in ("EU", "DE"):
            requirements.append({
                "title": "Ingredient Eligibility — EU/Germany",
                "description": f"Verify that ingredients ({', '.join(ingredient_names[:3])}{'...' if len(ingredient_names) > 3 else ''}) are permitted in the identified product category under EU/German regulations.",
                "category": "INGREDIENT",
                "jurisdiction": jurisdiction,
                "authority": "European Commission / BfArM",
                "source_name": "AYUR-INTEL Rule Engine",
                "source_reference": None,
                "applicability": "RELEVANT",
                "confidence": "HIGH",
                "status": "FOUND",
                "evidence_type": "SYSTEM_DERIVED",
                "evidence_detail": "Ingredients must be verified against EU positive lists and BfArM monographs.",
                "limitations": "Novel food status must be checked. Botanical identification must be confirmed.",
                "next_action": "Verify ingredients against EU positive lists and applicable monographs.",
            })
        elif jurisdiction == "US":
            requirements.append({
                "title": "Ingredient Eligibility — USA",
                "description": f"Verify that ingredients ({', '.join(ingredient_names[:3])}{'...' if len(ingredient_names) > 3 else ''}) are listed in the Dietary Supplement Ingredient Database or have GRAS status.",
                "category": "INGREDIENT",
                "jurisdiction": "US",
                "authority": "US FDA",
                "source_name": "AYUR-INTEL Rule Engine",
                "source_reference": None,
                "applicability": "RELEVANT",
                "confidence": "HIGH",
                "status": "FOUND",
                "evidence_type": "SYSTEM_DERIVED",
                "evidence_detail": "Ingredients must be verified against FDA dietary supplement ingredient lists and GRAS database.",
                "limitations": "New dietary ingredient (NDI) notification may be required. Botanical identity must be confirmed.",
                "next_action": "Verify each ingredient against FDA databases. Check for NDI requirements.",
            })

    # 3. Claims requirements
    if claims:
        claims_text = "; ".join(str(c) for c in claims[:3])
        if jurisdiction == "US":
            requirements.append({
                "title": "Claims Compliance — USA",
                "description": f"Proposed claims ({claims_text}) must comply with DSHEA labeling requirements. Structure/function claims require notification to FDA.",
                "category": "CLAIMS",
                "jurisdiction": "US",
                "authority": "US FDA",
                "source_name": "AYUR-INTEL Rule Engine",
                "source_reference": None,
                "applicability": "RELEVANT",
                "confidence": "HIGH",
                "status": "FOUND",
                "evidence_type": "SYSTEM_DERIVED",
                "evidence_detail": "All claims must comply with DSHEA. Disease claims require drug approval.",
                "limitations": "Exact claim wording must be reviewed for compliance. Structure/function vs disease claim distinction is critical.",
                "next_action": "Review each proposed claim against DSHEA guidelines. Ensure no disease claims.",
            })
        elif jurisdiction == "IN":
            requirements.append({
                "title": "Claims Compliance — India",
                "description": f"Proposed claims ({claims_text}) must comply with applicable AYUSH/FSSAI advertising and labeling rules.",
                "category": "CLAIMS",
                "jurisdiction": "IN",
                "authority": "Ministry of Ayush / ASCI",
                "source_name": "AYUR-INTEL Rule Engine",
                "source_reference": None,
                "applicability": "RELEVANT",
                "confidence": "MEDIUM",
                "status": "FOUND",
                "evidence_type": "SYSTEM_DERIVED",
                "evidence_detail": "Claims must comply with advertising standards and product category rules.",
                "limitations": "Exact claim compliance depends on final product classification.",
                "next_action": "Review claims against applicable Indian advertising and labeling standards.",
            })
        elif jurisdiction in ("EU", "DE"):
            requirements.append({
                "title": "Claims Compliance — EU/Germany",
                "description": f"Proposed claims ({claims_text}) must comply with EU Regulation 1924/2006 on nutrition and health claims.",
                "category": "CLAIMS",
                "jurisdiction": jurisdiction,
                "authority": "European Commission / EFSA",
                "source_name": "AYUR-INTEL Rule Engine",
                "source_reference": None,
                "applicability": "RELEVANT",
                "confidence": "MEDIUM",
                "status": "FOUND",
                "evidence_type": "SYSTEM_DERIVED",
                "evidence_detail": "Claims must be authorized under EU regulation. Health claims require EFSA assessment.",
                "limitations": "Claim authorization status must be verified against EU claims register.",
                "next_action": "Check each claim against the EU Health Claims Register.",
            })

    # 4. Labelling requirements
    requirements.append({
        "title": "Labelling Requirements",
        "description": f"Product labelling must comply with {SUPPORTED_JURISDICTIONS.get(jurisdiction, {}).get('name', jurisdiction)} regulations for the identified product category.",
        "category": "LABELLING",
        "jurisdiction": jurisdiction,
        "authority": f"Regulatory authority — {SUPPORTED_JURISDICTIONS.get(jurisdiction, {}).get('name', jurisdiction)}",
        "source_name": "AYUR-INTEL Rule Engine",
        "source_reference": None,
        "applicability": "RELEVANT",
        "confidence": "HIGH",
        "status": "FOUND",
        "evidence_type": "SYSTEM_DERIVED",
        "evidence_detail": "Labelling must include required elements for the product category in the target jurisdiction.",
        "limitations": "Exact labelling requirements depend on final product classification.",
        "next_action": "Review labelling requirements for the identified product category.",
    })

    # 5. Documentation
    requirements.append({
        "title": "Documentation / Dossier Requirements",
        "description": f"Prepare documentation potentially required for {SUPPORTED_JURISDICTIONS.get(jurisdiction, {}).get('name', jurisdiction)} market entry.",
        "category": "DOCUMENTATION",
        "jurisdiction": jurisdiction,
        "authority": f"Regulatory authority — {SUPPORTED_JURISDICTIONS.get(jurisdiction, {}).get('name', jurisdiction)}",
        "source_name": "AYUR-INTEL Rule Engine",
        "source_reference": None,
        "applicability": "POTENTIALLY_RELEVANT",
        "confidence": "MEDIUM",
        "evidence_type": "SYSTEM_DERIVED",
        "evidence_detail": "Documentation requirements vary by product category and jurisdiction.",
        "limitations": "Exact documentation requirements depend on product classification and registration pathway.",
        "next_action": "Identify specific documentation requirements for the product category.",
    })

    # Deduplicate requirements by semantic key preserving order
    deduped_reqs = []
    seen_keys = set()
    for req in requirements:
        key = (
            (req.get("title") or "").strip().lower(),
            (req.get("jurisdiction") or "").strip().upper(),
            (req.get("category") or "").strip().upper(),
            (req.get("authority") or "").strip().lower(),
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_reqs.append(req)

    return deduped_reqs


# -------------------------------------------------------------------
# Information Gaps & Document Checklist
# -------------------------------------------------------------------

def _identify_gaps(product_data: dict) -> List[str]:
    """Identify information gaps in the product data."""
    gaps = []

    if not product_data.get("form"):
        gaps.append("Product form/dosage form not specified")
    if not product_data.get("intended_use"):
        gaps.append("Intended use not specified")
    if not product_data.get("ingredients"):
        gaps.append("Ingredients not listed")
    if not product_data.get("formulation"):
        gaps.append("Formulation details not provided")
    if not product_data.get("process"):
        gaps.append("Manufacturing process not described")
    if not product_data.get("brand"):
        gaps.append("Brand name not specified")
    if not product_data.get("claims"):
        gaps.append("No proposed claims specified")

    ingredients = product_data.get("ingredients", [])
    if ingredients:
        for ing in ingredients:
            if isinstance(ing, dict):
                if ing.get("status") == "NEEDS_VERIFICATION":
                    gaps.append(f"Ingredient identity verification needed: {ing.get('name', 'Unknown')}")
                    break

    return gaps


def _build_document_checklist(product_data: dict, jurisdiction: str, category: str) -> List[dict]:
    """Build a checklist of potentially required documents."""
    checklist = [
        {"item": "Product composition / formula", "status": "REQUIRED" if product_data.get("formulation") else "MISSING", "category": "FORMULATION"},
        {"item": "Ingredient identity & botanical name", "status": "PARTIAL" if product_data.get("ingredients") else "MISSING", "category": "INGREDIENTS"},
        {"item": "Product specifications", "status": "MISSING", "category": "SPECIFICATIONS"},
        {"item": "Manufacturing process description", "status": "FOUND" if product_data.get("process") else "MISSING", "category": "PROCESS"},
        {"item": "Proposed labelling / artwork", "status": "MISSING", "category": "LABELLING"},
        {"item": "Proposed claims with supporting evidence", "status": "PARTIAL" if product_data.get("claims") else "MISSING", "category": "CLAIMS"},
        {"item": "Safety / toxicology data", "status": "MISSING", "category": "SAFETY"},
        {"item": "Stability data", "status": "MISSING", "category": "STABILITY"},
        {"item": "Quality control / certificate of analysis", "status": "MISSING", "category": "QUALITY"},
    ]

    # Jurisdiction-specific items
    if jurisdiction == "IN":
        checklist.append({"item": "AYUSH product registration documents", "status": "MISSING", "category": "REGISTRATION"})
        checklist.append({"item": "GMP compliance certificate", "status": "MISSING", "category": "GMP"})
    elif jurisdiction in ("EU", "DE"):
        checklist.append({"item": "EU Traditional Herbal Registration dossier", "status": "MISSING", "category": "REGISTRATION"})
        checklist.append({"item": "GMP certificate (EU Directive 2001/83)", "status": "MISSING", "category": "GMP"})
        checklist.append({"item": "Summary of Product Characteristics (SmPC)", "status": "MISSING", "category": "DOCUMENTATION"})
    elif jurisdiction == "US":
        checklist.append({"item": "FDA facility registration", "status": "MISSING", "category": "REGISTRATION"})
        checklist.append({"item": "cGMP compliance documentation", "status": "MISSING", "category": "GMP"})
        checklist.append({"item": "Dietary Supplement Fact Sheet", "status": "MISSING", "category": "LABELLING"})
        checklist.append({"item": "Adverse event reporting system", "status": "MISSING", "category": "SAFETY"})

    return checklist


# -------------------------------------------------------------------
# Main Analysis
# -------------------------------------------------------------------

def generate_regulatory_analysis(
    db: Session,
    user: User,
    case_public_id: str,
    jurisdiction: str,
) -> Optional[RegulatoryProfile]:
    """Generate regulatory intelligence analysis for a Product Case.

    Reads Product Passport data, classifies the product, searches
    regulatory sources, and generates a comprehensive regulatory profile.
    """
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    # Extract product data from case fields
    ingredients = _deserialize_list(case.ingredients)
    claims = _deserialize_list(case.claims)

    product_data = {
        "name": case.name,
        "form": case.form,
        "intended_use": case.intended_use,
        "ingredients": ingredients,
        "claims": claims,
        "formulation": case.formulation,
        "process": case.process,
        "brand": case.brand,
        "packaging": case.packaging,
    }

    # Classify product
    category, category_confidence, category_reasoning = classify_product(
        case.form, ingredients, case.intended_use, claims, jurisdiction
    )

    # Search regulatory sources
    adapters = get_sources_for_jurisdiction(jurisdiction)
    search_results: List[RegulatorySearchResult] = []
    for adapter in adapters:
        try:
            result = adapter.search(product_data, jurisdiction)
            search_results.append(result)
        except Exception as e:
            logger.error("Source %s failed: %s", adapter.source_info().name, e)
            info = adapter.source_info()
            search_results.append(RegulatorySearchResult(
                source=info,
                status="ERROR",
                error_message=str(e),
            ))

    sources_configured = sum(1 for r in search_results if r.source.configured)
    sources_total = len(search_results)
    sources_consulted = [r.source.name for r in search_results]

    # Generate requirements
    req_dicts = _generate_requirements(product_data, jurisdiction, category, search_results)

    # Identify gaps and checklist
    gaps = _identify_gaps(product_data)
    checklist = _build_document_checklist(product_data, jurisdiction, category)

    # Create or update profile
    existing = (
        db.query(RegulatoryProfile)
        .filter(
            RegulatoryProfile.product_case_id == case.id,
            RegulatoryProfile.jurisdiction == jurisdiction,
            RegulatoryProfile.owner_id == user.id,
        )
        .order_by(RegulatoryProfile.created_at.desc())
        .first()
    )
    if existing:
        db.query(RegulatoryRequirement).filter(RegulatoryRequirement.profile_id == existing.id).delete(synchronize_session="fetch")
        db.expire(existing, ["requirements"])
        db.flush()
        profile = existing
        profile.updated_at = datetime.now(timezone.utc)
    else:
        profile = RegulatoryProfile(
            owner_id=user.id,
            product_case_id=case.id,
            jurisdiction=jurisdiction,
        )
        db.add(profile)
        db.flush()

    # Update profile fields
    profile.potential_category = category
    profile.category_confidence = category_confidence
    profile.category_reasoning = category_reasoning
    profile.sources_consulted = json.dumps(sources_consulted)
    profile.sources_configured = sources_configured
    profile.sources_total = sources_total
    profile.information_gaps = json.dumps(gaps)
    profile.document_checklist = json.dumps(checklist)

    # Create requirement records
    req_records = []
    for req_dict in req_dicts:
        req = RegulatoryRequirement(
            profile_id=profile.id,
            title=req_dict["title"],
            description=req_dict.get("description"),
            category=req_dict.get("category"),
            jurisdiction=req_dict["jurisdiction"],
            authority=req_dict.get("authority"),
            source_name=req_dict.get("source_name"),
            source_reference=req_dict.get("source_reference"),
            applicability=req_dict.get("applicability", "POTENTIALLY_RELEVANT"),
            confidence=req_dict.get("confidence"),
            status=req_dict.get("status", "FOUND"),
            evidence_type=req_dict.get("evidence_type"),
            evidence_detail=req_dict.get("evidence_detail"),
            limitations=req_dict.get("limitations"),
            next_action=req_dict.get("next_action"),
        )
        db.add(req)
        req_records.append(req)

    db.flush()

    # Update counts
    profile.total_requirements = len(req_records)
    profile.relevant_count = sum(1 for r in req_records if r.applicability == "RELEVANT")
    profile.potentially_relevant_count = sum(1 for r in req_records if r.applicability == "POTENTIALLY_RELEVANT")
    profile.needs_verification_count = sum(1 for r in req_records if r.applicability == "NEEDS_VERIFICATION")
    profile.info_missing_count = len(gaps)

    db.commit()
    db.refresh(profile)

    return profile


# -------------------------------------------------------------------
# Serialization
# -------------------------------------------------------------------

def profile_to_dict(profile: RegulatoryProfile) -> dict:
    """Serialize a RegulatoryProfile to a JSON-safe dict with defensive deduplication."""
    requirements = []
    seen_req_keys = set()
    for req in profile.requirements:
        key = (
            (req.title or "").strip().lower(),
            (req.jurisdiction or "").strip().upper(),
            (req.category or "").strip().upper(),
            (req.authority or "").strip().lower(),
        )
        if key in seen_req_keys:
            continue
        seen_req_keys.add(key)
        requirements.append({
            "id": req.public_id,
            "title": req.title,
            "description": req.description,
            "category": req.category,
            "subcategory": req.subcategory,
            "jurisdiction": req.jurisdiction,
            "authority": req.authority,
            "source_name": req.source_name,
            "source_reference": req.source_reference,
            "applicability": req.applicability,
            "confidence": req.confidence,
            "status": req.status,
            "evidence_type": req.evidence_type,
            "evidence_detail": req.evidence_detail,
            "effective_date": req.effective_date,
            "publication_date": req.publication_date,
            "limitations": req.limitations,
            "next_action": req.next_action,
            "created_at": req.created_at.isoformat() if req.created_at else "",
        })

    case = profile.product_case
    ingredients = _deserialize_list(case.ingredients) if case else []
    claims = _deserialize_list(case.claims) if case else []

    # Compute ingredient eligibility & Schedule E-1 compliance
    from api.services.ingredient_eligibility import check_ingredient_eligibility
    eligibility_evals = []
    verified_count = 0
    e1_count = 0
    for ing in ingredients:
        if isinstance(ing, dict):
            iname = ing.get("name") or ing.get("input_name") or ing.get("ingredient_name") or ""
            ibot = ing.get("botanical") or ing.get("botanical_name") or ""
        else:
            iname = str(ing).strip()
            ibot = ""
        if iname or ibot:
            res = check_ingredient_eligibility(iname, ibot)
            eligibility_evals.append(res)
            if res.get("verified"):
                verified_count += 1
            if res.get("schedule_e1"):
                e1_count += 1

    tot_ings = len(eligibility_evals)
    eligibility_summary = {
        "evaluations": eligibility_evals,
        "verified_count": verified_count,
        "total_count": tot_ings,
        "schedule_e1_count": e1_count,
        "is_all_verified": (verified_count == tot_ings and tot_ings > 0),
        "has_schedule_e1": (e1_count > 0),
    }

    return {
        "id": profile.public_id,
        "product_case_id": case.public_id if case else "",
        "product_name": case.name if case else "Product Analysis",
        "product_form": case.form if case else "Formulation",
        "intended_use": case.intended_use if case else "General Wellness",
        "ingredients": ingredients,
        "claims": claims,
        "jurisdiction": profile.jurisdiction,
        "potential_category": profile.potential_category,
        "category_confidence": profile.category_confidence,
        "category_reasoning": profile.category_reasoning,
        "total_requirements": profile.total_requirements,
        "relevant_count": profile.relevant_count,
        "potentially_relevant_count": profile.potentially_relevant_count,
        "needs_verification_count": profile.needs_verification_count,
        "info_missing_count": profile.info_missing_count,
        "sources_consulted": _deserialize_list(profile.sources_consulted),
        "sources_configured": profile.sources_configured,
        "sources_total": profile.sources_total,
        "information_gaps": _deserialize_list(profile.information_gaps),
        "document_checklist": _deserialize_list(profile.document_checklist),
        "status": profile.status,
        "requirements": requirements,
        "created_at": profile.created_at.isoformat() if profile.created_at else "",
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else "",
        "ingredient_eligibility": eligibility_summary,

        # Enriched India Regulatory Intelligence details
        "ayush_details": {
            "authority": "Ministry of Ayush / State Licensing Authority (SLA)",
            "act": "Drugs and Cosmetics Act, 1940",
            "gmp": "Schedule T Compliance Mandatory",
            "portal_name": "e-AUSHADHI Portal",
            "portal_url": "https://www.e-aushadhi.gov.in",
            "forms": [
                {
                    "form": "Form 24-D",
                    "title": "Application for License / NOC to manufacture Ayurvedic drugs",
                    "timeline": "30-45 Days",
                    "fee": "₹1,000",
                    "description": "Form submitted to State Licensing Authority along with formulation details and lab test reports.",
                    "download_url": "https://cdsco.gov.in/opencms/opencms/system/modules/CDSCO.WEB/elements/download_file_division.jsp?num_id=MTQ2Mw=="
                },
                {
                    "form": "Form 24-E",
                    "title": "Grant of License to manufacture for sale of Ayurvedic drugs",
                    "timeline": "60 Days",
                    "fee": "₹2,000",
                    "description": "Final manufacturing license issued post physical site audit by SLA Inspectors.",
                    "download_url": "https://cdsco.gov.in/opencms/opencms/system/modules/CDSCO.WEB/elements/download_file_division.jsp?num_id=MTQ2NA=="
                },
                {
                    "form": "Form 24-E-I",
                    "title": "GMP Certificate (Schedule T Compliance)",
                    "timeline": "30 Days",
                    "fee": "₹1,015",
                    "description": "Mandatory Good Manufacturing Practices certificate for herbal processing premises.",
                    "download_url": "https://cdsco.gov.in/opencms/opencms/system/modules/CDSCO.WEB/elements/download_file_division.jsp?num_id=MTQ2NQ=="
                }
            ]
        },
        "fssai_details": {
            "authority": "Food Safety and Standards Authority of India (FSSAI)",
            "act": "Food Safety and Standards Act, 2006",
            "enforcement": "Strict compliance mandated from Sept 1, 2025.",
            "fee": "₹7,500 + GST / Year (Central License)",
            "penalty": "Operating without license: Up to ₹2,00,000 fine and/or up to 6 months imprisonment under Section 63 of FSS Act 2006.",
            "portal_name": "FoSCoS Portal",
            "portal_url": "https://foscos.fssai.gov.in",
            "categories": [
                {
                    "code": "Category A",
                    "name": "Recipes from Authoritative Texts (Schedule A)",
                    "description": "Formulations declared in recognized texts (Ayurvedic Pharmacopoeia of India, Charaka Samhita, etc.). Direct filing on FoSCoS."
                },
                {
                    "code": "Category B / B1 / B2",
                    "name": "Proprietary Ayurveda Aahara / Novel Formulations",
                    "description": "Requires prior scientific evaluation and FSSAI Prior Approval Letter before commercial sale."
                }
            ]
        },
        "step_guides": {
            "ayush": [
                {"step": 1, "title": "Recipe & Ingredient Verification", "desc": "Ensure all botanical ingredients are documented in the Ayurvedic Pharmacopoeia of India (API).", "timeline": "Week 1-2"},
                {"step": 2, "title": "NABL Lab Analytical Testing", "desc": "Conduct mandatory testing for heavy metals, pesticide residues, microbial limits, and aflatoxins.", "timeline": "Week 3-4"},
                {"step": 3, "title": "e-AUSHADHI Filing (Form 24-D)", "desc": "Create portal profile on e-AUSHADHI, upload formulation dossier, label proof, and pay government fee.", "timeline": "Week 5-6"},
                {"step": 4, "title": "SLA Premises Audit & License (Form 24-E)", "desc": "Host State Licensing Inspector for Schedule T audit. Receive license and GMP Certificate (24-E-I).", "timeline": "Week 7-10"}
            ],
            "fssai": [
                {"step": 1, "title": "Category Classification", "desc": "Determine if formulation qualifies as Category A (Schedule A recipe) or Category B (Proprietary).", "timeline": "Week 1"},
                {"step": 2, "title": "FSSAI Prior Approval (If Proprietary)", "desc": "For Category B, submit safety rationale and claim data to FSSAI Scientific Committee.", "timeline": "Week 2-6"},
                {"step": 3, "title": "FoSCoS Central License Filing", "desc": "File online application under 'Ayurveda Aahara' head on FoSCoS portal with laboratory test results.", "timeline": "Week 7"},
                {"step": 4, "title": "License Issue & Packaging Logo", "desc": "Obtain 14-digit FSSAI License number and print mandatory 'Ayurveda Aahara' logo on packaging.", "timeline": "Week 8-9"}
            ]
        },
        "disclaimer": "This regulatory intelligence report is generated strictly for research and decision-support purposes under Indian regulatory frameworks (AYUSH & FSSAI). It does not constitute formal legal or regulatory advice. Consult a licensed regulatory attorney prior to commercial distribution."
    }

