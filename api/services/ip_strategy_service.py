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

from api.models.models import (
    IPStrategy,
    IPStrategyItem,
    ProductCase,
    User,
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

    # ORM Model extraction
    name = getattr(case_input, "name", "Unnamed Product")
    form = getattr(case_input, "form", "") or ""
    process = getattr(case_input, "process", "") or ""
    intended_use = getattr(case_input, "intended_use", "") or ""

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
        "name": name,
        "form": form,
        "process": process,
        "intended_use": intended_use,
        "ingredients": ingredients,
        "traditional_elements": getattr(case_input, "traditional_elements", []),
        "innovative_elements": getattr(case_input, "innovative_elements", []),
        "unique_combinations": getattr(case_input, "unique_combinations", [])
    }


def generate_ip_roadmap(case_input: Any) -> Dict[str, Any]:
    """Generate complete IP strategy roadmap for a product"""
    case_data = _extract_case_dict(case_input)

    name = case_data.get('name', 'Unnamed Product')
    ingredients = case_data.get('ingredients', [])
    traditional_elements = case_data.get('traditional_elements', [])
    innovative_elements = case_data.get('innovative_elements', [])

    # Derive elements if not already passed
    if not traditional_elements and ingredients:
        traditional_elements = [{"name": i.get("name", "") if isinstance(i, dict) else str(i), "reason": "Classical Ayurvedic herb"} for i in ingredients]

    innovative_count = len(innovative_elements)
    traditional_count = len(traditional_elements)

    # Determine IP Readiness
    if innovative_count >= 3:
        readiness = "High"
        readiness_color = "high"
        readiness_icon = "🟢"
        readiness_desc = "Your product has strong innovative elements. You're ready for patent filing and comprehensive IP protection."
        readiness_note = "Your product has innovative elements that can be protected through patents. This gives you strong IP protection potential."
    elif innovative_count >= 1:
        readiness = "Medium"
        readiness_color = "medium"
        readiness_icon = "🟡"
        readiness_desc = "Your product has some innovative elements. Consider strengthening them before patent filing."
        readiness_note = "Your product has some innovative elements. Focus on strengthening them for better IP protection."
    else:
        readiness = "Low"
        readiness_color = "low"
        readiness_icon = "🔴"
        readiness_desc = "Your product is primarily traditional. Focus on brand protection, AYUSH registration, and trade secrets."
        readiness_note = "Your product uses classical Ayurvedic ingredients. This means it's safe, trusted, and based on traditional knowledge. IP strategy is tailored accordingly."

    # Generate steps with portal data
    steps = generate_roadmap_steps(case_data, innovative_count, traditional_count)

    # Generate success indicators
    success_indicators = generate_success_indicators(case_data, innovative_count)

    # Generate summary
    summary = generate_summary(case_data, innovative_count, traditional_count)

    total_cost_min = sum(step.get('cost_min', 0) for step in steps)
    total_cost_max = sum(step.get('cost_max', 0) for step in steps)

    return {
        "product_name": name,
        "readiness": readiness,
        "readiness_color": readiness_color,
        "readiness_icon": readiness_icon,
        "readiness_description": readiness_desc,
        "readiness_note": readiness_note,
        "steps": steps,
        "success_indicators": success_indicators,
        "summary": summary,
        "total_cost_min": total_cost_min,
        "total_cost_max": total_cost_max,
        "jurisdiction": "India (IPO/CGPDTM/AYUSH)",
        "generated_on": datetime.now().strftime("%d %B, %Y"),
        "disclaimer": "This roadmap is advisory only. Consult a qualified patent attorney for legal advice on IP protection. All costs and timelines are estimates and may vary."
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
            status="GENERATED",
            total_items=4,
            high_priority_count=1,
            medium_priority_count=2,
            low_priority_count=1,
            info_needed_count=0
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)

    return strategy


def strategy_to_dict(strategy: IPStrategy) -> Dict[str, Any]:
    """Convert IPStrategy model to dictionary."""
    case = strategy.product_case
    return generate_ip_roadmap(case)
