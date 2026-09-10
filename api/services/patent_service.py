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

    return {
        "id": rec.public_id,
        "provider_record_id": provider_id,
        "source_name": rec.source_name,
        "authority": rec.authority,
        "jurisdiction": rec.jurisdiction,
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
        "score_breakdown": score_breakdown or {
            "technological_overlap": 0,
            "ingredient_overlap": 0,
            "formulation_process_overlap": 0,
            "claim_concept_overlap": 0,
        },
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

def generate_query_plan(case: ProductCase, components: List[InnovationComponent]) -> List[dict]:
    """Generate 5–10 structured search queries categorized by prior-art classification."""
    plan: List[dict] = []

    ingredients = _deserialize_list(case.ingredients) if case.ingredients else []
    ing_names = []
    botanical_names = []

    for ing in ingredients:
        name = ing.get("name", "") if isinstance(ing, dict) else str(ing)
        name_clean = name.strip()
        if name_clean:
            if "(" in name_clean and ")" in name_clean:
                common = name_clean.split("(")[0].strip()
                botanical = name_clean.split("(")[1].split(")")[0].strip()
                ing_names.append(common)
                botanical_names.append(botanical)
            else:
                ing_names.append(name_clean)

    # 1. BOTANICAL
    if botanical_names:
        bot_query = " OR ".join([f'"{b}"' for b in botanical_names[:3]])
        plan.append({
            "category": "BOTANICAL",
            "query": bot_query,
            "rationale": "Screens for prior art covering key active botanical species."
        })
    elif ing_names:
        plan.append({
            "category": "BOTANICAL",
            "query": " OR ".join([f'"{i}"' for i in ing_names[:3]]),
            "rationale": "Screens for prior art covering primary active ingredients."
        })

    # 2. COMBINATION
    if len(ing_names) >= 2 or (ing_names and botanical_names):
        comb_terms = (botanical_names if botanical_names else ing_names)[:3]
        comb_query = " AND ".join([f'"{t}"' for t in comb_terms])
        plan.append({
            "category": "COMBINATION",
            "query": comb_query,
            "rationale": "Screens for prior art covering multi-active synergistic combinations."
        })

    # 3. FORMULATION
    if case.formulation:
        form_query = f'"{case.formulation}" formulation'
        plan.append({
            "category": "FORMULATION",
            "query": form_query,
            "rationale": f"Screens for prior art on matrix and galenic structure ({case.formulation})."
        })
    elif case.form:
        plan.append({
            "category": "FORMULATION",
            "query": f'"{case.form}" herbal formulation',
            "rationale": f"Screens for prior art in product form ({case.form})."
        })

    # 4. PROCESS
    if case.process:
        proc_query = f'"{case.process}" extraction process'
        plan.append({
            "category": "PROCESS",
            "query": proc_query,
            "rationale": f"Screens for prior art regarding extraction / manufacturing process ({case.process})."
        })

    # 5. DELIVERY
    case_cat = getattr(case, "category", None)
    case_ind = getattr(case, "indications", None)
    if case.form or case_cat:
        delivery_term = case.form or case_cat or "topical"
        plan.append({
            "category": "DELIVERY",
            "query": f'"{delivery_term}" delivery composition',
            "rationale": "Screens for prior art on delivery system and targeted site action."
        })

    # 6. USE
    if case_ind or case.intended_use:
        inds = _deserialize_list(case_ind) if case_ind else []
        ind_str = inds[0] if inds else (case.intended_use or "therapeutic")
        plan.append({
            "category": "USE",
            "query": f'"{ind_str}" therapeutic composition',
            "rationale": f"Screens for prior art targeting indication ({ind_str})."
        })

    # 7. CLAIM_CONCEPT
    claims = _deserialize_list(case.claims) if case.claims else []
    if claims:
        claim_str = claims[0] if isinstance(claims[0], str) else claims[0].get("text", "")
        plan.append({
            "category": "CLAIM_CONCEPT",
            "query": f'"{claim_str[:40]}"',
            "rationale": "Screens for prior art matching primary product claim concepts."
        })

    # Add innovation components if needed to reach 5-10 queries
    if components:
        for comp in components:
            if len(plan) >= 10:
                break
            if comp.component_value:
                plan.append({
                    "category": "CLAIM_CONCEPT",
                    "query": f'"{comp.component_value}"',
                    "rationale": f"Screens for prior art on innovation component: {comp.component_type}."
                })

    # Ensure minimum 5 queries
    if len(plan) < 5 and case.name:
        plan.append({
            "category": "CLAIM_CONCEPT",
            "query": f'"{case.name}"',
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
        matched_queries = []
        for q in query_plan:
            q_raw = q.get("query", "").replace('"', '').lower()
            terms = [t.strip() for t in q_raw.split() if len(t.strip()) > 3 and t not in ("and", "or", "process", "formulation")]
            if any(t in text for t in terms):
                matched_queries.append(q.get("query", ""))

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

    # Clamp rule: if tech, form_proc, and claim_conc are all low (<= 20), cap score at 79 (HIGH)
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
        model = genai.GenerativeModel("gemini-1.5-flash")

        patent_payloads = []
        for item in candidates:
            res: PatentResult = item["result"]
            patent_payloads.append({
                "publication_number": res.publication_number or res.application_number,
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
    "publication_number": "...",
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

        response = model.generate_content(prompt)
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:]
        if text_resp.endswith("```"):
            text_resp = text_resp[:-3]
        text_resp = text_resp.strip()

        evaluations = json.loads(text_resp)
        eval_map = {e.get("publication_number"): e for e in evaluations if isinstance(e, dict)}

        analyzed = []
        for item in candidates:
            res: PatentResult = item["result"]
            pub_num = res.publication_number or res.application_number
            gem_eval = eval_map.get(pub_num)

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
                    "important_difference": gem_eval.get("important_difference", "Product case specifies standardized herbal ratios."),
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
    # Get components
    analysis = (
        db.query(InnovationAnalysis)
        .filter(InnovationAnalysis.product_case_id == case.id)
        .order_by(InnovationAnalysis.created_at.desc())
        .first()
    )
    components = list(analysis.components) if analysis else []

    # Generate Query Plan
    query_plan = generate_query_plan(case, components)

    # Search Google Patents Adapter
    registry = get_patent_registry()
    search_jurisdictions = jurisdictions or ["IN", "US", "EP", "WO", "GLOBAL"]

    # Gather search queries from plan
    keywords = [q["query"] for q in query_plan]

    responses = registry.search_all(
        query=case.name or "Ayurvedic formulation",
        keywords=keywords,
        jurisdictions=search_jurisdictions,
        limit=limit,
    )

    all_raw_results: List[PatentResult] = []
    for resp in responses:
        all_raw_results.extend(resp.results)

    # Deduplicate by publication_number & group families
    unique_candidates: Dict[str, PatentResult] = {}
    family_members_map: Dict[str, List[str]] = {}

    for res in all_raw_results:
        pub_num = res.publication_number or res.application_number
        if not pub_num:
            continue
        clean_pub = pub_num.replace(" ", "").upper()

        if clean_pub not in unique_candidates:
            unique_candidates[clean_pub] = res
            family_members_map[clean_pub] = [pub_num]
        else:
            if pub_num not in family_members_map[clean_pub]:
                family_members_map[clean_pub].append(pub_num)

    deduped_results = list(unique_candidates.values())

    # Pre-rank
    pre_ranked = _pre_rank_candidate_patents(deduped_results, case, query_plan)

    # Semantic evaluation on top candidates
    analyzed_candidates = _analyze_patents_with_gemini(pre_ranked[:20], case)

    now = datetime.now(timezone.utc)

    # Create Search session record
    search = PatentSearch(
        owner_id=owner.id,
        product_case_id=case.id,
        search_concepts=json.dumps(query_plan),
        jurisdictions_searched=json.dumps(search_jurisdictions),
        total_results=len(analyzed_candidates),
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
        clean_pub = pub_num.replace(" ", "").upper()
        f_members = family_members_map.get(clean_pub, [pub_num])

        # Check existing record
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
                jurisdiction=res.jurisdiction,
                source_url=res.source_url,
                publication_number=res.publication_number,
                application_number=res.application_number,
                patent_type=res.patent_type,
                title=res.title,
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

    # Sort descending by relevance score (placing non-null score items first)
    persisted_relevances.sort(key=lambda x: (x["relevance_score"] is not None, x["relevance_score"] if x["relevance_score"] is not None else -1), reverse=True)

    metrics = {
        "total_retrieved": len(persisted_relevances),
        "very_high_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "VERY_HIGH"),
        "high_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "HIGH"),
        "moderate_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "MODERATE"),
        "low_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "LOW"),
        "not_analyzed_count": sum(1 for i in persisted_relevances if i.get("relevance_level") == "NOT_ANALYZED"),
        "evidence_basis": "ABSTRACT-LEVEL SCREENING",
    }

    return {
        "search_id": search.public_id,
        "product_case_id": case.public_id,
        "query_plan": query_plan,
        "summary_metrics": metrics,
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

    if not force_rerun:
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
        else:
            # Fresh case with no prior search run — Return empty state without making provider or LLM calls
            return {
                "search_id": None,
                "product_case_id": case.public_id,
                "query_plan": [],
                "summary_metrics": {
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
