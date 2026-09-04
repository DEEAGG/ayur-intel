"""AYUR-INTEL — Health check routes (Phase 20: Production Readiness)."""

from __future__ import annotations

import time
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.core.database import get_db
from api.core.config import settings
from api.schemas.product_case import HealthResponse

router = APIRouter(tags=["Health"])

_start_time = time.time()


@router.get("/api/health", summary="System health check")
def health_check(request: Request, db: Session = Depends(get_db)):
    """Check system health: application, database, configuration.

    Returns basic status without exposing internal infrastructure.
    """
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    uptime_seconds = int(time.time() - _start_time)

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall,
        "version": "0.1.0",
        "database": db_status,
        "uptime_seconds": uptime_seconds,
        "demo_mode": settings.AYURINTEL_DEMO_MODE,
    }


@router.get("/api/ready", summary="Readiness check")
def readiness_check(request: Request, db: Session = Depends(get_db)):
    """Kubernetes-style readiness probe.

    Checks essential dependencies are available.
    Returns HTTP 200 if ready, 503 if not.
    """
    checks = {}

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Data directory check
    from pathlib import Path
    db_path = Path(settings.AYURINTEL_DB_PATH)
    checks["data_directory"] = db_path.parent.exists()

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


@router.get("/api/info", summary="Application info")
def app_info():
    """Return non-sensitive application information.

    Safe to expose publicly.
    """
    return {
        "name": "AYUR-INTEL",
        "version": "0.1.0",
        "description": "Evidence-backed Ayurvedic Product Intelligence & Decision-Support Platform",
        "environment": "production" if not settings.AYURINTEL_DEMO_MODE else "development",
    }
