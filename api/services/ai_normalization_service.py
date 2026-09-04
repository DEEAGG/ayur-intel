"""AYUR-INTEL — AI Normalization Service for Product Passport Intake.

Normalizes natural language product descriptions (in English, Hindi, Hinglish, or mixed languages)
into structured Product Passport properties without inventing facts.

Supports:
1. Google Gemini API (if GEMINI_API_KEY / GOOGLE_API_KEY / AYURINTEL_GEMINI_API_KEY is configured in env).
2. High-accuracy deterministic local Ayurvedic & botanical knowledge rule normalizer as fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ayur_intel.ai_normalization")

# ---------------------------------------------------------------------------
# Comprehensive Ayurvedic & Botanical Knowledge Dictionary (for deterministic fallback)
# ---------------------------------------------------------------------------

BOTANICAL_KNOWLEDGE_BASE = {
    "ashwagandha": {"common_name": "Ashwagandha", "botanical_name": "Withania somnifera", "hindi": "अश्वगंधा", "parts": "Root", "traditional_category": "Rasayana / Balya"},
    "brahmi": {"common_name": "Brahmi", "botanical_name": "Bacopa monnieri", "hindi": "ब्राह्मी", "parts": "Whole plant", "traditional_category": "Medhya Rasayana"},
    "tulsi": {"common_name": "Tulsi (Holy Basil)", "botanical_name": "Ocimum sanctum", "hindi": "तुलसी", "parts": "Leaves", "traditional_category": "Swasahara / Hridya"},
    "holy basil": {"common_name": "Tulsi (Holy Basil)", "botanical_name": "Ocimum sanctum", "hindi": "तुलसी", "parts": "Leaves", "traditional_category": "Swasahara"},
    "shankhpushpi": {"common_name": "Shankhpushpi", "botanical_name": "Convolvulus pluricaulis", "hindi": "शंखपुष्पी", "parts": "Whole herb", "traditional_category": "Medhya"},
    "jatamansi": {"common_name": "Jatamansi", "botanical_name": "Nardostachys jatamansi", "hindi": "जटामांसी", "parts": "Rhizome", "traditional_category": "Manasadoshahara"},
    "amla": {"common_name": "Amla (Indian Gooseberry)", "botanical_name": "Phyllanthus emblica", "hindi": "आंवला", "parts": "Fruit", "traditional_category": "Rasayana"},
    "amalaki": {"common_name": "Amalaki", "botanical_name": "Phyllanthus emblica", "hindi": "आमलकी", "parts": "Fruit", "traditional_category": "Rasayana"},
    "turmeric": {"common_name": "Turmeric / Haridra", "botanical_name": "Curcuma longa", "hindi": "हल्दी", "parts": "Rhizome", "traditional_category": "Lekhaniya / Vranaropana"},
    "haldi": {"common_name": "Haridra (Turmeric)", "botanical_name": "Curcuma longa", "hindi": "हल्दी", "parts": "Rhizome", "traditional_category": "Lekhaniya"},
    "haridra": {"common_name": "Haridra", "botanical_name": "Curcuma longa", "hindi": "हरिद्रा", "parts": "Rhizome", "traditional_category": "Lekhaniya"},
    "neem": {"common_name": "Neem", "botanical_name": "Azadirachta indica", "hindi": "नीम", "parts": "Leaves / Bark", "traditional_category": "Kandughna / Tikta"},
    "giloy": {"common_name": "Giloy (Guduchi)", "botanical_name": "Tinospora cordifolia", "hindi": "गिलोय", "parts": "Stem", "traditional_category": "Jvarahara / Rasayana"},
    "guduchi": {"common_name": "Guduchi", "botanical_name": "Tinospora cordifolia", "hindi": "गुडूची", "parts": "Stem", "traditional_category": "Rasayana"},
    "shatavari": {"common_name": "Shatavari", "botanical_name": "Asparagus racemosus", "hindi": "शतावरी", "parts": "Root", "traditional_category": "Stanyajanana / Rasayana"},
    "triphala": {"common_name": "Triphala", "botanical_name": "Terminalia chebula + T. bellirica + Phyllanthus emblica", "hindi": "त्रिफला", "parts": "Fruit blend", "traditional_category": "Deepana / Pachana"},
    "guggulu": {"common_name": "Guggulu", "botanical_name": "Commiphora mukul", "hindi": "गुग्गुल", "parts": "Exudate", "traditional_category": "Medohara"},
    "guggul": {"common_name": "Guggul", "botanical_name": "Commiphora mukul", "hindi": "गुग्गुल", "parts": "Exudate", "traditional_category": "Medohara"},
    "mulethi": {"common_name": "Mulethi (Licorice)", "botanical_name": "Glycyrrhiza glabra", "hindi": "मुलेठी", "parts": "Root", "traditional_category": "Kanthya / Rasayana"},
    "yashtimadhu": {"common_name": "Yashtimadhu", "botanical_name": "Glycyrrhiza glabra", "hindi": "यष्टिमधु", "parts": "Root", "traditional_category": "Kanthya"},
    "licorice": {"common_name": "Licorice (Yashtimadhu)", "botanical_name": "Glycyrrhiza glabra", "hindi": "मुलेठी", "parts": "Root", "traditional_category": "Kanthya"},
    "ginger": {"common_name": "Ginger / Shunthi", "botanical_name": "Zingiber officinale", "hindi": "अदरक / सोंठ", "parts": "Rhizome", "traditional_category": "Deepana"},
    "shunthi": {"common_name": "Shunthi (Dry Ginger)", "botanical_name": "Zingiber officinale", "hindi": "सोंठ", "parts": "Dry Rhizome", "traditional_category": "Deepana"},
    "black pepper": {"common_name": "Maricha (Black Pepper)", "botanical_name": "Piper nigrum", "hindi": "काली मिर्च", "parts": "Fruit", "traditional_category": "Pramathi"},
    "maricha": {"common_name": "Maricha", "botanical_name": "Piper nigrum", "hindi": "मरिच", "parts": "Fruit", "traditional_category": "Deepana"},
    "pippali": {"common_name": "Pippali (Long Pepper)", "botanical_name": "Piper longum", "hindi": "पिप्पली", "parts": "Fruit", "traditional_category": "Kaphahara"},
    "cardamom": {"common_name": "Ela (Cardamom)", "botanical_name": "Elettaria cardamomum", "hindi": "इलायची", "parts": "Seeds", "traditional_category": "Hridya"},
    "ela": {"common_name": "Ela", "botanical_name": "Elettaria cardamomum", "hindi": "एला", "parts": "Seeds", "traditional_category": "Hridya"},
    "cinnamon": {"common_name": "Twak (Cinnamon)", "botanical_name": "Cinnamomum verum", "hindi": "दालचीनी", "parts": "Bark", "traditional_category": "Dipana"},
    "dalchini": {"common_name": "Dalchini", "botanical_name": "Cinnamomum verum", "hindi": "दालचीनी", "parts": "Bark", "traditional_category": "Dipana"},
    "safed musli": {"common_name": "Safed Musli", "botanical_name": "Chlorophytum borivilianum", "hindi": "सफेद मूसली", "parts": "Root", "traditional_category": "Vrishya"},
    "gotu kola": {"common_name": "Gotu Kola (Mandukaparni)", "botanical_name": "Centella asiatica", "hindi": "मंडूकपर्णी", "parts": "Leaves", "traditional_category": "Medhya"},
    "mandukaparni": {"common_name": "Mandukaparni", "botanical_name": "Centella asiatica", "hindi": "मंडूकपर्णी", "parts": "Whole plant", "traditional_category": "Medhya"},
    "arjuna": {"common_name": "Arjuna", "botanical_name": "Terminalia arjuna", "hindi": "अर्जुन", "parts": "Bark", "traditional_category": "Hridya"},
    "manjistha": {"common_name": "Manjistha", "botanical_name": "Rubia cordifolia", "hindi": "मंजिष्ठा", "parts": "Stem / Root", "traditional_category": "Raktashodhaka"},
    "haritaki": {"common_name": "Haritaki", "botanical_name": "Terminalia chebula", "hindi": "हरड़", "parts": "Fruit", "traditional_category": "Rasayana"},
    "bibhitaki": {"common_name": "Bibhitaki", "botanical_name": "Terminalia bellirica", "hindi": "बहेड़ा", "parts": "Fruit", "traditional_category": "Bhedana"},
}

FORM_KEYWORDS = {
    "powder": "Powder / Churna",
    "churna": "Powder / Churna",
    "churn": "Powder / Churna",
    "tablet": "Tablet / Vati",
    "vati": "Tablet / Vati",
    "gutika": "Tablet / Vati",
    "capsule": "Capsule",
    "oil": "Oil / Taila",
    "taila": "Oil / Taila",
    "tailam": "Oil / Taila",
    "tel": "Oil / Taila",
    "drink": "Liquid / Beverage",
    "beverage": "Liquid / Beverage",
    "tea": "Tea / Decoction",
    "decoction": "Tea / Decoction",
    "kwath": "Tea / Decoction",
    "kadha": "Tea / Decoction",
    "syrup": "Syrup / Asava-Arishta",
    "asava": "Syrup / Asava-Arishta",
    "arishta": "Syrup / Asava-Arishta",
    "cream": "Cream / Ointment",
    "ointment": "Cream / Ointment",
    "lepa": "Cream / Ointment",
    "gel": "Gel",
    "granules": "Granules",
    "ghrita": "Medicated Ghee / Ghrita",
    "ghee": "Medicated Ghee / Ghrita",
}

INTENDED_USE_KEYWORDS = {
    "stress": "Stress Relief & Relaxation",
    "relax": "Stress Relief & Relaxation",
    "anxiety": "Stress Relief & Relaxation",
    "tension": "Stress Relief & Relaxation",
    "mental": "Cognitive Health & Focus",
    "brain": "Cognitive Health & Focus",
    "memory": "Cognitive Health & Focus",
    "focus": "Cognitive Health & Focus",
    "cogniti": "Cognitive Health & Focus",
    "medhya": "Cognitive Health & Focus",
    "sleep": "Sleep & Calming Support",
    "insomnia": "Sleep & Calming Support",
    "nidra": "Sleep & Calming Support",
    "digestion": "Digestive Health & Gut Support",
    "digest": "Digestive Health & Gut Support",
    "gut": "Digestive Health & Gut Support",
    "pachan": "Digestive Health & Gut Support",
    "acidity": "Digestive Health & Gut Support",
    "immune": "Immunity & Defense",
    "immunity": "Immunity & Defense",
    "rasayana": "General Wellness & Longevity",
    "wellness": "General Wellness & Longevity",
    "vitality": "Energy & Vitality",
    "energy": "Energy & Vitality",
    "stamina": "Energy & Vitality",
    "balya": "Energy & Vitality",
    "skin": "Skin & Beauty Care",
    "glow": "Skin & Beauty Care",
    "beauty": "Skin & Beauty Care",
    "hair": "Hair & Scalp Health",
    "joint": "Joint Health & Mobility",
    "pain": "Joint & Muscle Comfort",
    "inflammation": "Anti-inflammatory Support",
    "detox": "Detoxification & Purification",
    "shodhana": "Detoxification & Purification",
}

PROCESS_KEYWORDS = {
    "extract": "Standardized Extraction",
    "extraction": "Standardized Extraction",
    "hplc": "HPLC-Verified Standardized Extraction",
    "standardized": "Standardized Extraction",
    "powder": "Powdering & Micronizing",
    "grind": "Fine Grinding / Pulverization",
    "crush": "Crushing & Milling",
    "blend": "Dry Blending & Mixing",
    "mix": "Formulation Mixing",
    "ferment": "Classical Fermentation (Sandhana)",
    "decoct": "Aqueous Decoction (Kwatha Vidhi)",
    "boil": "Thermal Processing / Decoction",
    "heat": "Thermal Processing / Snehapaka",
    "oil process": "Medicated Oil Processing (Taila Paka)",
    "gmp": "GMP-Certified Facility Processing",
}

JURISDICTION_KEYWORDS = {
    "india": "IN",
    "bharat": "IN",
    "hindustan": "IN",
    "us": "US",
    "usa": "US",
    "united states": "US",
    "america": "US",
    "germany": "DE",
    "deutschland": "DE",
    "eu": "EU",
    "europe": "EU",
    "uk": "GB",
    "britain": "GB",
    "japan": "JP",
    "australia": "AU",
}


def _get_gemini_api_key() -> Optional[str]:
    """Check for Gemini / Google API key in environment variables."""
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "AYURINTEL_GEMINI_API_KEY"):
        val = os.getenv(key)
        if val and val.strip():
            return val.strip()
    return None


# ---------------------------------------------------------------------------
# Gemini API Normalizer
# ---------------------------------------------------------------------------

def _normalize_with_gemini(raw_text: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Invoke Google Gemini REST API to normalize natural language product description."""
    system_prompt = (
        "You are an expert Ayurvedic and botanical pharmacologist. "
        "Extract structured Product Passport attributes from the user text without inventing facts. "
        "Respond ONLY with valid JSON in this structure: "
        "{\"product_name\": \"string or null\", \"product_type\": \"string\", \"form\": \"string\", "
        "\"ingredients\": [{\"name\": \"Common\", \"botanical\": \"Latin\", \"quantity\": \"string or null\"}], "
        "\"intended_use\": [\"string\"], \"claims\": [\"string\"], \"process\": \"string or null\", "
        "\"jurisdictions\": [\"IN\", \"US\", \"DE\"], \"confidence\": \"HIGH|MEDIUM|LOW\", \"uncertainties\": []}"
    )

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": system_prompt},
                    {"text": f"User Input:\n{raw_text}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidate = res_data.get("candidates", [{}])[0]
            content_part = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
            if content_part:
                cleaned = content_part.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                parsed = json.loads(cleaned.strip())
                parsed["normalized_by"] = "gemini_api"
                return parsed
    except Exception as e:
        logger.warning("Gemini normalization failed or timed out: %s. Falling back to local rules.", e)
        return None


# ---------------------------------------------------------------------------
# Deterministic Ayurvedic & Botanical Rule Normalizer (Fallback)
# ---------------------------------------------------------------------------

def _normalize_deterministic(
    raw_text: str,
    explicit_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic, high-accuracy Ayurvedic normalizer that never invents data."""
    explicit = explicit_data or {}
    text_lower = (raw_text or "").lower()

    # 1. Product Name
    product_name = explicit.get("name") or None
    if not product_name and raw_text:
        match = re.search(r'(?:called|name is|naam hai|named|product\s+is)\s+["\']?([^,"\'.\n]+)["\']?', raw_text, re.IGNORECASE)
        if match:
            product_name = match.group(1).strip()
        else:
            first_words = raw_text.split()[:4]
            if first_words and any(w[0].isupper() for w in first_words if w):
                product_name = " ".join(first_words).strip(",. ")

    # 2. Ingredients Identification
    identified_ingredients: List[Dict[str, Any]] = []
    seen_botanicals = set()

    # First check explicit ingredients passed from UI
    if "ingredients" in explicit and isinstance(explicit["ingredients"], list):
        for item in explicit["ingredients"]:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
                botanical = item.get("botanical", "").strip()
                qty = item.get("quantity")
            elif isinstance(item, str):
                name = item.strip()
                botanical = ""
                qty = None
            else:
                continue

            if not name:
                continue

            name_key = name.lower()
            matched_info = BOTANICAL_KNOWLEDGE_BASE.get(name_key)
            if not botanical and matched_info:
                botanical = matched_info["botanical_name"]

            key = (botanical or name).lower()
            if key not in seen_botanicals:
                seen_botanicals.add(key)
                identified_ingredients.append({
                    "name": matched_info["common_name"] if matched_info else name,
                    "botanical": botanical or (matched_info["botanical_name"] if matched_info else ""),
                    "quantity": qty,
                    "status": "IDENTIFIED" if (botanical or matched_info) else "USER_PROVIDED"
                })

    # Also extract ingredients mentioned in free text / description
    for key, info in BOTANICAL_KNOWLEDGE_BASE.items():
        pattern = r'\b' + re.escape(key) + r'\b'
        if re.search(pattern, text_lower) or key in text_lower:
            bot_key = info["botanical_name"].lower()
            if bot_key not in seen_botanicals:
                seen_botanicals.add(bot_key)
                qty_match = re.search(
                    r'(?:(\d+\s*(?:mg|gm|g|ml|%))\s+' + re.escape(key) + r'|' + re.escape(key) + r'\s+(\d+\s*(?:mg|gm|g|ml|%)))',
                    text_lower
                )
                qty = (qty_match.group(1) or qty_match.group(2)) if qty_match else None
                identified_ingredients.append({
                    "name": info["common_name"],
                    "botanical": info["botanical_name"],
                    "quantity": qty,
                    "traditional_category": info.get("traditional_category"),
                    "status": "IDENTIFIED"
                })

    # 3. Dosage Form
    form = explicit.get("form") or None
    if not form:
        for kw, form_label in FORM_KEYWORDS.items():
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                form = form_label
                break
    if not form:
        form = "Capsule / Formulation (Unspecified)"

    # 4. Intended Uses
    intended_uses = list(explicit.get("intended_use_list") or [])
    if explicit.get("intended_use") and explicit["intended_use"] not in intended_uses:
        intended_uses.append(explicit["intended_use"])

    for kw, benefit in INTENDED_USE_KEYWORDS.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            if benefit not in intended_uses:
                intended_uses.append(benefit)

    # 5. Process & Manufacturing
    process = explicit.get("process") or None
    detected_processes = []
    for kw, proc_label in PROCESS_KEYWORDS.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            if proc_label not in detected_processes:
                detected_processes.append(proc_label)
    if not process and detected_processes:
        process = ", ".join(detected_processes)

    # 6. Claims
    claims = list(explicit.get("claims") or [])
    if not claims and intended_uses:
        for use in intended_uses[:3]:
            claims.append(f"Supports {use.lower()}")

    # 7. Jurisdictions
    jurisdictions = list(explicit.get("jurisdictions") or [])
    for kw, code in JURISDICTION_KEYWORDS.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            if code not in jurisdictions:
                jurisdictions.append(code)
    if not jurisdictions:
        jurisdictions = ["IN"]

    # 8. Product Type
    product_type = explicit.get("product_type") or "Ayurvedic & Herbal Formulation"

    return {
        "product_name": product_name or "New Ayurvedic Product",
        "product_type": product_type,
        "form": form,
        "ingredients": identified_ingredients,
        "intended_use": intended_uses or ["General Wellness"],
        "claims": claims,
        "process": process or "Standard Ayurvedic / Herbal preparation",
        "jurisdictions": jurisdictions,
        "original_text": raw_text,
        "confidence": "HIGH" if identified_ingredients else "MEDIUM",
        "uncertainties": [
            "Specific ingredient quantities not fully specified"
        ] if any(not ing.get("quantity") for ing in identified_ingredients) else [],
        "normalized_by": "local_botanical_rule_engine"
    }


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def normalize_product_passport(
    raw_text: str = "",
    explicit_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize user input using Gemini if available, with robust deterministic fallback."""
    api_key = _get_gemini_api_key()
    combined_text = (raw_text or "").strip()
    
    if explicit_data:
        parts = []
        if combined_text:
            parts.append(f"Description: {combined_text}")
        if explicit_data.get("name"):
            parts.append(f"Product Name: {explicit_data['name']}")
        if explicit_data.get("product_type"):
            parts.append(f"Category: {explicit_data['product_type']}")
        if explicit_data.get("ingredients_text"):
            parts.append(f"Ingredients: {explicit_data['ingredients_text']}")
        if explicit_data.get("process"):
            parts.append(f"Process: {explicit_data['process']}")
        if explicit_data.get("claims_text"):
            parts.append(f"Claims: {explicit_data['claims_text']}")
        if explicit_data.get("notes"):
            parts.append(f"Notes: {explicit_data['notes']}")
        combined_text = "\n".join(parts)

    if api_key and combined_text:
        ai_result = _normalize_with_gemini(combined_text, api_key)
        if ai_result:
            if explicit_data:
                if explicit_data.get("name"):
                    ai_result["product_name"] = explicit_data["name"]
                if explicit_data.get("jurisdictions"):
                    ai_result["jurisdictions"] = explicit_data["jurisdictions"]
            ai_result["original_text"] = raw_text
            return ai_result

    return _normalize_deterministic(combined_text, explicit_data)
