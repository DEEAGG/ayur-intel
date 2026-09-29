"""AYUR-INTEL — In-App Assistant Knowledge Base.

Contains authoritative, grounded knowledge chunks representing the actual platform
architecture, features, workflows, and explicit boundaries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


KNOWLEDGE_CHUNKS: List[Dict[str, Any]] = [
    {
        "id": "kb_platform_overview",
        "title": "AYUR-INTEL Platform & Mission",
        "content": (
            "AYUR-INTEL is an India-first, evidence-backed Ayurvedic product intelligence and "
            "decision-support platform. It solves the fragmentation in commercializing botanical formulations "
            "by connecting classical Ayurvedic wisdom (Samhitas, Dravya guna, API) with modern scientific research, "
            "Indian Patent Office prior-art analytics, and statutory regulatory pathways (ASU Drugs vs FSSAI Nutraceuticals). "
            "It is designed for Ayurvedic formulation scientists, brand founders, R&D labs, and regulatory teams."
        ),
        "tags": [
            "ayur-intel", "what is ayur-intel", "platform", "purpose", "mission",
            "overview", "kya hai", "about", "positioning", "decision support", "ayurveda"
        ],
        "related_feature": "Platform Overview",
        "default_action": "OPEN_DASHBOARD",
    },
    {
        "id": "kb_tech_stack",
        "title": "AYUR-INTEL Technology Stack",
        "content": (
            "AYUR-INTEL's confirmed architecture is built on:\n"
            "• Backend: FastAPI (Python 3.12 asynchronous web framework) with Uvicorn ASGI server and Pydantic v2 schemas.\n"
            "• Database: SQLite (local development at data/ayur_intel.db) and PostgreSQL (via Supabase in production), "
            "managed through SQLAlchemy 2.0 ORM with connection pooling.\n"
            "• AI & LLM: Google Gemini API (using google.generativeai / gemini-flash-latest) powering multilingual "
            "AI normalization, multi-domain risk synthesis, and the in-app RAG assistant.\n"
            "• Frontend: Single Page Application (SPA) built with vanilla JavaScript, modern CSS3 with an Institutional "
            "Botanical design system, D3.js (v7) for interactive knowledge graphs and growth trees, and Google Material Symbols.\n"
            "• External APIs: PlantNet API for botanical image recognition and species identification."
        ),
        "tags": [
            "tech stack", "technology", "techstack", "stack", "architecture", "built with",
            "fastapi", "python", "gemini", "supabase", "sqlite", "frontend", "backend",
            "kis tech stack", "pe bana hai", "technologies", "libraries", "database"
        ],
        "related_feature": "Platform Architecture",
        "default_action": "OPEN_DASHBOARD",
    },
    {
        "id": "kb_ai_usage",
        "title": "How AYUR-INTEL Uses Artificial Intelligence",
        "content": (
            "AYUR-INTEL uses Google Gemini AI in specific, bounded decision-support functions:\n"
            "1. Multilingual Normalization: Translates colloquial English, Hindi, and Hinglish product descriptions into "
            "structured English, auto-detecting botanical ingredients with scientific Latin binomials (e.g. Ashwagandha -> Withania somnifera), "
            "dosage forms, and proposed benefit claims.\n"
            "2. Risk Intelligence Synthesis: Evaluates cross-module evidence (patents, regulatory requirements, claims, and formulations) "
            "to produce quantified risk scores, severity levels, evidence gap warnings, and mitigation steps.\n"
            "3. In-App RAG Assistant: Retrieves relevant knowledge chunks and provides contextual answers and navigation shortcuts in user's language.\n"
            "Crucially, AYUR-INTEL pairs AI with deterministic rule engines and fallbacks to ensure total reliability even when Gemini is offline."
        ),
        "tags": [
            "ai", "how ai is used", "gemini", "artificial intelligence", "ai normalization",
            "ai use", "ai use cases", "ai kaha use", "machine learning", "llm"
        ],
        "related_feature": "AI Normalization & Risk",
        "default_action": "OPEN_DASHBOARD",
    },
    {
        "id": "kb_product_creation",
        "title": "Product Creation Workflow",
        "content": (
            "To create a product in AYUR-INTEL:\n"
            "1. Click '+ New' in the topbar or 'New Case' in the sidebar, or navigate to Products and click 'Create Product'.\n"
            "2. This opens the 7-step Product Passport Wizard:\n"
            "   • Step 1: Basic Identity (Product Name, Brand, Stage: Idea, R&D, Pilot, Pre-Launch, Commercial).\n"
            "   • Step 2: Formulation & Ingredients (Select herbs with automated botanical Latin mapping).\n"
            "   • Step 3: Dosage Form (Capsules, Tablets/Vati, Syrups/Asava, Oils/Taila, Churna/Powder).\n"
            "   • Step 4: Intended Use & Indications (e.g. Cognitive Health, Stress Relief, Immunity, Digestion).\n"
            "   • Step 5: Manufacturing Process (Classical extraction vs modern standardized extract).\n"
            "   • Step 6: Proposed Claims & AI Normalization (Accepts natural Hindi, Hinglish, or English).\n"
            "   • Step 7: Final Review & Creation.\n"
            "Once created, the product is immediately saved to the database and unlocked for Patent, Regulatory, Risk, and Monitoring intelligence."
        ),
        "tags": [
            "create product", "how do i create a product", "new product", "naya product",
            "product banana", "passport wizard", "add product", "workflow", "create", "kaise banau"
        ],
        "related_feature": "Product Passport Wizard",
        "default_action": "CREATE_PRODUCT",
    },
    {
        "id": "kb_products_inventory",
        "title": "Products Inventory & Active Product Case",
        "content": (
            "You can find all your saved formulations in the 'Products' section (sidebar: Products / view: product-cases).\n"
            "• Each product card displays its name, formulation dosage form, lifecycle stage (IDEA, RND, PILOT, PRE_LAUNCH, COMMERCIAL), "
            "and completion status.\n"
            "• Clicking on any product card sets it as the active product case and opens its Case Intelligence command center.\n"
            "• You can also switch the active case anytime via the Topbar Case Context dropdown."
        ),
        "tags": [
            "where are my products", "products", "my products", "mere products",
            "products list", "inventory", "view products", "kaha hai", "cases", "switch case", "saved products"
        ],
        "related_feature": "Products Management",
        "default_action": "OPEN_PRODUCTS",
    },
    {
        "id": "kb_product_passport",
        "title": "Product Passport Overview",
        "content": (
            "The Product Passport is the comprehensive digital identity and master dossier of an Ayurvedic formulation. It contains:\n"
            "• Botanical Identity: Herbal ingredients, scientific Latin names, parts used (root, leaf, etc.), and classical Dravya classifications.\n"
            "• Technical Specifications: Dosage form, manufacturing and extraction methods, and classical references (Charaka, Sushruta, Bhavaprakasha, API).\n"
            "• Commercial & Regulatory Specs: Proposed wellness claims, target health indications, and target jurisdictions.\n"
            "• AI-Normalized Records: Structured translations from multilingual user inputs.\n"
            "The Product Passport acts as the single source of truth feeding directly into Indian Patent searches, Regulatory pathways, and Risk analysis."
        ),
        "tags": [
            "what is product passport", "product passport", "passport", "digital blueprint",
            "formulation passport", "passport kya hai", "passport wizard", "dossier"
        ],
        "related_feature": "Product Passport",
        "default_action": "OPEN_PRODUCT_PASSPORT",
    },
    {
        "id": "kb_patent_intelligence",
        "title": "Indian Patent Intelligence & Prior Art",
        "content": (
            "AYUR-INTEL's Indian Patent Intelligence module analyzes patentability and freedom-to-operate for your active formulation against "
            "Indian Patent Office (IPO) records and global ASU (Ayurveda, Siddha, Unani) patent data.\n"
            "Key capabilities:\n"
            "• Section 3(p) Analysis: Evaluates whether your formulation qualifies as unpatentable traditional knowledge or mere aggregation of known properties under Section 3(p) of the Indian Patents Act, 1970.\n"
            "• Prior-Art Shortlisting: Identifies colliding patents based on ingredient combinations, extraction techniques, and therapeutic indications.\n"
            "• AI Claim Comparison: Highlights overlapping claim elements between your formulation and published patents.\n"
            "• IP Readiness Score: Computes an overall novelty and freedom-to-operate score with actionable drafting recommendations."
        ),
        "tags": [
            "how does patent intelligence work", "patent", "patent intelligence", "patents",
            "prior art", "ipo", "section 3p", "freedom to operate", "patent check",
            "patent kya karta hai", "ip readiness", "patentability"
        ],
        "related_feature": "Patent Intelligence",
        "default_action": "OPEN_PATENT",
    },
    {
        "id": "kb_regulatory_intelligence",
        "title": "Regulatory Pathways & Compliance Intelligence",
        "content": (
            "The Regulatory Intelligence module determines statutory pathways and compliance mandates for Ayurvedic products in India:\n"
            "• Dual Statutory Pathways: Classifies products between ASU Drug framework (Ayurvedic Classical Medicine vs Ayurvedic Proprietary Medicine "
            "under Drugs & Cosmetics Act, 1940 & Rules 1945) and FSSAI Food Safety framework (Nutraceuticals & Health Supplements Regulations 2022).\n"
            "• Mandatory Testing Mandates: Flags statutory lab tests under the Ayurvedic Pharmacopoeia of India (API), including heavy metal thresholds "
            "(lead, mercury, cadmium, arsenic), microbial limits, pesticide residues, and aflatoxins.\n"
            "• Advertising & Claims Compliance: Identifies permissible health maintenance claims vs prohibited therapeutic claims under the Drugs and "
            "Magic Remedies (Objectionable Advertisements) Act, 1954 and ASCI codes."
        ),
        "tags": [
            "regulatory intelligence", "what does regulatory intelligence do", "regulatory",
            "compliance", "ayush", "fssai", "drugs and cosmetics act", "rules", "nirdesh",
            "kanoon", "approval", "statutory", "regulations", "licensing"
        ],
        "related_feature": "Regulatory Intelligence",
        "default_action": "OPEN_REGULATORY",
    },
    {
        "id": "kb_risk_assessment",
        "title": "Multi-Domain Risk Assessment",
        "content": (
            "The Risk Assessment module synthesizes bounded case evidence across 5 core domains into an executive risk matrix:\n"
            "1. IP & Patent Freedom-to-Operate Risk (Section 3(p) collision, third-party patent infringement).\n"
            "2. Regulatory Classification Ambiguity (borderline ASU drug vs FSSAI nutraceutical).\n"
            "3. Claims & Advertising Exposure (curative/disease-treatment claim penalties under DMR Act).\n"
            "4. Ingredient & Formulation Safety (schedule E(1) poisonous plants, safe limits, contraindications).\n"
            "5. Market & Commercial Readiness.\n"
            "Output includes an Overall Risk Score (0-100), severity levels (Low, Moderate, High, Critical), confidence ratings, "
            "evidence gap analysis, and phased mitigation plans (immediate, before submission, before launch). Powered by Gemini with a rule engine fallback."
        ),
        "tags": [
            "risk", "risk assessment", "ai risk", "mitigation", "severity",
            "compliance risk", "khatra", "risk check", "risk profile"
        ],
        "related_feature": "Risk Assessment",
        "default_action": "OPEN_RISK",
    },
    {
        "id": "kb_monitoring",
        "title": "Continuous Regulatory & Surveillance Monitoring",
        "content": (
            "The Monitoring Center provides real-time surveillance tailored to each product case:\n"
            "• Regulatory Gazette & Circulars: Tracks new notices from Ministry of AYUSH, FSSAI advisories, CDSCO drug alerts, and State Licensing Authorities.\n"
            "• Ingredient Bans & Safety Alerts: Alerts on newly restricted botanical species, safety advisories, and updated permissible contaminant limits.\n"
            "• Competitor Patent Watch: Monitors new patent filings and published grants at the Indian Patent Office containing your formulation's active herbs.\n"
            "Product isolation is strictly preserved so monitoring streams remain separate for each product case."
        ),
        "tags": [
            "what is monitoring", "monitoring", "surveillance", "alerts", "watch",
            "tracking", "monitoring kholo", "monitoring center", "advisories", "gazette"
        ],
        "related_feature": "Monitoring Center",
        "default_action": "OPEN_MONITORING",
    },
    {
        "id": "kb_evidence_hub",
        "title": "Unified Evidence Hub",
        "content": (
            "The Unified Evidence Hub links your product formulation and promotional claims directly to authoritative scientific and classical sources:\n"
            "• Classical Samhitas: Verbatim citations from Charaka Samhita, Sushruta Samhita, and Ashtanga Hridaya.\n"
            "• Pharmacopoeias: Monographs from the Ayurvedic Pharmacopoeia of India (API) and Ayurvedic Formulary of India (AFI).\n"
            "• Modern Clinical Research: Peer-reviewed clinical trials and pharmacological studies indexed from PubMed and DHARA.\n"
            "• Patent & Prior-Art Records: Referenced IPO patent documents.\n"
            "Every finding features an evidence confidence score, data origin tag, and traceable excerpt."
        ),
        "tags": [
            "evidence", "evidence hub", "clinical research", "samhita", "charaka",
            "api", "traceability", "proof", "praman", "unified evidence"
        ],
        "related_feature": "Unified Evidence Hub",
        "default_action": "OPEN_EVIDENCE",
    },
    {
        "id": "kb_decision_dashboard",
        "title": "Executive Decision Dashboard",
        "content": (
            "The Decision Dashboard aggregates readiness metrics across all intelligence modules into a strategic go/no-go evaluation:\n"
            "• Overall Commercial Readiness Score (0-100).\n"
            "• Domain Readiness Breakdown: IP readiness, regulatory clarity, scientific evidence strength, and formulation freeze.\n"
            "• Phased Milestone Roadmap: Clear milestones from R&D and lab validation to licensing filing and commercial launch.\n"
            "• Statutory Action Checklist: Key legal, clinical, and regulatory tasks required prior to market launch."
        ),
        "tags": [
            "decision dashboard", "readiness", "go no go", "executive dashboard",
            "milestones", "commercialization", "roadmap"
        ],
        "related_feature": "Decision Dashboard",
        "default_action": "OPEN_DECISION_DASHBOARD",
    },
    {
        "id": "kb_limitations_and_disclaimer",
        "title": "Platform Boundaries & Legal Disclaimers",
        "content": (
            "IMPORTANT PLATFORM LIMITATIONS & BOUNDARIES:\n"
            "• AYUR-INTEL does NOT guarantee patent approval, patent grant, patentability, or official clearance from the Indian Patent Office or any international authority.\n"
            "• AYUR-INTEL does NOT guarantee regulatory approval, statutory compliance, or licensing from the Ministry of AYUSH, State Licensing Authorities, or FSSAI.\n"
            "• AYUR-INTEL is an evidence-backed intelligence and decision-support system, NOT a legal or regulatory certifying body. All classifications, novelty signals, and risk scores are advisory.\n"
            "• Official patent applications and regulatory dossiers must always be reviewed by certified patent attorneys and qualified Ayurvedic regulatory practitioners."
        ),
        "tags": [
            "guarantee", "approval", "patent approval", "regulatory approval",
            "does it guarantee patent approval", "does it guarantee regulatory compliance",
            "guarantee patent", "guarantee compliance", "legal advice", "disclaimer",
            "limitations", "pakka hoga", "guarantee hai"
        ],
        "related_feature": "Disclaimers & Boundaries",
        "default_action": "OPEN_DASHBOARD",
    },
    {
        "id": "kb_navigation_guide",
        "title": "AYUR-INTEL Navigation & Shortcuts",
        "content": (
            "How to navigate the AYUR-INTEL interface:\n"
            "• Topbar: Switch active product case via the center dropdown ('Active Product: ...'). Click '+ New' to create a formulation.\n"
            "• Sidebar Workspace: Dashboard (overview metrics), Plant Discovery (botanical identification), Products (saved formulations), "
            "Case Intelligence (active product command center), Knowledge Hub (herbal monographs), Monitoring (circulars & patent watches).\n"
            "• Ask AYUR-INTEL Assistant: Click the bottom-right floating leaf button anytime to ask questions, explore features, or get direct navigation buttons."
        ),
        "tags": [
            "navigation", "how to use", "guide", "menu", "sidebar", "topbar",
            "how to navigate", "kaha hai", "kholna", "kaise use kare"
        ],
        "related_feature": "Navigation & UI",
        "default_action": "OPEN_DASHBOARD",
    },
]
