"""AYUR-INTEL — Database engine and session management.

Uses SQLAlchemy with SQLite for local development.
To switch to PostgreSQL: change DATABASE_URL in .env.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("ayur_intel.database")

# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

# Production: PostgreSQL (Supabase) — Vercel pe use hoga
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Vercel Production: PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
    )
    logger.info("🔗 Using PostgreSQL (Production)")
else:
    # Development: SQLite
    from api.core.config import settings

    engine = create_engine(
        f"sqlite:///{settings.AYURINTEL_DB_PATH}",
        connect_args={"check_same_thread": False},
        echo=settings.AYURINTEL_DEBUG,
        pool_pre_ping=True,
    )
    logger.info("🔗 Using SQLite (Development)")

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

    if not DATABASE_URL:
        # Only create SQLite directory if using SQLite
        Path(settings.AYURINTEL_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    models.Base.metadata.create_all(bind=engine)

    # Auto-migration: ensure is_demo column exists in product_cases for existing PostgreSQL/SQLite DBs
    with engine.begin() as conn:
        try:
            if "sqlite" in str(engine.url):
                conn.execute(text("ALTER TABLE product_cases ADD COLUMN is_demo BOOLEAN DEFAULT 0"))
            else:
                conn.execute(text("ALTER TABLE product_cases ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_cases_is_demo ON product_cases (is_demo)"))
        except Exception as e:
            logger.debug("Column migration note: %s", e)

    logger.info("Database initialized successfully")