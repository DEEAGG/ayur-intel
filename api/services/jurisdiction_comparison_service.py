"""AYUR-INTEL — Jurisdiction Comparison Service (Phase 10).

Normalizes regulatory requirements across jurisdictions, performs
cross-jurisdiction comparison, highlights differences, and generates
decision-support summaries.

This is RESEARCH decision-support, NOT legal advice.
Uses deterministic rule-based normalization — no AI provider required.
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
from api.models.jurisdiction_comparison import (
    JurisdictionComparison,
    ComparisonJurisdiction,
    ComparisonItem,
    ComparisonValue,
)
from api.services.regulatory_service import (
    generate_regulatory_analysis,
    profile_to_dict,
    classify_product,
    _deserialize_list,
)
from api.services.regulatory_adapter import SUPPORTED_JURISDICTIONS

logger = logging.getLogger("ayur_intel.jurisdiction_comparison_service")


# ---------------------------------------------------------------------------
# Normalization categories
# ---------------------------------------------------------------------------

# Normalized comparison categories and the source requirements that map to them
NORMALIZED_CATEGORIES = {
    "CLASSIFICATION": {
        "label": "Product Classification",
        "sort_order": 0,
        "source_categories": ["CLASSIFICATION"],
    },
    "INGREDIENTS": {
        "label": "Ingredient Requirements",
        "sort_order": 1,
        "source_categories": ["INGREDIENT"],
    },
    "CLAIMS": {
        "label": "Claims Compliance",
        "sort_order": 2,
        "source_categories": ["CLAIMS"],
    },
    "LABELLING": {
        "label": "Labelling Requirements",
        "sort_order": 3,
        "source_categories": ["LABELLING"],
    },
    "DOCUMENTATION": {
        "label": "Documentation / Dossier",
        "sort_order": 4,
        "source_categories": ["DOCUMENTATION"],
    },
    "SAFETY": {
        "label": "Safety Requirements",
        "sort_order": 5,
        "source_categories": ["SAFETY"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deserialize(value: Optional[str]) -> list:
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


# ---------------------------------------------------------------------------
# Normalize Requirements
# ---------------------------------------------------------------------------

def _normalize_requirements(
    requirements: List[RegulatoryRequirement],
    jurisdiction: str,
) -> Dict[str, dict]:
    """Group requirements by normalized category and extract key value."""
    normalized: Dict[str, dict] = {}

    for cat_key, cat_info in NORMALIZED_CATEGORIES.items():
        # Find requirements in this category
        cat_reqs = [
            r for r in requirements
            if r.category in cat_info["source_categories"]
        ]

        if cat_reqs:
            # Build a composite value from the best requirement
            primary = cat_reqs[0]  # first match is typically most relevant
            values = []
            for r in cat_reqs:
                values.append({
                    "title": r.title,
                    "description": r.description or "",
                    "authority": r.authority or "",
                    "source_name": r.source_name or "",
                    "evidence_detail": r.evidence_detail or "",
                    "limitations": r.limitations or "",
                    "next_action": r.next_action or "",
                    "applicability": r.applicability or "POTENTIALLY_RELEVANT",
                    "confidence": r.confidence or "MEDIUM",
                })

            normalized[cat_key] = {
                "value": primary.description or primary.title or "",
                "status": "FOUND",
                "confidence": primary.confidence or "MEDIUM",
                "source_name": primary.source_name or "",
                "evidence_detail": primary.evidence_detail or "",
                "evidence_type": primary.evidence_type or "",
                "authority": primary.authority or "",
                "details": values,
            }
        else:
            normalized[cat_key] = {
                "value": None,
                "status": "MISSING",
                "confidence": None,
                "source_name": None,
                "evidence_detail": None,
                "evidence_type": None,
                "authority": None,
                "details": [],
            }

    return normalized


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

def _compare_values(
    jurisdiction_values: Dict[str, dict],
    jurisdictions: List[str],
) -> List[dict]:
    """Compare normalized values across jurisdictions.

    Detects differences and builds comparison items.
    """
    items = []

    for cat_key, cat_info in NORMALIZED_CATEGORIES.items():
        values_for_item = []
        has_difference = False
        statuses = set()

        for jur in jurisdictions:
            jv = jurisdiction_values.get(jur, {}).get(cat_key, {})
            value_text = jv.get("value") or ""
            status = jv.get("status", "MISSING")
            statuses.add(status)

            values_for_item.append({
                "jurisdiction": jur,
                "value": value_text,
                "status": status,
                "confidence": jv.get("confidence"),
                "source_name": jv.get("source_name"),
                "evidence_detail": jv.get("evidence_detail"),
                "evidence_type": jv.get("evidence_type"),
                "authority": jv.get("authority"),
            })

        # Detect differences: if statuses are not all the same, it's a difference
        if len(statuses) > 1:
            has_difference = True

        # Also check if values differ meaningfully
        non_empty = [v for v in values_for_item if v.get("value")]
        if len(non_empty) > 1:
            # Multiple jurisdictions have data — check if they're similar
            texts = set(v["value"][:100] for v in non_empty if v.get("value"))
            if len(texts) > 1:
                has_difference = True

        # Build difference description
        diff_desc = None
        if has_difference:
            found_jurisdictions = [v["jurisdiction"] for v in values_for_item if v["status"] == "FOUND"]
            missing_jurisdictions = [v["jurisdiction"] for v in values_for_item if v["status"] != "FOUND"]

            parts = []
            if found_jurisdictions and missing_jurisdictions:
                parts.append(
                    f"Information found for {', '.join(found_jurisdictions)} but not for {', '.join(missing_jurisdictions)}."
                )
            elif len(set(v.get("value", "") for v in values_for_item if v.get("value"))) > 1:
                parts.append("Different regulatory requirements identified across jurisdictions.")

            if parts:
                diff_desc = " ".join(parts)

        items.append({
            "category": cat_key,
            "normalized_label": cat_info["label"],
            "sort_order": cat_info["sort_order"],
            "is_difference": has_difference,
            "difference_description": diff_desc,
            "values": values_for_item,
        })

    return items


# ---------------------------------------------------------------------------
# Build Key Differences
# ---------------------------------------------------------------------------

def _build_key_differences(items: List[dict]) -> List[str]:
    """Extract the top key differences for the summary."""
    diffs = []
    for item in items:
        if item["is_difference"]:
            diffs.append(item["difference_description"] or f"{item['normalized_label']} differs across jurisdictions.")
    return diffs[:5]


# ---------------------------------------------------------------------------
# Main Comparison
# ---------------------------------------------------------------------------

def generate_jurisdiction_comparison(
    db: Session,
    user: User,
    case_public_id: str,
    jurisdiction_codes: List[str],
) -> Optional[JurisdictionComparison]:
    """Generate a cross-jurisdiction regulatory comparison.

    1. Load or generate Regulatory Profiles for each jurisdiction
    2. Normalize requirements into common categories
    3. Compare across jurisdictions
    4. Highlight differences
    5. Save comparison
    """
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    # Ensure we have at least 2 jurisdictions
    if len(jurisdiction_codes) < 2:
        return None

    # Limit to 5 jurisdictions
    jurisdiction_codes = jurisdiction_codes[:5]

    # Validate jurisdictions
    valid_codes = [c for c in jurisdiction_codes if c in SUPPORTED_JURISDICTIONS]
    if len(valid_codes) < 2:
        return None

    # Generate or load regulatory profiles for each jurisdiction
    jurisdiction_data: Dict[str, dict] = {}
    comparison_jurisdictions = []

    for jur in valid_codes:
        # Try to load existing profile
        existing = (
            db.query(RegulatoryProfile)
            .filter(
                RegulatoryProfile.product_case_id == case.id,
                RegulatoryProfile.jurisdiction == jur,
                RegulatoryProfile.owner_id == user.id,
            )
            .order_by(RegulatoryProfile.created_at.desc())
            .first()
        )

        if existing:
            profile = existing
        else:
            # Generate a new profile
            profile = generate_regulatory_analysis(db, user, case_public_id, jur)

        if profile:
            jur_info = SUPPORTED_JURISDICTIONS[jur]
            sources_configured = profile.sources_configured
            sources_total = profile.sources_total
            source_coverage = (
                "FULL" if sources_configured == sources_total
                else "PARTIAL" if sources_configured > 0
                else "NONE"
            )

            jurisdiction_data[jur] = {
                "profile": profile,
                "profile_dict": profile_to_dict(profile),
            }

            comparison_jurisdictions.append({
                "jurisdiction": jur,
                "jurisdiction_name": jur_info.get("name", jur),
                "flag": jur_info.get("flag", ""),
                "regulatory_profile_id": profile.id,
                "confidence": profile.category_confidence or "LOW",
                "source_coverage": source_coverage,
                "sources_configured": sources_configured,
                "sources_total": sources_total,
                "requirements_count": profile.total_requirements,
                "category": profile.potential_category,
            })

    if len(comparison_jurisdictions) < 2:
        return None

    # Normalize requirements per jurisdiction
    jurisdiction_normalized: Dict[str, Dict[str, dict]] = {}
    for jur in valid_codes:
        if jur in jurisdiction_data:
            profile_dict = jurisdiction_data[jur]["profile_dict"]
            reqs = jurisdiction_data[jur]["profile"].requirements
            jurisdiction_normalized[jur] = _normalize_requirements(reqs, jur)
        else:
            jurisdiction_normalized[jur] = {k: {"value": None, "status": "MISSING"} for k in NORMALIZED_CATEGORIES}

    # Compare across jurisdictions
    items_data = _compare_values(jurisdiction_normalized, valid_codes)

    # Build key differences
    key_diffs = _build_key_differences(items_data)

    # Count differences
    diffs_count = sum(1 for item in items_data if item["is_difference"])

    # Information gaps
    gaps_total = 0
    for jur in valid_codes:
        if jur in jurisdiction_data:
            profile = jurisdiction_data[jur]["profile"]
            gaps = _deserialize(profile.information_gaps)
            gaps_total += len(gaps)

    # Create or update comparison record
    existing = (
        db.query(JurisdictionComparison)
        .filter(
            JurisdictionComparison.product_case_id == case.id,
            JurisdictionComparison.owner_id == user.id,
        )
        .order_by(JurisdictionComparison.created_at.desc())
        .first()
    )
    if existing:
        # Delete old data
        for item in existing.items:
            for val in item.values:
                db.delete(val)
            db.delete(item)
        for cj in existing.jurisdictions:
            db.delete(cj)
        db.flush()
        comparison = existing
        comparison.updated_at = datetime.now(timezone.utc)
    else:
        comparison = JurisdictionComparison(
            owner_id=user.id,
            product_case_id=case.id,
        )
        db.add(comparison)
        db.flush()

    # Update comparison fields
    comparison.jurisdictions_count = len(valid_codes)
    comparison.total_items = len(items_data)
    comparison.differences_found = diffs_count
    comparison.information_gaps_total = gaps_total
    comparison.key_differences = json.dumps(key_diffs) if key_diffs else None
    comparison.decision_support_notes = (
        f"Comparison of {len(valid_codes)} jurisdictions. "
        f"{diffs_count} key differences identified. "
        f"This comparison reflects the information currently available in AYUR-INTEL "
        f"and is not legal/regulatory advice."
    )

    # Create ComparisonJurisdiction records
    cj_records = []
    for cjd in comparison_jurisdictions:
        cj = ComparisonJurisdiction(
            comparison_id=comparison.id,
            jurisdiction=cjd["jurisdiction"],
            jurisdiction_name=cjd["jurisdiction_name"],
            flag=cjd["flag"],
            regulatory_profile_id=cjd.get("regulatory_profile_id"),
            confidence=cjd["confidence"],
            source_coverage=cjd["source_coverage"],
            sources_configured=cjd["sources_configured"],
            sources_total=cjd["sources_total"],
            requirements_count=cjd["requirements_count"],
            category=cjd["category"],
        )
        db.add(cj)
        cj_records.append(cj)
    db.flush()

    # Create ComparisonItem and ComparisonValue records
    for item_data in items_data:
        item = ComparisonItem(
            comparison_id=comparison.id,
            category=item_data["category"],
            normalized_label=item_data["normalized_label"],
            sort_order=item_data["sort_order"],
            is_difference="true" if item_data["is_difference"] else "false",
            difference_description=item_data.get("difference_description"),
        )
        db.add(item)
        db.flush()

        # Find the ComparisonJurisdiction for each value
        for val_data in item_data["values"]:
            jur = val_data["jurisdiction"]
            cj = next((c for c in cj_records if c.jurisdiction == jur), None)
            if cj:
                val = ComparisonValue(
                    comparison_item_id=item.id,
                    comparison_jurisdiction_id=cj.id,
                    value=val_data.get("value"),
                    status=val_data.get("status", "MISSING"),
                    confidence=val_data.get("confidence"),
                    source_name=val_data.get("source_name"),
                    evidence_detail=val_data.get("evidence_detail"),
                    evidence_type=val_data.get("evidence_type"),
                    authority=val_data.get("authority"),
                )
                db.add(val)

    db.commit()
    db.refresh(comparison)

    return comparison


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def comparison_to_dict(comparison: JurisdictionComparison) -> dict:
    """Serialize a JurisdictionComparison to a JSON-safe dict."""
    jurisdictions = []
    for cj in comparison.jurisdictions:
        jurisdictions.append({
            "id": cj.public_id,
            "jurisdiction": cj.jurisdiction,
            "jurisdiction_name": cj.jurisdiction_name,
            "flag": cj.flag,
            "confidence": cj.confidence,
            "source_coverage": cj.source_coverage,
            "sources_configured": cj.sources_configured,
            "sources_total": cj.sources_total,
            "requirements_count": cj.requirements_count,
            "category": cj.category,
        })

    items = []
    for item in comparison.items:
        values = []
        for val in item.values:
            values.append({
                "id": val.public_id,
                "value": val.value,
                "status": val.status,
                "confidence": val.confidence,
                "source_name": val.source_name,
                "evidence_detail": val.evidence_detail,
                "evidence_type": val.evidence_type,
                "authority": val.authority,
                "jurisdiction": val.jurisdiction.jurisdiction if val.jurisdiction else "",
            })

        items.append({
            "id": item.public_id,
            "category": item.category,
            "normalized_label": item.normalized_label,
            "sort_order": item.sort_order,
            "is_difference": item.is_difference == "true",
            "difference_description": item.difference_description,
            "values": values,
        })

    return {
        "id": comparison.public_id,
        "product_case_id": comparison.product_case.public_id if comparison.product_case else "",
        "product_name": comparison.product_case.name if comparison.product_case else "",
        "jurisdictions": jurisdictions,
        "items": items,
        "total_items": comparison.total_items,
        "jurisdictions_count": comparison.jurisdictions_count,
        "differences_found": comparison.differences_found,
        "information_gaps_total": comparison.information_gaps_total,
        "key_differences": _deserialize(comparison.key_differences),
        "decision_support_notes": comparison.decision_support_notes,
        "status": comparison.status,
        "created_at": comparison.created_at.isoformat() if comparison.created_at else "",
        "updated_at": comparison.updated_at.isoformat() if comparison.updated_at else "",
    }
