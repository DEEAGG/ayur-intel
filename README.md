# AYUR-INTEL

**Evidence-backed Ayurvedic Product Intelligence & Decision-Support Platform**

AYUR-INTEL is a comprehensive intelligence platform that helps Ayurvedic product innovators navigate the complex landscape of patent protection, regulatory compliance, and market entry across multiple jurisdictions.

---

## ⚠️ Important Disclaimers

- **AYUR-INTEL is a decision-support tool**, not a patent office, law firm, or regulatory authority
- **AI analysis is advisory only** — all legal/regulatory conclusions require qualified experts
- **Patent findings are overlap detection**, not infringement analysis or patentability opinions
- **Regulatory information requires verification** with official sources
- **Plant identification is for reference only** — never consume unidentified plants
- **Always consult qualified professionals** for actual product decisions

---

## Features (21 Phases)

| Phase | Feature | Description |
|-------|---------|-------------|
| 1 | Infrastructure | Health checks, database, configuration |
| 2 | Product Cases | Create, manage, track Ayurvedic product cases |
| 3-4 | Product Passport | Guided data collection for product information |
| 5 | Innovation Analysis | Decompose products into traditional vs differentiated components |
| 6 | Patent Intelligence | Search patent databases across jurisdictions |
| 7 | Patent Deep Analysis | Detailed patent overlap analysis |
| 8 | IP Strategy | Strategic IP recommendations |
| 9 | Regulatory Intelligence | Multi-jurisdiction regulatory analysis |
| 10 | Jurisdiction Comparison | Side-by-side regulatory comparison |
| 11 | Evidence & Citation | Evidence tracking with source citations |
| 12 | Risk & Self-Extension | Risk detection and information gap resolution |
| 13 | Decision Dashboard | Unified decision summary and next steps |
| 14 | Continuous Monitoring | Monitor sources for changes and updates |
| 15 | Knowledge Graph | Interactive visualization of entity relationships |
| 16 | AI Source Router | Intelligent question routing to authoritative sources |
| 17 | Security & Data Protection | Authentication, authorization, audit logging |
| 18 | Human-in-the-Loop Review | Expert review workflow for high-risk findings |
| 19 | Analytics & Impact Intelligence | Workflow analytics and metrics |
| 20 | Production Readiness | Health checks, deployment config, documentation |
| 21 | Final Integration | End-to-end validation and launch preparation |

---

## Quick Start

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd ayur-intel

# Install dependencies
pip install -r requirements.txt

# Start the server
python start_server.py
```

### Access

- **Application**: http://127.0.0.1:8000
- **API Documentation**: http://127.0.0.1:8000/api/docs
- **Health Check**: http://127.0.0.1:8000/api/health

---

## Demo Data

```bash
# Start the server first
python start_server.py &

# Create demo data
python scripts/create_demo_data.py
```

See [DEMO_GUIDE.md](DEMO_GUIDE.md) for the complete SIH demonstration flow.

---

## Architecture

```
AYUR-INTEL
├── api/                    # FastAPI backend
│   ├── core/              # Configuration, database, security
│   ├── models/            # SQLAlchemy models
│   ├── routers/           # API route handlers
│   ├── schemas/           # Pydantic request/response schemas
│   └── services/          # Business logic services
├── web/                   # Frontend SPA
│   ├── templates/         # HTML templates
│   └── static/            # CSS, JavaScript, assets
├── scripts/               # Utility scripts
├── data/                  # Data files
└── docs/                  # Documentation
```

### Key Technologies

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.9+, FastAPI, SQLAlchemy |
| Database | SQLite (development), PostgreSQL (production) |
| Frontend | Vanilla JavaScript, D3.js |
| Security | CORS, CSP, CSRF protection, audit logging |

---

## API Endpoints

### Core
- `GET /api/health` — Health check
- `GET /api/ready` — Readiness check

### Product Cases
- `GET /api/cases` — List cases
- `POST /api/cases` — Create case
- `GET /api/cases/{id}` — Get case details

### Intelligence
- `POST /api/cases/{id}/innovation-analysis` — Run innovation analysis
- `POST /api/cases/{id}/patent-search` — Search patents
- `POST /api/cases/{id}/regulatory-analysis` — Run regulatory analysis
- `POST /api/cases/{id}/jurisdiction-comparison` — Compare jurisdictions

### Decision Support
- `GET /api/cases/{id}/decision-dashboard` — Decision summary
- `POST /api/cases/{id}/risk-analysis` — Risk analysis
- `GET /api/cases/{id}/knowledge-graph` — Knowledge graph

### Monitoring
- `GET /api/cases/{id}/monitoring` — Monitoring configuration
- `POST /api/cases/{id}/monitoring/run` — Run monitoring check

### Security
- `GET /api/security/status` — Security features status
- `GET /api/security/audit-logs` — Audit log entries

Full API documentation: http://127.0.0.1:8000/api/docs

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AYURINTEL_HOST` | Server host | `127.0.0.1` |
| `AYURINTEL_PORT` | Server port | `8000` |
| `AYURINTEL_DB_PATH` | Database file path | `./data/ayur_intel.db` |
| `AYURINTEL_DEMO_MODE` | Enable demo mode | `true` |
| `AYURINTEL_DEBUG` | Enable debug logging | `true` |
| `AYURINTEL_SESSION_SECRET` | Session secret key | Auto-generated |
| `AYURINTEL_CORS_ALLOW_ORIGINS` | CORS origins | `http://127.0.0.1:8000` |

See `.env.example` for the complete list.

---

## Documentation

| Document | Description |
|----------|-------------|
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | SIH demonstration flow |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment guide |
| [SECURITY.md](SECURITY.md) | Security review and configuration |

---

## Project Status

**READY WITH LIMITATIONS**

- ✅ All 21 phases implemented and tested
- ✅ End-to-end workflow functional
- ✅ Security features active
- ✅ Demo data available
- ⚠️ External source connections are simulated
- ⚠️ No production authentication (demo mode only)
- ⚠️ No automated CI/CD pipeline

---

## License

Proprietary — Smart India Hackathon (SIH) 2026
