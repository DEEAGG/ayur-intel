"""AYUR-INTEL — DRAVYA Ingredient Search & Details API Routes.

Provides fast, comprehensive search and retrieval endpoints powered by the imported
DRAVYA database (data/dravya.db) covering 400 Ayurvedic medicinal plants.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, Query, Body

from api.core.config import PROJECT_ROOT
from api.services.ingredient_eligibility import check_ingredient_eligibility

logger = logging.getLogger("ayur_intel.routers.ingredients")

router = APIRouter(prefix="/api/ingredients", tags=["DRAVYA Ingredients"])

DB_PATH = PROJECT_ROOT / "data" / "dravya.db"


def strip_accents(text: str) -> str:
    """Strip accents and diacritical marks from text."""
    if not text:
        return ""
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def get_db_connection() -> sqlite3.Connection:
    """Get SQLite connection to dravya.db with dictionary row factory."""
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="DRAVYA database not initialized. Please run scripts/import_dravya_to_db.py",
        )
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/stats")
def get_ingredient_stats() -> Dict[str, Any]:
    """Return summary statistics of the DRAVYA database."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM plants")
        plant_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM vernacular_names")
        vernacular_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM plant_properties")
        property_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM etymologies")
        etymology_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM parts_used")
        parts_count = cur.fetchone()[0]

        return {
            "total_plants": plant_count,
            "total_vernacular_names": vernacular_count,
            "total_properties": property_count,
            "total_etymologies": etymology_count,
            "total_parts_used": parts_count,
            "source": "CCRAS DRAVYA Portal (https://dravya.ccras.org.in/)",
        }
    finally:
        conn.close()


@router.get("/eligibility/{name}")
def get_ingredient_eligibility(name: str) -> Dict[str, Any]:
    """Return complete ingredient eligibility analysis based on DRAVYA monograph data and Schedule E-1 checks."""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Ingredient name is required")
    return check_ingredient_eligibility(name.strip())


@router.get("/verify/{name}")
def verify_ingredient(name: str) -> Dict[str, Any]:
    """Quick verification check for an ingredient (returns high-level status & score)."""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Ingredient name is required")
    res = check_ingredient_eligibility(name.strip())
    return {
        "name": res["name"],
        "status": res["status"],
        "eligibility_level": res["eligibility_level"],
        "score": res["score"],
        "verified": res["verified"],
        "schedule_e1": res["schedule_e1"],
        "schedule_e1_warning": res.get("schedule_e1_warning"),
        "scientific_name": res.get("scientific_name"),
    }


@router.post("/batch-eligibility")
def get_batch_eligibility(ingredients: List[Any] = Body(...)) -> Dict[str, Any]:
    """Evaluate eligibility for a list of ingredients in a product case."""
    evaluations: List[Dict[str, Any]] = []
    verified_count = 0
    e1_count = 0

    for item in ingredients:
        if isinstance(item, dict):
            name = item.get("name") or item.get("input_name") or item.get("ingredient_name") or ""
            botanical = item.get("botanical") or item.get("botanical_name") or ""
        else:
            name = str(item).strip()
            botanical = ""

        if not name and not botanical:
            continue

        res = check_ingredient_eligibility(name, botanical)
        evaluations.append(res)
        if res.get("verified"):
            verified_count += 1
        if res.get("schedule_e1"):
            e1_count += 1

    total = len(evaluations)
    return {
        "total_ingredients": total,
        "verified_count": verified_count,
        "schedule_e1_count": e1_count,
        "is_all_verified": (verified_count == total and total > 0),
        "evaluations": evaluations,
    }


def generate_search_variants(query: str) -> List[str]:
    """Generate common Ayurvedic transliteration variants (e.g. w/v, sh/s)."""
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


@router.get("/search")
def search_ingredients(
    q: str = Query(..., min_length=1, description="Search query across scientific, common, vernacular names and properties"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
) -> Dict[str, Any]:
    """Search plants by scientific name, vernacular/common name, or Ayurvedic properties."""
    clean_q = q.strip()
    variants = generate_search_variants(clean_q)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        matched_ids: Dict[int, int] = {}

        for term in variants:
            like_term = f"%{term}%"
            cur.execute(
                "SELECT plant_id, scientific_name FROM plants WHERE scientific_name LIKE ?",
                (like_term,),
            )
            for row in cur.fetchall():
                pid = row["plant_id"]
                score = 100 if term == row["scientific_name"].lower() else 80
                matched_ids[pid] = max(matched_ids.get(pid, 0), score)

            cur.execute(
                "SELECT plant_id, name, language FROM vernacular_names WHERE name LIKE ?",
                (like_term,),
            )
            for row in cur.fetchall():
                pid = row["plant_id"]
                score = 70 if term == row["name"].lower() else 60
                matched_ids[pid] = max(matched_ids.get(pid, 0), score)

            cur.execute(
                """
                SELECT plant_id, sanskrit_synonym, sanskrit_diacritical, english_meaning 
                FROM etymologies 
                WHERE sanskrit_synonym LIKE ? 
                   OR sanskrit_diacritical LIKE ? 
                   OR english_meaning LIKE ?
                """,
                (like_term, like_term, like_term),
            )
            for row in cur.fetchall():
                pid = row["plant_id"]
                matched_ids[pid] = max(matched_ids.get(pid, 0), 50)

            cur.execute(
                "SELECT plant_id, property_value FROM plant_properties WHERE property_value LIKE ?",
                (like_term,),
            )
            for row in cur.fetchall():
                pid = row["plant_id"]
                matched_ids[pid] = max(matched_ids.get(pid, 0), 40)

        if not matched_ids:
            return {
                "query": q,
                "total_results": 0,
                "results": [],
            }

        sorted_pids = sorted(matched_ids.keys(), key=lambda x: matched_ids[x], reverse=True)[:limit]
        placeholders = ",".join("?" for _ in sorted_pids)
        cur.execute(
            f"SELECT plant_id, scientific_name, family, url FROM plants WHERE plant_id IN ({placeholders})",
            sorted_pids,
        )
        plants_by_id = {row["plant_id"]: row for row in cur.fetchall()}

        results: List[Dict[str, Any]] = []
        for pid in sorted_pids:
            plant_row = plants_by_id.get(pid)
            if not plant_row:
                continue

            cur.execute(
                "SELECT language, name FROM vernacular_names WHERE plant_id = ? ORDER BY language LIMIT 15",
                (pid,),
            )
            v_rows = cur.fetchall()
            vernacular: Dict[str, List[str]] = {}
            for v in v_rows:
                vernacular.setdefault(v["language"], []).append(v["name"])

            cur.execute(
                """
                SELECT property_type, property_value 
                FROM plant_properties 
                WHERE plant_id = ? 
                LIMIT 15
                """,
                (pid,),
            )
            prop_rows = cur.fetchall()
            properties: Dict[str, List[str]] = {}
            for pr in prop_rows:
                p_type = pr["property_type"]
                p_val = pr["property_value"]
                if p_val and p_val not in properties.get(p_type, []):
                    properties.setdefault(p_type, []).append(p_val)

            results.append({
                "plant_id": pid,
                "scientific_name": plant_row["scientific_name"],
                "family": plant_row["family"],
                "url": plant_row["url"],
                "match_score": matched_ids[pid],
                "vernacular_names": vernacular,
                "properties_summary": properties,
            })

        return {
            "query": q,
            "total_results": len(results),
            "results": results,
        }
    finally:
        conn.close()


@router.get("/autocomplete")
def autocomplete_ingredients(
    q: str = Query(..., min_length=1, description="Prefix search query"),
    limit: int = Query(10, ge=1, le=30),
) -> List[Dict[str, Any]]:
    """Fast autocomplete suggestions for product search inputs."""
    clean_q = q.strip()
    variants = generate_search_variants(clean_q)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        seen: Set[str] = set()
        suggestions: List[Dict[str, Any]] = []

        for term in variants:
            like_prefix = f"{term}%"
            like_contains = f"%{term}%"

            cur.execute(
                """
                SELECT DISTINCT p.plant_id, p.scientific_name, p.family,
                       v.name AS matched_vernacular, v.language AS matched_language
                FROM plants p
                LEFT JOIN vernacular_names v ON p.plant_id = v.plant_id AND (v.name LIKE ? OR v.name LIKE ?)
                WHERE p.scientific_name LIKE ? OR p.scientific_name LIKE ?
                   OR v.name LIKE ? OR v.name LIKE ?
                LIMIT ?
                """,
                (like_prefix, like_contains, like_prefix, like_contains, like_prefix, like_contains, limit * 2),
            )
            for r in cur.fetchall():
                pid = r["plant_id"]
                matched_name = r["matched_vernacular"] or r["scientific_name"]
                key = f"{pid}_{matched_name}"
                if key not in seen:
                    seen.add(key)
                    suggestions.append({
                        "plant_id": pid,
                        "scientific_name": r["scientific_name"],
                        "family": r["family"],
                        "matched_name": matched_name,
                        "language": r["matched_language"] or "Scientific",
                    })
                if len(suggestions) >= limit:
                    break
            if len(suggestions) >= limit:
                break

        return suggestions[:limit]
    finally:
        conn.close()


@router.get("/{plant_id}")
def get_ingredient_detail(plant_id: int) -> Dict[str, Any]:
    """Retrieve comprehensive profile of a single medicinal plant by ID."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT plant_id, scientific_name, family, url, created_at FROM plants WHERE plant_id = ?",
            (plant_id,),
        )
        plant_row = cur.fetchone()
        if not plant_row:
            raise HTTPException(status_code=404, detail=f"Plant with ID {plant_id} not found")

        cur.execute(
            "SELECT language, name FROM vernacular_names WHERE plant_id = ? ORDER BY language, name",
            (plant_id,),
        )
        v_rows = cur.fetchall()
        vernacular: Dict[str, List[str]] = {}
        for v in v_rows:
            vernacular.setdefault(v["language"], []).append(v["name"])

        cur.execute(
            "SELECT property_type, property_name, property_value FROM plant_properties WHERE plant_id = ?",
            (plant_id,),
        )
        prop_rows = cur.fetchall()
        properties: Dict[str, List[Dict[str, str]]] = {}
        for pr in prop_rows:
            p_type = pr["property_type"]
            properties.setdefault(p_type, []).append({
                "name": pr["property_name"],
                "value": pr["property_value"],
            })

        cur.execute(
            """
            SELECT sanskrit_synonym, sanskrit_diacritical, reference, etymology_sanskrit, english_meaning
            FROM etymologies WHERE plant_id = ?
            """,
            (plant_id,),
        )
        etymologies = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT part_name, part_hindi, part_diacritical, reference FROM parts_used WHERE plant_id = ?",
            (plant_id,),
        )
        parts_used = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT name FROM mahakashaya WHERE plant_id = ?", (plant_id,))
        mahakashaya = [r["name"] for r in cur.fetchall()]

        cur.execute("SELECT name FROM varga WHERE plant_id = ?", (plant_id,))
        varga = [r["name"] for r in cur.fetchall()]

        cur.execute("SELECT name FROM skandha WHERE plant_id = ?", (plant_id,))
        skandha = [r["name"] for r in cur.fetchall()]

        return {
            "plant_id": plant_row["plant_id"],
            "scientific_name": plant_row["scientific_name"],
            "family": plant_row["family"],
            "url": plant_row["url"],
            "vernacular_names": vernacular,
            "properties": properties,
            "etymologies": etymologies,
            "parts_used": parts_used,
            "mahakashaya": mahakashaya,
            "varga": varga,
            "skandha": skandha,
        }
    finally:
        conn.close()
