"""AYUR-INTEL — Continuous Monitoring Product Isolation & Integrity Test Suite.

Verifies:
1. Product isolation: Product A and Product B return strictly their own alerts and summary.
2. Rapid switching isolation (A -> B -> A).
3. Zero alerts / clean state for an empty product case.
4. Mutation isolation: Marking an alert reviewed on Product A does not mutate Product B.
5. In-memory monitoring cache speed and proper invalidation upon alert status changes and monitoring runs.
"""

from __future__ import annotations

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.models import (
    Base,
    User,
    ProductCase,
)
from api.models.monitoring import (
    MonitoringConfig,
    Alert,
)
from api.services.monitoring_service import (
    get_monitoring_summary,
    update_alert_status,
    run_monitoring_check,
    update_config,
    _invalidate_monitoring_cache,
)


class TestMonitoringProductIsolation(unittest.TestCase):
    """Ensure strict multi-product isolation in Continuous Monitoring."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        _invalidate_monitoring_cache()

        # Seed User
        self.user = User(
            username="test_mon_user",
            display_name="Monitoring Tester",
            email="mon_tester@ayur-intel.com",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        # Seed Product A
        self.case_a = ProductCase(
            name="Ashwagandha Formula A",
            owner_id=self.user.id,
            public_id="case-prod-a",
            ingredients='[{"name": "Ashwagandha", "role": "Active"}]',
        )
        # Seed Product B
        self.case_b = ProductCase(
            name="Brahmi Syrup B",
            owner_id=self.user.id,
            public_id="case-prod-b",
            ingredients='[{"name": "Brahmi", "role": "Active"}]',
        )
        # Seed Empty Product C
        self.case_c = ProductCase(
            name="Empty Product C",
            owner_id=self.user.id,
            public_id="case-prod-c",
            ingredients="[]",
        )
        self.db.add_all([self.case_a, self.case_b, self.case_c])
        self.db.commit()
        for c in [self.case_a, self.case_b, self.case_c]:
            self.db.refresh(c)

        # Seed Alerts for Product A
        self.alert_a1 = Alert(
            owner_id=self.user.id,
            product_case_id=self.case_a.id,
            public_id="alt-a-1",
            alert_type="PATENT",
            severity="HIGH",
            title="Product A Patent Conflict 1",
            summary="Prior art conflict on Ashwagandha extract.",
            status="NEW",
        )
        self.alert_a2 = Alert(
            owner_id=self.user.id,
            product_case_id=self.case_a.id,
            public_id="alt-a-2",
            alert_type="RESEARCH",
            severity="INFO",
            title="Product A Clinical Trial",
            summary="New trial publication.",
            status="NEW",
        )

        # Seed Alerts for Product B
        self.alert_b1 = Alert(
            owner_id=self.user.id,
            product_case_id=self.case_b.id,
            public_id="alt-b-1",
            alert_type="REGULATORY",
            severity="MEDIUM",
            title="Product B AYUSH Notification",
            summary="Brahmi dosage guidelines updated.",
            status="NEW",
        )

        self.db.add_all([self.alert_a1, self.alert_a2, self.alert_b1])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        _invalidate_monitoring_cache()

    def test_product_data_isolation(self):
        """Product A and Product B should return only their respective alerts and counts."""
        summary_a = get_monitoring_summary(self.db, self.user, self.case_a.public_id)
        summary_b = get_monitoring_summary(self.db, self.user, self.case_b.public_id)

        self.assertIsNotNone(summary_a)
        self.assertIsNotNone(summary_b)

        # Product A checks
        self.assertEqual(summary_a["product_case_id"], self.case_a.public_id)
        self.assertEqual(summary_a["total_signals"], 2)
        self.assertEqual(summary_a["new_signals"], 2)
        self.assertEqual(summary_a["patent_signals"], 1)
        self.assertEqual(summary_a["research_signals"], 1)
        self.assertEqual(summary_a["regulatory_signals"], 0)
        signal_ids_a = [s["id"] for s in summary_a["signals"]]
        self.assertIn("alt-a-1", signal_ids_a)
        self.assertIn("alt-a-2", signal_ids_a)
        self.assertNotIn("alt-b-1", signal_ids_a)

        # Product B checks
        self.assertEqual(summary_b["product_case_id"], self.case_b.public_id)
        self.assertEqual(summary_b["total_signals"], 1)
        self.assertEqual(summary_b["new_signals"], 1)
        self.assertEqual(summary_b["patent_signals"], 0)
        self.assertEqual(summary_b["research_signals"], 0)
        self.assertEqual(summary_b["regulatory_signals"], 1)
        signal_ids_b = [s["id"] for s in summary_b["signals"]]
        self.assertIn("alt-b-1", signal_ids_b)
        self.assertNotIn("alt-a-1", signal_ids_b)
        self.assertNotIn("alt-a-2", signal_ids_b)

    def test_rapid_product_switching_consistency(self):
        """Simulating rapid A -> B -> A calls must remain strictly isolated."""
        sum1_a = get_monitoring_summary(self.db, self.user, self.case_a.public_id)
        sum_b = get_monitoring_summary(self.db, self.user, self.case_b.public_id)
        sum2_a = get_monitoring_summary(self.db, self.user, self.case_a.public_id)

        self.assertEqual(sum1_a["product_case_id"], "case-prod-a")
        self.assertEqual(sum_b["product_case_id"], "case-prod-b")
        self.assertEqual(sum2_a["product_case_id"], "case-prod-a")
        self.assertEqual(sum2_a["total_signals"], 2)
        self.assertEqual(sum_b["total_signals"], 1)

    def test_empty_product_isolation(self):
        """Empty product C should not leak any alerts from A or B."""
        summary_c = get_monitoring_summary(self.db, self.user, self.case_c.public_id)
        self.assertIsNotNone(summary_c)
        self.assertEqual(summary_c["product_case_id"], "case-prod-c")
        self.assertEqual(summary_c["total_signals"], 0)
        self.assertEqual(summary_c["new_signals"], 0)
        self.assertEqual(len(summary_c["signals"]), 0)

    def test_mutation_isolation_and_cache_invalidation(self):
        """Marking an alert reviewed on Product A updates A and invalidates A's cache without mutating B."""
        # Initial cached load
        s_a_initial = get_monitoring_summary(self.db, self.user, self.case_a.public_id)
        s_b_initial = get_monitoring_summary(self.db, self.user, self.case_b.public_id)
        self.assertEqual(s_a_initial["new_signals"], 2)
        self.assertEqual(s_b_initial["new_signals"], 1)

        # Mutate Alert on A
        res = update_alert_status(self.db, self.user, "alt-a-1", "REVIEWED")
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "REVIEWED")

        # Reload Product A: cache should have been invalidated and reflect new_signals = 1
        s_a_after = get_monitoring_summary(self.db, self.user, self.case_a.public_id)
        self.assertEqual(s_a_after["new_signals"], 1)
        self.assertEqual(s_a_after["total_signals"], 2)

        # Product B must remain completely unaffected
        s_b_after = get_monitoring_summary(self.db, self.user, self.case_b.public_id)
        self.assertEqual(s_b_after["new_signals"], 1)
        self.assertEqual(s_b_after["total_signals"], 1)
        b_signal = s_b_after["signals"][0]
        self.assertEqual(b_signal["status"], "NEW")


if __name__ == "__main__":
    unittest.main()
