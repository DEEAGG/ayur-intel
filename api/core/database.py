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
        
        # 1. Ensure columns exist for existing databases
        new_cols = [
            ("product_cases", "is_demo", "BOOLEAN DEFAULT 0" if is_sqlite else "BOOLEAN DEFAULT FALSE"),
            ("patent_records", "provider_record_id", "VARCHAR(100)"),
            ("patent_records", "family_id", "VARCHAR(100)"),
            ("patent_records", "family_members_json", "TEXT"),
            ("patent_relevances", "evidence_basis", "VARCHAR(50) DEFAULT 'TITLE_ABSTRACT'"),
            ("patent_relevances", "evidence_coverage", "VARCHAR(50) DEFAULT 'STANDARD'"),
            ("patent_relevances", "score_breakdown_json", "TEXT"),
            ("patent_relevances", "matched_components_json", "TEXT"),
            ("patent_relevances", "matched_queries_json", "TEXT"),
            ("patent_relevances", "why_relevant", "TEXT"),
            ("patent_relevances", "important_difference", "TEXT"),
            ("patent_relevances", "limitations", "TEXT"),
            ("patent_searches", "raw_discovered_count", "INTEGER DEFAULT 0"),
            ("patent_searches", "unique_screened_count", "INTEGER DEFAULT 0"),
            ("knowledge_evidence", "content_hash", "VARCHAR(64)"),
            ("knowledge_evidence", "license_note", "TEXT"),
        ]

        for table, col, col_type in new_cols:
            try:
                if is_sqlite:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            except Exception as e:
                logger.debug("Column migration note (%s.%s): %s", table, col, e)

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
            "CREATE INDEX IF NOT EXISTS ix_knowledge_evidence_content_hash ON knowledge_evidence (content_hash)",
            "CREATE INDEX IF NOT EXISTS ix_knowledge_syntheses_document_identifier ON knowledge_syntheses (document_identifier)",
            "CREATE INDEX IF NOT EXISTS ix_knowledge_syntheses_evidence_fingerprint ON knowledge_syntheses (evidence_fingerprint)",
            "CREATE INDEX IF NOT EXISTS ix_knowledge_syntheses_grounding_status ON knowledge_syntheses (grounding_status)",
            "CREATE INDEX IF NOT EXISTS ix_risk_assessments_product_case_id ON risk_assessments (product_case_id)",
            "CREATE INDEX IF NOT EXISTS ix_risk_assessments_public_id ON risk_assessments (public_id)",
            "CREATE INDEX IF NOT EXISTS ix_risk_assessments_owner_id ON risk_assessments (owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_dravya_plants_plant_id ON dravya_plants (plant_id)",
            "CREATE INDEX IF NOT EXISTS ix_dravya_plants_scientific_name ON dravya_plants (scientific_name)",
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
    _seed_initial_knowledge_hub_if_empty()


def _seed_initial_knowledge_hub_if_empty() -> None:
    """Seed initial source-backed evidence records into DB if empty."""
    from api.models.models import KnowledgeEvidence
    from api.services.knowledge_source_adapters import (
        ClassicalSamhitaAdapter,
        PubMedCentralAdapter,
        FssaiRegulationsAdapter,
        AyushGuidelinesAdapter,
        DrugsActAdapter,
    )
    from api.services.knowledge_ingestion_service import KnowledgeIngestionService
    from api.services.product_case_service import get_or_create_demo_user

    db = SessionLocal()
    try:
        from api.models.models import DravyaPlant
        from api.services.dravya_service import DravyaService

        # Always ensure DRAVYA plants are ingested if missing
        if db.query(DravyaPlant).count() == 0:
            DravyaService.ingest_dravya_dataset(db)

        user = get_or_create_demo_user(db)

        # Ensure evidence for each official source adapter exists
        if db.query(KnowledgeEvidence).filter(KnowledgeEvidence.source_identifier.ilike("%NIIMH%")).count() == 0:
            c_adapter = ClassicalSamhitaAdapter()
            c_res = c_adapter.search(query="", limit=20)
            KnowledgeIngestionService.ingest_results(db, user.id, c_res.results)

        if db.query(KnowledgeEvidence).filter(KnowledgeEvidence.source_identifier.ilike("%PMC%")).count() < 20:
            p_adapter = PubMedCentralAdapter()
            p_res = p_adapter.search(query="", limit=20)
            KnowledgeIngestionService.ingest_results(db, user.id, p_res.results)

        if db.query(KnowledgeEvidence).filter(KnowledgeEvidence.source_identifier.ilike("%FSSAI%")).count() == 0:
            f_adapter = FssaiRegulationsAdapter()
            f_res = f_adapter.search(query="", limit=10)
            KnowledgeIngestionService.ingest_results(db, user.id, f_res.results)

        if db.query(KnowledgeEvidence).filter(KnowledgeEvidence.source_identifier.ilike("%AYUSH%")).count() == 0:
            g_adapter = AyushGuidelinesAdapter()
            g_res = g_adapter.search(query="", limit=10)
            KnowledgeIngestionService.ingest_results(db, user.id, g_res.results)

        if db.query(KnowledgeEvidence).filter(KnowledgeEvidence.source_identifier.ilike("%DRUGS%")).count() == 0:
            d_adapter = DrugsActAdapter()
            d_res = d_adapter.search(query="", limit=10)
            KnowledgeIngestionService.ingest_results(db, user.id, d_res.results)

        logger.info("Successfully seeded initial Knowledge Hub evidence records and DRAVYA plants.")
    except Exception as e:
        logger.warning("Initial Knowledge Hub seeding skipped: %s", e)
    finally:
        db.close()