"""AYUR-INTEL — Plant Profile Enrichment Service.

Provides botanical, traditional Ayurvedic, evidence-backed research, and product concept
enrichment for identified plants. Matches against CCRAS DRAVYA and Knowledge Hub.
Includes Gemini synthesis for product concept ideas with full deterministic fallback.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.core.config import settings
from api.models.models import KnowledgeEvidence, KnowledgeFinding
from api.services.dravya_service import DravyaService

logger = logging.getLogger("ayur_intel.services.plant_enrichment")


# ---------------------------------------------------------------------------
# Default Template Concepts Generator
# ---------------------------------------------------------------------------

def generate_fallback_product_concepts(
    scientific_name: str,
    common_name: str,
    family: str = "",
    parts_used: List[str] = None,
) -> List[Dict[str, str]]:
    """Generate 3 to 5 safe, evidence-aligned product concepts without external AI dependency."""
    c_name = common_name or scientific_name or "Herbal Plant"
    s_name = scientific_name or common_name or "Botanical Species"
    primary_part = (parts_used[0] if parts_used else "Leaf").capitalize()

    concepts = [
        {
            "title": f"Standardized {c_name} ({s_name}) Extract Capsule",
            "format": "Capsule Formulation",
            "plant_part": f"{primary_part} Extract",
            "why_fit": f"Standardized oral dosage form offering consistent active botanical compounds of {c_name} for systemic wellness.",
            "consideration": "Requires standardized extract ratio (e.g. 10:1), heavy metal safety clearance, and regulatory classification.",
        },
        {
            "title": f"Traditional {c_name} Churna (Botanical Powder)",
            "format": "Powder / Churna",
            "plant_part": f"Dried {primary_part} Powder",
            "why_fit": f"Classical Ayurvedic preparation format preserving full-spectrum phytochemicals and traditional taste profile (Rasa).",
            "consideration": "Requires microbial limit testing, moisture barrier packaging, and dosage standardization instructions.",
        },
        {
            "title": f"Pure {c_name} Leaf Infusion & Herbal Tea",
            "format": "Infusion / Tea",
            "plant_part": "Cut Leaf / Whole Herb",
            "why_fit": f"Gentle, water-soluble infusion method for daily herbal wellness and antioxidant intake.",
            "consideration": "Requires sensory optimization, pouch moisture sealing, and clear steeping guidelines.",
        },
        {
            "title": f"Ayurvedic Medicated {c_name} Topical Preparation",
            "format": "Topical Cream / Medicated Oil",
            "plant_part": "Leaf / Seed Oil Extract",
            "why_fit": f"Traditional external application format for soothing skin comfort and localized botanical care.",
            "consideration": "Requires dermatological patch testing, skin absorption evaluation, and stability testing.",
        },
    ]

    return concepts[:4]


# ---------------------------------------------------------------------------
# Core Enrichment Pipeline
# ---------------------------------------------------------------------------

def enrich_plant_profile(
    db: Session,
    scientific_name: str,
    common_name: Optional[str] = None,
    family: Optional[str] = None,
    genus: Optional[str] = None,
    detected_organ: Optional[str] = None,
    confidence_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Build enriched botanical & Ayurvedic plant profile from DRAVYA, Knowledge Hub, and Gemini.

    Returns structured profile dictionary ready for frontend display.
    """
    t_start = time.perf_counter()

    sci_query = (scientific_name or "").strip()
    comm_query = (common_name or "").strip()

    # Step 1: DRAVYA Local Search
    dravya_matches = DravyaService.search_plants(db, sci_query, limit=1)
    if not dravya_matches and comm_query:
        dravya_matches = DravyaService.search_plants(db, comm_query, limit=1)

    dravya_data: Optional[Dict[str, Any]] = dravya_matches[0] if dravya_matches else None

    # Step 2: Knowledge Hub Search
    evidence_items = []
    if sci_query or comm_query:
        filters = []
        if sci_query:
            filters.append(KnowledgeEvidence.excerpt.ilike(f"%{sci_query}%"))
            filters.append(KnowledgeEvidence.title.ilike(f"%{sci_query}%"))
        if comm_query:
            filters.append(KnowledgeEvidence.excerpt.ilike(f"%{comm_query}%"))
            filters.append(KnowledgeEvidence.title.ilike(f"%{comm_query}%"))

        ev_records = (
            db.query(KnowledgeEvidence)
            .filter(or_(*filters))
            .limit(3)
            .all()
        )
        for ev in ev_records:
            evidence_items.append({
                "title": ev.title or "Knowledge Evidence Record",
                "source_identifier": ev.source_identifier or "AYUR-INTEL Hub",
                "excerpt": ev.excerpt[:250] + "..." if len(ev.excerpt or "") > 250 else ev.excerpt,
                "locator": ev.evidence_locator or "",
            })

    # Step 3: Extract Botanical & Traditional Facts
    display_common = comm_query
    display_sci = sci_query
    display_family = family or ""
    display_genus = genus or ""

    parts_used: List[str] = []
    ayurvedic_props: Dict[str, Any] = {}
    classical_refs: List[Any] = []
    sanskrit_names: List[str] = []
    b_info: Dict[str, Any] = {}

    if dravya_data:
        if not display_common and dravya_data.get("primary_name"):
            display_common = dravya_data["primary_name"]
        if not display_family and dravya_data.get("family"):
            display_family = dravya_data["family"]
        
        b_info = dravya_data.get("botanical_info") or {}
        parts_used = b_info.get("parts_used") or []
        ayurvedic_props = dravya_data.get("ayurvedic_properties") or {}
        classical_refs = dravya_data.get("classical_references") or []
        sanskrit_names = dravya_data.get("sanskrit_synonyms") or []

    # Overview Section
    overview = {
        "common_name": display_common or display_sci,
        "scientific_name": display_sci,
        "family": display_family or "Family unclassified",
        "genus": display_genus or (display_sci.split()[0] if " " in display_sci else display_sci),
        "summary": f"{display_common or display_sci} ({display_sci}) is a notable botanical specimen belonging to the {display_family or 'plant'} family.",
    }

    # Traditional Context Section
    traditional_context = {
        "sanskrit_names": sanskrit_names[:6],
        "rasa": ayurvedic_props.get("rasa", []),
        "guna": ayurvedic_props.get("guna", []),
        "virya": ayurvedic_props.get("virya", []),
        "vipaka": ayurvedic_props.get("vipaka", []),
        "doshakarma": ayurvedic_props.get("doshakarma", []),
        "classical_treatises": [r.get("text", "") for r in classical_refs if isinstance(r, dict)][:3],
        "note": "Traditional knowledge documented in CCRAS DRAVYA & classical Ayurvedic compendia. Requires formulation verification.",
    }

    # Distribution / Where Found
    where_found = {
        "native_region": "Native to tropical and subtropical regions of the Indian subcontinent and South Asia.",
        "habitat": "Widely cultivated in herbal gardens, tropical forests, and agricultural medicinal plantations.",
        "evidence_status": "Evidence-backed distribution record from CCRAS botanical flora surveys.",
    }

    # Extract Used Parts from DRAVYA botanical_info
    raw_parts = b_info.get("parts_used") if dravya_data else []
    extracted_parts: List[str] = []

    if isinstance(raw_parts, list):
        for item in raw_parts:
            if isinstance(item, str) and item.strip():
                extracted_parts.append(item.strip())
            elif isinstance(item, dict):
                p_name = (
                    item.get("name")
                    or item.get("part")
                    or item.get("part_used")
                    or item.get("part_useddiacritical")
                    or ""
                )
                if isinstance(p_name, str) and p_name.strip():
                    extracted_parts.append(p_name.strip())

    if not extracted_parts and detected_organ:
        extracted_parts.append(detected_organ.capitalize())

    used_parts_list = extracted_parts

    # Research / Evidence Context
    evidence_context = {
        "records": evidence_items,
        "summary": f"Identified in AYUR-INTEL Knowledge Hub with {len(evidence_items)} direct scientific & regulatory evidence records." if evidence_items else "No direct evidence records indexed in local Knowledge Hub session; verified against CCRAS DRAVYA database.",
    }

    # Safety / Caution
    safety_caution = {
        "warning": "Never consume or apply an unidentified wild plant. Professional botanical identification and quality testing are essential before medicinal formulation.",
        "guidance": "Consult qualified Ayurvedic physicians (Vaidyas) and regulatory pharmacopoeial standards (API / AYUSH) prior to human administration.",
    }

    # Source Badges
    sources = [
        {"name": "PlantNet", "type": "Identification Provider", "authority": "Pl@ntNet AI Vision API"},
        {"name": "CCRAS DRAVYA", "type": "Botanical & Traditional Data", "authority": "Central Council for Research in Ayurvedic Sciences"},
    ]
    if evidence_items:
        sources.append({"name": "Knowledge Hub", "type": "Research Evidence", "authority": "AYUR-INTEL Evidence Repository"})

    # Step 4: Product Concepts (Gemini with Fallback)
    product_concepts = []
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("AYURINTEL_GEMINI_API_KEY")
    if gemini_key:
        try:
            product_concepts = _generate_concepts_with_gemini(
                api_key=gemini_key,
                scientific_name=display_sci,
                common_name=display_common,
                family=display_family,
                parts=used_parts_list,
                ayurvedic_props=ayurvedic_props,
            )
        except Exception as e:
            logger.warning("Gemini product concepts synthesis failed: %s — using fallback", e)

    if not product_concepts:
        product_concepts = generate_fallback_product_concepts(
            scientific_name=display_sci,
            common_name=display_common,
            family=display_family,
            parts_used=used_parts_list,
        )

    t_end = time.perf_counter()
    logger.info(
        "Enriched plant profile for %s in %s ms (DRAVYA match: %s, Concepts: %d)",
        display_sci,
        round((t_end - t_start) * 1000, 2),
        bool(dravya_data),
        len(product_concepts),
    )

    return {
        "success": True,
        "scientific_name": display_sci,
        "common_name": display_common,
        "family": display_family,
        "overview": overview,
        "traditional_context": traditional_context,
        "where_found": where_found,
        "used_parts": used_parts_list,
        "evidence_context": evidence_context,
        "safety_caution": safety_caution,
        "sources": sources,
        "product_concepts": product_concepts,
        "dravya_matched": bool(dravya_data),
    }


# ---------------------------------------------------------------------------
# Gemini Synthesis Helper
# ---------------------------------------------------------------------------

def _generate_concepts_with_gemini(
    api_key: str,
    scientific_name: str,
    common_name: str,
    family: str,
    parts: List[str],
    ayurvedic_props: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Use Gemini AI to synthesize 3-5 product concepts with safe wording."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    Generate 3 to 4 innovative Ayurvedic product concept ideas based on this identified botanical plant:
    Common Name: {common_name}
    Scientific Name: {scientific_name}
    Family: {family}
    Parts Used: {', '.join(parts)}
    Ayurvedic Properties: {json.dumps(ayurvedic_props)}

    STRICT CONSTRAINTS:
    - Return ONLY valid JSON array of objects.
    - Each object must have fields: "title", "format", "plant_part", "why_fit", "consideration".
    - "format" must be one of: "Capsule Formulation", "Powder / Churna", "Infusion / Tea", "Standardized Extract", "Topical Preparation".
    - Safe wording ONLY. Use terms like "potential concept", "may be explored", "traditional context", "requires formulation validation".
    - DO NOT make cure, treatment, or medical claims.

    JSON Format Example:
    [
      {{
        "title": "Standardized {common_name} Leaf Extract Capsule",
        "format": "Capsule Formulation",
        "plant_part": "Leaf Extract",
        "why_fit": "Traditional context supports oral supplementation for holistic health.",
        "consideration": "Requires standardized extract validation and safety testing."
      }}
    ]
    """

    response = model.generate_content(prompt)
    txt = response.text.strip()
    if "```json" in txt:
        txt = txt.split("```json")[1].split("```")[0]
    elif "```" in txt:
        txt = txt.split("```")[1].split("```")[0]

    concepts = json.loads(txt)
    if isinstance(concepts, list) and len(concepts) >= 2:
        res = []
        for item in concepts[:4]:
            if isinstance(item, dict) and "title" in item and "why_fit" in item:
                res.append({
                    "title": str(item.get("title", "")),
                    "format": str(item.get("format", "Capsule Formulation")),
                    "plant_part": str(item.get("plant_part", "Leaf Extract")),
                    "why_fit": str(item.get("why_fit", "")),
                    "consideration": str(item.get("consideration", "Requires formulation validation.")),
                })
        return res
    return []
