"""AYUR-INTEL — AI Source Router Service (Phase 16).

Deterministic rule-based source routing that classifies user questions,
detects jurisdiction, maps to required source types, and ranks candidate
sources from the Source Registry.

No AI fabrication — all routing decisions are transparent and traceable.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import User, ProductCase, Source

logger = logging.getLogger("ayur_intel.source_router")


# -------------------------------------------------------------------
# Source type definitions with capabilities
# -------------------------------------------------------------------
SOURCE_TYPE_CONFIG = {
    "PATENT": {
        "label": "Patent Authority",
        "icon": "gavel",
        "color": "#f44336",
        "keywords": [
            "patent", "filing", "application", "granted", "prior art",
            "invention", "claim", "publication", "priority date",
            "patent family", "infringement", "novelty", "patentability",
        ],
        "capabilities": [
            "Patent publication search",
            "Patent family lookup",
            "Patent status verification",
            "Claim analysis",
            "Prior art identification",
        ],
        "cannot": [
            "Medical diagnosis",
            "Regulatory compliance",
            "Safety assessment",
        ],
        "authority_priority": {
            "GOV": 1, "PATENT_AUTHORITY": 1, "OFFICIAL": 2,
            "INTERNATIONAL": 3, "DATABASE": 4, "SCIENTIFIC": 5,
            "OTHER": 6,
        },
    },
    "REGULATORY": {
        "label": "Regulatory Source",
        "icon": "policy",
        "color": "#2196f3",
        "keywords": [
            "regulation", "regulatory", "compliance", "requirement",
            "approval", "notification", "registration", "category",
            "classification", "guideline", "guidance", "authority",
            "ministry", "agency", "fda", "ayush", "bfarm", "ema",
            "herbal", "supplement", "drug", "medicinal", "traditional medicine",
            "allowed", "permitted", "prohibited", "restriction",
            "labeling", "labelling", "claims", "safety", "manufacturing",
        ],
        "capabilities": [
            "Regulatory requirement lookup",
            "Product classification guidance",
            "Compliance requirement mapping",
            "Labeling requirements",
            "Safety requirements",
        ],
        "cannot": [
            "Patent novelty assessment",
            "Infringement determination",
            "Clinical trial design",
        ],
        "authority_priority": {
            "GOV": 1, "REGULATORY_AUTHORITY": 1, "OFFICIAL": 2,
            "INTERNATIONAL": 3, "DATABASE": 4, "SCIENTIFIC": 5,
            "OTHER": 6,
        },
    },
    "TRADITIONAL_KNOWLEDGE": {
        "label": "Traditional Knowledge Source",
        "icon": "menu_book",
        "color": "#ff9800",
        "keywords": [
            "traditional", "ayurveda", "ayurvedic", "siddha", "unani",
            "folk", "indigenous", "ancient", "historical use",
            "traditional use", "ethnobotanical", "classical text",
            "charaka", "sushruta", "ashtanga", "dosha",
            "prakriti", "rasa", "virya", "vipaka", " karma",
            "preparation", "formulation", "bhasma", "ashava",
        ],
        "capabilities": [
            "Traditional use documentation",
            "Classical text references",
            "Ethnobotanical data",
            "Preparation methods",
            "Traditional formulations",
        ],
        "cannot": [
            "Modern patent analysis",
            "Regulatory compliance",
            "Clinical evidence",
        ],
        "authority_priority": {
            "TK_AUTHORITY": 1, "GOV": 2, "OFFICIAL": 2,
            "INTERNATIONAL": 3, "DATABASE": 4, "SCIENTIFIC": 5,
            "OTHER": 6,
        },
    },
    "BOTANICAL": {
        "label": "Botanical Source",
        "icon": "eco",
        "color": "#4caf50",
        "keywords": [
            "plant", "botanical", "species", "genus", "family",
            "identification", "taxonomy", "morphology", "cultivation",
            "extraction", "part used", "active compound", "phytochemical",
            "withania", "bacopa", "centella", "inositol", "ashwagandha",
            "brahmi", "gotu kola", "tulsi", "neem", "turmeric",
        ],
        "capabilities": [
            "Plant identification",
            "Botanical classification",
            "Phytochemical data",
            "Cultivation information",
            "Extraction methods",
        ],
        "cannot": [
            "Patent analysis",
            "Regulatory compliance",
            "Traditional use documentation",
        ],
        "authority_priority": {
            "BOTANICAL_AUTHORITY": 1, "GOV": 2, "SCIENTIFIC": 3,
            "DATABASE": 4, "OTHER": 5,
        },
    },
    "SCIENTIFIC": {
        "label": "Scientific/Research Source",
        "icon": "science",
        "color": "#9c27b0",
        "keywords": [
            "study", "research", "clinical", "trial", "evidence",
            "publication", "journal", "peer-reviewed", "efficacy",
            "safety", "toxicology", "pharmacology", "bioavailability",
            "randomized", "meta-analysis", "systematic review",
            "dosage", "dose", "adverse", "interaction",
        ],
        "capabilities": [
            "Scientific literature search",
            "Clinical evidence",
            "Pharmacological data",
            "Safety/toxicology data",
            "Efficacy evidence",
        ],
        "cannot": [
            "Patent analysis",
            "Regulatory compliance",
            "Traditional knowledge documentation",
        ],
        "authority_priority": {
            "SCIENTIFIC_AUTHORITY": 1, "PUBLISHER": 2,
            "DATABASE": 3, "OTHER": 4,
        },
    },
    "PRODUCT": {
        "label": "Product Information",
        "icon": "inventory_2",
        "color": "#2d4a3e",
        "keywords": [
            "product", "ingredient", "formulation", "dosage",
            "composition", "brand", "package", "form", "capsule",
            "tablet", "powder", "extract", "intended use",
        ],
        "capabilities": [
            "Product passport data",
            "Ingredient information",
            "Formulation details",
            "User-provided product data",
        ],
        "cannot": [
            "External authoritative evidence",
            "Patent analysis",
            "Regulatory compliance",
        ],
        "authority_priority": {
            "USER_PROVIDED": 1, "PRODUCT_DATABASE": 2, "OTHER": 3,
        },
    },
}


# -------------------------------------------------------------------
# Jurisdiction detection
# -------------------------------------------------------------------
JURISDICTION_PATTERNS = {
    "IN": [
        r"\b(india|indian|ayush|ayush\b|ayurveda\b|ayurvedic\b|siddha|unani)",
        r"\b(ministry\s+of\s+ayush|ayush\s+ministry)",
        r"\b(ip\s+india|indian\s+patent)",
    ],
    "US": [
        r"\b(usa|u\.?s\.?|united\s+states|american)",
        r"\b(fda|uspto|nih|cdc|federal\s+register)",
        r"\b(dietary\s+supplement|dshea|dsupplement)",
    ],
    "EU": [
        r"\b(eu|european\s+union|europe|european)",
        r"\b(european\s+medicines\s+agency|ema|european\s+commission)",
        r"\b(herbal\s+directive|traditional\s+herbal|thmpd)",
    ],
    "DE": [
        r"\b(germany|german|deutschland|deutsch)",
        r"\b(bfarm|bundesinstitut)",
    ],
    "GLOBAL": [
        r"\b(who|world\s+health|global|international|wipo)",
    ],
}


def detect_jurisdiction(question: str, case_jurisdictions: List[str] = None) -> List[str]:
    """Detect jurisdictions from the question text.

    Returns a list of detected jurisdiction codes, ordered by relevance.
    Falls back to case jurisdictions if none detected from question.
    """
    q = question.lower()
    detected = []

    for jur_code, patterns in JURISDICTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q, re.IGNORECASE):
                if jur_code not in detected:
                    detected.append(jur_code)
                break

    # If no jurisdiction detected, fall back to case jurisdictions
    if not detected and case_jurisdictions:
        detected = list(case_jurisdictions)

    # If still nothing, default to GLOBAL
    if not detected:
        detected = ["GLOBAL"]

    return detected


# -------------------------------------------------------------------
# Question classification
# -------------------------------------------------------------------
def classify_question(question: str) -> Dict:
    """Classify a user question into topic categories.

    Returns a dict with:
    - primary_topic: the most likely source type
    - secondary_topics: other relevant source types
    - confidence: classification confidence
    - detected_keywords: keywords that matched
    """
    q = question.lower()
    scores = {}
    matched_keywords = {}

    for stype, config in SOURCE_TYPE_CONFIG.items():
        score = 0
        matches = []
        for kw in config["keywords"]:
            if kw.lower() in q:
                # Longer keywords get more weight
                weight = len(kw.split()) * 2 + 1
                score += weight
                matches.append(kw)
        if score > 0:
            scores[stype] = score
            matched_keywords[stype] = matches

    if not scores:
        return {
            "primary_topic": "GENERAL",
            "secondary_topics": [],
            "confidence": "LOW",
            "detected_keywords": {},
        }

    # Sort by score
    sorted_topics = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_topics[0]

    # Confidence based on score margin
    if len(sorted_topics) > 1:
        margin = primary[1] - sorted_topics[1][1]
        confidence = "HIGH" if margin >= 3 else "MEDIUM"
    else:
        confidence = "HIGH"

    # Secondary topics (score >= 50% of primary)
    threshold = primary[1] * 0.5
    secondary = [t[0] for t in sorted_topics[1:] if t[1] >= threshold]

    return {
        "primary_topic": primary[0],
        "secondary_topics": secondary,
        "confidence": confidence,
        "detected_keywords": matched_keywords,
    }


# -------------------------------------------------------------------
# Source ranking
# -------------------------------------------------------------------
def _source_authority_rank(source: Source) -> int:
    """Get the authority rank of a source (lower = better)."""
    if not source.source_type:
        return 10
    config = SOURCE_TYPE_CONFIG.get(source.source_type, {})
    priority_map = config.get("authority_priority", {})
    return priority_map.get(source.authority, 8) if source.authority else 8


def rank_sources(
    sources: List[Source],
    required_type: str,
    jurisdiction: str,
    case_jurisdictions: List[str] = None,
) -> List[Dict]:
    """Rank candidate sources for a given routing need.

    Returns ranked list of sources with routing metadata.
    """
    candidates = []

    for source in sources:
        if not source.is_active:
            continue

        # Check if source type matches
        type_match = source.source_type == required_type

        # Check jurisdiction match
        jur_match = (
            source.jurisdiction == jurisdiction
            or source.jurisdiction == "GLOBAL"
            or jurisdiction == "GLOBAL"
        )

        # Calculate relevance score
        score = 0
        reasons = []

        if type_match:
            score += 10
            reasons.append("source type matches required type")

        if jur_match:
            score += 5
            if source.jurisdiction == jurisdiction:
                reasons.append(f"jurisdiction matches {jurisdiction}")
            elif source.jurisdiction == "GLOBAL":
                reasons.append("global source applicable")

        # Authority ranking
        auth_rank = _source_authority_rank(source)
        score += max(0, 10 - auth_rank)
        reasons.append(f"authority priority: {auth_rank}")

        # Configured sources get a boost
        if source.is_configured:
            score += 3
            reasons.append("source is configured")

        if score > 0:
            candidates.append({
                "source_id": source.public_id,
                "name": source.name,
                "authority": source.authority,
                "source_type": source.source_type,
                "jurisdiction": source.jurisdiction,
                "is_configured": source.is_configured,
                "url": source.url,
                "description": source.description,
                "relevance_score": score,
                "reasons": reasons,
                "authority_rank": auth_rank,
            })

    # Sort by relevance score (desc), then authority rank (asc)
    candidates.sort(key=lambda x: (-x["relevance_score"], x["authority_rank"]))

    return candidates


# -------------------------------------------------------------------
# Main routing decision
# -------------------------------------------------------------------
def route_question(
    db: Session,
    user: User,
    question: str,
    case_public_id: str = None,
) -> Dict:
    """Route a user question to appropriate sources.

    This is the main entry point for the Source Router.
    """
    # Get case context if available
    case = None
    case_jurisdictions = []
    if case_public_id:
        case = (
            db.query(ProductCase)
            .filter(ProductCase.public_id == case_public_id, ProductCase.owner_id == user.id)
            .first()
        )
        if case:
            try:
                case_jurisdictions = json.loads(case.jurisdictions) if case.jurisdictions else []
            except (json.JSONDecodeError, TypeError):
                case_jurisdictions = []

    # Step 1: Classify the question
    classification = classify_question(question)
    primary_topic = classification["primary_topic"]
    secondary_topics = classification["secondary_topics"]

    # Step 2: Detect jurisdiction
    jurisdictions = detect_jurisdiction(question, case_jurisdictions)

    # Step 3: Get all active sources
    all_sources = db.query(Source).filter(Source.is_active == True).all()

    # Step 4: Route for each jurisdiction
    routing_decisions = []

    for jur in jurisdictions:
        # Primary source routing
        primary_sources = rank_sources(all_sources, primary_topic, jur, case_jurisdictions)

        # Secondary source routing
        secondary_sources = []
        for stype in secondary_topics:
            secondary_sources.extend(rank_sources(all_sources, stype, jur, case_jurisdictions))

        # Deduplicate secondary sources
        seen_secondary = set()
        deduped_secondary = []
        for s in secondary_sources:
            if s["source_id"] not in seen_secondary:
                seen_secondary.add(s["source_id"])
                deduped_secondary.append(s)

        # Build routing decision
        selected_source = primary_sources[0] if primary_sources else None
        alternatives = primary_sources[1:3] + deduped_secondary[:2]

        # Determine routing confidence
        if selected_source:
            if selected_source["is_configured"]:
                routing_confidence = "HIGH"
            else:
                routing_confidence = "MEDIUM"
        else:
            routing_confidence = "UNKNOWN"

        # Build explanation
        if selected_source:
            explanation_parts = []
            explanation_parts.append(f"The question concerns {primary_topic.lower().replace('_', ' ')} information")
            if jur != "GLOBAL":
                explanation_parts.append(f"for {jur} jurisdiction")
            explanation_parts.append(f"Source '{selected_source['name']}' was selected because:")
            for reason in selected_source["reasons"][:3]:
                explanation_parts.append(f"- {reason}")
            explanation = " ".join(explanation_parts[:2]) + ". " + ". ".join(explanation_parts[2:])
        else:
            explanation = f"No suitable {primary_topic.lower().replace('_', ' ')} source found for {jur} jurisdiction."

        # Check for source conflicts (multiple high-ranking sources)
        has_conflict = False
        conflict_details = None
        if len(primary_sources) >= 2:
            top_two = primary_sources[:2]
            if abs(top_two[0]["relevance_score"] - top_two[1]["relevance_score"]) <= 2:
                has_conflict = True
                conflict_details = {
                    "source_a": top_two[0],
                    "source_b": top_two[1],
                    "note": "Both sources have similar relevance. Review recommended.",
                }

        routing_decisions.append({
            "jurisdiction": jur,
            "primary_topic": primary_topic,
            "detected_keywords": classification["detected_keywords"].get(primary_topic, []),
            "selected_source": selected_source,
            "alternative_sources": alternatives,
            "routing_confidence": routing_confidence,
            "explanation": explanation,
            "has_conflict": has_conflict,
            "conflict_details": conflict_details,
            "source_type_info": SOURCE_TYPE_CONFIG.get(primary_topic, {}),
        })

    # Multi-source routing summary
    all_source_types_needed = [primary_topic] + secondary_topics
    source_type_summary = []
    for stype in all_source_types_needed:
        config = SOURCE_TYPE_CONFIG.get(stype, {})
        available_count = sum(1 for s in all_sources if s.source_type == stype and s.is_active)
        configured_count = sum(1 for s in all_sources if s.source_type == stype and s.is_active and s.is_configured)
        source_type_summary.append({
            "source_type": stype,
            "label": config.get("label", stype),
            "icon": config.get("icon", "help"),
            "color": config.get("color", "#757575"),
            "available_count": available_count,
            "configured_count": configured_count,
            "is_primary": stype == primary_topic,
        })

    return {
        "question": question,
        "classification": {
            "primary_topic": primary_topic,
            "secondary_topics": secondary_topics,
            "confidence": classification["confidence"],
            "all_detected_keywords": classification["detected_keywords"],
        },
        "jurisdictions": jurisdictions,
        "routing_decisions": routing_decisions,
        "source_type_summary": source_type_summary,
        "total_sources_available": len(all_sources),
        "total_sources_configured": sum(1 for s in all_sources if s.is_configured),
        "disclaimer": "Source routing is based on configured source registry and question classification. "
                       "Routing confidence reflects source availability, not factual accuracy.",
    }


# -------------------------------------------------------------------
# Get available sources
# -------------------------------------------------------------------
def get_source_registry(db: Session) -> Dict:
    """Get the complete source registry with capabilities."""
    sources = db.query(Source).filter(Source.is_active == True).all()

    registry = []
    for source in sources:
        config = SOURCE_TYPE_CONFIG.get(source.source_type, {})
        registry.append({
            "id": source.public_id,
            "name": source.name,
            "authority": source.authority,
            "source_type": source.source_type,
            "source_type_label": config.get("label", source.source_type),
            "source_type_icon": config.get("icon", "help"),
            "source_type_color": config.get("color", "#757575"),
            "jurisdiction": source.jurisdiction,
            "url": source.url,
            "description": source.description,
            "is_configured": source.is_configured,
            "is_active": source.is_active,
            "capabilities": config.get("capabilities", []),
            "cannot": config.get("cannot", []),
            "authority_priority": _source_authority_rank(source),
        })

    # Group by source type
    by_type = {}
    for s in registry:
        t = s["source_type"] or "UNKNOWN"
        if t not in by_type:
            by_type[t] = {
                "type": t,
                "label": SOURCE_TYPE_CONFIG.get(t, {}).get("label", t),
                "icon": SOURCE_TYPE_CONFIG.get(t, {}).get("icon", "help"),
                "color": SOURCE_TYPE_CONFIG.get(t, {}).get("color", "#757575"),
                "sources": [],
            }
        by_type[t]["sources"].append(s)

    return {
        "total_sources": len(registry),
        "configured_sources": sum(1 for s in registry if s["is_configured"]),
        "active_sources": sum(1 for s in registry if s["is_active"]),
        "sources": registry,
        "by_type": list(by_type.values()),
        "source_types": list(SOURCE_TYPE_CONFIG.keys()),
    }


# -------------------------------------------------------------------
# Quick route helpers for other services
# -------------------------------------------------------------------
def get_best_source_for_type(
    db: Session,
    source_type: str,
    jurisdiction: str = "GLOBAL",
) -> Optional[Source]:
    """Get the best available source for a given type and jurisdiction."""
    sources = (
        db.query(Source)
        .filter(Source.source_type == source_type, Source.is_active == True)
        .all()
    )
    if not sources:
        return None

    ranked = rank_sources(sources, source_type, jurisdiction)
    if ranked:
        return db.query(Source).filter(Source.public_id == ranked[0]["source_id"]).first()
    return None
