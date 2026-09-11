"""AYUR-INTEL — IP Strategy Roadmap Service.

Generates complete, product-specific, India-focused IP Strategy Roadmaps
with readiness assessments, step-by-step guidance (AYUSH, CGPDTM, IPO, GI),
success indicators, registration guides, and cost/timeline estimates.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from api.models import (
    IPStrategy,
    IPStrategyItem,
    ProductCase,
    User,
    InnovationAnalysis,
    InnovationComponent,
    PatentSearch,
    PatentRelevance,
    PatentAnalysis,
    RiskAssessment,
)

logger = logging.getLogger("ayur_intel.ip_strategy_service")

# India-specific IP authorities
IP_AUTHORITIES = {
    "ipo": "Indian Patent Office (IPO)",
    "cgpdtm": "Controller General of Patents, Designs & Trademarks (CGPDTM)",
    "ayush": "Ministry of AYUSH"
}

# Cost estimates (₹)
COST_ESTIMATES = {
    "ayush_registration": {"min": 0, "max": 0, "currency": "₹"},
    "trademark_filing": {"min": 4500, "max": 9000, "currency": "₹"},
    "prior_art_search": {"min": 5000, "max": 15000, "currency": "₹"},
    "patent_filing_india": {"min": 10000, "max": 50000, "currency": "₹"},
    "trade_secret": {"min": 0, "max": 5000, "currency": "₹"},
    "attorney_consultation": {"min": 2000, "max": 10000, "currency": "₹"},
    "gi_tagging": {"min": 5000, "max": 20000, "currency": "₹"},
    "international_patent": {"min": 50000, "max": 200000, "currency": "₹"}
}

# Timeline estimates (weeks)
TIMELINE_ESTIMATES = {
    "ayush_registration": {"min": 2, "max": 4, "unit": "weeks"},
    "trademark_filing": {"min": 24, "max": 48, "unit": "weeks"},
    "prior_art_search": {"min": 2, "max": 3, "unit": "weeks"},
    "patent_filing_india": {"min": 12, "max": 24, "unit": "months"},
    "trade_secret": {"min": 1, "max": 2, "unit": "weeks"},
    "gi_tagging": {"min": 12, "max": 24, "unit": "months"},
    "international_patent": {"min": 24, "max": 48, "unit": "months"}
}

# Registration Guides Data
REGISTRATION_GUIDES = {
    "ayush": {
        "title": "📜 AYUSH Registration Guide",
        "steps": [
            "📄 **Step 1: Documentation** - Prepare Aadhaar, PAN, Company registration (CoI, MoA, AoA), product list, component list, equipment list, staff qualifications (B.Sc/BAMS/B.Pharm)",
            "✅ **Step 2: Apply for GMP Certificate** - Get Good Manufacturing Practice certificate from Ministry of AYUSH",
            "📝 **Step 3: Fill Application** - Download and fill AYUSH license application form with product details",
            "📤 **Step 4: Submit to Portal** - Upload form with documents on e-AUSHADHI portal. Fees: ₹2,000 - ₹15,000",
            "⏳ **Step 5: Verification & Approval** - Department verifies, may inspect facility. Certificate issued upon approval"
        ],
        "portalLink": "https://www.e-aushadhi.gov.in/",
        "portalText": "Go to AYUSH Portal →",
        "guide_type": "ayush"
    },
    "trademark": {
        "title": "🏷️ Trademark Registration Guide",
        "steps": [
            "🔍 **Step 1: Trademark Search** - Check if your mark is available at ipindia.gov.in",
            "📋 **Step 2: File Form TM-A** - Apply online with trademark specimen, goods list, and Power of Attorney. Fees: ₹4,500 - ₹9,000/class",
            "📑 **Step 3: Examination** - CGPDTM examines (6-12 months). Respond to objections if any",
            "📰 **Step 4: Publication** - Mark published in Trademark Journal (4 months opposition period)",
            "✅ **Step 5: Registration** - Certificate issued. Valid 10 years, renewable"
        ],
        "portalLink": "https://www.ipindia.gov.in/",
        "portalText": "Go to IP India Portal →",
        "guide_type": "trademark"
    },
    "gi": {
        "title": "🌍 GI Tagging Guide",
        "steps": [
            "👥 **Step 1: Form Association** - Organize producers/association representing interest of producers",
            "📄 **Step 2: File Application** - Submit in triplicate with statement of case, 3 certified maps of region",
            "📋 **Step 3: Documentation** - Details of special characteristics, inspection structure, applicant details",
            "📤 **Step 4: Submit to GI Registry** - Send to Geographical Indications Registry, Chennai. Fees: ₹5,000 - ₹20,000",
            "📰 **Step 5: Publication** - Application published in GI Journal (3 months opposition period)",
            "✅ **Step 6: Registration** - Certificate issued. Valid 10 years, renewable"
        ],
        "portalLink": "https://www.ipindia.gov.in/gi-filing-process-step-by-step",
        "portalText": "Go to GI Registry Portal →",
        "guide_type": "gi"
    },
    "design": {
        "title": "🎨 Design Patent Guide",
        "steps": [
            "📐 **Step 1: Prepare Drawings** - Create PDF/JPG drawings showing article from all sides (shape, configuration, pattern)",
            "📋 **Step 2: File Form 01** - Submit design application with Power of Attorney and applicant details. Fees: ₹5,000 - ₹15,000",
            "🔍 **Step 3: Examination** - IPO examines for novelty and originality (6-9 months)",
            "✅ **Step 4: Registration** - Certificate issued. Valid 10 years, extendable by 5 years"
        ],
        "portalLink": "https://www.ipindia.gov.in/",
        "portalText": "Go to IPO Portal →",
        "guide_type": "design"
    }
}


def _extract_case_dict(case_input: Any) -> Dict[str, Any]:
    """Extract standard dictionary from ProductCase ORM model or dict."""
    if isinstance(case_input, dict):
        return case_input

    name = getattr(case_input, "name", "Unnamed Product")
    form = getattr(case_input, "form", "") or ""
    process = getattr(case_input, "process", "") or ""
    intended_use = getattr(case_input, "intended_use", "") or ""
    notes = getattr(case_input, "notes", "") or ""
    packaging = getattr(case_input, "packaging", "") or ""

    raw_claims = getattr(case_input, "claims", None)
    if isinstance(raw_claims, str):
        try:
            claims = json.loads(raw_claims)
        except Exception:
            claims = []
    elif isinstance(raw_claims, list):
        claims = raw_claims
    else:
        claims = []

    raw_ingredients = getattr(case_input, "ingredients", None)
    if isinstance(raw_ingredients, str):
        try:
            ingredients = json.loads(raw_ingredients)
        except Exception:
            ingredients = []
    elif isinstance(raw_ingredients, list):
        ingredients = raw_ingredients
    else:
        ingredients = []

    return {
        "id": getattr(case_input, "id", None),
        "public_id": getattr(case_input, "public_id", None),
        "name": name,
        "form": form,
        "process": process,
        "intended_use": intended_use,
        "notes": notes,
        "packaging": packaging,
        "claims": claims,
        "ingredients": ingredients,
        "traditional_elements": getattr(case_input, "traditional_elements", []),
        "innovative_elements": getattr(case_input, "innovative_elements", []),
        "unique_combinations": getattr(case_input, "unique_combinations", [])
    }


def calculate_ip_readiness(case_input: Any, db: Optional[Session] = None) -> Dict[str, Any]:
    """Calculate deterministic 0-100 IP Readiness score based on grounded multi-module intelligence.

    Component A: Product Definition (max 20)
    Component B: Innovation Articulation (max 20)
    Component C: Prior-Art Intelligence (max 25)
    Component D: Technical Differentiation Evidence (max 20)
    Component E: Strategy Preparedness (max 15)
    Total: 0-100
    """
    case_data = _extract_case_dict(case_input)
    name = case_data.get("name", "Unnamed Product")
    ingredients = case_data.get("ingredients", [])
    form = case_data.get("form", "")
    intended_use = case_data.get("intended_use", "")
    process = case_data.get("process", "")
    notes = case_data.get("notes", "")
    claims = case_data.get("claims", [])
    packaging = case_data.get("packaging", "")

    case_id = case_data.get("id")
    if case_id is None and hasattr(case_input, "id"):
        case_id = case_input.id

    # If db is not explicitly passed, attempt session recovery from ORM object
    if db is None and hasattr(case_input, "__table__"):
        try:
            db = Session.object_session(case_input)
        except Exception:
            db = None

    # -------------------------------------------------------------------
    # A. Product Definition (max 20 pts)
    # -------------------------------------------------------------------
    reasons_a = []
    score_a = 0
    if name and name != "Unnamed Product":
        score_a += 3
        reasons_a.append("Product identity and title defined.")

    if ingredients and len(ingredients) > 0:
        score_a += 5
        reasons_a.append(f"Composition structured with {len(ingredients)} botanical ingredient(s).")
        has_qty = any(isinstance(i, dict) and ("quantity" in i or "mg" in i or "amount" in i) for i in ingredients)
        if has_qty:
            score_a += 4
            reasons_a.append("Quantitative ingredient amounts / dosage breakdown specified.")

    if form:
        score_a += 3
        reasons_a.append(f"Dosage form specified ({form}).")

    if intended_use:
        score_a += 3
        reasons_a.append("Intended use and therapeutic indication defined.")

    if process or packaging:
        score_a += 2
        reasons_a.append("Preparation process or packaging parameters present.")

    score_a = min(20, score_a)

    # -------------------------------------------------------------------
    # B. Innovation Articulation (max 20 pts)
    # -------------------------------------------------------------------
    reasons_b = []
    score_b = 0

    innov_analysis = None
    if db and case_id:
        try:
            innov_analysis = db.query(InnovationAnalysis).filter(InnovationAnalysis.product_case_id == case_id).first()
        except Exception:
            innov_analysis = None

    if innov_analysis:
        score_b += 5
        reasons_b.append("Innovation Analysis pipeline executed.")
        if (innov_analysis.total_components or 0) > 0:
            score_b += 5
            reasons_b.append(f"{innov_analysis.total_components} product component(s) structured.")
        if (innov_analysis.differentiated_count or 0) > 0:
            score_b += 5
            reasons_b.append(f"{innov_analysis.differentiated_count} technical differentiation factor(s) identified.")
        if (innov_analysis.traditional_count or 0) + (innov_analysis.investigation_count or 0) > 0:
            score_b += 5
            reasons_b.append("Classical vs innovative component grounding completed.")
    else:
        comb_text = f"{process} {notes} {' '.join(str(c) for c in claims)}".lower()
        if any(w in comb_text for w in ["standardized", "extract", "hplc", "fraction", "ratio", "bio-enhancer", "piperine"]):
            score_b += 6
            reasons_b.append("Technical innovation & standardization terms present in formulation description.")
        else:
            reasons_b.append("Innovation Analysis has not been executed yet for this product case.")

    score_b = min(20, score_b)

    # -------------------------------------------------------------------
    # C. Prior-Art Intelligence (max 25 pts)
    # -------------------------------------------------------------------
    reasons_c = []
    score_c = 0

    p_searches = 0
    p_relevances = 0
    p_analyses = 0

    if db and case_id:
        try:
            p_searches = db.query(PatentSearch).filter(PatentSearch.product_case_id == case_id).count()
            p_relevances = db.query(PatentRelevance).filter(PatentRelevance.product_case_id == case_id).count()
            p_analyses = db.query(PatentAnalysis).filter(PatentAnalysis.product_case_id == case_id).count()
        except Exception:
            pass

    if p_searches > 0:
        score_c += 10
        reasons_c.append("Prior-art patent search completed.")
        if p_relevances > 0:
            score_c += 5
            reasons_c.append(f"{p_relevances} prior-art patent document(s) screened for relevance.")
    else:
        reasons_c.append("Prior-art patent search has not yet been conducted.")

    if p_relevances >= 5:
        score_c += 5
        reasons_c.append("Comprehensive candidate patent dataset analyzed.")
    elif p_relevances > 0:
        score_c += 3

    if p_analyses > 0:
        score_c += 5
        reasons_c.append("Deep patent analysis and technical comparison performed.")

    score_c = min(25, score_c)

    # -------------------------------------------------------------------
    # D. Technical Differentiation Evidence (max 20 pts)
    # -------------------------------------------------------------------
    reasons_d = []
    score_d = 0

    d_components = []
    if db and innov_analysis:
        try:
            d_components = db.query(InnovationComponent).filter(
                InnovationComponent.analysis_id == innov_analysis.id
            ).all()
        except Exception:
            d_components = []

    if d_components:
        diff_types = set(getattr(c, "component_type", "") for c in d_components if getattr(c, "status", "") == "DIFFERENTIATED")
        if any(t in diff_types for t in ["COMPOSITION", "RATIO", "INGREDIENT"]):
            score_d += 5
            reasons_d.append("Compositional or quantitative ratio differentiation established.")
        if any(t in diff_types for t in ["PROCESS", "EXTRACTION"]):
            score_d += 5
            reasons_d.append("Extraction or processing technical distinction documented.")
        if any(t in diff_types for t in ["STANDARDIZATION", "QUALITY"]):
            score_d += 5
            reasons_d.append("Phytochemical standardization parameters defined.")
        if any(t in diff_types for t in ["FORMULATION", "DELIVERY"]):
            score_d += 5
            reasons_d.append("Dosage form or bio-delivery mechanism articulated.")
    else:
        comb_text = f"{process} {notes}".lower()
        if "hplc" in comb_text or "standardized" in comb_text or "%" in comb_text:
            score_d += 4
            reasons_d.append("Phytochemical standardization parameters present in processing text.")
        if "piperine" in comb_text or "bio-enhanc" in comb_text:
            score_d += 4
            reasons_d.append("Bio-enhancer strategy defined in processing text.")
        if not reasons_d:
            reasons_d.append("No technical differentiation evidence documented yet.")

    score_d = min(20, score_d)

    # -------------------------------------------------------------------
    # E. IP Documentation & Strategy Preparedness (max 15 pts)
    # -------------------------------------------------------------------
    reasons_e = []
    score_e = 0

    # 1. Baseline roadmap generated & persisted (+3)
    score_e += 3
    reasons_e.append("Baseline India IP Protection Roadmap generated.")

    # 2. Case-specific formulation parameters grounded in roadmap (+3)
    if ingredients and len(ingredients) > 0 and (form or process):
        score_e += 3
        reasons_e.append("Roadmap incorporates case-specific formulation composition and dosage form parameters.")

    # 3. Strategy integrates prior-art intelligence findings (+3)
    if p_searches > 0 or p_relevances > 0:
        score_e += 3
        reasons_e.append("Strategy integrates prior-art patent search and document screening findings.")

    # 4. Strategy integrates technical differentiation / innovation findings (+3)
    if innov_analysis or d_components or (score_b > 0 and score_d > 0):
        score_e += 3
        reasons_e.append("Strategy incorporates grounded technical differentiation and innovation components.")

    # 5. Risk matrix alignment and evidence gap / verification steps identified (+3)
    r_count = 0
    if db and case_id:
        try:
            r_count = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == case_id).count()
        except Exception:
            r_count = 0

    if r_count > 0:
        score_e += 3
        reasons_e.append(f"Risk matrix and IP mitigation strategy active ({r_count} risk findings).")

    score_e = min(15, score_e)

    # -------------------------------------------------------------------
    # Total Score & Centralized Level Threshold Mapping
    # -------------------------------------------------------------------
    total_score = score_a + score_b + score_c + score_d + score_e
    total_score = max(0, min(100, total_score))

    if total_score >= 85:
        level = "VERY HIGH"
        color = "very_high"
        icon = "💎"
        desc = "Your product is exceptionally well-prepared with comprehensive formulation, prior-art intelligence, and technical differentiation."
        note = "Strong IP evaluation baseline established across product identity, prior-art screening, and strategy preparedness."
    elif total_score >= 70:
        level = "HIGH"
        color = "high"
        icon = "🟢"
        desc = "Your product has strong technical documentation and prior-art intelligence for IP evaluation."
        note = "Well-prepared for IP strategy review. Focus on addressing specific evidence gaps before filing."
    elif total_score >= 50:
        level = "MODERATE"
        color = "medium"
        icon = "🟡"
        desc = "Your product has moderate IP preparedness. Essential identity is present, but prior art or technical differentiation can be strengthened."
        note = "Consider conducting a prior-art search or running Innovation Analysis to build technical differentiation."
    elif total_score >= 25:
        level = "LOW"
        color = "low"
        icon = "🟠"
        desc = "Your product has basic identity information but limited prior-art search or technical differentiation evidence."
        note = "Complete the Product Passport and execute Prior-Art Intelligence to improve IP readiness."
    else:
        level = "VERY LOW"
        color = "very_low"
        icon = "🔴"
        desc = "Your product case has minimal structured information. Initial data entry and prior art screening are required."
        note = "Fill in the Product Passport ingredients, intended use, and dosage form to begin IP evaluation."

    strengths = []
    gaps = []
    next_actions = []

    if score_a >= 15:
        strengths.append("Structured Product Identity & quantitative composition well-defined")
    else:
        gaps.append("Incomplete Product Passport identity details (ingredients, quantities, form)")
        next_actions.append("Complete missing Product Passport details in formulation tab")

    if score_c >= 15:
        strengths.append("Prior-art patent intelligence search and screening completed")
    else:
        gaps.append("Prior-art patent search has not been executed or screened")
        next_actions.append("Run Patent Intelligence to screen Indian & international patent databases")

    if score_b >= 10 or score_d >= 10:
        strengths.append("Technical differentiation and innovation components identified")
    else:
        gaps.append("Technical differentiation and innovation claims need further articulation")
        next_actions.append("Run Innovation Analysis to identify unique composition or process features")

    if score_e >= 10:
        strengths.append("IP Strategy roadmap and regulatory registration guidance prepared")

    return {
        "readiness_score": total_score,
        "readiness_level": level,
        "readiness_color": color,
        "readiness_icon": icon,
        "readiness_description": desc,
        "readiness_note": note,
        "readiness_breakdown": {
            "product_definition": {"score": score_a, "max_score": 20, "reasons": reasons_a},
            "innovation_articulation": {"score": score_b, "max_score": 20, "reasons": reasons_b},
            "prior_art_intelligence": {"score": score_c, "max_score": 25, "reasons": reasons_c},
            "technical_differentiation": {"score": score_d, "max_score": 20, "reasons": reasons_d},
            "strategy_preparedness": {"score": score_e, "max_score": 15, "reasons": reasons_e},
        },
        "strengths": strengths,
        "gaps": gaps,
        "next_actions": next_actions,
    }


def generate_ip_roadmap(case_input: Any, db: Optional[Session] = None) -> Dict[str, Any]:
    """Generate complete IP strategy roadmap for a product case with grounded 0-100 IP readiness scoring."""
    case_data = _extract_case_dict(case_input)

    name = case_data.get("name", "Unnamed Product")
    ingredients = case_data.get("ingredients", [])
    traditional_elements = case_data.get("traditional_elements", [])
    innovative_elements = case_data.get("innovative_elements", [])

    if not traditional_elements and ingredients:
        traditional_elements = [{"name": i.get("name", "") if isinstance(i, dict) else str(i), "reason": "Classical Ayurvedic herb"} for i in ingredients]

    innovative_count = len(innovative_elements)
    traditional_count = len(traditional_elements)

    # Calculate grounded 0-100 IP Readiness Score & Breakdown
    readiness_data = calculate_ip_readiness(case_input, db=db)

    # Generate steps with portal data
    steps = generate_roadmap_steps(case_data, innovative_count, traditional_count)

    # Generate success indicators
    success_indicators = generate_success_indicators(case_data, innovative_count)

    # Generate summary
    summary = generate_summary(case_data, innovative_count, traditional_count)

    total_cost_min = sum(step.get("cost_min", 0) for step in steps)
    total_cost_max = sum(step.get("cost_max", 0) for step in steps)

    return {
        "product_name": name,
        "readiness_score": readiness_data["readiness_score"],
        "readiness_level": readiness_data["readiness_level"],
        "readiness": readiness_data["readiness_level"],  # Legacy compatibility field
        "readiness_color": readiness_data["readiness_color"],
        "readiness_icon": readiness_data["readiness_icon"],
        "readiness_description": readiness_data["readiness_description"],
        "readiness_note": readiness_data["readiness_note"],
        "readiness_breakdown": readiness_data["readiness_breakdown"],
        "strengths": readiness_data["strengths"],
        "gaps": readiness_data["gaps"],
        "next_actions": readiness_data["next_actions"],
        "steps": steps,
        "success_indicators": success_indicators,
        "summary": summary,
        "total_cost_min": total_cost_min,
        "total_cost_max": total_cost_max,
        "jurisdiction": "India (IPO/CGPDTM/AYUSH)",
        "generated_on": datetime.now().strftime("%d %B, %Y"),
        "disclaimer": "IP Readiness represents preparedness for IP evaluation and filing strategy. It is NOT legal advice and does NOT guarantee patentability or non-infringement."
    }


def generate_roadmap_steps(case_data: Dict, innovative_count: int, traditional_count: int) -> List[Dict]:
    """Generate 4-step roadmap based on product type"""
    name = case_data.get('name', 'Unnamed Product')
    ingredients = case_data.get('ingredients', [])
    ingredient_names = []
    for i in ingredients:
        if isinstance(i, dict):
            ingredient_names.append(i.get('name', ''))
        elif isinstance(i, str):
            ingredient_names.append(i)
    ingredient_list = ', '.join(ingredient_names[:3]) if ingredient_names else "key herbs"

    steps = []

    # STEP 1: AYUSH Registration
    steps.append({
        "step": 1,
        "title": "Document Traditional Knowledge with AYUSH",
        "icon": "📜",
        "what": "Register your product formulation with the Ministry of AYUSH",
        "why": "Establishes prior art, provides credibility, and documents traditional knowledge",
        "how": f"Submit product details, ingredients ({ingredient_list}), and classical references to AYUSH portal",
        "timeline_min": 2,
        "timeline_max": 4,
        "timeline_unit": "weeks",
        "cost_min": 0,
        "cost_max": 0,
        "cost_currency": "₹",
        "status": "pending",
        "action": "Submit to AYUSH",
        "authority": "Ministry of AYUSH",
        "portal_link": "https://www.e-aushadhi.gov.in/",
        "portal_text": "Go to AYUSH Portal →",
        "guide_type": "ayush"
    })

    # STEP 2: Trademark
    steps.append({
        "step": 2,
        "title": "Protect Brand Identity with Trademark",
        "icon": "🏷️",
        "what": f"File trademark for '{name}' brand name and logo",
        "why": "Protects your brand identity and prevents others from using similar names",
        "how": "File trademark application with CGPDTM under Class 5 (Pharmaceuticals) or Class 30 (Herbal products)",
        "timeline_min": 24,
        "timeline_max": 48,
        "timeline_unit": "weeks",
        "cost_min": 4500,
        "cost_max": 9000,
        "cost_currency": "₹",
        "status": "pending",
        "action": "File Trademark",
        "authority": "CGPDTM",
        "portal_link": "https://www.ipindia.gov.in/",
        "portal_text": "Go to IP India Portal →",
        "guide_type": "trademark"
    })

    # STEP 3 & 4: Based on innovation level
    if innovative_count >= 2:
        steps.append({
            "step": 3,
            "title": "File Indian Patent Application",
            "icon": "📄",
            "what": f"File patent application for '{name}' formulation and process",
            "why": "Protects your innovative elements and creates IP assets",
            "how": f"Prepare patent specification with formulation details, ingredients ({ingredient_list}), and process. File with IPO.",
            "timeline_min": 12,
            "timeline_max": 24,
            "timeline_unit": "months",
            "cost_min": 10000,
            "cost_max": 50000,
            "cost_currency": "₹",
            "status": "pending",
            "action": "Consult Patent Attorney",
            "authority": "IPO",
            "portal_link": "https://www.ipindia.gov.in/",
            "portal_text": "Go to IPO Portal →",
            "guide_type": "design"
        })
        steps.append({
            "step": 4,
            "title": "Protect Formulation as Trade Secret",
            "icon": "🔒",
            "what": f"Document '{name}' formulation ratios and process as trade secrets",
            "why": "Protects unique formulation details that may not be patentable",
            "how": "Create internal documentation, confidentiality agreements, and access controls",
            "timeline_min": 1,
            "timeline_max": 2,
            "timeline_unit": "weeks",
            "cost_min": 0,
            "cost_max": 5000,
            "cost_currency": "₹",
            "status": "pending",
            "action": "Create Documentation",
            "authority": "Internal",
            "portal_link": "",
            "portal_text": "",
            "guide_type": ""
        })
    elif innovative_count == 1:
        steps.append({
            "step": 3,
            "title": "Conduct Prior Art Search",
            "icon": "🔍",
            "what": f"Search Indian Patent Database for similar formulations",
            "why": "Assess novelty before investing in patent filing",
            "how": f"Search IPO database using ingredients ({ingredient_list}) and formulation keywords",
            "timeline_min": 2,
            "timeline_max": 3,
            "timeline_unit": "weeks",
            "cost_min": 5000,
            "cost_max": 15000,
            "cost_currency": "₹",
            "status": "pending",
            "action": "Search IPO Database",
            "authority": "IPO",
            "portal_link": "https://www.ipindia.gov.in/",
            "portal_text": "Go to IPO Portal →",
            "guide_type": "design"
        })
        steps.append({
            "step": 4,
            "title": "Protect Formulation as Trade Secret",
            "icon": "🔒",
            "what": f"Document '{name}' formulation ratios and process as trade secrets",
            "why": "Protects unique formulation details",
            "how": "Create internal documentation and confidentiality agreements",
            "timeline_min": 1,
            "timeline_max": 2,
            "timeline_unit": "weeks",
            "cost_min": 0,
            "cost_max": 5000,
            "cost_currency": "₹",
            "status": "pending",
            "action": "Create Documentation",
            "authority": "Internal",
            "portal_link": "",
            "portal_text": "",
            "guide_type": ""
        })
    else:
        steps.append({
            "step": 3,
            "title": "Explore Geographical Indication (GI) Tagging",
            "icon": "🌍",
            "what": f"Explore GI tagging for '{name}' if using region-specific ingredients",
            "why": "Adds premium value and protects regional authenticity",
            "how": f"Research GI eligibility based on ingredients ({ingredient_list}) and production region",
            "timeline_min": 12,
            "timeline_max": 24,
            "timeline_unit": "months",
            "cost_min": 5000,
            "cost_max": 20000,
            "cost_currency": "₹",
            "status": "pending",
            "action": "Research GI Eligibility",
            "authority": "GI Registry",
            "portal_link": "https://www.ipindia.gov.in/gi-filing-process-step-by-step",
            "portal_text": "Go to GI Registry Portal →",
            "guide_type": "gi"
        })
        steps.append({
            "step": 4,
            "title": "File Design Patent (Optional)",
            "icon": "🎨",
            "what": f"Consider design patent for '{name}' packaging",
            "why": "Protects unique packaging and visual identity",
            "how": "File design patent application with IPO",
            "timeline_min": 6,
            "timeline_max": 12,
            "timeline_unit": "months",
            "cost_min": 5000,
            "cost_max": 15000,
            "cost_currency": "₹",
            "status": "pending",
            "action": "Consult Design Attorney",
            "authority": "IPO",
            "portal_link": "https://www.ipindia.gov.in/",
            "portal_text": "Go to IPO Portal →",
            "guide_type": "design"
        })

    return steps


def generate_success_indicators(case_data: Dict, innovative_count: int) -> List[Dict]:
    """Generate success indicators checklist"""
    indicators = [
        {
            "icon": "📜",
            "title": "AYUSH Registration Complete",
            "description": "Product registered with Ministry of AYUSH",
            "status": "pending",
            "key": "ayush"
        },
        {
            "icon": "🏷️",
            "title": "Trademark Application Filed",
            "description": "Brand name protected with CGPDTM",
            "status": "pending",
            "key": "trademark"
        }
    ]

    if innovative_count >= 2:
        indicators.append({
            "icon": "📄",
            "title": "Patent Application Filed",
            "description": "Patent application submitted to IPO",
            "status": "pending",
            "key": "patent"
        })
    else:
        indicators.append({
            "icon": "🔒",
            "title": "Trade Secret Documentation Complete",
            "description": "Formulation and process documented as trade secrets",
            "status": "pending",
            "key": "tradesecret"
        })

    indicators.append({
        "icon": "🔍",
        "title": "Prior Art Search Completed",
        "description": "Indian patent database searched for similar formulations",
        "status": "pending",
        "key": "priorart"
    })

    return indicators


def generate_summary(case_data: Dict, innovative_count: int, traditional_count: int) -> str:
    """Generate product-specific summary"""
    name = case_data.get('name', 'Unnamed Product')

    if innovative_count >= 3:
        return f"Your product '{name}' has {innovative_count} innovative elements. You're well-positioned for patent filing. Focus on Step 3 (Patent Filing) and Step 4 (Trade Secret) to maximize IP protection."
    elif innovative_count >= 1:
        return f"Your product '{name}' has {innovative_count} innovative element(s) and {traditional_count} traditional elements. Prioritize Step 1 (AYUSH) and Step 2 (Trademark), then assess patent potential via Step 3 (Prior Art Search)."
    else:
        return f"Your product '{name}' uses {traditional_count} traditional ingredients. Focus on Step 1 (AYUSH Registration) and Step 2 (Trademark). Consider Step 3 (GI Tagging) if region-specific."


def generate_ip_strategy(db: Session, user: User, case_id: str) -> Optional[IPStrategy]:
    """Generate or retrieve database IPStrategy model."""
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_id,
        ProductCase.owner_id == user.id
    ).first()
    if not case:
        return None

    strategy = db.query(IPStrategy).filter(
        IPStrategy.product_case_id == case.id,
        IPStrategy.owner_id == user.id
    ).first()

    if not strategy:
        strategy = IPStrategy(
            product_case_id=case.id,
            owner_id=user.id,
            status="COMPLETED",
            total_items=4,
            high_priority_count=1,
            medium_priority_count=2,
            low_priority_count=1,
            info_needed_count=0
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
    else:
        # Update existing strategy row to ensure status and items are accurate
        strategy.total_items = 4
        strategy.status = "COMPLETED"
        db.commit()
        db.refresh(strategy)

    return strategy


def strategy_to_dict(strategy: IPStrategy, db: Optional[Session] = None) -> Dict[str, Any]:
    """Convert IPStrategy model to dictionary with grounded 0-100 IP readiness scoring."""
    case = strategy.product_case
    if db is None and hasattr(strategy, "__table__"):
        try:
            db = Session.object_session(strategy)
        except Exception:
            db = None
    return generate_ip_roadmap(case, db=db)
