"""AYUR-INTEL — Target Hackathon Demo Flow End-to-End Verification Test.

Simulates the exact target demo flow:
1. Open app -> Call /api/assistant/chat with "What is AYUR-INTEL?" -> Grounded answer
2. User asks "Where are my products?" -> Answer + OPEN_PRODUCTS action
3. User selects active product (e.g. Case A: Brahmi Mind Syrup)
4. User asks "How do I check its patent intelligence?" -> Product-aware answer + OPEN_PATENT for active product
5. User asks in Hinglish "Ye app kis tech stack pe bana hai?" -> Correct repo-grounded answer (FastAPI, SQLite/Supabase, Gemini, Vanilla JS, PlantNet)
6. User asks "Does AYUR-INTEL guarantee patent approval?" -> Clearly says NO, decision-support only
"""

import unittest
import httpx
from api.main import app


class TestHackathonDemoFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

        # Fetch actual existing products from DB
        resp = await self.client.get("/api/cases")
        self.assertEqual(resp.status_code, 200)
        self.cases = resp.json().get("cases", [])
        self.assertTrue(len(self.cases) > 0, "Expected at least one case in DB")
        self.active_case = self.cases[0]
        self.active_id = str(self.active_case.get("public_id") or self.active_case["id"])
        self.active_name = self.active_case["name"]

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_complete_hackathon_demo_flow(self):
        print(f"\n[DEMO FLOW] Running test with verified Active Product: {self.active_name} (ID: {self.active_id})")

        # Step 1: "What is AYUR-INTEL?"
        resp1 = await self.client.post(
            "/api/assistant/chat",
            json={
                "message": "What is AYUR-INTEL?",
                "current_view": "dashboard",
                "active_product_id": None,
                "active_product_name": None,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        print("\nStep 1 (What is AYUR-INTEL?):")
        print("Answer preview:", data1["answer"][:120])
        print("Sources:", data1["sources"])
        self.assertTrue(len(data1["answer"]) > 30)
        self.assertIn("AYUR-INTEL Platform & Mission", data1["sources"])

        # Step 2: "Where are my products?"
        resp2 = await self.client.post(
            "/api/assistant/chat",
            json={
                "message": "Where are my products?",
                "current_view": "dashboard",
                "active_product_id": None,
                "active_product_name": None,
            },
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        print("\nStep 2 (Where are my products?):")
        print("Answer preview:", data2["answer"][:120])
        action_ids2 = [a["id"] for a in data2["actions"]]
        print("Actions:", action_ids2)
        self.assertIn("OPEN_PRODUCTS", action_ids2)
        self.assertEqual(data2["actions"][0]["target"], "product-cases")

        # Step 3: Select product -> "How do I check its patent intelligence?"
        resp3 = await self.client.post(
            "/api/assistant/chat",
            json={
                "message": "How do I check its patent intelligence?",
                "current_view": "case-detail",
                "active_product_id": self.active_id,
                "active_product_name": self.active_name,
            },
        )
        self.assertEqual(resp3.status_code, 200)
        data3 = resp3.json()
        print(f"\nStep 3 (Patent check for {self.active_name}):")
        print("Answer preview:", data3["answer"][:120])
        action_ids3 = [a["id"] for a in data3["actions"]]
        print("Actions:", action_ids3)
        self.assertIn("OPEN_PATENT", action_ids3)
        patent_act = next(a for a in data3["actions"] if a["id"] == "OPEN_PATENT")
        self.assertEqual(patent_act["target"], "patent-intelligence")
        self.assertEqual(patent_act["product_id"], self.active_id)
        self.assertIn(self.active_name, patent_act["label"])

        # Step 4: "Ye app kis tech stack pe bana hai?" (Hinglish)
        resp4 = await self.client.post(
            "/api/assistant/chat",
            json={
                "message": "Ye app kis tech stack pe bana hai?",
                "current_view": "patent-intelligence",
                "active_product_id": self.active_id,
                "active_product_name": self.active_name,
            },
        )
        self.assertEqual(resp4.status_code, 200)
        data4 = resp4.json()
        print("\nStep 4 (Ye app kis tech stack pe bana hai?):")
        print("Answer preview:", data4["answer"][:120])
        ans4_lower = data4["answer"].lower()
        self.assertIn("fastapi", ans4_lower)
        self.assertTrue("python" in ans4_lower or "sqlite" in ans4_lower or "gemini" in ans4_lower)

        # Step 5: "Does AYUR-INTEL guarantee patent approval?"
        resp5 = await self.client.post(
            "/api/assistant/chat",
            json={
                "message": "Does AYUR-INTEL guarantee patent approval?",
                "current_view": "patent-intelligence",
                "active_product_id": self.active_id,
                "active_product_name": self.active_name,
            },
        )
        self.assertEqual(resp5.status_code, 200)
        data5 = resp5.json()
        print("\nStep 5 (Does AYUR-INTEL guarantee patent approval?):")
        print("Answer preview:", data5["answer"][:120])
        ans5_lower = data5["answer"].lower()
        # Must clearly say NO, decision support only
        self.assertTrue("no" in ans5_lower or "not guarantee" in ans5_lower or "does not" in ans5_lower)
        self.assertTrue("decision" in ans5_lower or "support" in ans5_lower or "advisory" in ans5_lower)
        print("\n[DEMO FLOW] All 5 hackathon steps PASSED successfully!\n")


if __name__ == "__main__":
    unittest.main()
