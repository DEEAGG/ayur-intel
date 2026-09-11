"""AYUR-INTEL — FastAPI Application.

Main application entry point. Serves the API and static frontend.

Run with:
    cd ayur-intel
    python -m api.main
    # or
    uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.core.config import PROJECT_ROOT, settings
from api.core.database import init_db
from api.routers import health, innovation, knowledge, patent, patent_analysis, ip_strategy, regulatory, plant_discovery, product_cases, jurisdiction_comparison, evidence, risk, decision, monitoring, knowledge_graph, source_router, security, review, analytics, ingredients, auth

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if settings.AYURINTEL_DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ayur_intel")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AYUR-INTEL",
    description=(
        "Evidence-backed Ayurvedic Product Intelligence & "
        "Decision-Support Platform"
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

allowed_origins = [
    o.strip()
    for o in settings.AYURINTEL_CORS_ALLOW_ORIGINS.split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(product_cases.router)
app.include_router(plant_discovery.router)
app.include_router(knowledge.router)
app.include_router(innovation.router)
app.include_router(patent.router)
app.include_router(patent_analysis.router)
app.include_router(ip_strategy.router)
app.include_router(regulatory.router)
app.include_router(jurisdiction_comparison.router)
app.include_router(evidence.router)
app.include_router(risk.router)
app.include_router(decision.router)
app.include_router(monitoring.router)
app.include_router(knowledge_graph.router)
app.include_router(source_router.router)
app.include_router(security.router)
app.include_router(review.router)
app.include_router(analytics.router)
app.include_router(ingredients.router)

# ---------------------------------------------------------------------------
# Security Headers Middleware

from api.core.security import security_headers_middleware

app.middleware("http")(security_headers_middleware)

# ---------------------------------------------------------------------------
# Request Correlation ID Middleware

import uuid

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to every request for tracing."""
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:16]
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id
    return response

# ---------------------------------------------------------------------------
# Static files & SPA fallback
# ---------------------------------------------------------------------------

WEB_ROOT = PROJECT_ROOT / "web"

# Mount static assets
if (WEB_ROOT / "static").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    """Serve the main SPA index.html."""
    index_path = WEB_ROOT / "templates" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse(
        "<h1>AYUR-INTEL</h1><p>Frontend not built yet. "
        "See <a href='/api/docs'>API docs</a>.</p>"
    )


# SPA fallback — serve index.html for any non-API, non-static route
@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def spa_fallback(full_path: str):
    """SPA fallback: serve index.html for client-side routed paths."""
    # Don't intercept API or static routes
    if full_path.startswith("api/") or full_path.startswith("static/"):
        return JSONResponse({"error": "Not found"}, status_code=404)

    index_path = WEB_ROOT / "templates" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse(
        "<h1>AYUR-INTEL</h1><p>Frontend not built yet.</p>"
    )


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    """Initialize database on application startup."""
    logger.info("AYUR-INTEL starting up...")
    logger.info("Database: %s", settings.AYURINTEL_DB_PATH)
    logger.info("Demo mode: %s", settings.AYURINTEL_DEMO_MODE)

    # Initialize database tables & perform canonical demo migration if needed
    init_db()
    try:
        from api.core.database import SessionLocal
        from api.services.product_case_service import get_or_create_demo_user, get_or_create_demo_case
        db = SessionLocal()
        try:
            demo_user = get_or_create_demo_user(db)
            get_or_create_demo_case(db, demo_user)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Startup demo initialization note: %s", e)

    logger.info("AYUR-INTEL ready at http://%s:%s", settings.AYURINTEL_HOST, settings.AYURINTEL_PORT)
    logger.info("API docs at http://%s:%s/api/docs", settings.AYURINTEL_HOST, settings.AYURINTEL_PORT)


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on application shutdown."""
    logger.info("AYUR-INTEL shutting down.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.AYURINTEL_HOST,
        port=settings.AYURINTEL_PORT,
        reload=settings.AYURINTEL_DEBUG,
    )
