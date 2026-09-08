import os
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("ayur_intel.ai_normalization")

# Botanical knowledge base (fallback)
BOTANICAL_KNOWLEDGE_BASE = {
    "ashwagandha": "Withania somnifera",
    "brahmi": "Bacopa monnieri",
    "tulsi": "Ocimum sanctum",
    "neem": "Azadirachta indica",
    "haldi": "Curcuma longa",
    "turmeric": "Curcuma longa",
    "amla": "Phyllanthus emblica",
    "giloy": "Tinospora cordifolia",
    "shatavari": "Asparagus racemosus",
    "shankhpushpi": "Convolvulus pluricaulis",
    "jatamansi": "Nardostachys jatamansi",
    "mulethi": "Glycyrrhiza glabra",
    "triphala": "Triphala",
    "haritaki": "Terminalia chebula",
    "bibhitaki": "Terminalia bellirica",
}

def normalize_product_passport(raw_text: str, explicit_data: Dict = None) -> Dict:
    """Normalize product description using Gemini AI or fallback."""
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("AYURINTEL_GEMINI_API_KEY")
    
    if api_key:
        try:
            return _normalize_with_gemini(raw_text, explicit_data)
        except Exception as e:
            logger.error(f"Gemini failed: {e}")
            return _normalize_with_fallback(raw_text, explicit_data)
    
    return _normalize_with_fallback(raw_text, explicit_data)

def _normalize_with_gemini(raw_text: str, explicit_data: Dict) -> Dict:
    """Use Gemini AI for normalization."""
    import google.generativeai as genai
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("AYURINTEL_GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Analyze this Ayurvedic product description (which may be written in Hindi, Hinglish, English, or mixed language) and extract structured information.
    
    CRITICAL REQUIREMENT:
    You MUST translate the description into fluent, professional English. The 'normalized_description' MUST ALWAYS be written in 100% proper English, translating all Hindi/Hinglish/regional phrases accurately. DO NOT return Hindi or Hinglish in 'normalized_description'.
    Example:
    Input: "Isme sar dard ki problem ko solve krah" -> normalized_description: "This formulation helps relieve headaches and soothing head tension."
    Input: "Yeh ek Ayurvedic herbal capsule formulation hai jisme Ashwagandha aur Brahmi ko use kiya gaya hai for mental calmness" -> normalized_description: "A standardized Ayurvedic capsule formulation enriched with Ashwagandha (Withania somnifera) and Brahmi (Bacopa monnieri), formulated to promote mental calmness and stress reduction."
    
    DESCRIPTION: "{raw_text}"
    
    Extract and structure:
    1. Ingredients with botanical (Latin) names if known (return empty list [] if no ingredients are mentioned)
    2. Dosage form (Capsules, Powder / Churna, Syrup / Asava, Tablet / Vati, Oil / Taila, etc., or null if not mentioned)
    3. Intended use / health indications (e.g. Headache & Migraine Relief, Stress Relief, Cognitive Health, Immunity, Digestion)
    4. Preparation process (if mentioned, else null)
    5. Proposed benefit claims
    6. normalized_description: Fluent, professional English translation and structured description.
    7. product_suggestions: 2-3 innovative Ayurvedic product or formulation ideas based ONLY on the detected ingredients (return empty list [] if no ingredients are mentioned).
    
    RULES:
    - Extract accurately without inventing unmentioned herbs.
    - If no ingredients are mentioned, return [] for ingredients and [] for product_suggestions.
    - Return null for missing fields.
    - Return ONLY valid JSON.
    
    Output format:
    {{
      "product_name": "string or null",
      "normalized_description": "fluent English translation and summary",
      "ingredients": [
        {{"input_name": "string", "botanical_name": "string or null", "quantity": "string or null"}}
      ],
      "form": "string or null",
      "intended_use": ["string"] or null,
      "process": "string or null",
      "claims": ["string"] or null,
      "product_suggestions": ["string"],
      "confidence": {{
        "ingredients": "high/medium/low",
        "form": "high/medium/low",
        "intended_use": "high/medium/low"
      }}
    }}
    """
    
    response = model.generate_content(prompt)
    response_text = response.text.strip()
    
    # Extract JSON from markdown if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]
    
    result = json.loads(response_text)
    
    # Add botanical names if missing
    if "ingredients" in result and isinstance(result["ingredients"], list):
        for ing in result["ingredients"]:
            if isinstance(ing, dict) and not ing.get("botanical_name"):
                ing["botanical_name"] = _find_botanical_name(ing.get("input_name", ""))
    
    # Ensure normalized_description is in English
    if not result.get("normalized_description"):
        result["normalized_description"] = _generate_english_description(result, raw_text)
    if result.get("product_suggestions") is None:
        result["product_suggestions"] = _generate_suggestions(result.get("ingredients", []))
    
    return result

def _normalize_with_fallback(raw_text: str, explicit_data: Dict) -> Dict:
    """Dictionary-based fallback normalization."""
    result = {
        "product_name": None,
        "normalized_description": "",
        "ingredients": [],
        "form": None,
        "intended_use": [],
        "process": None,
        "claims": [],
        "product_suggestions": [],
        "confidence": {
            "ingredients": "low",
            "form": "low",
            "intended_use": "low"
        }
    }
    
    text_lower = raw_text.lower()
    
    # Extract ingredients from text
    for common_name, botanical in BOTANICAL_KNOWLEDGE_BASE.items():
        if common_name in text_lower:
            result["ingredients"].append({
                "input_name": common_name.capitalize(),
                "botanical_name": botanical,
                "quantity": None
            })
    
    # Detect dosage form
    forms = [
        ("capsule", "Capsule Formulation"),
        ("churna", "Powder / Churna"),
        ("powder", "Powder / Churna"),
        ("tablet", "Tablet / Vati"),
        ("vati", "Tablet / Vati"),
        ("syrup", "Syrup / Asava-Arishta"),
        ("liquid", "Liquid Extract"),
        ("oil", "Ayurvedic Medicated Oil (Taila)"),
        ("tel", "Ayurvedic Medicated Oil (Taila)"),
        ("cream", "Herbal Topical Cream"),
        ("tea", "Herbal Infusion / Kwatha")
    ]
    for pattern, label in forms:
        if pattern in text_lower:
            result["form"] = label
            result["confidence"]["form"] = "medium"
            break
    
    # Detect intended use & symptoms (including Hindi/Hinglish)
    use_patterns = [
        ("sar dard", "Headache & Migraine Relief"),
        ("sir dard", "Headache & Migraine Relief"),
        ("headache", "Headache & Migraine Relief"),
        ("migraine", "Headache & Migraine Relief"),
        ("stress", "Stress Relief & Relaxation"),
        ("tanaav", "Stress Relief & Relaxation"),
        ("chinta", "Stress Relief & Relaxation"),
        ("anxiety", "Stress Relief & Relaxation"),
        ("sleep", "Sleep & Calming Support"),
        ("neend", "Sleep & Calming Support"),
        ("memory", "Cognitive Health & Focus"),
        ("brain", "Cognitive Health & Focus"),
        ("dimag", "Cognitive Health & Focus"),
        ("immunity", "Immunity & Defense"),
        ("digestion", "Digestive Health & Gut Support"),
        ("pachan", "Digestive Health & Gut Support"),
        ("pet dard", "Digestive Health & Gut Support"),
        ("gas", "Digestive Health & Gut Support"),
        ("kabz", "Digestive Health & Gut Support"),
        ("skin", "Skin & Beauty Care"),
        ("twacha", "Skin & Beauty Care"),
        ("energy", "Energy & Vitality"),
        ("rasayana", "General Wellness & Longevity (Rasayana)"),
        ("joint", "Joint & Muscle Comfort"),
        ("jodo ka dard", "Joint & Muscle Comfort"),
        ("cough", "Respiratory & Throat Health"),
        ("khasi", "Respiratory & Throat Health"),
        ("sardi", "Respiratory & Throat Health")
    ]
    found_uses = []
    for pattern, label in use_patterns:
        if pattern in text_lower and label not in found_uses:
            found_uses.append(label)
    if found_uses:
        result["intended_use"] = found_uses
        result["confidence"]["intended_use"] = "medium"
    
    # Detect claims
    if any(k in text_lower for k in ["sar dard", "sir dard", "headache", "migraine"]):
        result["claims"].append("Helps relieve headaches and soothing head tension")
    if "stress" in text_lower or "calm" in text_lower or "tanaav" in text_lower:
        result["claims"].append("Supports stress management & relaxation")
    if "memory" in text_lower or "focus" in text_lower or "brain" in text_lower or "dimag" in text_lower:
        result["claims"].append("Enhances cognitive function & mental clarity")
    if "immunity" in text_lower:
        result["claims"].append("Supports natural immune defense")
    if any(k in text_lower for k in ["digestion", "pachan", "pet dard", "gas", "kabz"]):
        result["claims"].append("Promotes healthy digestion and gut balance")
    
    if result["ingredients"]:
        result["confidence"]["ingredients"] = "medium"
    
    # Generate English normalized description
    result["normalized_description"] = _generate_english_description(result, raw_text)
    
    # Generate product suggestions based on ingredients
    result["product_suggestions"] = _generate_suggestions(result["ingredients"])
    
    return result

def _generate_english_description(data: Dict, original_text: str) -> str:
    """Generate structured, professional English product description."""
    ingredients = data.get("ingredients") or []
    ing_names = []
    for ing in ingredients:
        if isinstance(ing, dict):
            name = ing.get("input_name") or ing.get("name") or ""
            bot = ing.get("botanical_name") or ing.get("botanical") or ""
            if name and bot:
                ing_names.append(f"{name} ({bot})")
            elif name:
                ing_names.append(name)
        elif isinstance(ing, str) and ing.strip():
            ing_names.append(ing.strip())
    
    form = data.get("form") or "herbal formulation"
    uses = data.get("intended_use") or []
    
    if ing_names and uses:
        uses_str = ", ".join(uses)
        ings_str = ", ".join(ing_names)
        return f"A standardized Ayurvedic {form.lower()} enriched with {ings_str}, formulated to support {uses_str.lower()}."
    elif ing_names:
        ings_str = ", ".join(ing_names)
        return f"A classical Ayurvedic {form.lower()} containing active botanical extracts of {ings_str}."
    elif uses:
        uses_str = ", ".join(uses)
        return f"A classical Ayurvedic formulation developed to support {uses_str.lower()} and holistic balance."
    elif original_text:
        text_lower = original_text.lower()
        if any(k in text_lower for k in ["sar dard", "sir dard", "headache", "migraine"]):
            return "This formulation helps relieve headaches and provides soothing cranial comfort."
        if any(k in text_lower for k in ["pet", "pachan", "gas", "kabz", "digest"]):
            return "This formulation promotes healthy digestion and digestive wellness."
        if any(k in text_lower for k in ["stress", "tanaav", "calm", "relax"]):
            return "This formulation helps relieve stress and promotes mental calmness."
        return "A targeted Ayurvedic herbal formulation crafted for holistic therapeutic support and wellness."
    return "Standardized Ayurvedic herbal formulation."

def _generate_suggestions(ingredients: List) -> List[str]:
    """Generate smart Ayurvedic product suggestions strictly based on selected ingredients."""
    names = []
    for ing in ingredients:
        if isinstance(ing, dict):
            n = (ing.get("input_name") or ing.get("name") or "").strip()
            if n:
                names.append(n.capitalize())
        elif isinstance(ing, str) and ing.strip():
            names.append(ing.strip().capitalize())
    
    # If no ingredients exist, return ZERO default suggestions
    if not names:
        return []
    
    herb_combo = " & ".join(names[:2])
    suggestions = [
        f"{herb_combo} Wellness & Balance Formulation",
        f"{herb_combo} Daily Rasayana Supplement"
    ]
    if len(names) == 1:
        suggestions.append(f"Standardized {names[0]} Herbal Extract")
    else:
        suggestions.append(f"Traditional Polyherbal Blend ({herb_combo})")
            
    return suggestions[:3]

def _find_botanical_name(input_name: str) -> Optional[str]:
    """Find botanical name from knowledge base."""
    input_lower = input_name.lower().strip()
    
    for key, value in BOTANICAL_KNOWLEDGE_BASE.items():
        if key in input_lower or input_lower in key:
            return value
    
    return None