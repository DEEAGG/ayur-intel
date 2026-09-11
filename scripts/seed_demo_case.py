"""AYUR-INTEL — Seed Demo Case & Database Cleanup Script.

1. Ensures `is_demo` column exists in `product_cases`.
2. Cleans up duplicate / test cases.
3. Seeds the official pre-filled Demo Product Case:
   "Ashwagandha & Brahmi Cognitive Wellness Capsules" (public_id: demo-001, is_demo: True).
4. Pre-computes innovation analysis, IP strategy, regulatory profile, and risk models.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.core.database import SessionLocal, engine
from api.models import models
from api.services.product_case_service import get_or_create_demo_user, get_or_create_demo_case
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo")


def migrate_sqlite_schema():
    """Ensure SQLite schema has the is_demo column."""
    db_path = PROJECT_ROOT / "data" / "ayur_intel.db"
    if not db_path.exists():
        logger.info("SQLite DB not found, will be created by SQLAlchemy.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(product_cases)")
    columns = [row[1] for row in cursor.fetchall()]

    if "is_demo" not in columns:
        logger.info("Adding 'is_demo' column to product_cases...")
        cursor.execute("ALTER TABLE product_cases ADD COLUMN is_demo BOOLEAN DEFAULT 0")
        conn.commit()
        logger.info("✅ Column 'is_demo' added successfully.")
    else:
        logger.info("Column 'is_demo' already exists.")

    conn.close()


def cleanup_duplicate_cases(db):
    """Remove duplicate demo test cases while preserving real cases."""
    logger.info("Cleaning up duplicate test cases...")

    # Remove any test cases with duplicate names or old demo artifacts
    test_names = [
        "Tulsi & Neem Wellness & Balance Formulation",
    ]
    for name in test_names:
        cases = db.query(models.ProductCase).filter(models.ProductCase.name == name).all()
        if cases:
            logger.info(f"Found {len(cases)} entries for '{name}' — removing duplicates...")
            for c in cases:
                cid = c.id
                db.execute(text("DELETE FROM case_versions WHERE case_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM innovation_analyses WHERE product_case_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM regulatory_profiles WHERE product_case_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM patent_analyses WHERE product_case_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM ip_strategies WHERE product_case_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM risks WHERE product_case_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM product_cases WHERE id = :cid"), {"cid": cid})
            db.commit()
            logger.info(f"✅ Removed duplicate '{name}' entries.")

    # Remove duplicate 'Herbis' if more than one exists
    herbis_cases = db.query(models.ProductCase).filter(models.ProductCase.name == "Herbis").order_by(models.ProductCase.id.asc()).all()
    if len(herbis_cases) > 1:
        logger.info(f"Found {len(herbis_cases)} 'Herbis' products. Keeping primary and removing duplicates...")
        for c in herbis_cases[1:]:
            cid = c.id
            db.execute(text("DELETE FROM case_versions WHERE case_id = :cid"), {"cid": cid})
            db.execute(text("DELETE FROM product_cases WHERE id = :cid"), {"cid": cid})
        db.commit()
        logger.info("✅ Cleaned duplicate 'Herbis' products.")


def invalidate_demo_dependent_intelligence(db):
    """Safely clear stale demo-001 intelligence records without touching normal user cases."""
    demo_cases = db.query(models.ProductCase).filter(
        (models.ProductCase.public_id == "demo-001") | (models.ProductCase.is_demo == True)
    ).all()
    if not demo_cases:
        return
    for demo in demo_cases:
        cid = demo.id
        logger.info(f"Invalidating stale dependent intelligence for demo case ID {cid} (public_id: {demo.public_id})...")
        queries = [
            "DELETE FROM monitoring_alerts WHERE product_case_id = :cid",
            "DELETE FROM monitoring_configs WHERE product_case_id = :cid",
            "DELETE FROM monitoring_change_records WHERE product_case_id = :cid",
            "DELETE FROM risk_mitigation_actions WHERE risk_id IN (SELECT id FROM risks WHERE product_case_id = :cid)",
            "DELETE FROM risk_matrix_entries WHERE risk_id IN (SELECT id FROM risks WHERE product_case_id = :cid)",
            "DELETE FROM risk_assessments WHERE product_case_id = :cid",
            "DELETE FROM risks WHERE product_case_id = :cid",
            "DELETE FROM patent_relevances WHERE product_case_id = :cid",
            "DELETE FROM patent_searches WHERE product_case_id = :cid",
            "DELETE FROM patent_analyses WHERE product_case_id = :cid",
            "DELETE FROM ip_strategy_items WHERE strategy_id IN (SELECT id FROM ip_strategies WHERE product_case_id = :cid)",
            "DELETE FROM ip_strategies WHERE product_case_id = :cid",
            "DELETE FROM innovation_components WHERE analysis_id IN (SELECT id FROM innovation_analyses WHERE product_case_id = :cid)",
            "DELETE FROM innovation_analyses WHERE product_case_id = :cid",
            "DELETE FROM regulatory_profiles WHERE product_case_id = :cid",
            "DELETE FROM case_finding_evidence WHERE finding_id IN (SELECT id FROM case_findings WHERE product_case_id = :cid)",
            "DELETE FROM case_findings WHERE product_case_id = :cid",
            "DELETE FROM comparison_values WHERE comparison_item_id IN (SELECT id FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid))",
            "DELETE FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
            "DELETE FROM comparison_jurisdictions WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
            "DELETE FROM jurisdiction_comparisons WHERE product_case_id = :cid",
            "DELETE FROM knowledge_evidence WHERE finding_id IN (SELECT id FROM knowledge_findings WHERE product_case_id = :cid)",
            "DELETE FROM knowledge_findings WHERE product_case_id = :cid",
            "DELETE FROM plant_discoveries WHERE product_case_id = :cid",
            "DELETE FROM case_versions WHERE case_id = :cid",
            "DELETE FROM product_cases WHERE id = :cid",
        ]
        for q in queries:
            try:
                db.execute(text(q), {"cid": cid})
            except Exception as e:
                logger.debug("Table deletion note (%s): %s", q[:30], e)
    db.commit()
    logger.info("✅ Stale demo intelligence invalidated safely.")


def seed_demo():
    migrate_sqlite_schema()

    # Ensure all tables are created
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        invalidate_demo_dependent_intelligence(db)
        cleanup_duplicate_cases(db)

        logger.info("Seeding pre-filled official Ayurvedic Demo Product Case...")
        demo_case = get_or_create_demo_case(db, user)
        logger.info(f"✅ Demo case ready: {demo_case['name']} (ID: {demo_case['id']}, is_demo: {demo_case.get('is_demo')})")

        # Explicitly pre-generate Patent search and Gemini analysis for demo presentation
        try:
            from api.services.patent_service import get_or_run_patent_intelligence
            logger.info("Generating real Patent Intelligence prior-art search for showcase demo...")
            p_res = get_or_run_patent_intelligence(db=db, owner=user, case_public_id="demo-001", force_rerun=True)
            if p_res:
                logger.info(f"✅ Patent search pre-generated: Discovered={p_res['summary_metrics']['raw_discovered_count']}, Screened={p_res['summary_metrics']['unique_screened_count']}, Shortlisted={p_res['summary_metrics']['shortlisted_count']}, Analyzed={p_res['summary_metrics']['analyzed_count']}")
        except Exception as pe:
            logger.warning("Could not pre-generate patent intelligence for demo: %s", pe)

        # Verify active cases
        active_cases = db.query(models.ProductCase).filter(models.ProductCase.is_demo == False).all()
        logger.info(f"📊 Active Products in database (excluding demo): {len(active_cases)}")
        for c in active_cases:
            logger.info(f"   • {c.name} (ID: {c.public_id}, Stage: {c.stage})")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
