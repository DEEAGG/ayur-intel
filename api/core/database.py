"""AYUR-INTEL — Database engine and session management.

Uses SQLAlchemy with SQLite for local development.
To switch to PostgreSQL: change DATABASE_URL in .env.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from api.core.config import settings

logger = logging.getLogger("ayur_intel.database")

# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

# Production: PostgreSQL (Supabase) — Vercel pe use hoga
_DATABASE_URL = os.getenv("DATABASE_URL")

if not _DATABASE_URL:
    # Development: SQLite — local pe use hoga
    _DATABASE_URL = f"sqlite:///{settings.AYURINTEL_DB_PATH}"
    logger.info("🔗 Using SQLite (Development)")
else:
    logger.info("🔗 Using PostgreSQL (Production)")

engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in _DATABASE_URL else {},
    echo=settings.AYURINTEL_DEBUG,
    pool_pre_ping=True,
)

# Enable foreign keys for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite connections."""
    if "sqlite" in str(engine.url):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """Yield a database session. Used as a FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Create all tables if they don't exist.
    Import models before calling this so SQLAlchemy registers them.
    """
    from api.models import models  # noqa: F401 — triggers model registration
    Path(settings.AYURINTEL_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at %s", settings.AYURINTEL_DB_PATH)
