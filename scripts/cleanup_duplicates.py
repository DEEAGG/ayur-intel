"""AYUR-INTEL — Database Duplicates Cleanup Script.

Finds and removes duplicate product cases (keeping the latest instance)
and cleans up all child table associations. Works with both SQLite and PostgreSQL.

Run with:
    python scripts/cleanup_duplicates.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, text
from api.core.database import SessionLocal, engine
from api.models.models import ProductCase, User


def cleanup_duplicate_product_cases() -> None:
    """Find and delete duplicate product cases, keeping only the latest one."""
    print("=" * 60)
    print("AYUR-INTEL -- Database Duplicate Product Cleanup")
    print(f"Database URL: {engine.url}")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 1. Fetch all product cases
        all_cases = db.query(ProductCase).order_by(ProductCase.id.asc()).all()
        print(f"Total Product Cases currently in DB: {len(all_cases)}")

        # Group cases by (owner_id, lower_name)
        groups: dict[tuple[int, str], list[ProductCase]] = {}
        for c in all_cases:
            key = (c.owner_id, (c.name or "").strip().lower())
            groups.setdefault(key, []).append(c)

        duplicates_found = 0
        deleted_count = 0
        kept_cases = []

        for (owner_id, norm_name), cases in groups.items():
            if len(cases) > 1:
                duplicates_found += 1
                # Sort by ID ascending (or created_at) -- keep the last one (latest)
                cases_sorted = sorted(cases, key=lambda x: (x.created_at or x.id, x.id))
                keep = cases_sorted[-1]
                to_delete = cases_sorted[:-1]
                kept_cases.append(keep)

                print(f"\n[DUPLICATE DETECTED] for '{keep.name}' (Owner ID: {owner_id}):")
                print(f"   [KEEPING LATEST] ID={keep.id}, PublicID={keep.public_id}, Created={keep.created_at}")

                for item in to_delete:
                    print(f"   [DELETING DUPLICATE] ID={item.id}, PublicID={item.public_id}, Created={item.created_at}")
                    cid = item.id

                    child_deletes = [
                        "DELETE FROM regulatory_requirements WHERE profile_id IN (SELECT id FROM regulatory_profiles WHERE product_case_id = :cid)",
                        "DELETE FROM regulatory_profiles WHERE product_case_id = :cid",
                        "DELETE FROM claim_elements WHERE analysis_id IN (SELECT id FROM patent_analyses WHERE product_case_id = :cid)",
                        "DELETE FROM patent_comparisons WHERE analysis_id IN (SELECT id FROM patent_analyses WHERE product_case_id = :cid)",
                        "DELETE FROM patent_analyses WHERE product_case_id = :cid",
                        "DELETE FROM comparison_jurisdictions WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
                        "DELETE FROM comparison_items WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
                        "DELETE FROM comparison_values WHERE comparison_id IN (SELECT id FROM jurisdiction_comparisons WHERE product_case_id = :cid)",
                        "DELETE FROM jurisdiction_comparisons WHERE product_case_id = :cid",
                        "DELETE FROM plant_discoveries WHERE product_case_id = :cid",
                        "DELETE FROM knowledge_findings WHERE product_case_id = :cid",
                        "DELETE FROM case_versions WHERE case_id = :cid",
                        "DELETE FROM product_cases WHERE id = :cid",
                    ]

                    for stmt in child_deletes:
                        try:
                            db.execute(text(stmt), {"cid": cid})
                        except Exception as e:
                            print(f"      Query note on child delete: {e}")

                    deleted_count += 1
            else:
                kept_cases.append(cases[0])

        db.commit()

        print("\n" + "=" * 60)
        print("CLEANUP SUMMARY:")
        print(f"   - Duplicate Product Groups Found: {duplicates_found}")
        print(f"   - Duplicate Records Removed: {deleted_count}")
        print(f"   - Clean Products Remaining: {len(kept_cases)}")
        print("=" * 60)

        # Print remaining cases
        remaining = db.query(ProductCase).order_by(ProductCase.id.asc()).all()
        print("\nCurrent Active Cases in DB:")
        for r in remaining:
            print(f"   [{r.id}] {r.public_id} | {r.name} | is_demo={r.is_demo} | Status={r.status}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_duplicate_product_cases()
