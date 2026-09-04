# AYUR-INTEL — Architecture

## System Overview

AYUR-INTEL is a monolithic web application with a Python FastAPI backend and vanilla JavaScript SPA frontend.

```
┌─────────────────────────────────────────────────────┐
│                    Browser (SPA)                      │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ │
│  │Dashboard │ │ Case View│ │  Graph  │ │ Reviews  │ │
│  └─────────┘ └──────────┘ └─────────┘ └──────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────┴──────────────────────────────┐
│                   FastAPI Backend                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │Routers(20)│ │Services  │ │ Models   │ │Schemas │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Security │ │ Audit    │ │ Config   │            │
│  └──────────┘ └──────────┘ └──────────┘            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│              SQLite / PostgreSQL Database              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Product  │ │ Evidence │ │ Security │            │
│  │ Cases    │ │ & Risk   │ │ & Audit  │            │
│  └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────┘
```

---

## Backend Structure

```
api/
├── __init__.py
├── main.py              # FastAPI app, middleware, startup
├── core/
│   ├── config.py        # Pydantic settings (env vars)
│   ├── database.py      # SQLAlchemy engine & session
│   └── security.py      # Security middleware, validation, auth helpers
├── models/
│   ├── __init__.py      # Model imports
│   ├── models.py        # Core models (User, ProductCase, etc.)
│   ├── evidence.py      # Evidence & citation models
│   ├── risk.py          # Risk & self-extension models
│   ├── monitoring.py    # Monitoring models
│   ├── jurisdiction_comparison.py
│   ├── decision.py      # Decision dashboard models
│   ├── review.py        # Human review models
│   └── security.py      # Audit log model
├── routers/             # API route handlers (20 routers)
│   ├── health.py        # /api/health, /api/ready, /api/info
│   ├── product_cases.py # CRUD for product cases
│   ├── plant_discovery.py # Plant identification
│   ├── knowledge.py     # Traditional knowledge
│   ├── innovation.py    # Innovation decomposition
│   ├── patent.py        # Patent intelligence
│   ├── patent_analysis.py # Deep patent analysis
│   ├── ip_strategy.py   # IP strategy
│   ├── regulatory.py    # Regulatory intelligence
│   ├── jurisdiction_comparison.py
│   ├── evidence.py      # Evidence & citations
│   ├── risk.py          # Risk analysis
│   ├── decision.py      # Decision dashboard
│   ├── monitoring.py    # Continuous monitoring
│   ├── knowledge_graph.py # Knowledge graph
│   ├── source_router.py # AI source router
│   ├── security.py      # Security endpoints
│   ├── review.py        # Human review
│   └── analytics.py     # Analytics
├── schemas/             # Pydantic request/response schemas
│   ├── product_case.py
│   ├── patent.py
│   ├── regulatory.py
│   └── decision.py
└── services/            # Business logic (22 services)
    ├── product_case_service.py
    ├── innovation_service.py
    ├── patent_service.py
    ├── patent_analysis_service.py
    ├── patent_adapter.py
    ├── ip_strategy_service.py
    ├── regulatory_service.py
    ├── regulatory_adapter.py
    ├── jurisdiction_comparison_service.py
    ├── evidence_service.py
    ├── risk_service.py
    ├── decision_service.py
    ├── monitoring_service.py
    ├── knowledge_graph_service.py
    ├── source_router_service.py
    ├── source_adapter.py
    ├── plant_discovery_service.py
    ├── plant_identification.py
    ├── knowledge_service.py
    ├── audit_service.py
    ├── review_service.py
    └── analytics_service.py
```

---

## Database Schema (Key Tables)

### Core
- `users` — User accounts
- `product_cases` — Product cases (central entity)
- `innovation_components` — Innovation decomposition
- `innovation_analyses` — Analysis run history

### Patent & IP
- `patent_records` — Patent search results
- `patent_relevances` — Relevance scoring
- `patent_analyses` — Deep analysis results
- `patent_comparisons` — Comparison data
- `ip_strategy_items` — IP strategy recommendations

### Regulatory
- `regulatory_profiles` — Jurisdiction regulatory profiles
- `regulatory_requirements` — Specific requirements
- `jurisdiction_comparisons` — Cross-jurisdiction data
- `jurisdiction_comparison_items` — Comparison details

### Evidence & Risk
- `unified_evidence` — Evidence records
- `case_findings` — Findings with evidence links
- `risks` — Risk records
- `risk_evidence` — Risk-evidence associations
- `self_extension_requests` — Information gap resolution

### Monitoring
- `monitoring_configs` — Per-case monitoring settings
- `monitoring_sources` — Monitored sources
- `monitoring_runs` — Monitoring run history
- `monitoring_alerts` — Alert records

### Knowledge Graph
- (Dynamically generated — no persistent graph tables)

### Security & Review
- `audit_logs` — Security audit trail
- `review_requests` — Human review queue
- `review_items` — Review entity references
- `review_decisions` — Reviewer decisions
- `review_history` — Status change history

### Decision
- `decision_snapshots` — Dashboard state snapshots

---

## Data Flow

### Product Analysis Flow
```
Product Case Created
    ↓
Product Passport (ingredients, formulation, claims)
    ↓
Innovation Analysis (traditional vs differentiated)
    ↓
Patent Search (jurisdiction-aware)
    ↓
Patent Deep Analysis (overlap detection)
    ↓
IP Strategy (recommendations)
    ↓
Regulatory Intelligence (per jurisdiction)
    ↓
Jurisdiction Comparison (side-by-side)
    ↓
Risk Analysis (all phases combined)
    ↓
Evidence & Citation (linked to findings)
    ↓
Decision Dashboard (unified summary)
    ↓
Continuous Monitoring (source tracking)
    ↓
Knowledge Graph (relationship visualization)
```

### Security Flow
```
Request → Correlation ID → Security Headers → CORS → Authentication → Authorization → Route Handler
    ↓
Audit Logging → Response
```

### Risk Detection Flow
```
Risk Analysis Triggered
    ↓
Detect Patent Risks (from Phase 6-7)
    ↓
Detect Regulatory Risks (from Phase 9-10)
    ↓
Detect Claims Risks (from Product Passport)
    ↓
Detect Information Risks (missing data)
    ↓
Detect Jurisdiction Risks (cross-jurisdiction)
    ↓
Deduplication (skip existing risks)
    ↓
Create Risk Records + Evidence Links
    ↓
Self-Extension Requests (for gaps)
```

---

## Middleware Stack

1. **CORSMiddleware** — Cross-origin request handling
2. **Security Headers** — CSP, X-Content-Type, X-Frame, X-XSS, Referrer-Policy
3. **Correlation ID** — Request tracing via X-Request-ID

---

## Frontend Architecture

```
web/
├── templates/
│   └── index.html          # SPA entry point
└── static/
    ├── js/
    │   └── app.js          # Main application (SPA routing, state, rendering)
    ├── css/
    │   └── styles.css      # All styling
    └── lib/
        └── d3.min.js       # D3.js for knowledge graph
```

### SPA State Management
- Simple object-based state: `window.AYUR = { state, ... }`
- Views: dashboard, case-detail, innovation, patents, regulatory, etc.
- No build step — vanilla JavaScript

### Graph Visualization
- D3.js force-directed layout
- Zoom, pan, drag, search, filter
- Node detail panel on click

---

## Security Architecture

### Authentication
- Demo mode: auto-created demo user
- Production: session-based with configurable TTL

### Authorization
- All endpoints require `get_current_user` dependency
- Product Case ownership verified on every access
- IDOR protection: unauthorized access returns 404

### Input Validation
- Pydantic schemas with min/max constraints
- HTML escaping via `html.escape()`
- ID validation: alphanumeric + hyphens only

### Audit Logging
- All major actions logged to `audit_logs` table
- Metadata sanitized (no passwords, tokens, secrets)
- Queryable via `GET /api/security/audit-logs`

### Security Headers
- Content-Security-Policy (CSP)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

---

## Deployment

### Development
```bash
cd ayur-intel
pip install -r requirements.txt
python start_server.py
```

### Production
```bash
# Set environment variables
export AYURINTEL_DEMO_MODE=false
export AYURINTEL_DEBUG=false
export AYURINTEL_SESSION_SECRET=<strong-random-value>

# Run with production server
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment guide.

---

## Key Design Decisions

1. **Monolithic architecture** — Appropriate for team size and deployment simplicity
2. **SQLite for development** — Zero-config, easy setup; PostgreSQL-ready for production
3. **No build step** — Vanilla JS SPA with no Node.js dependency
4. **Server-side aggregation** — Analytics computed on backend, no raw data exposure
5. **Dedicated risk deduplication** — Prevents duplicate risks on re-analysis
6. **Dynamic knowledge graph** — No persistent graph storage; built from existing entities
7. **Simulated sources** — Architecture ready for live integration; demo uses simulated data
