"""AYUR-INTEL — Database Sync Script (SQLite -> Supabase PostgreSQL).

Syncs all tables and records from the local SQLite database (data/ayur_intel.db)
to Supabase PostgreSQL (via DATABASE_URL).

Usage:
    # Option 1: Using environment variable DATABASE_URL
    python scripts/sync_to_supabase.py

    # Option 2: Passing DATABASE_URL directly
    python scripts/sync_to_supabase.py --url "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres"

    # Option 3: Dry run (test connection and display table statistics)
    python scripts/sync_to_supabase.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sync_supabase")

# Tables in Foreign Key dependency order
SYNC_TABLES = [
    "users",
    "sources",
    "product_cases",
    "case_versions",
    "plant_discoveries",
    "knowledge_findings",
    "knowledge_evidence",
    "innovation_analyses",
    "innovation_components",
    "patent_records",
    "patent_searches",
    "patent_relevances",
    "patent_analyses",
    "patent_comparisons",
    "claim_elements",
    "ip_strategies",
    "ip_strategy_items",
    "regulatory_profiles",
    "regulatory_requirements",
    "jurisdiction_comparisons",
    "comparison_jurisdictions",
    "comparison_items",
    "comparison_values",
    "unified_evidence",
    "case_findings",
    "case_finding_evidence",
    "risks",
    "self_extension_requests",
    "risk_evidence",
    "risk_resolutions",
    "decision_dashboard_snapshots",
    "monitoring_configs",
    "monitoring_sources",
    "monitoring_runs",
    "change_records",
    "monitoring_alerts",
    "audit_logs",
    "review_requests",
    "review_items",
    "review_decisions",
    "review_history",
]


def get_sqlite_data(sqlite_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Read all rows from local SQLite database."""
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {sqlite_path}")

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    data: Dict[str, List[Dict[str, Any]]] = {}

    for table in SYNC_TABLES:
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = [dict(row) for row in cursor.fetchall()]
            data[table] = rows
            logger.info(f"  📦 Read {len(rows):>4} rows from SQLite: {table}")
        except sqlite3.OperationalError as e:
            logger.warning(f"  ⚠️  Table '{table}' not found in SQLite: {e}")
            data[table] = []

    conn.close()
    return data


def sync_to_postgres(database_url: str, sqlite_data: Dict[str, List[Dict[str, Any]]], dry_run: bool = False, clean_first: bool = False):
    """Sync data into Supabase PostgreSQL database."""
    # Ensure postgresql:// scheme (SQLAlchemy requirement)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    logger.info(f"Connecting to PostgreSQL...")
    engine = create_engine(database_url, echo=False)

    # 1. Initialize schema first
    from api.models import models
    logger.info("Ensuring database schema exists in PostgreSQL...")
    models.Base.metadata.create_all(bind=engine)
    logger.info("✅ Schema synchronized.")

    if dry_run:
        logger.info("🔍 Dry run completed successfully! No records were modified.")
        return

    with engine.begin() as conn:
        # Optionally clean existing seed data in reverse FK order
        if clean_first:
            logger.info("🧹 Cleaning existing data in reverse FK order...")
            for table in reversed(SYNC_TABLES):
                try:
                    conn.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
                except Exception:
                    conn.execute(text(f"DELETE FROM {table};"))
            logger.info("✅ Clean completed.")

        total_synced = 0

        # Insert records table by table
        for table in SYNC_TABLES:
            rows = sqlite_data.get(table, [])
            if not rows:
                continue

            columns = list(rows[0].keys())
            cols_str = ", ".join([f'"{c}"' for c in columns])
            params_str = ", ".join([f":{c}" for c in columns])

            # Upsert on ID if present, otherwise ignore conflicts
            if "id" in columns:
                update_set = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in columns if c != "id"])
                if update_set:
                    stmt = text(f"""
                        INSERT INTO "{table}" ({cols_str})
                        VALUES ({params_str})
                        ON CONFLICT ("id") DO UPDATE SET {update_set};
                    """)
                else:
                    stmt = text(f"""
                        INSERT INTO "{table}" ({cols_str})
                        VALUES ({params_str})
                        ON CONFLICT ("id") DO NOTHING;
                    """)
            else:
                stmt = text(f"""
                    INSERT INTO "{table}" ({cols_str})
                    VALUES ({params_str})
                    ON CONFLICT DO NOTHING;
                """)

            synced_count = 0
            for row in rows:
                try:
                    conn.execute(stmt, row)
                    synced_count += 1
                except Exception as e:
                    logger.warning(f"Error inserting row into {table}: {e}")

            logger.info(f"  ✨ Synced {synced_count}/{len(rows)} rows -> {table}")
            total_synced += synced_count

            # Reset Postgres sequence for serial primary key if exists
            if "id" in columns:
                try:
                    conn.execute(text(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table}', 'id'),
                            COALESCE((SELECT MAX(id) FROM "{table}"), 1),
                            true
                        );
                    """))
                except Exception:
                    pass

        logger.info(f"\n🎉 Successfully synced {total_synced} total records to Supabase PostgreSQL!")


def main():
    parser = argparse.ArgumentParser(description="Sync SQLite to Supabase PostgreSQL")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"), help="Supabase PostgreSQL DATABASE_URL")
    parser.add_argument("--sqlite", default=str(PROJECT_ROOT / "data" / "ayur_intel.db"), help="Path to SQLite DB")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without inserting")
    parser.add_argument("--clean", action="store_true", help="Clean tables in Supabase before importing")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    logger.info(f"📖 Reading local SQLite database: {sqlite_path}")
    data = get_sqlite_data(sqlite_path)

    total_rows = sum(len(r) for r in data.values())
    logger.info(f"📊 Found {total_rows} total rows across {len(data)} tables in SQLite.")

    db_url = args.url or os.getenv("DATABASE_URL")
    if not db_url:
        logger.info("\nℹ️  No DATABASE_URL provided.")
        logger.info("   To sync to Supabase, provide the DATABASE_URL connection string:")
        logger.info('   py -3.12 scripts/sync_to_supabase.py --url "postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres"')
        return

    sync_to_postgres(db_url, data, dry_run=args.dry_run, clean_first=args.clean)


if __name__ == "__main__":
    main()
