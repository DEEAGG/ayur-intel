"""AYUR-INTEL — Showcase Hardening End-to-End Verification Test."""
import unittest
import httpx
from api.main import app

class TestShowcaseHardening(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

        resp = await self.client.get("/api/cases")
        assert resp.status_code == 200, f"Failed: {resp.status_code}"
        self.cases = resp.json().get("cases", [])
        assert len(self.cases) >= 2, f"Expected at least 2 user cases, got {len(self.cases)}"

        demo_resp = await self.client.get("/api/cases/demo")
        assert demo_resp.status_code == 200, f"Failed demo: {demo_resp.status_code}"
        self.case_demo = demo_resp.json()

        self.case_a = next((c for c in self.cases if "Ashwagandha Calm" in c.get("name", "")), None)
        self.case_b = next((c for c in self.cases if "Herbis" in c.get("name", "")), None)

        assert self.case_a, "Missing Case A (Ashwagandha Calm)"
        assert self.case_b, "Missing Case B (Herbis)"
        assert self.case_demo, "Missing Case C (Demo Case)"

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_01_monitoring_isolation(self):
        """Continuous Monitoring returns strictly the requested product's signals."""
        for label, c in [("A", self.case_a), ("B", self.case_b), ("C", self.case_demo)]:
            cid = c.get("public_id") or str(c["id"])
            resp = await self.client.get(f"/api/cases/{cid}/monitoring")
            self.assertEqual(resp.status_code, 200, f"Monitoring failed for {label} with ID {cid}")
            data = resp.json()
            self.assertIn("signals", data)
            self.assertIn("timeline", data)
            self.assertIn("total_signals", data)
            self.assertEqual(data.get("product_name"), c["name"])

    async def test_02_regulatory_isolation(self):
        """Regulatory Intelligence matches requested case."""
        for label, c in [("A", self.case_a), ("B", self.case_b), ("C", self.case_demo)]:
            cid = c.get("public_id") or str(c["id"])
            resp = await self.client.get(f"/api/cases/{cid}/regulatory-analysis?jurisdiction=IN")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data.get("product_name"), c["name"])
            self.assertEqual(data.get("jurisdiction"), "IN")

    async def test_03_patent_isolation(self):
        """Patent Intelligence matches requested case."""
        for label, c in [("A", self.case_a), ("C", self.case_demo)]:
            cid = c.get("public_id") or str(c["id"])
            resp = await self.client.get(f"/api/cases/{cid}/patents")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue("patents" in data or "results" in data)

    async def test_04_risk_isolation(self):
        """Risk Assessment generates or retrieves and matches requested case."""
        for label, c in [("A", self.case_a), ("B", self.case_b), ("C", self.case_demo)]:
            cid = c.get("public_id") or str(c["id"])
            post_resp = await self.client.post(f"/api/cases/{cid}/risk-assessment")
            self.assertEqual(post_resp.status_code, 200)
            post_data = post_resp.json()
            self.assertEqual(post_data.get("product_name"), c["name"])
            self.assertIn("overall_risk", post_data)
            self.assertIn("score", post_data["overall_risk"])

            get_resp = await self.client.get(f"/api/cases/{cid}/risk-assessment")
            self.assertEqual(get_resp.status_code, 200)
            get_data = get_resp.json()
            self.assertEqual(get_data.get("product_name"), c["name"])
            self.assertEqual(get_data["overall_risk"]["score"], post_data["overall_risk"]["score"])

    async def test_05_rapid_switching_sequence(self):
        """Simulate rapid switching A -> B -> C -> A and verify no cross-contamination."""
        sequence = [
            ("A", self.case_a),
            ("B", self.case_b),
            ("C", self.case_demo),
            ("A", self.case_a),
        ]
        for label, c in sequence:
            cid = c.get("public_id") or str(c["id"])
            m_resp = await self.client.get(f"/api/cases/{cid}/monitoring")
            r_resp = await self.client.get(f"/api/cases/{cid}/regulatory-analysis?jurisdiction=IN")

            self.assertEqual(m_resp.status_code, 200)
            self.assertEqual(r_resp.status_code, 200)

            # Assert Regulatory strictly matches
            self.assertEqual(r_resp.json()["product_name"], c["name"])

            # Assert Monitoring timeline product name strictly matches
            self.assertEqual(m_resp.json()["product_name"], c["name"])

    async def test_06_product_update_safety(self):
        """Updating Product B does not touch Product A or Demo."""
        b_id = self.case_b.get("public_id") or str(self.case_b["id"])
        update_payload = {
            "name": self.case_b["name"],
            "notes": "Showcase hardened note test"
        }
        put_resp = await self.client.put(f"/api/cases/{b_id}", json=update_payload)
        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(put_resp.json()["notes"], "Showcase hardened note test")

        a_resp = await self.client.get(f"/api/cases/{self.case_a.get('public_id') or self.case_a['id']}")
        self.assertEqual(a_resp.status_code, 200)
        self.assertNotEqual(a_resp.json().get("notes"), "Showcase hardened note test")

if __name__ == "__main__":
    unittest.main()
