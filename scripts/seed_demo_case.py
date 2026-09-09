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


def seed_demo():
    migrate_sqlite_schema()

    # Ensure all tables are created
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        cleanup_duplicate_cases(db)

        logger.info("Seeding pre-filled official Ayurvedic Demo Product Case...")
        demo_case = get_or_create_demo_case(db, user)
        logger.info(f"✅ Demo case ready: {demo_case['name']} (ID: {demo_case['id']}, is_demo: {demo_case.get('is_demo')})")

        # Verify active cases
        active_cases = db.query(models.ProductCase).filter(models.ProductCase.is_demo == False).all()
        logger.info(f"📊 Active Products in database (excluding demo): {len(active_cases)}")
        for c in active_cases:
            logger.info(f"   • {c.name} (ID: {c.public_id}, Stage: {c.stage})")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
