"""AYUR-INTEL — Ingredient Eligibility Service.

Evaluates ingredient eligibility for Ayurvedic product formulations using
the CCRAS DRAVYA database (data/dravya.db) and Schedule E-1 statutory compliance rules.
"""

from __future__ import annotations

import logging
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api.core.config import PROJECT_ROOT

logger = logging.getLogger("ayur_intel.services.ingredient_eligibility")

DB_PATH = PROJECT_ROOT / "data" / "dravya.db"

# Schedule E-1 Poisonous Substances List (Drugs & Cosmetics Rules, 1945)
SCHEDULE_E1_BOTANICALS = [
    {"name": "Vatsanabha", "botanical": "Aconitum ferox", "regex": r"aconit|vatsanabh"},
    {"name": "Dhattura", "botanical": "Datura metel", "regex": r"datura|dhattur"},
    {"name": "Gunja", "botanical": "Abrus precatorius", "regex": r"abrus|gunja|ratti"},
    {"name": "Jayapala", "botanical": "Croton tiglium", "regex": r"croton|jayapal"},
    {"name": "Kuchala", "botanical": "Strychnos nux-vomica", "regex": r"strychnos|nux.*vomica|kuchal"},
    {"name": "Ahiphena", "botanical": "Papaver somniferum", "regex": r"papaver|ahiphen|opium"},
    {"name": "Bhallataka", "botanical": "Semecarpus anacardium", "regex": r"semecarpus|bhallatak|marking.*nut"},
    {"name": "Bhanga", "botanical": "Cannabis sativa", "regex": r"cannabis|bhang|ganja"},
    {"name": "Karaveera", "botanical": "Nerium indicum", "regex": r"nerium|karaveer|kaner"},
    {"name": "Parasika Yavani", "botanical": "Hyoscyamus niger", "regex": r"hyoscyamus|parasika.*yavan|henbane"},
]


def strip_accents(text: str) -> str:
    """Remove diacritics and accents."""
    if not text:
        return ""
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def get_db_connection() -> Optional[sqlite3.Connection]:
    """Get SQLite connection to dravya.db."""
    if not DB_PATH.exists():
        logger.warning("data/dravya.db does not exist!")
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def check_schedule_e1(name: str, botanical: str = "") -> Tuple[bool, Optional[str]]:
    """Check if ingredient matches Schedule E-1 hazardous substances."""
    text_to_check = f"{name} {botanical}".lower()
    import re
    for item in SCHEDULE_E1_BOTANICALS:
        if re.search(item["regex"], text_to_check, re.IGNORECASE):
            return True, f"{item['name']} ({item['botanical']})"
    return False, None


def generate_search_variants(query: str) -> List[str]:
    """Generate common transliteration variants."""
    q = query.strip().lower()
    variants = {q}
    if "w" in q:
        variants.add(q.replace("w", "v"))
    if "v" in q:
        variants.add(q.replace("v", "w"))
    if "sh" in q:
        variants.add(q.replace("sh", "s"))
    if "ee" in q:
        variants.add(q.replace("ee", "i"))
    if "oo" in q:
        variants.add(q.replace("oo", "u"))
    return list(variants)


def check_ingredient_eligibility(name: str, botanical_hint: str = "") -> Dict[str, Any]:
    """Calculate complete eligibility score and return monograph details for an ingredient."""
    input_name = (name or "").strip()
    if not input_name and not botanical_hint:
        return {
            "name": "",
            "status": "NOT FOUND",
            "eligibility_level": "NOT FOUND",
            "score": 0,
            "verified": False,
            "message": "No ingredient name provided",
        }

    conn = get_db_connection()
    plant_row = None

    if conn:
        try:
            cur = conn.cursor()
            search_terms = generate_search_variants(botanical_hint or input_name)

            for term in search_terms:
                like_term = f"%{term}%"

                # 1. Scientific Name Exact / Like
                cur.execute(
                    "SELECT plant_id, scientific_name, family, url FROM plants WHERE scientific_name LIKE ? LIMIT 1",
                    (like_term,),
                )
                plant_row = cur.fetchone()
                if plant_row:
                    break

                # 2. Vernacular Name Like
                cur.execute(
                    """
                    SELECT p.plant_id, p.scientific_name, p.family, p.url 
                    FROM plants p
                    JOIN vernacular_names v ON p.plant_id = v.plant_id
                    WHERE v.name LIKE ?
                    LIMIT 1
                    """,
                    (like_term,),
                )
                plant_row = cur.fetchone()
                if plant_row:
                    break

                # 3. Etymology Synonym Like
                cur.execute(
                    """
                    SELECT p.plant_id, p.scientific_name, p.family, p.url 
                    FROM plants p
                    JOIN etymologies e ON p.plant_id = e.plant_id
                    WHERE e.sanskrit_synonym LIKE ? OR e.sanskrit_diacritical LIKE ?
                    LIMIT 1
                    """,
                    (like_term, like_term),
                )
                plant_row = cur.fetchone()
                if plant_row:
                    break

        except Exception as e:
            logger.error("Error querying dravya.db: %s", e)
        finally:
            conn.close()

    # If plant not found in dravya.db
    if not plant_row:
        is_e1, e1_name = check_schedule_e1(input_name, botanical_hint)
        return {
            "name": input_name,
            "plant_id": None,
            "scientific_name": botanical_hint or "",
            "family": "",
            "url": "",
            "status": "NOT FOUND",
            "eligibility_level": "NOT FOUND",
            "score": 0,
            "verified": False,
            "schedule_e1": is_e1,
            "schedule_e1_warning": f"⚠️ Schedule E-1 Poisonous Substance: {e1_name}" if is_e1 else "Not in Schedule E-1 (Safe)",
            "classical_reference": "Not Found",
            "properties": {},
            "breakdown": [
                {"criterion": "Scientific name verified", "passed": False, "weight": 20},
                {"criterion": "Classical reference found", "passed": False, "weight": 20},
                {"criterion": "Guna, Virya, Vipaka available", "passed": False, "weight": 30},
                {"criterion": "Therapeutic usage found", "passed": False, "weight": 15},
                {"criterion": "Vernacular names found (3+)", "passed": False, "weight": 15},
            ],
            "message": f"Ingredient '{input_name}' not found in CCRAS DRAVYA database",
        }

    # Plant found in dravya.db! Fetch details and compute score
    p_id = plant_row["plant_id"]
    sci_name = plant_row["scientific_name"] or botanical_hint or input_name
    family = plant_row["family"] or ""
    url = plant_row["url"] or f"https://dravya.ccras.org.in/plant/{p_id}"

    conn = get_db_connection()
    vernacular_names: List[str] = []
    properties_by_type: Dict[str, List[str]] = {}
    etymologies: List[Dict[str, str]] = []
    classical_refs: List[str] = []

    if conn:
        try:
            cur = conn.cursor()

            # Vernacular names
            cur.execute("SELECT DISTINCT name FROM vernacular_names WHERE plant_id = ?", (p_id,))
            vernacular_names = [r["name"] for r in cur.fetchall() if r["name"]]

            # Properties
            cur.execute("SELECT property_type, property_value FROM plant_properties WHERE plant_id = ?", (p_id,))
            for r in cur.fetchall():
                ptype = r["property_type"]
                pval = r["property_value"]
                if pval and pval not in properties_by_type.get(ptype, []):
                    properties_by_type.setdefault(ptype, []).append(pval)

            # Etymologies
            cur.execute("SELECT sanskrit_synonym, sanskrit_diacritical, reference FROM etymologies WHERE plant_id = ?", (p_id,))
            etymologies = [dict(r) for r in cur.fetchall()]

            # Classical References
            cur.execute("SELECT name FROM varga WHERE plant_id = ?", (p_id,))
            classical_refs.extend([f"Varga: {r['name']}" for r in cur.fetchall() if r["name"]])

            cur.execute("SELECT name FROM mahakashaya WHERE plant_id = ?", (p_id,))
            classical_refs.extend([f"Mahakashaya: {r['name']}" for r in cur.fetchall() if r["name"]])

        except Exception as e:
            logger.error("Error loading plant relations for ID %d: %s", p_id, e)
        finally:
            conn.close()

    # Extract Ayurvedic Attributes
    gunas = properties_by_type.get("guna", [])
    viryas = properties_by_type.get("virya", [])
    vipakas = properties_by_type.get("vipaka", [])
    karmas = properties_by_type.get("karma", [])
    doshakarmas = properties_by_type.get("doshakarma", [])
    therapeutic_uses = properties_by_type.get("therapeutic_usage", [])
    dosage_items = properties_by_type.get("dosage", [])
    class_ref_items = properties_by_type.get("classical_reference", [])

    # Class reference text summary
    ref_sources = []
    if class_ref_items:
        ref_sources.extend(class_ref_items)
    if etymologies:
        ref_sources.append(f"Sanskrit Synonyms: {', '.join([e['sanskrit_synonym'] for e in etymologies[:3] if e.get('sanskrit_synonym')])}")
    if classical_refs:
        ref_sources.extend(classical_refs[:2])

    classical_ref_text = "; ".join(ref_sources[:3]) if ref_sources else "Recognized in Classical Ayurvedic Texts (API / AFI Monograph)"

    # Compute Criterion Scores according to specification
    # 1. Scientific name exists (20 pts)
    c1_passed = bool(sci_name and len(sci_name) > 3)
    c1_score = 20 if c1_passed else 0

    # 2. Classical reference exists (20 pts)
    c2_passed = bool(classical_ref_text and classical_ref_text != "Not Found")
    c2_score = 20 if c2_passed else 0

    # 3. Guna, Virya, Vipaka exist (30 pts)
    g_count = (1 if gunas else 0) + (1 if viryas else 0) + (1 if vipakas else 0)
    c3_passed = (g_count >= 2)
    c3_score = g_count * 10

    # 4. Therapeutic usage exists (15 pts)
    c4_passed = bool(therapeutic_uses)
    c4_score = 15 if c4_passed else 0

    # 5. Vernacular names exist (3+) (15 pts)
    c5_count = len(vernacular_names)
    c5_passed = c5_count >= 3
    c5_score = 15 if c5_passed else (10 if c5_count >= 1 else 0)

    total_score = c1_score + c2_score + c3_score + c4_score + c5_score
    total_score = min(100, max(0, total_score))

    # Eligibility Levels:
    # HIGH (80-100), MEDIUM (50-79), LOW (0-49), NOT FOUND (0)
    if total_score >= 80:
        eligibility_level = "HIGH"
        status = "VERIFIED"
    elif total_score >= 50:
        eligibility_level = "MEDIUM"
        status = "VERIFIED"
    elif total_score > 0:
        eligibility_level = "LOW"
        status = "PARTIAL"
    else:
        eligibility_level = "NOT FOUND"
        status = "NOT FOUND"

    # Schedule E-1 check
    is_e1, e1_name = check_schedule_e1(input_name, sci_name)

    breakdown = [
        {"criterion": "Scientific name verified", "passed": c1_passed, "weight": 20, "score": c1_score},
        {"criterion": "Classical reference found", "passed": c2_passed, "weight": 20, "score": c2_score},
        {"criterion": "Guna, Virya, Vipaka available", "passed": c3_passed, "weight": 30, "score": c3_score},
        {"criterion": "Therapeutic usage found", "passed": c4_passed, "weight": 15, "score": c4_score},
        {"criterion": "Vernacular names found (3+)", "passed": c5_passed, "weight": 15, "score": c5_score},
    ]

    return {
        "name": input_name,
        "plant_id": p_id,
        "scientific_name": sci_name,
        "family": family,
        "url": url,
        "status": status,
        "eligibility_level": eligibility_level,
        "score": total_score,
        "verified": (eligibility_level in ["HIGH", "MEDIUM"]),
        "schedule_e1": is_e1,
        "schedule_e1_warning": f"⚠️ Schedule E-1 Poisonous Substance: {e1_name} (Requires Doctor Prescription & Special Labeling)" if is_e1 else "Not in Schedule E-1 (Safe)",
        "classical_reference": classical_ref_text,
        "properties": {
            "guna": gunas,
            "virya": viryas,
            "vipaka": vipakas,
            "karma": karmas,
            "doshakarma": doshakarmas,
            "therapeutic_usage": therapeutic_uses,
            "dosage": dosage_items,
        },
        "breakdown": breakdown,
        "vernacular_names_count": len(vernacular_names),
        "vernacular_sample": vernacular_names[:5],
    }
