"""AYUR-INTEL — Patent Intelligence Service.

Searches patent sources, normalizes results, ranks relevance,
and saves findings to Product Cases. This is PATENT DISCOVERY,
not patentability determination.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    InnovationAnalysis,
    InnovationComponent,
    PatentRecord,
    PatentRelevance,
    PatentSearch,
    ProductCase,
    User,
)
from api.services.patent_adapter import (
    PatentResult,
    get_patent_registry,
)

logger = logging.getLogger("ayur_intel.patent_service")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _deserialize_list(value: Optional[str]) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _deserialize_dict(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def get_patent_jurisdiction(record: dict | PatentRecord | PatentResult | None) -> str:
    """Extract authoritative 2-letter jurisdiction code from official patent metadata.

    Returns 2-letter code (e.g. 'IN', 'US', 'WO', 'EP', 'GB', 'DE', etc.) or 'UNKNOWN'.
    NEVER infers India ('IN') from botanical terms, applicant names, or abstract text.
    """
    if not record:
        return "UNKNOWN"

    jurisdiction = None
    pub_num = ""
    provider_id = ""
    authority = ""

    if isinstance(record, dict):
        jurisdiction = record.get("jurisdiction")
        pub_num = record.get("publication_number") or ""
        provider_id = record.get("provider_record_id") or record.get("id") or ""
        authority = record.get("authority") or ""
    else:
        jurisdiction = getattr(record, "jurisdiction", None)
        pub_num = getattr(record, "publication_number", None) or ""
        provider_id = getattr(record, "provider_record_id", None) or getattr(record, "public_id", None) or ""
        authority = getattr(record, "authority", None) or ""

    if jurisdiction and isinstance(jurisdiction, str):
        j_upper = jurisdiction.strip().upper()
        if len(j_upper) == 2 and j_upper.isalpha() and j_upper not in ("GL", "UN"):
            return j_upper

    if pub_num and isinstance(pub_num, str):
        pub_upper = pub_num.strip().upper()
        m = re.match(r'^([A-Z]{2})\d', pub_upper)
        if m:
            return m.group(1)

    if provider_id and isinstance(provider_id, str):
        pid_upper = provider_id.strip().upper()
        m = re.match(r'^([A-Z]{2})\d', pid_upper)
        if m:
            return m.group(1)

    if authority and isinstance(authority, str):
        auth_upper = authority.strip().upper()
        if len(auth_upper) == 2 and auth_upper.isalpha():
            return auth_upper

    return "UNKNOWN"


def has_india_connection(record: dict | PatentRecord | PatentResult | None) -> bool:
    """Return True ONLY if record has explicit Indian patent filing metadata.

    Requires: IN publication number, IN application number, IN priority application, PCT/IN number,
    or explicit IN family member in official family metadata.
    NEVER classifies a patent as India-connected based on inventor/applicant location or name alone.
    """
    if not record:
        return False

    j_code = get_patent_jurisdiction(record)
    if j_code == "IN":
        return True

    pub_num = ""
    app_num = ""
    family_members = []

    if isinstance(record, dict):
        pub_num = record.get("publication_number") or ""
        app_num = record.get("application_number") or ""
        family_members = record.get("family_members") or []
    else:
        pub_num = getattr(record, "publication_number", None) or ""
        app_num = getattr(record, "application_number", None) or ""
        fm_json = getattr(record, "family_members_json", None)
        if fm_json:
            try:
                family_members = json.loads(fm_json)
            except Exception:
                family_members = []
        else:
            family_members = getattr(record, "family_members", None) or []

    if isinstance(pub_num, str) and pub_num.strip().upper().startswith("IN"):
        return True

    if isinstance(app_num, str) and "IN" in app_num.strip().upper():
        return True

    if isinstance(family_members, list):
        for member in family_members:
            if isinstance(member, str) and "IN" in member.strip().upper():
                return True

    return False


def _record_to_dict(rec: PatentRecord) -> dict:
    inventors = None
    if rec.inventors:
        try:
            inventors = json.loads(rec.inventors)
        except (json.JSONDecodeError, TypeError):
            inventors = [rec.inventors] if rec.inventors else None

    family_members = []
    if rec.family_members_json:
        try:
            family_members = json.loads(rec.family_members_json)
        except (json.JSONDecodeError, TypeError):
            family_members = []

    provider_id = getattr(rec, "provider_record_id", None)
    pub_num = rec.publication_number

    if pub_num:
        clean_pub = pub_num.replace(" ", "").replace("/", "").replace("-", "")
        open_patent_url = f"https://patents.google.com/patent/{clean_pub}/en"
    else:
        open_patent_url = rec.source_url or (f"https://europepmc.org/article/PAT/{provider_id}" if provider_id else "")

    j_code = get_patent_jurisdiction(rec)

    return {
        "id": rec.public_id,
        "provider_record_id": provider_id,
        "source_name": rec.source_name,
        "authority": rec.authority,
        "jurisdiction": j_code,
        "jurisdiction_code": j_code,
        "has_india_connection": has_india_connection(rec),
        "publication_number": rec.publication_number,
        "application_number": rec.application_number,
        "patent_type": rec.patent_type,
        "title": rec.title,
        "abstract": rec.abstract,
        "applicant": rec.applicant,
        "inventors": inventors,
        "priority_date": rec.priority_date,
        "filing_date": rec.filing_date,
        "publication_date": rec.publication_date,
        "status": rec.status,
        "source_url": rec.source_url,
        "open_patent_url": open_patent_url,
        "family_id": rec.family_id,
        "family_members": family_members,
        "retrieved_at": rec.retrieved_at.isoformat() if rec.retrieved_at else "",
        "created_at": rec.created_at.isoformat() if rec.created_at else "",
    }


def get_category_from_score(score: Optional[int]) -> str:
    """Authoritative score-to-category mapping according to system rules.

    0-34 LOW
    35-64 MODERATE
    65-79 HIGH
    80-100 VERY_HIGH
    None -> NOT_ANALYZED
    """
    if score is None:
        return "NOT_ANALYZED"
    score_val = int(score)
    if score_val >= 80:
        return "VERY_HIGH"
    elif score_val >= 65:
        return "HIGH"
    elif score_val >= 35:
        return "MODERATE"
    else:
        return "LOW"


def _relevance_to_dict(rel: PatentRelevance) -> dict:
    rec = rel.patent_record
    score_breakdown = _deserialize_dict(rel.score_breakdown_json)
    matched_components = _deserialize_list(rel.matched_components_json)
    matched_queries = _deserialize_list(rel.matched_queries_json)

    score = rel.relevance_score
    level = get_category_from_score(score) if score is not None else (rel.relevance_level or "NOT_ANALYZED")

    return {
        "id": rel.public_id,
        "patent": _record_to_dict(rec) if rec else {},
        "relevance_level": level,
        "relevance_score": score,
        "evidence_basis": rel.evidence_basis or "TITLE_ABSTRACT",
        "evidence_coverage": rel.evidence_coverage or "STANDARD",
        "score_breakdown": score_breakdown if score is not None else None,
        "matched_components": matched_components,
        "matched_queries": matched_queries,
        "why_relevant": rel.why_relevant or rel.explanation or "",
        "important_difference": rel.important_difference or "Full claim-level review required to establish precise legal boundary differences.",
        "limitations": rel.limitations or "Based on abstract-level screening. Non-prosecuted claims pending full specification verification.",
        "explanation": rel.explanation or "",
        "overlap_component": rel.overlap_component,
        "saved_by_user": rel.saved_by_user,
        "user_notes": rel.user_notes,
        "created_at": rel.created_at.isoformat() if rel.created_at else "",
    }


# -------------------------------------------------------------------
# Query Plan Generation (5-10 Categorized Structured Queries)
# -------------------------------------------------------------------

BOTANICAL_MARKERS = {
    "withania": "withanolides",
    "ashwagandha": "withanolides",
    "nardostachys": "jatamansone",
    "jatamansi": "jatamansone",
    "bacopa": "bacosides",
    "brahmi": "bacosides",
    "centella": "asiaticosides",
    "mandukaparni": "asiaticosides",
    "convolvulus": "flavonoids",
    "shankhpushpi": "flavonoids",
    "ocimum": "eugenol",
    "tulsi": "eugenol",
    "azadirachta": "azadirachtin",
    "neem": "azadirachtin",
    "curcuma": "curcumin",
    "turmeric": "curcumin",
    "zingiber": "gingerol",
    "ginger": "gingerol",
    "phyllanthus": "tannins",
    "amla": "tannins",
}


def generate_query_plan(case: ProductCase, components: List[InnovationComponent]) -> List[dict]:
    """Generate 7–10 short, concept-based search queries derived from product intelligence."""
    plan: List[dict] = []

    ingredients = _deserialize_list(case.ingredients) if case.ingredients else []
    ing_common = []
    ing_botanical = []
    markers = []

    for ing in ingredients:
        name = ing.get("name", "") if isinstance(ing, dict) else str(ing)
        bot_val = ing.get("botanical", "") if isinstance(ing, dict) else ""
        name_clean = name.strip()

        common_name = ""
        botanical_name = ""

        if "(" in name_clean and ")" in name_clean:
            common_name = name_clean.split("(")[0].strip()
            botanical_name = name_clean.split("(")[1].split(")")[0].strip()
        else:
            common_name = name_clean

        if bot_val and not botanical_name:
            botanical_name = bot_val.strip()

        if common_name:
            ing_common.append(common_name)
        if botanical_name:
            ing_botanical.append(botanical_name)

        check_str = (common_name + " " + botanical_name).lower()
        for k, v in BOTANICAL_MARKERS.items():
            if k in check_str and v not in markers:
                markers.append(v)

    # 1. BOTANICAL CONCEPT
    if ing_botanical:
        bot_query = " OR ".join([f'"{b}"' for b in ing_botanical[:3]])
        plan.append({
            "category": "BOTANICAL",
            "query": bot_query,
            "signals": " · ".join(ing_botanical[:3]),
            "rationale": "Screens for prior art covering key scientific botanical species."
        })

    # 2. COMMON NAMES
    if ing_common:
        common_query = " OR ".join([f'"{c}"' for c in ing_common[:3]])
        plan.append({
            "category": "COMMON_NAMES",
            "query": common_query,
            "signals": " · ".join(ing_common[:3]),
            "rationale": "Screens for prior art matching primary common herbal names."
        })

    # 3. COMBINATION CONCEPT
    if len(ing_botanical) >= 2:
        comb_query = " AND ".join([f'"{b}"' for b in ing_botanical[:3]])
        plan.append({
            "category": "COMBINATION",
            "query": comb_query,
            "signals": " · ".join(ing_botanical[:3]),
            "rationale": "Screens for prior art covering multi-active botanical combinations."
        })
    elif len(ing_common) >= 2:
        comb_query = " AND ".join([f'"{c}"' for c in ing_common[:3]])
        plan.append({
            "category": "COMBINATION",
            "query": comb_query,
            "signals": " · ".join(ing_common[:3]),
            "rationale": "Screens for prior art covering multi-herbal combinations."
        })

    # 4. STANDARDIZATION / ACTIVE MARKER CONCEPT
    if markers:
        mark_query = " AND ".join(markers[:2]) if len(markers) >= 2 else markers[0]
        plan.append({
            "category": "STANDARDIZATION",
            "query": mark_query,
            "signals": " · ".join(markers[:2]),
            "rationale": "Screens for prior art targeting active phytochemical markers."
        })

    # 5. PROCESS CONCEPT
    clean_proc = ""
    if case.process:
        p = case.process.lower()
        if "supercritical" in p:
            clean_proc = "supercritical fluid extraction"
        elif "hydro-alcoholic" in p or "hydroalcoholic" in p:
            clean_proc = "hydroalcoholic extraction"
        elif "decoction" in p:
            clean_proc = "herbal decoction process"
        elif "vacuum" in p:
            clean_proc = "vacuum concentration process"
        elif ing_botanical:
            clean_proc = f"{ing_botanical[0].split()[0]} extraction"

    if clean_proc:
        plan.append({
            "category": "PROCESS",
            "query": clean_proc,
            "signals": clean_proc,
            "rationale": "Screens for prior art regarding extraction and manufacturing process."
        })

    # 6. FORMULATION CONCEPT
    form_term = case.form or "capsule"
    form_herb = ing_common[0] if ing_common else "herbal"
    form_query = f"{form_herb} {form_term} formulation"
    plan.append({
        "category": "FORMULATION",
        "query": form_query,
        "signals": f"{form_herb} · {form_term}",
        "rationale": "Screens for prior art in product galenic form and delivery matrix."
    })

    # 7. USE / INDICATION CONCEPT
    clean_use = ""
    if case.intended_use:
        u = case.intended_use.lower()
        if "sleep" in u or "relaxation" in u or "insomnia" in u or "sedative" in u:
            clean_use = "sleep induction relaxation"
        elif "cognitive" in u or "memory" in u:
            clean_use = "cognitive memory focus"
        elif "stress" in u or "calm" in u:
            clean_use = "stress relief anxiety"
        elif "immune" in u or "purification" in u:
            clean_use = "immune support wellness"
        elif "skin" in u:
            clean_use = "skin rejuvenation topical"
        else:
            words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', u) if w not in ('support', 'relief', 'and', 'with', 'for')]
            clean_use = " ".join(words[:3])

    if clean_use:
        plan.append({
            "category": "USE",
            "query": f"{ing_common[0] if ing_common else 'herbal'} {clean_use}",
            "signals": clean_use,
            "rationale": "Screens for prior art targeting key therapeutic indication."
        })

    # 8. CLAIM CONCEPT
    claims = _deserialize_list(case.claims) if case.claims else []
    if claims:
        claim_raw = claims[0] if isinstance(claims[0], str) else claims[0].get("text", "")
        claim_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', claim_raw) if w.lower() not in ('supports', 'enhances', 'promotes', 'and', 'with', 'for')]
        claim_concept = " ".join(claim_words[:4])
        if claim_concept:
            plan.append({
                "category": "CLAIM_CONCEPT",
                "query": f"herbal {claim_concept}",
                "signals": claim_concept,
                "rationale": "Screens for prior art matching primary product claim concepts."
            })

    if components:
        for comp in components:
            if len(plan) >= 10:
                break
            if comp.component_value:
                val_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', comp.component_value) if w.lower() not in ('traditional', 'known', 'standard')]
                if val_words:
                    plan.append({
                        "category": "CLAIM_CONCEPT",
                        "query": f"{ing_common[0] if ing_common else 'herbal'} {' '.join(val_words[:3])}",
                        "signals": f"{comp.component_type}: {comp.component_value[:20]}",
                        "rationale": "Screens for prior art on innovation element."
                    })

    if len(plan) < 5 and case.name:
        plan.append({
            "category": "CLAIM_CONCEPT",
            "query": f'"{case.name}"',
            "signals": case.name,
            "rationale": "Screens for direct product name and exact term matches."
        })

    return plan[:10]


# -------------------------------------------------------------------
# Pre-ranking Candidates (Local Term Match)
# -------------------------------------------------------------------

def _pre_rank_candidate_patents(
    results: List[PatentResult],
    case: ProductCase,
    query_plan: List[dict],
) -> List[dict]:
    """Local term match scoring for retrieved candidate patents."""
    pre_ranked = []
    ingredients = _deserialize_list(case.ingredients) if case.ingredients else []
    ing_terms = []
    for ing in ingredients:
        n = ing.get("name", "") if isinstance(ing, dict) else str(ing)
        if n:
            ing_terms.append(n.lower().split("(")[0].strip())
            if "(" in n and ")" in n:
                ing_terms.append(n.split("(")[1].split(")")[0].strip().lower())

    for res in results:
        title = (res.title or "").lower()
        abstract = (res.abstract or "").lower()
        text = title + " " + abstract

        ing_matches = [t for t in ing_terms if t and t in text]
        matched_queries = res.matched_queries or []

        pre_score = len(ing_matches) * 20 + len(matched_queries) * 15
        if case.formulation and case.formulation.lower() in text:
            pre_score += 25
        if case.process and case.process.lower() in text:
            pre_score += 20

        pre_ranked.append({
            "result": res,
            "pre_score": pre_score,
            "ing_matches": ing_matches,
            "matched_queries": matched_queries,
        })

    pre_ranked.sort(key=lambda x: x["pre_score"], reverse=True)
    return pre_ranked


# -------------------------------------------------------------------
# Semantic Analysis with Gemini / Heuristic Fallback
# -------------------------------------------------------------------

def _calculate_score_and_category(breakdown: dict) -> Tuple[int, str]:
    """Calculate 0-100 score and assign category according to backend rules.

    Non-negotiable rule: Ingredient match alone cannot produce VERY_HIGH (80-100).
    """
    tech = breakdown.get("technological_overlap", 0)
    ing = breakdown.get("ingredient_overlap", 0)
    form_proc = breakdown.get("formulation_process_overlap", 0)
    claim_conc = breakdown.get("claim_concept_overlap", 0)

    raw_score = int(round(tech * 0.35 + ing * 0.25 + form_proc * 0.25 + claim_conc * 0.15))

    if tech <= 20 and form_proc <= 20 and claim_conc <= 20:
        raw_score = min(raw_score, 79)

    score = max(0, min(100, raw_score))

    if score >= 80:
        category = "VERY_HIGH"
    elif score >= 65:
        category = "HIGH"
    elif score >= 35:
        category = "MODERATE"
    else:
        category = "LOW"

    return score, category


def _analyze_candidates_heuristic(
    candidates: List[dict],
    case: ProductCase,
) -> List[dict]:
    """Deterministic fallback analyzer when Gemini API is unavailable."""
    analyzed = []
    ingredients = _deserialize_list(case.ingredients) if case.ingredients else []
    ing_names = [(i.get("name", "") if isinstance(i, dict) else str(i)).split("(")[0].strip() for i in ingredients]

    for item in candidates:
        res: PatentResult = item["result"]
        title = res.title or ""
        abstract = res.abstract or ""
        text = (title + " " + abstract).lower()

        matched_components = [i for i in ing_names if i and i.lower() in text]
        matched_queries = item.get("matched_queries", [])

        tech_overlap = 80 if len(matched_components) >= 2 else (50 if matched_components else 20)
        ing_overlap = min(100, len(matched_components) * 45)
        form_proc_overlap = 75 if (case.formulation and case.formulation.lower() in text) or (case.process and case.process.lower() in text) else 30
        claim_conc_overlap = 60 if matched_queries else 20

        breakdown = {
            "technological_overlap": tech_overlap,
            "ingredient_overlap": ing_overlap,
            "formulation_process_overlap": form_proc_overlap,
            "claim_concept_overlap": claim_conc_overlap,
        }

        score, category = _calculate_score_and_category(breakdown)

        why_rel = f"Abstract includes overlap with {', '.join(matched_components[:2]) if matched_components else 'herbal formulation elements'}."
        diff = "Product case specifies standardized herbal ratios and targeted galenic carrier not explicitly claimed in abstract."
        lim = "Abstract-level prior-art screening. Independent claim scope requires detailed legal prosecution review."

        analyzed.append({
            "result": res,
            "score_breakdown": breakdown,
            "relevance_score": score,
            "relevance_level": category,
            "matched_components": matched_components,
            "matched_queries": matched_queries,
            "why_relevant": why_rel,
            "important_difference": diff,
            "limitations": lim,
        })

    return analyzed


def _build_unanalyzed_candidates(candidates: List[dict]) -> List[dict]:
    """Return candidate records with NOT_ANALYZED status when Gemini AI evaluation is unavailable."""
    analyzed = []
    for item in candidates:
        res: PatentResult = item["result"]
        analyzed.append({
            "result": res,
            "score_breakdown": None,
            "relevance_score": None,
            "relevance_level": "NOT_ANALYZED",
            "matched_components": item.get("ing_matches", []),
            "matched_queries": item.get("matched_queries", []),
            "why_relevant": "AI semantic analysis temporarily unavailable.",
            "important_difference": "Detailed AI evaluation pending.",
            "limitations": "Public literature screening only. AI analysis currently unavailable.",
        })
    return analyzed


def _analyze_patents_with_gemini(
    candidates: List[dict],
    case: ProductCase,
) -> List[dict]:
    """Structured semantic evaluation using Gemini AI, processing ONLY actual retrieved patents."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("AYURINTEL_GEMINI_API_KEY")
    if not api_key:
        logger.info("No Gemini API key found; returning NOT_ANALYZED candidate records.")
        return _build_unanalyzed_candidates(candidates)

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        logger.info("Calling Gemini API (%s) for Patent Intelligence candidate analysis...", model_name)
        model = genai.GenerativeModel(model_name)

        patent_payloads = []
        for item in candidates:
            res: PatentResult = item["result"]
            rec_id = res.publication_number or res.application_number or res.provider_record_id
            patent_payloads.append({
                "identifier": rec_id,
                "publication_number": rec_id,
                "title": res.title,
                "abstract": res.abstract,
                "applicant": res.applicant,
            })

        prompt = f"""You are a specialized Patent Prior-Art Screening AI for AYUR-INTEL.
You MUST analyze ONLY the following retrieved real patent candidates against the given Ayurvedic Product Case.
DO NOT invent or generate any fictional patent numbers or titles.

PRODUCT CASE:
- Name: {case.name}
- Category: {getattr(case, 'category', 'Ayurvedic Skincare/Herbal')}
- Ingredients: {case.ingredients}
- Formulation: {case.formulation}
- Process: {case.process}
- Form: {case.form}

RETRIEVED PATENTS:
{json.dumps(patent_payloads, indent=2)}

SCORING RUBRIC BANDS (0-100 for each dimension):
- 0–20: Negligible overlap (no relevant terms or evidence in document text)
- 21–40: Weak overlap (broad field similarity or single distant term match)
- 41–60: Moderate overlap (partial ingredient match or general formulation form)
- 61–80: Strong overlap (multi-active ingredient match or specific process match)
- 81–100: Very strong overlap (direct multi-active combination, formulation matrix, and claim concept match)

Evaluate each patent across 4 dimensions:
1. technological_overlap (0-100)
2. ingredient_overlap (0-100)
3. formulation_process_overlap (0-100)
4. claim_concept_overlap (0-100)

Return ONLY a JSON array with objects containing:
[
  {{
    "identifier": "...",
    "matched_components": ["component1"],
    "matched_queries": ["query1"],
    "why_relevant": "Concise 1-2 sentence explanation of overlap.",
    "important_difference": "Concise explanation of how product case differs.",
    "limitations": "Screening limitations.",
    "technological_overlap": 75,
    "ingredient_overlap": 80,
    "formulation_process_overlap": 50,
    "claim_concept_overlap": 40
  }}
]
"""

        try:
            response = model.generate_content(prompt)
        except Exception as model_err:
            if "404" in str(model_err) or "NotFound" in type(model_err).__name__ or "not found" in str(model_err).lower():
                logger.info("Model %s unavailable; falling back to gemini-1.5-flash...", model_name)
                model_name = "gemini-1.5-flash"
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
            else:
                raise model_err
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:]
        if text_resp.endswith("```"):
            text_resp = text_resp[:-3]
        text_resp = text_resp.strip()

        evaluations = json.loads(text_resp)
        eval_map = {}
        for e in evaluations:
            if isinstance(e, dict):
                k = e.get("identifier") or e.get("publication_number")
                if k:
                    eval_map[k] = e

        analyzed = []
        for item in candidates:
            res: PatentResult = item["result"]
            rec_id = res.publication_number or res.application_number or res.provider_record_id
            gem_eval = eval_map.get(rec_id)

            if gem_eval:
                breakdown = {
                    "technological_overlap": int(gem_eval.get("technological_overlap", 50)),
                    "ingredient_overlap": int(gem_eval.get("ingredient_overlap", 50)),
                    "formulation_process_overlap": int(gem_eval.get("formulation_process_overlap", 50)),
                    "claim_concept_overlap": int(gem_eval.get("claim_concept_overlap", 50)),
                }
                score, category = _calculate_score_and_category(breakdown)

                analyzed.append({
                    "result": res,
                    "score_breakdown": breakdown,
                    "relevance_score": score,
                    "relevance_level": category,
                    "matched_components": gem_eval.get("matched_components", item.get("ing_matches", [])),
                    "matched_queries": gem_eval.get("matched_queries", item.get("matched_queries", [])),
                    "why_relevant": gem_eval.get("why_relevant", "Direct patent title/abstract overlap detected."),
                    "important_difference": gem_eval.get("important_difference", "Product case specifies standardized extract ratios."),
                    "limitations": gem_eval.get("limitations", "Abstract-level prior-art screening."),
                })
            else:
                analyzed.extend(_build_unanalyzed_candidates([item]))

        return analyzed

    except Exception as e:
        logger.warning(f"Gemini patent analysis encountered exception: {e}. Returning NOT_ANALYZED candidate records.")
        return _build_unanalyzed_candidates(candidates)


# -------------------------------------------------------------------
# Execute Intelligence Search & Persist
# -------------------------------------------------------------------

def run_patent_intelligence(
    db: Session,
    owner: User,
    case: ProductCase,
    jurisdictions: Optional[List[str]] = None,
    limit: int = 25,
) -> dict:
    """Execute full prior-art patent intelligence analysis for a Product Case."""
    analysis = (
        db.query(InnovationAnalysis)
        .filter(InnovationAnalysis.product_case_id == case.id)
        .order_by(InnovationAnalysis.created_at.desc())
        .first()
    )
    components = list(analysis.components) if analysis else []

    query_plan = generate_query_plan(case, components)

    registry = get_patent_registry()
    search_jurisdictions = jurisdictions or ["IN", "US", "EP", "WO", "GLOBAL"]

    keywords = [q["query"] for q in query_plan]

    responses = registry.search_all(
        query=case.name or "Ayurvedic formulation",
        keywords=keywords,
        jurisdictions=search_jurisdictions,
        limit=limit,
    )

    all_raw_results: List[PatentResult] = []
    total_queries_executed = 0
    total_queries_with_results = 0

    for resp in responses:
        all_raw_results.extend(resp.results)
        total_queries_executed += getattr(resp, "queries_executed", len(query_plan))
        total_queries_with_results += getattr(resp, "queries_with_results", 1 if resp.results else 0)

    # Deduplicate by publication_number / provider_record_id & group families
    unique_candidates: Dict[str, PatentResult] = {}
    family_members_map: Dict[str, List[str]] = {}

    for res in all_raw_results:
        rec_key = res.publication_number or res.application_number or res.provider_record_id
        if not rec_key:
            continue
        clean_key = rec_key.replace(" ", "").upper()

        if clean_key not in unique_candidates:
            unique_candidates[clean_key] = res
            family_members_map[clean_key] = [rec_key]
            if res.family_members:
                for fm in res.family_members:
                    if fm not in family_members_map[clean_key]:
                        family_members_map[clean_key].append(fm)
        else:
            existing = unique_candidates[clean_key]
            for q in (res.matched_queries or []):
                if q not in existing.matched_queries:
                    existing.matched_queries.append(q)
            if rec_key not in family_members_map[clean_key]:
                family_members_map[clean_key].append(rec_key)
            if not existing.application_number and res.application_number:
                existing.application_number = res.application_number
            if res.family_members:
                existing_fm = existing.family_members or []
                for fm in res.family_members:
                    if fm not in existing_fm:
                        existing_fm.append(fm)
                    if fm not in family_members_map[clean_key]:
                        family_members_map[clean_key].append(fm)
                existing.family_members = existing_fm

    deduped_results = list(unique_candidates.values())

    pre_ranked = _pre_rank_candidate_patents(deduped_results, case, query_plan)

    analyzed_candidates = _analyze_patents_with_gemini(pre_ranked[:20], case)

    raw_discovered = sum(getattr(resp, "raw_discovered_count", len(resp.results)) for resp in responses)
    if raw_discovered < len(deduped_results):
        raw_discovered = len(deduped_results)
    unique_screened = len(deduped_results)

    now = datetime.now(timezone.utc)

    query_plan_envelope = {
        "version": "2.0_INDIA_PATENT_UPGRADE",
        "plan": query_plan,
    }

    search = PatentSearch(
        owner_id=owner.id,
        product_case_id=case.id,
        search_concepts=json.dumps(query_plan_envelope),
        jurisdictions_searched=json.dumps(search_jurisdictions),
        total_results=len(analyzed_candidates),
        raw_discovered_count=raw_discovered,
        unique_screened_count=unique_screened,
        sources_searched=len(responses),
        sources_succeeded=sum(1 for r in responses if r.is_configured),
        status="COMPLETED",
        created_at=now,
    )
    db.add(search)
    db.commit()
    db.refresh(search)

    persisted_relevances = []

    for item in analyzed_candidates:
        res: PatentResult = item["result"]
        pub_num = res.publication_number or res.application_number or ""
        clean_pub = pub_num.replace(" ", "").upper() if pub_num else ""
        rec_key = pub_num or res.provider_record_id or ""
        clean_key = rec_key.replace(" ", "").upper() if rec_key else ""
        f_members = family_members_map.get(clean_key, [rec_key])

        record = None
        if res.provider_record_id:
            record = db.query(PatentRecord).filter(PatentRecord.provider_record_id == res.provider_record_id).first()
        if not record and res.publication_number:
            record = db.query(PatentRecord).filter(PatentRecord.publication_number == res.publication_number).first()

        if not record:
            record = PatentRecord(
                provider_record_id=res.provider_record_id,
                source_name=res.source_name,
                authority=res.authority,
                jurisdiction=res.jurisdiction or "GLOBAL",
                publication_number=res.publication_number,
                application_number=res.application_number,
                patent_type=res.patent_type or "PUBLICATION",
                title=res.title or "Untitled Patent Document",
                abstract=res.abstract,
                applicant=res.applicant,
                inventors=json.dumps(res.inventors) if res.inventors else None,
                priority_date=res.priority_date,
                filing_date=res.filing_date,
                publication_date=res.publication_date,
                status=res.status,
                family_id=res.family_id,
                family_members_json=json.dumps(res.family_members) if res.family_members else None,
                retrieved_at=now,
                created_at=now,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        else:
            rec_updated = False
            if not record.application_number and res.application_number:
                record.application_number = res.application_number
                rec_updated = True
            if res.family_members:
                existing_fm = []
                if record.family_members_json:
                    try:
                        existing_fm = json.loads(record.family_members_json)
                    except Exception:
                        existing_fm = []
                for fm in res.family_members:
                    if fm not in existing_fm:
                        existing_fm.append(fm)
                        rec_updated = True
                if rec_updated:
                    record.family_members_json = json.dumps(existing_fm)
            if not record.priority_date and res.priority_date:
                record.priority_date = res.priority_date
                rec_updated = True
            if not record.filing_date and res.filing_date:
                record.filing_date = res.filing_date
                rec_updated = True
            if rec_updated:
                db.commit()
                db.refresh(record)

        has_abstract = bool(res.abstract and len(res.abstract.strip()) > 10)
        has_claims = bool(getattr(res, "claims", None) and len(getattr(res, "claims", [])) > 0)
        if has_claims:
            ev_basis = "TITLE_ABSTRACT_CLAIMS"
        elif has_abstract:
            ev_basis = "TITLE_ABSTRACT"
        else:
            ev_basis = "TITLE_ONLY"

        relevance = PatentRelevance(
            product_case_id=case.id,
            patent_record_id=record.id,
            search_id=search.id,
            relevance_level=item["relevance_level"],
            relevance_score=item["relevance_score"],
            explanation=item["why_relevant"],
            evidence_basis=ev_basis,
            evidence_coverage="STANDARD",
            score_breakdown_json=json.dumps(item["score_breakdown"]) if item.get("score_breakdown") else None,
            matched_components_json=json.dumps(item["matched_components"]),
            matched_queries_json=json.dumps(item["matched_queries"]),
            why_relevant=item["why_relevant"],
            important_difference=item["important_difference"],
            limitations=item["limitations"],
            overlap_component=item["matched_components"][0] if item["matched_components"] else None,
            overlap_description=item["why_relevant"],
            saved_by_user=False,
            created_at=now,
            updated_at=now,
        )
        db.add(relevance)
        db.commit()
        db.refresh(relevance)

        persisted_relevances.append(_relevance_to_dict(relevance))

    persisted_relevances.sort(key=lambda x: (x["relevance_score"] is not None, x["relevance_score"] if x["relevance_score"] is not None else -1), reverse=True)

    vh_cnt = sum(1 for i in persisted_relevances if i.get("relevance_level") == "VERY_HIGH")
    h_cnt = sum(1 for i in persisted_relevances if i.get("relevance_level") == "HIGH")

    if vh_cnt > 0:
        prior_art_signal = "HIGH"
    elif h_cnt > 0:
        prior_art_signal = "MODERATE"
    else:
        prior_art_signal = "LOW"

    if total_queries_with_results == total_queries_executed and total_queries_executed > 0:
        discovery_coverage = "FULL"
    elif total_queries_with_results > 0:
        discovery_coverage = "PARTIAL"
    else:
        discovery_coverage = "ZERO"

    metrics = {
        "raw_discovered_count": raw_discovered,
        "unique_screened_count": unique_screened,
        "shortlisted_count": len(pre_ranked[:20]),
        "analyzed_count": len(persisted_relevances),
        "total_retrieved": len(persisted_relevances),
        "ai_attempted_count": len(persisted_relevances),
        "ai_successful_count": sum(1 for i in persisted_relevances if i.get("relevance_level") in ("LOW", "MODERATE", "HIGH", "VERY_HIGH")),
        "not_shortlisted_count": max(0, unique_screened - len(pre_ranked[:20])),
        "very_high_count": vh_cnt,
        "high_count": h_cnt,
        "moderate_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "MODERATE"),
        "low_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "LOW"),
        "not_analyzed_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "NOT_ANALYZED"),
        "queries_executed": total_queries_executed or len(query_plan),
        "queries_with_results": total_queries_with_results,
        "prior_art_signal": prior_art_signal,
        "discovery_coverage": discovery_coverage,
        "evidence_basis": "ABSTRACT-LEVEL SCREENING",
        "last_searched": now.isoformat(),
    }

    # Extract grounded potential differentiators
    potential_differentiators = []
    if persisted_relevances:
        diff_texts = [p.get("important_difference", "") for p in persisted_relevances if p.get("important_difference")]
        if case.formulation and "ratio" not in " ".join(diff_texts).lower():
            potential_differentiators.append(f"Product formulation specifies defined matrix composition: {case.formulation}")
        if case.process and "process" in case.process.lower():
            potential_differentiators.append(f"Specific extraction and purification process: {case.process}")
        if case.claims:
            claims_list = _deserialize_list(case.claims)
            if claims_list:
                c_str = claims_list[0] if isinstance(claims_list[0], str) else claims_list[0].get("text", "")
                potential_differentiators.append(f"Targeted claim concept from product case: {c_str}")

    return {
        "search_id": search.public_id,
        "product_case_id": case.public_id,
        "query_plan": query_plan,
        "summary_metrics": metrics,
        "potential_differentiators": potential_differentiators[:3],
        "results": persisted_relevances,
        "patents": persisted_relevances,
        "has_searched": True,
        "created_at": now.isoformat(),
    }


# -------------------------------------------------------------------
# GET-First Public API
# -------------------------------------------------------------------

def get_or_run_patent_intelligence(
    db: Session,
    owner: User,
    case_public_id: str,
    force_rerun: bool = False,
) -> Optional[dict]:
    """GET-first retrieval of persisted patent intelligence analysis for a Product Case."""
    query = db.query(ProductCase).filter(ProductCase.public_id == case_public_id)
    if owner is not None:
        query = query.filter((ProductCase.owner_id == owner.id) | ((ProductCase.public_id == "demo-001") & (ProductCase.is_demo == True)))
    else:
        query = query.filter((ProductCase.public_id == "demo-001") & (ProductCase.is_demo == True))
    case = query.first()
    if case is None:
        return None

    if not force_rerun:
        if case.is_demo or case.public_id == "demo-001":
            from api.services.product_case_service import ensure_demo_patent_snapshot
            ensure_demo_patent_snapshot(db, case)

        existing_search = (
            db.query(PatentSearch)
            .filter(PatentSearch.product_case_id == case.id)
            .order_by(PatentSearch.created_at.desc())
            .first()
        )
        if existing_search:
            if case.is_demo or case.public_id == "demo-001":
                sc_raw = existing_search.search_concepts or ""
                if "DEMO_SHOWCASE_V3_PRECOMPUTED" not in sc_raw:
                    logger.info("Invalidating stale demo patent search ID %s", existing_search.id)
                    db.query(PatentRelevance).filter(PatentRelevance.search_id == existing_search.id).delete()
                    db.query(PatentSearch).filter(PatentSearch.id == existing_search.id).delete()
                    db.commit()
                    ensure_demo_patent_snapshot(db, case)
                    existing_search = (
                        db.query(PatentSearch)
                        .filter(PatentSearch.product_case_id == case.id)
                        .order_by(PatentSearch.created_at.desc())
                        .first()
                    )

        if existing_search:
            relevances = (
                db.query(PatentRelevance)
                .filter(PatentRelevance.search_id == existing_search.id)
                .all()
            )
            items = [_relevance_to_dict(r) for r in relevances]
            items.sort(key=lambda x: (x["relevance_score"] is not None, x["relevance_score"] if x["relevance_score"] is not None else -1), reverse=True)

            qp_raw = existing_search.search_concepts
            query_plan = []
            if qp_raw:
                try:
                    parsed_qp = json.loads(qp_raw)
                    if isinstance(parsed_qp, dict):
                        query_plan = parsed_qp.get("plan", [])
                    elif isinstance(parsed_qp, list):
                        query_plan = parsed_qp
                except Exception:
                    query_plan = []

            raw_disc = getattr(existing_search, "raw_discovered_count", None) or len(items)
            uniq_scr = getattr(existing_search, "unique_screened_count", None) or len(items)

            metrics = {
                "raw_discovered_count": raw_disc,
                "unique_screened_count": uniq_scr,
                "shortlisted_count": min(20, len(items)),
                "analyzed_count": len(items),
                "total_retrieved": len(items),
                "ai_attempted_count": min(20, len(items)),
                "ai_successful_count": sum(1 for i in items if i.get("relevance_level") in ("LOW", "MODERATE", "HIGH", "VERY_HIGH")),
                "not_shortlisted_count": max(0, uniq_scr - min(20, len(items))),
                "very_high_count": sum(1 for i in items if i.get("relevance_level") == "VERY_HIGH"),
                "high_count": sum(1 for i in items if i.get("relevance_level") == "HIGH"),
                "moderate_count": sum(1 for i in items if i.get("relevance_level") == "MODERATE"),
                "low_count": sum(1 for i in items if i.get("relevance_level") == "LOW"),
                "not_analyzed_count": sum(1 for i in items if i.get("relevance_level") == "NOT_ANALYZED"),
                "evidence_basis": "ABSTRACT-LEVEL SCREENING",
            }

            return {
                "search_id": existing_search.public_id,
                "product_case_id": case.public_id,
                "query_plan": query_plan,
                "summary_metrics": metrics,
                "results": items,
                "patents": items,
                "has_searched": True,
                "analysis_mode": "VERIFIED_DEMO_SNAPSHOT" if (case.is_demo or case.public_id == "demo-001") else "LIVE_SEARCH",
                "created_at": existing_search.created_at.isoformat() if existing_search.created_at else "",
            }
        else:
            # Fresh case with no prior search run — Return empty state without making provider or LLM calls
            return {
                "search_id": None,
                "product_case_id": case.public_id,
                "query_plan": [],
                "summary_metrics": {
                    "raw_discovered_count": 0,
                    "unique_screened_count": 0,
                    "shortlisted_count": 0,
                    "analyzed_count": 0,
                    "total_retrieved": 0,
                    "very_high_count": 0,
                    "high_count": 0,
                    "moderate_count": 0,
                    "low_count": 0,
                    "not_analyzed_count": 0,
                    "evidence_basis": "NO_SEARCH_PERFORMED",
                },
                "results": [],
                "patents": [],
                "has_searched": False,
                "message": "No prior-art patent search has been run for this case yet. Click 'Run Prior-Art Search' to initiate discovery.",
                "created_at": None,
            }

    # Explicit force rerun or initial run
    return run_patent_intelligence(db=db, owner=owner, case=case)


def run_patent_search(
    db: Session,
    owner: User,
    case_public_id: str,
    jurisdictions: Optional[List[str]] = None,
    limit: int = 20,
) -> Optional[dict]:
    """Legacy wrapper for manual patent search trigger."""
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

    return run_patent_intelligence(
        db=db, owner=owner, case=case, jurisdictions=jurisdictions, limit=limit
    )


def get_saved_patents(
    db: Session,
    owner: User,
    case_public_id: str,
) -> List[dict]:
    """Get all saved patent relevances for a Product Case."""
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

    relevances = (
        db.query(PatentRelevance)
        .filter(
            PatentRelevance.product_case_id == case.id,
            PatentRelevance.saved_by_user == True,
        )
        .order_by(PatentRelevance.created_at.desc())
        .all()
    )

    return [_relevance_to_dict(r) for r in relevances]


def save_patent(
    db: Session,
    owner: User,
    case_public_id: str,
    patent_record_id: str,
    relevance_level: Optional[str] = None,
    explanation: Optional[str] = None,
    overlap_component: Optional[str] = None,
    overlap_description: Optional[str] = None,
    user_notes: Optional[str] = None,
) -> Optional[dict]:
    """Save a patent record to a Product Case."""
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

    record = (
        db.query(PatentRecord)
        .filter(PatentRecord.public_id == patent_record_id)
        .first()
    )
    if record is None:
        return None

    existing = (
        db.query(PatentRelevance)
        .filter(
            PatentRelevance.product_case_id == case.id,
            PatentRelevance.patent_record_id == record.id,
            PatentRelevance.saved_by_user == True,
        )
        .first()
    )
    if existing:
        if relevance_level:
            existing.relevance_level = relevance_level
        if explanation:
            existing.explanation = explanation
        if user_notes:
            existing.user_notes = user_notes
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return _relevance_to_dict(existing)

    now = datetime.now(timezone.utc)
    relevance = PatentRelevance(
        product_case_id=case.id,
        patent_record_id=record.id,
        relevance_level=relevance_level or "MEDIUM",
        explanation=explanation,
        overlap_component=overlap_component,
        overlap_description=overlap_description,
        saved_by_user=True,
        user_notes=user_notes,
        created_at=now,
        updated_at=now,
    )
    db.add(relevance)
    db.commit()
    db.refresh(relevance)

    return _relevance_to_dict(relevance)


def retry_patent_ai_analysis(
    db: Session,
    owner: User,
    case_public_id: str,
) -> Optional[dict]:
    """Re-run AI semantic evaluation on existing persisted shortlisted candidates without re-querying Europe PMC."""
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

    existing_search = (
        db.query(PatentSearch)
        .filter(PatentSearch.product_case_id == case.id)
        .order_by(PatentSearch.created_at.desc())
        .first()
    )
    if not existing_search:
        return None

    relevances = (
        db.query(PatentRelevance)
        .filter(PatentRelevance.search_id == existing_search.id)
        .all()
    )
    if not relevances:
        return None

    candidates = []
    for rel in relevances:
        rec = rel.patent_record
        if not rec:
            continue

        inventors = None
        if rec.inventors:
            try:
                inventors = json.loads(rec.inventors)
            except Exception:
                inventors = [rec.inventors]

        family_members = []
        if rec.family_members_json:
            try:
                family_members = json.loads(rec.family_members_json)
            except Exception:
                family_members = []

        res = PatentResult(
            provider_record_id=rec.provider_record_id,
            source_name=rec.source_name or "EUROPE_PMC",
            authority=rec.authority or "EPO",
            jurisdiction=rec.jurisdiction or "EP",
            source_url=rec.source_url or "",
            publication_number=rec.publication_number,
            application_number=rec.application_number,
            patent_type=rec.patent_type or "PATENT",
            title=rec.title or "",
            abstract=rec.abstract or "",
            applicant=rec.applicant or "",
            inventors=inventors,
            priority_date=rec.priority_date or "",
            filing_date=rec.filing_date or "",
            publication_date=rec.publication_date or "",
            status=rec.status or "PUBLISHED",
            family_id=rec.family_id,
            family_members=family_members,
            matched_queries=_deserialize_list(rel.matched_queries_json),
        )

        candidates.append({
            "result": res,
            "matched_queries": res.matched_queries,
            "ing_matches": _deserialize_list(rel.matched_components_json),
            "relevance_record": rel,
        })

    if not candidates:
        return None

    analyzed_candidates = _analyze_patents_with_gemini(candidates, case)
    now = datetime.now(timezone.utc)

    for item in analyzed_candidates:
        res: PatentResult = item["result"]
        rec_key = res.publication_number or res.application_number or res.provider_record_id

        target_rel = None
        for cand in candidates:
            c_res: PatentResult = cand["result"]
            c_key = c_res.publication_number or c_res.application_number or c_res.provider_record_id
            if c_key == rec_key:
                target_rel = cand["relevance_record"]
                break

        if target_rel:
            target_rel.relevance_level = item["relevance_level"]
            target_rel.relevance_score = item["relevance_score"]
            target_rel.explanation = item["why_relevant"]
            target_rel.score_breakdown_json = json.dumps(item["score_breakdown"]) if item.get("score_breakdown") else None
            target_rel.matched_components_json = json.dumps(item["matched_components"])
            target_rel.matched_queries_json = json.dumps(item["matched_queries"])
            target_rel.why_relevant = item["why_relevant"]
            target_rel.important_difference = item["important_difference"]
            target_rel.limitations = item["limitations"]
            target_rel.overlap_component = item["matched_components"][0] if item["matched_components"] else None
            target_rel.overlap_description = item["why_relevant"]
            target_rel.updated_at = now
            db.commit()

    updated_relevances = (
        db.query(PatentRelevance)
        .filter(PatentRelevance.search_id == existing_search.id)
        .all()
    )
    items = [_relevance_to_dict(r) for r in updated_relevances]
    items.sort(key=lambda x: (x["relevance_score"] is not None, x["relevance_score"] if x["relevance_score"] is not None else -1), reverse=True)

    query_plan = _deserialize_list(existing_search.search_concepts)
    metrics = {
        "total_retrieved": len(items),
        "very_high_count": sum(1 for i in items if i.get("relevance_level") == "VERY_HIGH"),
        "high_count": sum(1 for i in items if i.get("relevance_level") == "HIGH"),
        "moderate_count": sum(1 for i in items if i.get("relevance_level") == "MODERATE"),
        "low_count": sum(1 for i in items if i.get("relevance_level") == "LOW"),
        "not_analyzed_count": sum(1 for i in items if i.get("relevance_level") == "NOT_ANALYZED"),
        "evidence_basis": "ABSTRACT-LEVEL SCREENING",
    }

    return {
        "search_id": existing_search.public_id,
        "product_case_id": case.public_id,
        "query_plan": query_plan,
        "summary_metrics": metrics,
        "results": items,
        "patents": items,
        "has_searched": True,
        "created_at": existing_search.created_at.isoformat() if existing_search.created_at else "",
    }
