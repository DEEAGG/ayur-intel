"""AYUR-INTEL — Safe Duplicate Product Case Cleanup Script.

Finds duplicate Product Cases by (owner_id, lower(trim(name)), is_demo),
keeps the latest/primary canonical instance, and cleanly deletes redundant copies
along with all dependent child entities.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from collections import defaultdict

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.core.database import SessionLocal, engine
from api.models import models
from api.services.product_case_service import delete_product_case

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup_duplicates")


def audit_and_clean_duplicates(dry_run: bool = False) -> dict:
    """Audit and optionally clean duplicate product cases in database."""
    db = SessionLocal()
    try:
        cases = db.query(models.ProductCase).all()
        logger.info(f"Total product cases in database: {len(cases)}")

        # Group by (owner_id, lower(trim(name)), is_demo)
        groups = defaultdict(list)
        for c in cases:
            norm_name = (c.name or "").strip().lower()
            key = (c.owner_id, norm_name, bool(c.is_demo))
            groups[key].append(c)

        duplicates_found = 0
        deleted_count = 0
        report = []

        for (owner_id, norm_name, is_demo), case_list in groups.items():
            if len(case_list) > 1:
                duplicates_found += (len(case_list) - 1)
                sorted_cases = sorted(
                    case_list,
                    key=lambda x: (1 if x.public_id == "demo-001" else 0, x.id),
                    reverse=True
                )
                keep_case = sorted_cases[0]
                remove_cases = sorted_cases[1:]

                dup_info = {
                    "owner_id": owner_id,
                    "normalized_name": norm_name,
                    "is_demo": is_demo,
                    "retained": {"id": keep_case.id, "public_id": keep_case.public_id, "name": keep_case.name},
                    "duplicates": [{"id": c.id, "public_id": c.public_id, "name": c.name} for c in remove_cases]
                }
                report.append(dup_info)

                logger.info(
                    f"Duplicate group found: '{norm_name}' ({len(case_list)} copies). "
                    f"Retaining ID={keep_case.id} ({keep_case.public_id}), "
                    f"removing {len(remove_cases)} duplicate(s)..."
                )

                if not dry_run:
                    for c in remove_cases:
                        if c.public_id == "demo-001":
                            continue
                        success = delete_product_case(db=db, owner=keep_case.owner, public_id=c.public_id)
                        if success:
                            deleted_count += 1
                            logger.info(f"  [OK] Deleted duplicate case ID={c.id} ({c.public_id})")
                        else:
                            logger.warning(f"  [FAIL] Failed to delete duplicate case ID={c.id} ({c.public_id})")

        logger.info(
            f"Audit complete. Duplicate records found: {duplicates_found}, "
            f"Records cleaned: {deleted_count} (dry_run={dry_run})"
        )
        return {
            "total_cases": len(cases),
            "duplicates_found": duplicates_found,
            "deleted_count": deleted_count,
            "report": report
        }
    finally:
        db.close()


if __name__ == "__main__":
    dry_run_flag = "--dry-run" in sys.argv
    res = audit_and_clean_duplicates(dry_run=dry_run_flag)
    print("\n--- CLEANUP SUMMARY REPORT ---")
    print(f"Total Cases: {res['total_cases']}")
    print(f"Duplicates Found: {res['duplicates_found']}")
    print(f"Duplicates Deleted: {res['deleted_count']}")
    for r in res["report"]:
        print(f"Group: '{r['normalized_name']}' | Retained: {r['retained']} | Duplicates: {r['duplicates']}")
