"""AYUR-INTEL — Gemini-Backed AI Risk Intelligence Service.

Synthesizes bounded case evidence (Product Passport, Patent Intelligence,
Regulatory Pathways, Knowledge Evidence, Innovation Analysis) into
structured decision-support risk intelligence.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.core.config import settings
from api.models.models import (
    User, ProductCase,
    InnovationAnalysis, InnovationComponent,
    PatentRecord, PatentSearch, PatentRelevance, PatentAnalysis, PatentComparison, ClaimElement,
    RegulatoryProfile, RegulatoryRequirement,
)
from api.models.evidence import UnifiedEvidence, CaseFinding
from api.models.risk import Risk, RiskEvidence, RiskAssessment

logger = logging.getLogger("ayur_intel.gemini_risk_service")


def _deserialize(val: Any) -> Any:
    """Helper to parse JSON string or return val."""
    if val is None:
        return []
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return []
        try:
            return json.loads(val)
        except Exception:
            return []
    return []


# ---------------------------------------------------------------------------
# 1. Context Gathering & Evidence Key Indexing
# ---------------------------------------------------------------------------

def gather_case_risk_context(
    db: Session, case: ProductCase
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]], Dict[str, str]]:
    """Extract bounded structured context from all available case intelligence.

    Returns:
        (context_dict, valid_evidence_keys, evidence_coverage)
    """
    valid_keys: Dict[str, Dict[str, str]] = {}
    coverage: Dict[str, str] = {
        "product_passport": "Complete",
        "patent_intelligence": "Not Run",
        "regulatory_pathways": "Not Run",
        "knowledge_evidence": "Not Run",
        "innovation_analysis": "Not Run",
    }

    # --- 1. Product Passport ---
    ingredients_raw = _deserialize(case.ingredients)
    claims_raw = _deserialize(case.claims)
    jurisdictions_raw = _deserialize(case.jurisdictions)

    ingredients_summary = []
    for ing in (ingredients_raw if isinstance(ingredients_raw, list) else []):
        if isinstance(ing, dict):
            name = ing.get("name") or ing.get("input_name") or "Unknown"
            botanical = ing.get("botanical") or ing.get("botanical_name") or ""
            qty = ing.get("quantity") or ""
            status = ing.get("status") or ing.get("verification_status") or "VERIFIED"
            ingredients_summary.append({
                "name": name,
                "botanical": botanical,
                "quantity": qty,
                "status": status,
                "source": ing.get("source", ""),
                "indication": ing.get("therapeutic_indication", ""),
            })
            key = f"passport:ingredient:{name.lower().replace(' ', '_')}"
            valid_keys[key] = {
                "source_type": "passport",
                "label": f"Ingredient: {name} ({botanical})" if botanical else f"Ingredient: {name}",
            }
        elif isinstance(ing, str) and ing.strip():
            ingredients_summary.append({"name": ing.strip(), "status": "UNVERIFIED"})

    valid_keys["passport:identity"] = {"source_type": "passport", "label": f"Product Identity ({case.name})"}
    valid_keys["passport:formulation"] = {"source_type": "passport", "label": "Formulation & Dosage Form"}
    if claims_raw:
        valid_keys["passport:claims"] = {"source_type": "passport", "label": "Proposed Product Claims"}

    passport_context = {
        "name": case.name,
        "stage": case.stage or "IDEA",
        "form": case.form or "Not specified",
        "intended_use": case.intended_use or "Not specified",
        "formulation": case.formulation or "Not specified",
        "process": case.process or "Not specified",
        "brand": case.brand or "Not specified",
        "packaging": case.packaging or "Not specified",
        "jurisdictions": jurisdictions_raw or ["IN"],
        "claims": claims_raw or [],
        "ingredients": ingredients_summary,
    }

    # --- 2. Patent Intelligence ---
    patent_analyses = db.query(PatentAnalysis).filter(PatentAnalysis.product_case_id == case.id).all()
    patent_relevances = db.query(PatentRelevance).filter(PatentRelevance.product_case_id == case.id).all()
    patent_searches = db.query(PatentSearch).filter(PatentSearch.product_case_id == case.id).all()

    if patent_analyses or patent_relevances or patent_searches:
        coverage["patent_intelligence"] = "Available"
        valid_keys["patent:search_landscape"] = {"source_type": "patent", "label": "Indian Patent Landscape Search (IPO/CGPDTM)"}

        patent_items = []
        for pa in patent_analyses:
            pr = pa.patent_record
            pub_num = pr.publication_number if pr else "UNKNOWN_PATENT"
            p_key = f"patent:{pub_num}"
            valid_keys[p_key] = {
                "source_type": "patent",
                "label": f"Patent {pub_num} - {pr.title if pr else 'Prior Art'}",
            }
            patent_items.append({
                "publication_number": pub_num,
                "title": pr.title if pr else "Patent Record",
                "authority": pr.authority if pr else "IPO",
                "overall_relevance": pa.overall_relevance,
                "confidence": pa.overall_confidence,
                "summary": pa.summary,
            })

        for pr_rel in patent_relevances:
            pr = pr_rel.patent_record
            if pr and pr.publication_number:
                p_key = f"patent:{pr.publication_number}"
                if p_key not in valid_keys:
                    valid_keys[p_key] = {
                        "source_type": "patent",
                        "label": f"Patent {pr.publication_number}: {pr.title or 'Relevant Art'}",
                    }

        patent_context = {
            "status": "AVAILABLE",
            "total_records_analyzed": len(patent_analyses),
            "analyses": patent_items,
            "searches_count": len(patent_searches),
        }
    else:
        patent_context = {
            "status": "NOT_AVAILABLE",
            "summary": "Patent search / analysis has not been performed yet for this product case.",
        }

    # --- 3. Regulatory Pathways ---
    reg_profiles = db.query(RegulatoryProfile).filter(RegulatoryProfile.product_case_id == case.id).all()
    if reg_profiles:
        coverage["regulatory_pathways"] = "Available"
        reg_items = []
        for rp in reg_profiles:
            r_key = f"regulatory:{rp.jurisdiction}"
            valid_keys[r_key] = {
                "source_type": "regulatory",
                "label": f"Regulatory Profile ({rp.jurisdiction} - {rp.potential_category or 'AYUSH/FSSAI'})",
            }
            reqs = db.query(RegulatoryRequirement).filter(RegulatoryRequirement.profile_id == rp.id).all()
            reqs_summary = [
                {"title": r.title, "authority": r.authority, "applicability": r.applicability, "status": r.status}
                for r in reqs[:6]
            ]
            reg_items.append({
                "jurisdiction": rp.jurisdiction,
                "potential_category": rp.potential_category,
                "category_confidence": rp.category_confidence,
                "category_reasoning": rp.category_reasoning,
                "total_requirements": rp.total_requirements,
                "needs_verification_count": rp.needs_verification_count,
                "status": rp.status,
                "requirements": reqs_summary,
            })
        regulatory_context = {
            "status": "AVAILABLE",
            "profiles": reg_items,
        }
    else:
        regulatory_context = {
            "status": "NOT_AVAILABLE",
            "summary": "Regulatory pathway analysis has not been executed yet for this case.",
        }

    # --- 4. Knowledge & Unified Evidence ---
    case_findings = db.query(CaseFinding).filter(CaseFinding.product_case_id == case.id).all()
    if case_findings:
        coverage["knowledge_evidence"] = "Available"
        findings_summary = []
        for cf in case_findings[:6]:
            k_key = f"knowledge:finding_{cf.id}"
            valid_keys[k_key] = {
                "source_type": "knowledge",
                "label": f"Evidence Finding: {cf.title[:40]}",
            }
            findings_summary.append({
                "title": cf.title,
                "confidence": cf.confidence,
                "evidence_status": cf.evidence_status,
                "summary": cf.summary,
            })
        knowledge_context = {
            "status": "AVAILABLE",
            "findings": findings_summary,
        }
    else:
        knowledge_context = {
            "status": "NOT_AVAILABLE",
            "summary": "No unified knowledge findings recorded for this case.",
        }

    # --- 5. Innovation Analysis ---
    innov_analysis = db.query(InnovationAnalysis).filter(InnovationAnalysis.product_case_id == case.id).first()
    if innov_analysis:
        coverage["innovation_analysis"] = "Available"
        valid_keys["innovation:decomposition"] = {
            "source_type": "innovation",
            "label": "Innovation Decomposition Map",
        }
        components = db.query(InnovationComponent).filter(InnovationComponent.analysis_id == innov_analysis.id).all()
        innov_context = {
            "status": "AVAILABLE",
            "novelty_score": innov_analysis.overall_novelty_score,
            "differentiation_summary": innov_analysis.differentiation_summary,
            "components": [
                {
                    "type": c.component_type,
                    "label": c.component_label,
                    "novelty_signal": c.novelty_signal,
                    "notes": c.differentiation_notes,
                }
                for c in components[:6]
            ],
        }
    else:
        innov_context = {
            "status": "NOT_AVAILABLE",
            "summary": "Innovation analysis has not been run for this product case.",
        }

    full_context = {
        "product_passport": passport_context,
        "patent_intelligence": patent_context,
        "regulatory_pathways": regulatory_context,
        "knowledge_evidence": knowledge_context,
        "innovation_analysis": innov_context,
    }

    return full_context, valid_keys, coverage


# ---------------------------------------------------------------------------
# 2. Deterministic Rule-Based Fallback Engine
# ---------------------------------------------------------------------------

def generate_fallback_risk_assessment(
    context: Dict[str, Any],
    valid_evidence_keys: Dict[str, Dict[str, str]],
    coverage: Dict[str, str],
) -> Dict[str, Any]:
    """Deterministic, transparent rule-based risk evaluation.

    Used when Gemini is unconfigured or unavailable.
    """
    passport = context.get("product_passport", {})
    patents = context.get("patent_intelligence", {})
    regulatory = context.get("regulatory_pathways", {})
    ingredients = passport.get("ingredients", [])
    claims = passport.get("claims", [])
    product_name = passport.get("name", "Product Case")

    risks: List[Dict[str, Any]] = []
    gaps: List[str] = []

    # --- Domain 1: IP & Patent Risk ---
    ip_score = 25
    ip_level = "LOW"
    ip_conf = 0.85
    ip_summary = "No immediate patent infringement risk identified from available data."

    if patents.get("status") == "AVAILABLE":
        high_overlap = False
        medium_overlap = False
        overlap_patents = []
        for a in patents.get("analyses", []):
            rel = str(a.get("overall_relevance", ""))
            pub = a.get("publication_number", "")
            if "HIGH" in rel:
                high_overlap = True
                overlap_patents.append(pub)
            elif "MEDIUM" in rel:
                medium_overlap = True
                overlap_patents.append(pub)

        if high_overlap:
            ip_score = 75
            ip_level = "HIGH"
            ip_summary = f"High claim overlap detected with {len(overlap_patents)} patent publication(s) in Indian patent landscape."
            p_ref = f"patent:{overlap_patents[0]}" if overlap_patents and f"patent:{overlap_patents[0]}" in valid_evidence_keys else "patent:search_landscape"
            risks.append({
                "id": "ip-overlap-01",
                "title": "Patent Claim Overlap with Active Prior Art",
                "domain": "IP & Patent",
                "severity": "HIGH",
                "likelihood": "HIGH",
                "impact": "HIGH",
                "confidence": 0.88,
                "why_it_matters": "Active patent claims cover formulation ratios and extraction methods closely resembling your product specifications.",
                "evidence_refs": [{"source_type": "patent", "reference_key": p_ref}],
                "evidence_status": "SUPPORTED",
                "recommended_action": "Conduct a formal claim element comparison and design around overlapping claims prior to commercial filing.",
                "requires_human_verification": True,
            })
        elif medium_overlap:
            ip_score = 50
            ip_level = "MODERATE"
            ip_summary = "Moderate prior art similarity found. Requires verification of specific formulation ratios."
            risks.append({
                "id": "ip-overlap-02",
                "title": "Moderate Prior Art Similarity in Extraction Process",
                "domain": "IP & Patent",
                "severity": "MODERATE",
                "likelihood": "MEDIUM",
                "impact": "MEDIUM",
                "confidence": 0.80,
                "why_it_matters": "Similar solvent extraction and delivery mechanisms exist in published patent literature.",
                "evidence_refs": [{"source_type": "patent", "reference_key": "patent:search_landscape"}],
                "evidence_status": "SUPPORTED",
                "recommended_action": "Review dependent claims in relevant patent filings to confirm distinction in concentration or synergistic ratios.",
                "requires_human_verification": True,
            })
    else:
        ip_score = 55
        ip_level = "MODERATE"
        ip_conf = 0.50
        ip_summary = "Patent risk cannot be fully established because Patent Intelligence has not yet been executed."
        gaps.append("Patent Intelligence has not been generated for this case. Freedom-to-operate signals remain unverified.")
        risks.append({
            "id": "ip-gap-01",
            "title": "Unassessed Patent Freedom-to-Operate Exposure",
            "domain": "IP & Patent",
            "severity": "MODERATE",
            "likelihood": "MEDIUM",
            "impact": "HIGH",
            "confidence": 0.50,
            "why_it_matters": "Operating without patent intelligence leaves unmonitored risk of colliding with third-party IP rights in India.",
            "evidence_refs": [{"source_type": "passport", "reference_key": "passport:identity"}],
            "evidence_status": "MISSING",
            "recommended_action": "Run Patent Intelligence module to search IPO databases against your botanical ingredients and processes.",
            "requires_human_verification": True,
        })

    # --- Domain 2: Regulatory Risk ---
    reg_score = 30
    reg_level = "LOW"
    reg_conf = 0.80
    reg_summary = "Product aligns with recognized Ayurvedic/nutraceutical frameworks."

    if regulatory.get("status") == "AVAILABLE":
        for p in regulatory.get("profiles", []):
            jurisdiction = p.get("jurisdiction", "IN")
            cat_conf = p.get("category_confidence", "MEDIUM")
            cat = p.get("potential_category", "AYUSH / FSSAI")
            r_key = f"regulatory:{jurisdiction}" if f"regulatory:{jurisdiction}" in valid_evidence_keys else "passport:identity"

            if cat_conf in ("LOW", "LIMITED"):
                reg_score = max(reg_score, 68)
                reg_level = "HIGH"
                reg_summary = f"Regulatory classification between AYUSH (ASU Drug) and FSSAI (Nutraceutical) is borderline."
                risks.append({
                    "id": "reg-class-01",
                    "title": f"Borderline Regulatory Classification ({jurisdiction})",
                    "domain": "Regulatory",
                    "severity": "HIGH",
                    "likelihood": "HIGH",
                    "impact": "HIGH",
                    "confidence": 0.82,
                    "why_it_matters": "Ambiguity between Ayurvedic Proprietary Medicine (D&C Act) and FSSAI Nutraceutical regulations may lead to licensing rejection or marketing delays.",
                    "evidence_refs": [{"source_type": "regulatory", "reference_key": r_key}],
                    "evidence_status": "SUPPORTED",
                    "recommended_action": f"Confirm statutory filing route with State Licensing Authority (AYUSH) before submitting dossier.",
                    "requires_human_verification": True,
                })
            else:
                reg_score = max(reg_score, 45)
                reg_level = "MODERATE"
                reg_summary = f"Classified under {cat} for {jurisdiction}. Mandatory statutory documentation required."
    else:
        reg_score = 60
        reg_level = "MODERATE"
        reg_conf = 0.55
        reg_summary = "Regulatory pathway not yet computed. Applicable statutory requirements unverified."
        gaps.append("Regulatory Pathways analysis has not been executed. Target jurisdiction requirements must be verified.")

    # --- Domain 3: Claims & Compliance Risk ---
    claims_score = 25
    claims_level = "LOW"
    claims_conf = 0.85
    claims_summary = "Claims wording complies with standard Ayurvedic wellness terminology."

    treatment_keywords = ["treat", "cure", "heal", "prevent", "diagnose", "remedy", "disease", "cancer", "diabetes", "alzheimer"]
    flagged_claims = []
    for c_text in claims:
        if isinstance(c_text, str) and any(kw in c_text.lower() for kw in treatment_keywords):
            flagged_claims.append(c_text)

    if flagged_claims:
        claims_score = 78
        claims_level = "HIGH"
        claims_summary = f"Therapeutic/disease treatment claims detected that exceed allowable OTC wellness advertising bounds."
        c_ref = "passport:claims" if "passport:claims" in valid_evidence_keys else "passport:identity"
        risks.append({
            "id": "claim-treat-01",
            "title": "Therapeutic Treatment Claim Exposure under Advertising Standards",
            "domain": "Claims & Compliance",
            "severity": "HIGH",
            "likelihood": "HIGH",
            "impact": "HIGH",
            "confidence": 0.90,
            "why_it_matters": "Disease treatment claims trigger stringent clinical trial mandates under Drugs & Magic Remedies Act and ASCI guidelines.",
            "evidence_refs": [{"source_type": "passport", "reference_key": c_ref}],
            "evidence_status": "SUPPORTED",
            "recommended_action": "Revise label claims from curative ('treats/cures') to supportive wellness claims ('supports cognitive vitality/promotes calm').",
            "requires_human_verification": True,
        })
    elif not claims:
        claims_score = 45
        claims_level = "MODERATE"
        claims_summary = "No explicit product claims defined yet in Product Passport."
        gaps.append("Proposed promotional and label claims are missing from the Product Passport.")

    # --- Domain 4: Ingredient & Formulation Risk ---
    ing_score = 30
    ing_level = "LOW"
    ing_conf = 0.85
    ing_summary = "Botanical ingredients have established Ayurvedic classical references."

    unverified_ings = [i.get("name") for i in ingredients if i.get("status") in ("UNVERIFIED", "NEEDS_VERIFICATION")]
    if unverified_ings:
        ing_score = 58
        ing_level = "MODERATE"
        ing_summary = f"Botanical identity or standard extract ratio unverified for: {', '.join(unverified_ings[:2])}."
        risks.append({
            "id": "ing-verify-01",
            "title": "Botanical Identity & Standardization Verification Needed",
            "domain": "Ingredient & Formulation",
            "severity": "MODERATE",
            "likelihood": "MEDIUM",
            "impact": "MEDIUM",
            "confidence": 0.85,
            "why_it_matters": "Standardization of active markers is required for quality consistency and pharmacopoeial compliance (API / IP).",
            "evidence_refs": [{"source_type": "passport", "reference_key": "passport:ingredients"} if "passport:ingredients" in valid_evidence_keys else {"source_type": "passport", "reference_key": "passport:identity"}],
            "evidence_status": "PARTIAL",
            "recommended_action": "Attach Certificate of Analysis (CoA) with quantified bioactive markers for all active raw botanicals.",
            "requires_human_verification": True,
        })

    # --- Domain 5: Market / Commercial Risk ---
    market_score = 40
    market_level = "MODERATE"
    market_conf = 0.75
    market_summary = "Competitive category with strong demand for evidence-backed standardization."

    # Compute overall score
    domain_scores = [
        {"domain": "IP & Patent", "score": ip_score, "level": ip_level, "confidence": ip_conf, "summary": ip_summary},
        {"domain": "Regulatory", "score": reg_score, "level": reg_level, "confidence": reg_conf, "summary": reg_summary},
        {"domain": "Claims & Compliance", "score": claims_score, "level": claims_level, "confidence": claims_conf, "summary": claims_summary},
        {"domain": "Ingredient & Formulation", "score": ing_score, "level": ing_level, "confidence": ing_conf, "summary": ing_summary},
        {"domain": "Market / Commercial", "score": market_score, "level": market_level, "confidence": market_conf, "summary": market_summary},
    ]

    overall_score = round(sum(d["score"] for d in domain_scores) / len(domain_scores))
    if overall_score >= 70:
        overall_level = "CRITICAL" if overall_score >= 85 else "HIGH"
    elif overall_score >= 40:
        overall_level = "MODERATE"
    else:
        overall_level = "LOW"

    overall_conf = round(sum(d["confidence"] for d in domain_scores) / len(domain_scores), 2)

    # Sort risks by severity
    sev_rank = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1}
    risks.sort(key=lambda x: sev_rank.get(x.get("severity", "LOW"), 0), reverse=True)

    # Mitigation plan
    mitigation_plan = {
        "immediate": [
            "Review and adjust proposed marketing claims to ensure alignment with OTC Ayurvedic guidance.",
            "Verify raw material botanical species identity and obtain active ingredient CoAs.",
        ],
        "before_regulatory_submission": [
            "Finalize product dossier classification under appropriate AYUSH/FSSAI schedule.",
            "Perform heavy metal, pesticide, and microbial validation tests per pharmacopoeial standards.",
        ],
        "before_market_launch": [
            "Complete Freedom-to-Operate claim comparison against active IPO patent filings.",
            "Confirm compliant packaging artwork with mandatory statutory declarations.",
        ],
    }

    if not gaps:
        gaps.append("All primary intelligence dimensions have been incorporated into this assessment.")

    return {
        "overall_risk": {
            "score": overall_score,
            "level": overall_level,
            "confidence": overall_conf,
            "summary": f"Primary exposure is concentrated around {risks[0]['domain'] if risks else 'compliance'} and formulation standardization.",
        },
        "domain_scores": domain_scores,
        "top_risks": risks[:4],
        "mitigation_plan": mitigation_plan,
        "evidence_gaps": gaps,
        "disclaimer": "This assessment synthesizes available AYUR-INTEL evidence using deterministic decision-support rules. It does not constitute legal, patent, or medical clearance.",
    }


# ---------------------------------------------------------------------------
# 3. Gemini AI Synthesis
# ---------------------------------------------------------------------------

def _build_gemini_prompt(
    context: Dict[str, Any], valid_evidence_keys: Dict[str, Dict[str, str]]
) -> str:
    """Construct bounded, safety-delimited prompt for Gemini."""
    keys_list_str = "\n".join([f"- {k}: ({v.get('source_type')}) {v.get('label')}" for k, v in valid_evidence_keys.items()])

    prompt = f"""
You are the AYUR-INTEL AI Risk Intelligence Engine, specialized in Ayurvedic intellectual property, Indian patent law (CGPDTM/IPO), and statutory regulatory compliance (AYUSH, FSSAI, Drugs & Cosmetics Act).

Your task: Synthesize the supplied product case intelligence into a structured, evidence-aware, decision-support risk assessment.

STRICT INSTRUCTIONS:
1. USE ONLY the supplied case data and reasonable domain inference.
2. NEVER invent patents, publication numbers, regulatory authorities, clinical trials, or evidence keys.
3. You may ONLY reference evidence keys from the "VALID EVIDENCE KEYS" list below in your "evidence_refs". If a finding has no matching key, use "passport:identity" or set evidence_status to "INFERRED" or "MISSING".
4. If patent or regulatory intelligence is marked "NOT_AVAILABLE", explicitly state that patent/regulatory risk cannot be fully confirmed due to missing analysis. DO NOT fabricate patent overlaps.
5. Highlight uncertainty and identify evidence gaps.
6. Provide concise, actionable mitigation steps.
7. Return ONLY valid JSON matching the exact output schema. Do NOT wrap with commentary.

VALID EVIDENCE KEYS (Use only these keys in evidence_refs):
{keys_list_str}

SUPPLIED PRODUCT CASE INTELLIGENCE:
```json
{json.dumps(context, indent=2)}
```

OUTPUT SCHEMA (Return strictly this JSON structure):
{{
  "overall_risk": {{
    "score": 0-100,
    "level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
    "confidence": 0.0-1.0,
    "summary": "1-2 sentence executive summary of key risk exposure"
  }},
  "domain_scores": [
    {{
      "domain": "IP & Patent",
      "score": 0-100,
      "level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
      "confidence": 0.0-1.0,
      "summary": "Summary of IP risk"
    }},
    {{
      "domain": "Regulatory",
      "score": 0-100,
      "level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
      "confidence": 0.0-1.0,
      "summary": "Summary of regulatory risk"
    }},
    {{
      "domain": "Claims & Compliance",
      "score": 0-100,
      "level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
      "confidence": 0.0-1.0,
      "summary": "Summary of claims risk"
    }},
    {{
      "domain": "Ingredient & Formulation",
      "score": 0-100,
      "level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
      "confidence": 0.0-1.0,
      "summary": "Summary of ingredient risk"
    }},
    {{
      "domain": "Market / Commercial",
      "score": 0-100,
      "level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
      "confidence": 0.0-1.0,
      "summary": "Summary of commercial risk"
    }}
  ],
  "top_risks": [
    {{
      "id": "stable-id-key",
      "title": "Clear concise risk title",
      "domain": "IP & Patent" | "Regulatory" | "Claims & Compliance" | "Ingredient & Formulation" | "Market / Commercial",
      "severity": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
      "likelihood": "LOW" | "MEDIUM" | "HIGH",
      "impact": "LOW" | "MEDIUM" | "HIGH",
      "confidence": 0.0-1.0,
      "why_it_matters": "Direct explanation of consequences",
      "evidence_refs": [
        {{
          "source_type": "passport" | "patent" | "regulatory" | "knowledge" | "innovation",
          "reference_key": "valid-key-from-above-list"
        }}
      ],
      "evidence_status": "SUPPORTED" | "PARTIAL" | "INFERRED" | "MISSING",
      "recommended_action": "Actionable mitigation recommendation",
      "requires_human_verification": true
    }}
  ],
  "mitigation_plan": {{
    "immediate": ["Action 1", "Action 2"],
    "before_regulatory_submission": ["Action 1", "Action 2"],
    "before_market_launch": ["Action 1", "Action 2"]
  }},
  "evidence_gaps": [
    "Specific missing evidence or unrun intelligence item"
  ],
  "disclaimer": "This assessment synthesizes available AYUR-INTEL evidence using AI. It is decision-support information and does not constitute legal, patent, medical, or regulatory clearance."
}}
"""
    return prompt


def synthesize_risk_with_gemini(
    context: Dict[str, Any],
    valid_evidence_keys: Dict[str, Dict[str, str]],
    coverage: Dict[str, str],
) -> Tuple[Dict[str, Any], str, Optional[str]]:
    """Synthesize risk intelligence using Gemini API, or fall back to Rule Engine.

    Returns:
        (assessment_data, assessment_source, model_used)
        where assessment_source is "GEMINI" | "RULE_ENGINE"
    """
    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("AYURINTEL_GEMINI_API_KEY")
        or settings.GEMINI_API_KEY
        or settings.AYURINTEL_GEMINI_API_KEY
    )

    if not api_key:
        logger.info("ℹ️ Gemini API key not configured — using deterministic rule engine.")
        fallback = generate_fallback_risk_assessment(context, valid_evidence_keys, coverage)
        return fallback, "RULE_ENGINE", None

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"response_mime_type": "application/json"}
        )

        prompt = _build_gemini_prompt(context, valid_evidence_keys)
        logger.info("Calling Gemini API (%s) for Risk Intelligence...", model_name)
        response = model.generate_content(prompt)

        raw_text = response.text.strip() if response and response.text else ""
        if not raw_text:
            raise ValueError("Empty response received from Gemini API.")

        # Strip markdown fences if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        parsed_json = json.loads(raw_text)
        validated = validate_and_sanitize_risk_data(parsed_json, valid_evidence_keys, coverage)
        logger.info("✅ Gemini AI Risk Assessment generated and validated successfully.")
        return validated, "GEMINI", model_name

    except Exception as e:
        logger.warning("⚠️ Gemini API call failed (%s) — safely engaging rule-based fallback.", str(e))
        fallback = generate_fallback_risk_assessment(context, valid_evidence_keys, coverage)
        return fallback, "RULE_ENGINE", None


# ---------------------------------------------------------------------------
# 4. Response Validation & Reference Filtering
# ---------------------------------------------------------------------------

def validate_and_sanitize_risk_data(
    data: Dict[str, Any],
    valid_evidence_keys: Dict[str, Dict[str, str]],
    coverage: Dict[str, str],
) -> Dict[str, Any]:
    """Validate structure, clamp values, sanitize enums, and filter invalid evidence keys."""
    if not isinstance(data, dict):
        raise ValueError("Invalid payload: expected root object.")

    # Overall Risk
    ov = data.get("overall_risk") or {}
    score = max(0, min(100, int(ov.get("score", 50))))
    level = str(ov.get("level", "MODERATE")).upper()
    if level not in ("LOW", "MODERATE", "HIGH", "CRITICAL"):
        level = "MODERATE"
    conf = max(0.0, min(1.0, float(ov.get("confidence", 0.8))))
    summary = str(ov.get("summary") or "Synthesized risk evaluation based on case data.")

    overall_risk = {
        "score": score,
        "level": level,
        "confidence": round(conf, 2),
        "summary": summary,
    }

    # Domain Scores
    domain_scores = []
    raw_domains = data.get("domain_scores") or []

    for d in raw_domains:
        if not isinstance(d, dict):
            continue
        d_name = d.get("domain", "General")
        d_score = max(0, min(100, int(d.get("score", 50))))
        d_level = str(d.get("level", "MODERATE")).upper()
        if d_level not in ("LOW", "MODERATE", "HIGH", "CRITICAL"):
            d_level = "MODERATE"
        d_conf = max(0.0, min(1.0, float(d.get("confidence", 0.8))))
        d_sum = str(d.get("summary") or "")
        domain_scores.append({
            "domain": d_name,
            "score": d_score,
            "level": d_level,
            "confidence": round(d_conf, 2),
            "summary": d_sum,
        })

    # Top Risks & Evidence Reference Filtering
    top_risks = []
    raw_risks = data.get("top_risks") or []
    seen_titles = set()

    for idx, r in enumerate(raw_risks):
        if not isinstance(r, dict):
            continue
        title = str(r.get("title") or f"Risk Item #{idx+1}").strip()
        if title in seen_titles:
            continue
        seen_titles.add(title)

        r_id = str(r.get("id") or f"risk-{idx+1}").lower().replace(" ", "-")
        r_domain = str(r.get("domain") or "General")
        r_sev = str(r.get("severity") or "MODERATE").upper()
        if r_sev not in ("LOW", "MODERATE", "HIGH", "CRITICAL"):
            r_sev = "MODERATE"

        r_lik = str(r.get("likelihood") or "MEDIUM").upper()
        if r_lik not in ("LOW", "MEDIUM", "HIGH"):
            r_lik = "MEDIUM"

        r_imp = str(r.get("impact") or "MEDIUM").upper()
        if r_imp not in ("LOW", "MEDIUM", "HIGH"):
            r_imp = "MEDIUM"

        r_conf = max(0.0, min(1.0, float(r.get("confidence", 0.8))))
        why = str(r.get("why_it_matters") or "")
        action = str(r.get("recommended_action") or "Verify compliance and risk factors.")
        human_req = bool(r.get("requires_human_verification", True))

        # Filter and validate evidence refs
        raw_refs = r.get("evidence_refs") or []
        validated_refs = []
        for ref in raw_refs:
            if not isinstance(ref, dict):
                continue
            k = ref.get("reference_key", "").strip()
            if k in valid_evidence_keys:
                ref_info = valid_evidence_keys[k]
                validated_refs.append({
                    "source_type": ref_info.get("source_type", ref.get("source_type", "passport")),
                    "reference_key": k,
                    "label": ref_info.get("label", k),
                })

        # If no valid refs matched, fallback to passport identity
        if not validated_refs:
            validated_refs.append({
                "source_type": "passport",
                "reference_key": "passport:identity",
                "label": valid_evidence_keys.get("passport:identity", {}).get("label", "Product Passport"),
            })

        ev_status = str(r.get("evidence_status") or "SUPPORTED").upper()
        if ev_status not in ("SUPPORTED", "PARTIAL", "INFERRED", "MISSING"):
            ev_status = "SUPPORTED"

        top_risks.append({
            "id": r_id,
            "title": title,
            "domain": r_domain,
            "severity": r_sev,
            "likelihood": r_lik,
            "impact": r_imp,
            "confidence": round(r_conf, 2),
            "why_it_matters": why,
            "evidence_refs": validated_refs,
            "evidence_status": ev_status,
            "recommended_action": action,
            "requires_human_verification": human_req,
        })

    # Mitigation Plan
    raw_mit = data.get("mitigation_plan") or {}
    mitigation_plan = {
        "immediate": [str(x) for x in raw_mit.get("immediate", []) if str(x).strip()],
        "before_regulatory_submission": [str(x) for x in raw_mit.get("before_regulatory_submission", []) if str(x).strip()],
        "before_market_launch": [str(x) for x in raw_mit.get("before_market_launch", []) if str(x).strip()],
    }

    # Evidence Gaps
    raw_gaps = data.get("evidence_gaps") or []
    evidence_gaps = [str(g) for g in raw_gaps if str(g).strip()]

    disclaimer = str(
        data.get("disclaimer")
        or "This assessment synthesizes available AYUR-INTEL evidence using decision-support intelligence. It is not legal or regulatory advice."
    )

    return {
        "overall_risk": overall_risk,
        "domain_scores": domain_scores,
        "top_risks": top_risks,
        "mitigation_plan": mitigation_plan,
        "evidence_gaps": evidence_gaps,
        "disclaimer": disclaimer,
    }


# ---------------------------------------------------------------------------
# 5. Database Persistence & Atomic Synchronization
# ---------------------------------------------------------------------------

def save_or_replace_risk_assessment(
    db: Session,
    user: User,
    case: ProductCase,
    assessment_dict: Dict[str, Any],
    source: str,
    model_used: Optional[str],
    coverage: Dict[str, str],
) -> RiskAssessment:
    """Atomically persist complete RiskAssessment and synchronize legacy Risk rows."""
    now = datetime.now(timezone.utc)
    ov = assessment_dict.get("overall_risk", {})

    existing = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == case.id).first()
    if existing:
        assessment_record = existing
        assessment_record.assessment_source = source
        assessment_record.model_used = model_used
        assessment_record.overall_score = int(ov.get("score", 50))
        assessment_record.overall_level = ov.get("level", "MODERATE")
        assessment_record.overall_confidence = float(ov.get("confidence", 0.80))
        assessment_record.overall_summary = ov.get("summary", "")
        assessment_record.domain_scores_json = json.dumps(assessment_dict.get("domain_scores", []))
        assessment_record.top_risks_json = json.dumps(assessment_dict.get("top_risks", []))
        assessment_record.mitigation_plan_json = json.dumps(assessment_dict.get("mitigation_plan", {}))
        assessment_record.evidence_gaps_json = json.dumps(assessment_dict.get("evidence_gaps", []))
        assessment_record.evidence_coverage_json = json.dumps(coverage)
        assessment_record.raw_response_json = json.dumps(assessment_dict)
        assessment_record.disclaimer = assessment_dict.get("disclaimer")
        assessment_record.updated_at = now
    else:
        assessment_record = RiskAssessment(
            owner_id=user.id,
            product_case_id=case.id,
            assessment_source=source,
            model_used=model_used,
            schema_version=1,
            overall_score=int(ov.get("score", 50)),
            overall_level=ov.get("level", "MODERATE"),
            overall_confidence=float(ov.get("confidence", 0.80)),
            overall_summary=ov.get("summary", ""),
            domain_scores_json=json.dumps(assessment_dict.get("domain_scores", [])),
            top_risks_json=json.dumps(assessment_dict.get("top_risks", [])),
            mitigation_plan_json=json.dumps(assessment_dict.get("mitigation_plan", {})),
            evidence_gaps_json=json.dumps(assessment_dict.get("evidence_gaps", [])),
            evidence_coverage_json=json.dumps(coverage),
            raw_response_json=json.dumps(assessment_dict),
            disclaimer=assessment_dict.get("disclaimer"),
            created_at=now,
            updated_at=now,
        )
        db.add(assessment_record)

    db.flush()

    # --- Synchronize legacy risks and risk_evidence tables in same transaction ---
    old_risks = db.query(Risk).filter(Risk.product_case_id == case.id).all()
    for old_r in old_risks:
        db.query(RiskEvidence).filter(RiskEvidence.risk_id == old_r.id).delete()
    db.query(Risk).filter(Risk.product_case_id == case.id).delete()
    db.flush()

    # Category mapper for legacy table
    cat_map = {
        "IP & Patent": "PATENT_IP",
        "Regulatory": "REGULATORY",
        "Claims & Compliance": "CLAIMS",
        "Ingredient & Formulation": "INGREDIENT_PRODUCT_INFO",
        "Market / Commercial": "DATA_EVIDENCE_GAP",
    }

    for tr in assessment_dict.get("top_risks", []):
        r_row = Risk(
            owner_id=user.id,
            product_case_id=case.id,
            category=cat_map.get(tr.get("domain"), "PATENT_IP"),
            level=tr.get("severity", "MEDIUM"),
            title=tr.get("title", "Risk"),
            description=tr.get("why_it_matters"),
            affected_component_type=tr.get("domain"),
            affected_component_label=case.name,
            confidence=str(tr.get("confidence", "0.8")),
            data_origin="INFERENCE" if source == "GEMINI" else "RULE_ENGINE",
            evidence_summary=tr.get("why_it_matters"),
            next_action=tr.get("recommended_action"),
            source_phase="AI_RISK_ENGINE",
            status="OPEN",
            created_at=now,
            updated_at=now,
        )
        db.add(r_row)
        db.flush()

        for ev in tr.get("evidence_refs", []):
            rev = RiskEvidence(
                risk_id=r_row.id,
                evidence_type=ev.get("source_type", "passport").upper(),
                evidence_title=ev.get("label", ev.get("reference_key")),
                evidence_reference=ev.get("reference_key"),
                evidence_description=f"Evidence source for {tr.get('title')}",
                evidence_source_name=f"AYUR-INTEL {ev.get('source_type', '').capitalize()}",
                relationship_type="SUPPORTS",
                created_at=now,
            )
            db.add(rev)

    db.commit()
    db.refresh(assessment_record)
    return assessment_record


def format_risk_assessment_response(
    record: RiskAssessment, case: ProductCase
) -> Dict[str, Any]:
    """Convert DB model into JSON response schema."""
    conf = 0.8
    try:
        conf = float(record.overall_confidence)
    except Exception:
        conf = 0.8

    return {
        "id": record.public_id,
        "product_case_id": case.public_id,
        "product_name": case.name,
        "assessment_source": record.assessment_source,
        "model_used": record.model_used,
        "schema_version": record.schema_version,
        "overall_risk": {
            "score": record.overall_score,
            "level": record.overall_level,
            "confidence": conf,
            "summary": record.overall_summary or "",
        },
        "domain_scores": _deserialize(record.domain_scores_json),
        "top_risks": _deserialize(record.top_risks_json),
        "mitigation_plan": _deserialize(record.mitigation_plan_json),
        "evidence_gaps": _deserialize(record.evidence_gaps_json),
        "evidence_coverage": _deserialize(record.evidence_coverage_json),
        "disclaimer": record.disclaimer or "Decision support only.",
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "updated_at": record.updated_at.isoformat() if record.updated_at else "",
    }
