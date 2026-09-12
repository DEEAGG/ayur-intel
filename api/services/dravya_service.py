"""AYUR-INTEL — DRAVYA Plant Knowledge Service.

Handles structured ingestion, normalized indexing, and fast local search for the
CCRAS DRAVYA ~400 plant knowledge dataset (dravya_full_data.json).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from api.models.models import DravyaPlant

logger = logging.getLogger("ayur_intel.dravya_service")


def normalize_text(text: str) -> str:
    """Normalize string for botanical & Ayurvedic search matching."""
    if not text:
        return ""
    # Strip diacritics / accents (e.g. Aśvagandhā -> Asvagandha)
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_text = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Lowercase
    s = ascii_text.lower().strip()
    # Normalize common transliteration variants
    s_norm = (
        s.replace("sh", "s")
        .replace("w", "v")
        .replace("ph", "f")
        .replace("th", "t")
        .replace("bh", "b")
        .replace("dh", "d")
        .replace("ch", "c")
    )
    cleaned = re.sub(r"[^a-z0-9\s]", "", s_norm)
    return re.sub(r"\s+", " ", cleaned).strip()


class DravyaService:
    """Service for managing CCRAS DRAVYA plant dataset ingestion and search."""

    @classmethod
    def get_dataset_path(cls) -> str:
        """Locate dravya_full_data.json in workspace."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        possible_paths = [
            os.path.join(base_dir, "dravya_full_data.json"),
            os.path.join(os.getcwd(), "dravya_full_data.json"),
            "dravya_full_data.json",
        ]
        for p in possible_paths:
            if os.path.exists(p):
                return p
        return possible_paths[0]

    @classmethod
    def ingest_dravya_dataset(
        cls, db: Session, json_path: Optional[str] = None
    ) -> int:
        """Idempotently ingest ~400 DRAVYA plants from JSON into dravya_plants table.

        0 Gemini calls. 0 External HTTP calls. 0 duplicates on repeat.
        """
        path = json_path or cls.get_dataset_path()
        if not os.path.exists(path):
            logger.warning("DRAVYA dataset JSON not found at %s", path)
            return db.query(DravyaPlant).count()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to load DRAVYA dataset JSON: %s", e)
            return db.query(DravyaPlant).count()

        plants_raw = data.get("plants", [])
        if not plants_raw:
            return 0

        ingested_count = 0
        updated_count = 0

        for plant_raw in plants_raw:
            p_id = plant_raw.get("plant_id")
            if p_id is None:
                continue

            raw_str = json.dumps(plant_raw, sort_keys=True, ensure_ascii=False)
            chash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

            # Extract fields
            sci_name = plant_raw.get("scientific_name") or f"Plant {p_id}"
            family = plant_raw.get("family") or ""
            url = plant_raw.get("url") or f"https://dravya.ccras.org.in/plant-details/{p_id}"

            vern = plant_raw.get("vernacular_names") or {}
            raw_aliases = set()
            raw_aliases.add(sci_name)

            if sci_name:
                parts = sci_name.split()
                if len(parts) >= 2:
                    raw_aliases.add(f"{parts[0]} {parts[1]}")
                    raw_aliases.add(parts[0])

            if family:
                raw_aliases.add(family)

            if isinstance(vern, dict):
                for lang, names in vern.items():
                    if isinstance(names, list):
                        for n in names:
                            raw_aliases.add(str(n))
                    elif isinstance(names, str):
                        raw_aliases.add(names)

            # Determine primary_name (canonical display/heading name).
            # Sanskrit entries in vernacular_names are SYNONYMS only, not the display name.
            # Priority: Hindi[0] > Assamese[0] > first etymology diacritical > scientific_name
            # Sanskrit synonyms are preserved in aliases but NOT used as the display heading.
            sanskrit_list = vern.get("Sanskrit", []) if isinstance(vern, dict) else []
            hindi_list = vern.get("Hindi", []) if isinstance(vern, dict) else []
            english_list = vern.get("English", []) if isinstance(vern, dict) else []
            assamese_list = vern.get("Assamese", []) if isinstance(vern, dict) else []

            # Collect etymology diacriticals as candidate names
            etym_list = plant_raw.get("etymology", []) or []
            etym_diacriticals = []
            if isinstance(etym_list, list):
                for e in etym_list:
                    d = (e.get("sanskrit_diacritical") or "").strip() if isinstance(e, dict) else ""
                    if d:
                        etym_diacriticals.append(d)

            primary_name = ""
            if hindi_list:
                primary_name = hindi_list[0]
            elif assamese_list:
                primary_name = assamese_list[0]
            elif etym_diacriticals:
                primary_name = etym_diacriticals[0]
            else:
                primary_name = sci_name

            aliases_list = sorted(list(raw_aliases))
            norm_aliases = [normalize_text(a) for a in aliases_list if normalize_text(a)]
            search_text = " | ".join(sorted(list(set(aliases_list + norm_aliases))))

            # Structure JSON blobs
            ayurvedic_props = {
                "rasa": plant_raw.get("rasa", []),
                "guna": plant_raw.get("guna", []),
                "virya": plant_raw.get("virya", []),
                "vipaka": plant_raw.get("vipaka", []),
                "karma": plant_raw.get("karma", []),
                "doshakarma": plant_raw.get("doshakarma", []),
                "mahakashaya": plant_raw.get("mahakashaya", []),
                "varga": plant_raw.get("varga", []),
                "skandha": plant_raw.get("skandha", []),
            }
            botanical_info = {
                "parts_used": plant_raw.get("parts_used", []),
                "etymology": plant_raw.get("etymology", ""),
            }
            therapeutic_usage = plant_raw.get("therapeutic_usage", [])
            dosage_formulations = {
                "dosage": plant_raw.get("dosage", []),
                "dosage_formulations": plant_raw.get("dosage_formulations", []),
            }
            classical_references = plant_raw.get("classical_references", [])

            # Check DB record
            db_plant = db.query(DravyaPlant).filter(DravyaPlant.plant_id == p_id).first()
            if db_plant:
                if db_plant.content_hash != chash:
                    db_plant.scientific_name = sci_name
                    db_plant.family = family
                    db_plant.primary_name = primary_name
                    db_plant.aliases_json = json.dumps(aliases_list, ensure_ascii=False)
                    db_plant.search_text = search_text
                    db_plant.ayurvedic_properties_json = json.dumps(ayurvedic_props, ensure_ascii=False)
                    db_plant.botanical_info_json = json.dumps(botanical_info, ensure_ascii=False)
                    db_plant.therapeutic_usage_json = json.dumps(therapeutic_usage, ensure_ascii=False)
                    db_plant.dosage_formulations_json = json.dumps(dosage_formulations, ensure_ascii=False)
                    db_plant.classical_references_json = json.dumps(classical_references, ensure_ascii=False)
                    db_plant.url = url
                    db_plant.content_hash = chash
                    db_plant.raw_json = raw_str
                    db.add(db_plant)
                    updated_count += 1
            else:
                new_plant = DravyaPlant(
                    plant_id=p_id,
                    scientific_name=sci_name,
                    family=family,
                    primary_name=primary_name,
                    aliases_json=json.dumps(aliases_list, ensure_ascii=False),
                    search_text=search_text,
                    ayurvedic_properties_json=json.dumps(ayurvedic_props, ensure_ascii=False),
                    botanical_info_json=json.dumps(botanical_info, ensure_ascii=False),
                    therapeutic_usage_json=json.dumps(therapeutic_usage, ensure_ascii=False),
                    dosage_formulations_json=json.dumps(dosage_formulations, ensure_ascii=False),
                    classical_references_json=json.dumps(classical_references, ensure_ascii=False),
                    url=url,
                    content_hash=chash,
                    raw_json=raw_str,
                )
                db.add(new_plant)
                ingested_count += 1

        db.commit()
        total_in_db = db.query(DravyaPlant).count()
        logger.info(
            "DRAVYA dataset ingested successfully: %d inserted, %d updated, %d total in DB.",
            ingested_count,
            updated_count,
            total_in_db,
        )
        return total_in_db

    @classmethod
    def get_plant_count(cls, db: Session) -> int:
        """Return total count of ingested DRAVYA plants in DB."""
        return db.query(DravyaPlant).count()

    @classmethod
    def search_plants(
        cls, db: Session, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Normalized ranking search against DRAVYA plant records.

        Ranking strategy:
        1. Exact primary_name or scientific_name match
        2. Exact alias match (case/diacritic insensitive)
        3. Normalized prefix match
        4. Normalized substring match
        """
        q_raw = (query or "").strip()
        if not q_raw:
            return []

        q_norm = normalize_text(q_raw)
        q_lower = q_raw.lower()

        # Query candidates from DB
        candidates = (
            db.query(DravyaPlant)
            .filter(
                or_(
                    DravyaPlant.scientific_name.ilike(f"%{q_raw}%"),
                    DravyaPlant.primary_name.ilike(f"%{q_raw}%"),
                    DravyaPlant.search_text.ilike(f"%{q_raw}%"),
                    DravyaPlant.search_text.ilike(f"%{q_norm}%"),
                )
            )
            .all()
        )

        if not candidates:
            # Fallback scan across all plants if strict query missed (400 plants is very small)
            candidates = db.query(DravyaPlant).all()

        scored_matches = []
        for plant in candidates:
            score = cls._score_plant_match(plant, q_raw, q_norm, q_lower)
            if score > 0:
                scored_matches.append((score, plant))

        scored_matches.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, plant in scored_matches[:limit]:
            results.append(cls.to_dict(plant, score=score))

        return results

    @classmethod
    def _score_plant_match(
        cls, plant: DravyaPlant, q_raw: str, q_norm: str, q_lower: str
    ) -> int:
        """Calculate match relevance score for a plant record."""
        p_sci = (plant.scientific_name or "").lower()
        p_prim = (plant.primary_name or "").lower()

        # 1. Exact primary or scientific name match
        if q_lower == p_prim or q_lower == p_sci:
            return 100

        # Normalized scientific or primary match
        norm_sci = normalize_text(plant.scientific_name)
        norm_prim = normalize_text(plant.primary_name)
        if q_norm == norm_prim or q_norm == norm_sci:
            return 95

        aliases = []
        try:
            aliases = json.loads(plant.aliases_json)
        except Exception:
            aliases = []

        norm_aliases = [normalize_text(a) for a in aliases]

        # 2. Exact alias match
        for a in aliases:
            if q_lower == a.lower():
                return 90
        for na in norm_aliases:
            if q_norm == na:
                return 88

        # 3. Prefix match on scientific, primary, or alias
        if p_sci.startswith(q_lower) or p_prim.startswith(q_lower):
            return 80
        for na in norm_aliases:
            if na.startswith(q_norm) and len(q_norm) >= 3:
                return 75

        # 4. Substring match
        if q_lower in p_sci or q_lower in p_prim:
            return 60
        for na in norm_aliases:
            if q_norm in na and len(q_norm) >= 4:
                return 50

        # 5. Search text match
        search_txt = (plant.search_text or "").lower()
        if q_norm in search_txt and len(q_norm) >= 4:
            return 40

        return 0

    @classmethod
    def get_plant_by_id(cls, db: Session, plant_id: int) -> Optional[Dict[str, Any]]:
        """Fetch plant dictionary by CCRAS plant_id."""
        plant = db.query(DravyaPlant).filter(DravyaPlant.plant_id == plant_id).first()
        if not plant:
            return None
        return cls.to_dict(plant)

    @classmethod
    def to_dict(cls, plant: DravyaPlant, score: Optional[int] = None) -> Dict[str, Any]:
        """Convert DravyaPlant model to structured dictionary."""
        def safe_json(val, default):
            if not val:
                return default
            try:
                return json.loads(val)
            except Exception:
                return default

        raw_obj = safe_json(plant.raw_json, {})
        vern = raw_obj.get("vernacular_names", {})
        sanskrit_synonyms = vern.get("Sanskrit", []) if isinstance(vern, dict) else []

        return {
            "id": plant.public_id,
            "plant_id": plant.plant_id,
            "scientific_name": plant.scientific_name,
            "family": plant.family or "",
            "primary_name": plant.primary_name or plant.scientific_name,
            "sanskrit_synonyms": sanskrit_synonyms,
            "aliases": safe_json(plant.aliases_json, []),
            "ayurvedic_properties": safe_json(plant.ayurvedic_properties_json, {}),
            "botanical_info": safe_json(plant.botanical_info_json, {}),
            "therapeutic_usage": safe_json(plant.therapeutic_usage_json, []),
            "dosage_formulations": safe_json(plant.dosage_formulations_json, {}),
            "classical_references": safe_json(plant.classical_references_json, []),
            "vernacular_names": vern,
            "url": plant.url or f"https://dravya.ccras.org.in/plant-details/{plant.plant_id}",
            "content_hash": plant.content_hash,
            "source_provenance": "DRAVYA / CCRAS Plant Knowledge",
            "source_authority": "Central Council for Research in Ayurvedic Sciences (CCRAS)",
            "score": score,
        }

    @classmethod
    def get_search_index(cls, db: Session) -> List[Dict[str, Any]]:
        """Return compact search index of all ~400 DRAVYA plants for instant client-side typeahead."""
        plants = db.query(DravyaPlant).order_by(DravyaPlant.plant_id.asc()).all()
        index = []
        for plant in plants:
            def safe_json(val, default):
                if not val:
                    return default
                try:
                    return json.loads(val)
                except Exception:
                    return default

            aliases = safe_json(plant.aliases_json, [])
            raw_obj = safe_json(plant.raw_json, {})
            vern = raw_obj.get("vernacular_names", {}) if isinstance(raw_obj, dict) else {}

            index.append({
                "plant_id": plant.plant_id,
                "scientific_name": plant.scientific_name,
                "primary_name": plant.primary_name or plant.scientific_name,
                "family": plant.family or "",
                "aliases": aliases,
                "vernacular_names": vern,
                "url": plant.url or f"https://dravya.ccras.org.in/plant-details/{plant.plant_id}",
            })
        return index
