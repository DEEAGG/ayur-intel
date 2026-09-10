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
    # Production: PostgreSQL (Supabase / Render)
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=False,
    )
    logger.info("🔗 Using PostgreSQL with connection pooling (Production)")
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

    # Auto-migration & performance indexes for existing SQLite/PostgreSQL databases
    with engine.begin() as conn:
        is_sqlite = "sqlite" in str(engine.url)
        
        # 1. Ensure is_demo column exists
        try:
            if is_sqlite:
                conn.execute(text("ALTER TABLE product_cases ADD COLUMN is_demo BOOLEAN DEFAULT 0"))
            else:
                conn.execute(text("ALTER TABLE product_cases ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE"))
        except Exception as e:
            logger.debug("Column migration note (is_demo): %s", e)

        # 2. Performance indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_product_cases_public_id ON product_cases (public_id)",
            "CREATE INDEX IF NOT EXISTS ix_product_cases_owner_id ON product_cases (owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_product_cases_status ON product_cases (status)",
            "CREATE INDEX IF NOT EXISTS ix_product_cases_is_demo ON product_cases (is_demo)",
            "CREATE INDEX IF NOT EXISTS ix_product_cases_created_at ON product_cases (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_product_cases_updated_at ON product_cases (updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_product_cases_owner_demo_status ON product_cases (owner_id, is_demo, status)",
            "CREATE INDEX IF NOT EXISTS ix_case_versions_case_id ON case_versions (case_id)",
            "CREATE INDEX IF NOT EXISTS ix_plant_discoveries_owner_id ON plant_discoveries (owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_plant_discoveries_product_case_id ON plant_discoveries (product_case_id)",
            "CREATE INDEX IF NOT EXISTS ix_knowledge_findings_owner_id ON knowledge_findings (owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_knowledge_findings_product_case_id ON knowledge_findings (product_case_id)",
            "CREATE INDEX IF NOT EXISTS ix_risk_assessments_product_case_id ON risk_assessments (product_case_id)",
            "CREATE INDEX IF NOT EXISTS ix_risk_assessments_public_id ON risk_assessments (public_id)",
            "CREATE INDEX IF NOT EXISTS ix_risk_assessments_owner_id ON risk_assessments (owner_id)",
        ]


        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
            except Exception as e:
                logger.debug("Index creation note (%s): %s", idx_sql, e)

        # 3. Atomic Uniqueness Constraint (owner_id + normalized product name + is_demo)
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_product_cases_owner_name_demo ON product_cases (owner_id, lower(trim(name)), is_demo)"))
        except Exception as e:
            logger.warning("Unique index creation deferred (duplicate cleanup required first): %s", e)

    logger.info("Database initialized with performance indexes successfully")