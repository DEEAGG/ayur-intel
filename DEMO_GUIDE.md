# AYUR-INTEL — SIH Demonstration Guide

## Overview

AYUR-INTEL is an **Evidence-backed Ayurvedic Product Intelligence & Decision-Support Platform**.

This guide explains how to demonstrate the complete system for Smart India Hackathon (SIH).

---

## ⚠️ Important Disclaimers

- **AI analysis is advisory only** — it is NOT legal, medical, or regulatory advice
- All patent/regulatory findings are based on **simulated sources** for demonstration
- The system does NOT provide patentability conclusions or regulatory approvals
- Always consult qualified experts for actual product decisions
- Plant identification is for reference only — never consume unidentified plants

---

## Quick Start

### Option 1: Fresh Demo Data

```bash
cd ayur-intel
python start_server.py &
sleep 5
python scripts/create_demo_data.py
```

### Option 2: Existing Data

Start the server and open `http://127.0.0.1:8000` — demo cases are already loaded.

---

## SIH Demonstration Flow (15 Steps)

### Step 1: Product Discovery

**What the user sees:**
- Dashboard with existing Product Cases
- Ability to create new cases or discover unknown plants

**What to say:**
> "AYUR-INTEL helps innovators analyze Ayurvedic products for patent, regulatory, and market intelligence. Let me show you a complete workflow."

**Action:** Click on "AshwaCalm — Stress Relief & Cognitive Support" case.

---

### Step 2: Product Passport

**What the user sees:**
- Complete product information: name, ingredients, formulation, claims
- Jurisdictions: India, USA, Germany
- Guided data collection for beginners

**What to say:**
> "The Product Passport captures all essential information about the Ayurvedic product — ingredients with botanical names, formulation details, and target markets."

**Key points to mention:**
- Ingredients: Ashwagandha, Brahmi, Shankhpushpi, Jatamansi
- Each with botanical (Latin) name
- Form: Capsule
- Target jurisdictions: IN, US, DE

---

### Step 3: Innovation Analysis

**What the user sees:**
- Traditional vs Differentiated components identified
- Innovation decomposition showing product structure

**What to say:**
> "The system decomposes the product into innovation components — identifying which aspects are traditional knowledge-based and which represent differentiated innovation."

**Key points:**
- Traditional Knowledge components (e.g., Ashwagandha formulation)
- Differentiated components (e.g., specific extraction process)

---

### Step 4: Patent Intelligence

**What the user sees:**
- Patent search results across jurisdictions
- Patent relevance scoring
- Potential overlap detection

**What to say:**
> "AYUR-INTEL searches patent databases to identify potentially relevant patents. It shows jurisdiction, relevance, and potential overlap — but never claims patentability or infringement."

**Key disclaimer:**
> "This is a potential patent overlap detection, NOT an infringement analysis. Patent attorneys should review all findings."

---

### Step 5: IP Strategy Map

**What the user sees:**
- IP strategy recommendations
- Patent, trademark, trade secret considerations
- Priority-ranked strategy items

**What to say:**
> "The IP Strategy module provides strategic recommendations based on the innovation analysis and patent findings."

---

### Step 6: Regulatory Intelligence

**What the user sees:**
- Multi-jurisdiction regulatory profiles
- Product classification for each jurisdiction
- Requirements specific to India, USA, and Germany

**What to say:**
> "Regulatory Intelligence analyzes the product against each target jurisdiction's requirements. Note how the regulatory classification differs — India recognizes traditional medicine, while Germany has different herbal product categories."

**Key demonstration:**
- India: Traditional Medicine / Ayurvedic Drug
- USA: Dietary Supplement (DSHEA)
- Germany: Herbal Medicinal Product (EU Directive 2004/24/EC)

---

### Step 7: Jurisdiction Comparison

**What the user sees:**
- Side-by-side comparison of regulatory requirements
- Key differences highlighted
- Recommendation for each jurisdiction

**What to say:**
> "The Jurisdiction Comparison shows at a glance how requirements differ. For example, Germany requires a registered herbal product, while India has a simplified pathway for traditional Ayurvedic products."

---

### Step 8: Risk Analysis

**What the user sees:**
- Risk categories: Patent/IP, Regulatory, Claims, Evidence gaps
- Risk levels: HIGH, MEDIUM, LOW
- Risk evidence and recommended next actions

**What to say:**
> "Risk Analysis identifies potential concerns across all dimensions — regulatory classification uncertainty, claims that need verification, and evidence gaps. Each risk includes evidence and a recommended next step."

**Key disclaimer:**
> "Risk levels are advisory signals, not danger assessments. They indicate areas that need human expert review."

---

### Step 9: Evidence & Citation

**What the user sees:**
- Evidence items linked to findings
- Source citations
- Evidence coverage status

**What to say:**
> "Every important finding is backed by evidence with source citations. The Evidence Engine ensures traceability — you can always trace back to the original source."

---

### Step 10: Decision Dashboard

**What the user sees:**
- Overall decision summary
- Readiness assessment
- Next steps recommended
- Analysis completeness

**What to say:**
> "The Decision Dashboard provides a single view of all analysis results. It shows readiness status and specific next steps — for example, configuring source adapters for live patent/regulatory data."

**Key disclaimer:**
> "This dashboard is a decision-support tool. Final product decisions should always involve qualified legal and regulatory experts."

---

### Step 11: Continuous Monitoring

**What the user sees:**
- Monitoring configuration (enabled, weekly)
- Sources being monitored
- Recent alerts and monitoring history

**What to say:**
> "Once a product case is saved, AYUR-INTEL can monitor relevant sources for changes — new patents, regulatory updates, or jurisdiction-specific requirement changes."

---

### Step 12: Knowledge Graph

**What the user sees:**
- Interactive graph visualization
- Nodes: Product, Ingredients, Patents, Regulations, Risks, Evidence
- Relationships between entities
- Zoom, pan, search, and filter capabilities

**What to say:**
> "The Knowledge Graph visualizes all relationships in the product case — from ingredients to plants, from patents to jurisdictions, from evidence to sources. This helps understand the interconnected nature of product intelligence."

**Action:** Use the graph — zoom, click on nodes, show details, filter by type.

---

### Step 13: AI Source Router

**What the user sees:**
- Question input
- Automatic topic classification
- Jurisdiction detection
- Source routing with explanation

**What to say:**
> "When users ask questions, the Source Router intelligently determines what type of source should answer — patent authority for patent questions, regulatory sources for regulatory questions. It considers jurisdiction automatically."

**Demo question:**
> "What are the regulatory requirements for ashwagandha in Germany?"
> → Routes to: EU Regulatory Sources (Germany jurisdiction detected)

---

### Step 14: Human Review

**What the user sees:**
- Review queue
- Review detail with evidence
- Decision options: Confirm, Reject, More Info, Escalate

**What to say:**
> "High-risk findings automatically trigger human review requests. The reviewer can inspect all evidence, sources, and AI reasoning before making a decision."

**Key principle:**
> "AI is advisory. Important decisions require human expert review."

---

### Step 15: Analytics

**What the user sees:**
- Product analysis metrics
- Workflow funnel
- Risk distribution
- Evidence coverage

**What to say:**
> "Analytics provide insight into the analysis workflow — how many components were analyzed, risk distribution, evidence coverage, and workflow progression."

---

## Plant Discovery Demo (Optional)

If time permits, demonstrate the Plant Discovery feature:

1. Navigate to Plant Discovery
2. Upload a plant image (or use demo)
3. Show "Possible Identification" with confidence warning
4. Show safety warning: "Expert verification recommended"
5. Create Product Passport from discovery

**What to say:**
> "AYUR-INTEL can help identify unknown plants from images, but always with clear confidence indicators and safety warnings. Never consume an unidentified plant based only on AI identification."

---

## Key Selling Points for SIH

1. **End-to-End Intelligence**: From product creation to monitoring — all 21 phases integrated
2. **Multi-Jurisdiction**: India, USA, Germany — with jurisdiction-aware routing
3. **Evidence-Based**: Every finding has evidence with source citations
4. **Human-in-the-Loop**: High-risk findings trigger expert review
5. **Knowledge Graph**: Visualizes complex product-intelligence relationships
6. **Safety-First**: Clear disclaimers, no false claims, AI is advisory only
7. **Production-Ready**: Security headers, audit logging, input validation

---

## Technical Architecture (for judges)

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | Vanilla JS SPA |
| Graph Viz | D3.js force-directed |
| Security | CORS, CSP, CSRF, Audit Logging |
| Phases | 21 integrated phases |

---

## Common Judge Questions

**Q: Is this a replacement for patent attorneys?**
A: No. AYUR-INTEL is a decision-support tool. It provides intelligence and evidence, but all legal conclusions require qualified professionals.

**Q: Are the patent/regulatory results real?**
A: For this demonstration, results are from simulated sources. In production, it would connect to real patent offices and regulatory databases.

**Q: How does AI help?**
A: AI assists with classification, summarization, and routing. It never invents patents, regulations, or evidence. All factual claims must be grounded in source evidence.

**Q: Can this be used for non-Ayurvedic products?**
A: The current system is optimized for Ayurvedic/herbal products, but the architecture supports extension to other traditional medicine systems.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Server not running | `cd ayur-intel && python start_server.py` |
| No demo data | `python scripts/create_demo_data.py` |
| Blank page | Hard refresh (Ctrl+Shift+R) |
| API errors | Check server logs at `.freebuff/preview-*.log` |
