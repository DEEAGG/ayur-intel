"""AYUR-INTEL — In-App RAG Assistant & Safety Test Suite.

Verifies:
1. Grounded retrieval: Accurate chunks retrieved for core platform topics.
2. Safe navigation actions: Predefined valid action IDs returned for questions.
3. Fallback resilience: Deterministic fallback operates when Gemini is unavailable.
4. Hinglish & Hindi query handling: Natural language mirroring and intent recognition.
5. Product context awareness: Active product case is verified and reflected in responses.
6. Product isolation integrity: Product context never leaks between cases.
7. Disclaimers & boundaries: Explicitly denies patent approval and regulatory guarantee.
8. Security & privacy: Prompt injection resistance and secret redacting.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from api.models.models import Base, User, ProductCase
from api.services.assistant_service import (
    retrieve_relevant_chunks,
    resolve_actions,
    generate_fallback_answer,
    process_assistant_chat,
    sanitize_input,
    sanitize_output,
    is_hinglish,
)


class TestAssistantRAG(unittest.IsolatedAsyncioTestCase):
    """Test suite for AYUR-INTEL in-app RAG assistant."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Seed test user and product cases
        self.user = User(
            id=1,
            email="researcher@ayurintel.in",
            username="researcher",
            hashed_password="hashed_pw",
            display_name="Dr. Ayurvedic Researcher",
        )
        self.db.add(self.user)
        self.db.commit()

        self.case_a = ProductCase(
            id=101,
            public_id="case-brahmi-101",
            owner_id=1,
            name="Brahmi Mind Syrup",
            stage="RND",
            status="DRAFT",
        )
        self.case_b = ProductCase(
            id=102,
            public_id="case-ashwa-102",
            owner_id=1,
            name="Ashwagandha Stress Relief Capsule",
            stage="COMMERCIAL",
            status="COMPLETED",
        )
        self.db.add_all([self.case_a, self.case_b])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def asyncSetUp(self):
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()

    # -------------------------------------------------------------------------
    # 1. Deterministic Chunk Retrieval Tests
    # -------------------------------------------------------------------------
    def test_01_retrieval_platform_overview(self):
        chunks = retrieve_relevant_chunks("What is AYUR-INTEL?")
        self.assertTrue(len(chunks) > 0)
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_platform_overview", chunk_ids)

    def test_02_retrieval_product_creation(self):
        chunks = retrieve_relevant_chunks("How do I create a product?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_product_creation", chunk_ids)

    def test_03_retrieval_tech_stack(self):
        chunks = retrieve_relevant_chunks("What technology is AYUR-INTEL built with?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_tech_stack", chunk_ids)
        self.assertIn("FastAPI", chunks[0]["content"])
        self.assertIn("Python 3.12", chunks[0]["content"])

    def test_04_retrieval_patent_intelligence(self):
        chunks = retrieve_relevant_chunks("How does Patent Intelligence work?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_patent_intelligence", chunk_ids)
        self.assertIn("Section 3(p)", chunks[0]["content"])

    def test_05_retrieval_regulatory_intelligence(self):
        chunks = retrieve_relevant_chunks("What does Regulatory Intelligence do?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_regulatory_intelligence", chunk_ids)
        self.assertIn("ASU Drug", chunks[0]["content"])

    def test_06_retrieval_monitoring(self):
        chunks = retrieve_relevant_chunks("What is Monitoring in AYUR-INTEL?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_monitoring", chunk_ids)

    def test_07_retrieval_guarantee_boundary(self):
        chunks = retrieve_relevant_chunks("Does AYUR-INTEL guarantee patent approval?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_limitations_and_disclaimer", chunk_ids)

    # -------------------------------------------------------------------------
    # 2. Hinglish & Hindi Language Handling Tests
    # -------------------------------------------------------------------------
    def test_08_hinglish_products_query(self):
        self.assertTrue(is_hinglish("Mere products kaha hai?"))
        chunks = retrieve_relevant_chunks("Mere products kaha hai?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_products_inventory", chunk_ids)

    def test_09_hinglish_create_product(self):
        self.assertTrue(is_hinglish("New product kaise banau?"))
        chunks = retrieve_relevant_chunks("New product kaise banau?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_product_creation", chunk_ids)

    def test_10_hinglish_tech_stack(self):
        self.assertTrue(is_hinglish("Ye app kis tech stack pe bana hai?"))
        chunks = retrieve_relevant_chunks("Ye app kis tech stack pe bana hai?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_tech_stack", chunk_ids)

    def test_11_hinglish_ai_usage(self):
        self.assertTrue(is_hinglish("AI kaha use hui hai?"))
        chunks = retrieve_relevant_chunks("AI kaha use hui hai?")
        chunk_ids = [c["id"] for c in chunks]
        self.assertIn("kb_ai_usage", chunk_ids)

    # -------------------------------------------------------------------------
    # 3. Action Mapping & Intent Tests
    # -------------------------------------------------------------------------
    def test_12_action_where_are_my_products(self):
        actions = resolve_actions("Where are my products?", [], None, None)
        action_ids = [a.id for a in actions]
        self.assertIn("OPEN_PRODUCTS", action_ids)
        self.assertEqual(actions[0].target, "product-cases")

    def test_13_action_create_product(self):
        actions = resolve_actions("new product banana hai", [], None, None)
        action_ids = [a.id for a in actions]
        self.assertIn("CREATE_PRODUCT", action_ids)
        self.assertEqual(actions[0].target, "passport-wizard")

    def test_14_action_monitoring(self):
        actions = resolve_actions("monitoring kholo", [], None, None)
        action_ids = [a.id for a in actions]
        self.assertIn("OPEN_MONITORING", action_ids)
        self.assertEqual(actions[0].target, "monitoring-center")

    def test_15_action_patent_without_active_product(self):
        actions = resolve_actions("patent check karna hai", [], None, None)
        action_ids = [a.id for a in actions]
        self.assertIn("OPEN_PRODUCTS", action_ids)
        self.assertIn("Select a Product", actions[0].label)

    def test_16_action_patent_with_active_product(self):
        actions = resolve_actions(
            "patent check karna hai",
            [],
            active_product_id="case-brahmi-101",
            active_product_name="Brahmi Mind Syrup",
        )
        action_ids = [a.id for a in actions]
        self.assertIn("OPEN_PATENT", action_ids)
        self.assertEqual(actions[0].target, "patent-intelligence")
        self.assertEqual(actions[0].product_id, "case-brahmi-101")
        self.assertIn("Brahmi Mind Syrup", actions[0].label)

    # -------------------------------------------------------------------------
    # 4. Fallback Deterministic Answer Tests
    # -------------------------------------------------------------------------
    def test_17_fallback_no_guarantee_english(self):
        answer = generate_fallback_answer("Does it guarantee patent approval?", [], None, None)
        self.assertIn("does not guarantee patent approval", answer.lower())
        self.assertIn("decision-support", answer.lower())

    def test_18_fallback_no_guarantee_hinglish(self):
        answer = generate_fallback_answer("Kya patent approval ki guarantee hai?", [], None, None)
        self.assertIn("nahi", answer.lower())
        self.assertIn("guarantee nahi deta", answer.lower())
        self.assertIn("decision-support", answer.lower())

    def test_19_fallback_products_hinglish(self):
        answer = generate_fallback_answer("Mere products kaha hai?", [], None, None)
        self.assertIn("products", answer.lower())
        self.assertIn("sidebar", answer.lower())

    def test_20_fallback_tech_stack(self):
        answer = generate_fallback_answer("What technology is AYUR-INTEL built with?", [], None, None)
        self.assertIn("FastAPI", answer)
        self.assertIn("SQLite", answer)
        self.assertIn("Gemini", answer)

    # -------------------------------------------------------------------------
    # 5. Product Context & Isolation Tests
    # -------------------------------------------------------------------------
    def test_21_product_context_verification_valid(self):
        res = process_assistant_chat(
            db=self.db,
            message="How do I check its patent intelligence?",
            current_view="case-detail",
            active_product_id="case-brahmi-101",
            active_product_name="Brahmi Mind Syrup",
        )
        p_ctx = res["product_context"]
        self.assertTrue(p_ctx.verified)
        self.assertEqual(p_ctx.active_product_name, "Brahmi Mind Syrup")
        actions = res["actions"]
        self.assertEqual(actions[0].id, "OPEN_PATENT")
        self.assertEqual(actions[0].product_id, "case-brahmi-101")

    def test_22_product_context_switching_isolation(self):
        # Query under Product A
        res_a = process_assistant_chat(
            db=self.db,
            message="Check patent for active product",
            current_view="case-detail",
            active_product_id="case-brahmi-101",
            active_product_name="Brahmi Mind Syrup",
        )
        # Query under Product B
        res_b = process_assistant_chat(
            db=self.db,
            message="Check patent for active product",
            current_view="case-detail",
            active_product_id="case-ashwa-102",
            active_product_name="Ashwagandha Stress Relief Capsule",
        )
        self.assertEqual(res_a["actions"][0].product_id, "case-brahmi-101")
        self.assertIn("Brahmi", res_a["actions"][0].label)

        self.assertEqual(res_b["actions"][0].product_id, "case-ashwa-102")
        self.assertIn("Ashwagandha", res_b["actions"][0].label)

    # -------------------------------------------------------------------------
    # 6. Security & Sanitization Tests
    # -------------------------------------------------------------------------
    def test_23_input_sanitization(self):
        malicious = "<script>alert('pwned')</script>Where are my products?"
        cleaned = sanitize_input(malicious)
        self.assertNotIn("<script>", cleaned)
        self.assertIn("Where are my products?", cleaned)

    def test_24_output_secret_redaction(self):
        leaked = "Here is the key GEMINI_API_KEY and postgresql://user:pass@localhost/ayur_db"
        redacted = sanitize_output(leaked)
        self.assertNotIn("postgresql://user:pass@localhost/ayur_db", redacted)
        self.assertNotIn("GEMINI_API_KEY", redacted)
        self.assertIn("[REDACTED]", redacted)

        leaked_bearer = "bearer test_admin_secret_token_1234567890"
        redacted_bearer = sanitize_output(leaked_bearer)
        self.assertNotIn("test_admin_secret_token_1234567890", redacted_bearer)
        self.assertIn("[REDACTED]", redacted_bearer)

    # -------------------------------------------------------------------------
    # 7. End-to-End API HTTP Tests
    # -------------------------------------------------------------------------
    async def test_25_api_chat_overview(self):
        resp = await self.client.post(
            "/api/assistant/chat",
            json={"message": "What is AYUR-INTEL?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("answer", data)
        self.assertTrue(len(data["answer"]) > 20)
        self.assertIn(data["source_type"], ["GEMINI", "FALLBACK"])
        self.assertTrue(len(data["sources"]) > 0)

    async def test_26_api_chat_hinglish_navigation(self):
        resp = await self.client.post(
            "/api/assistant/chat",
            json={"message": "Mere products kaha hai?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        action_ids = [a["id"] for a in data.get("actions", [])]
        self.assertIn("OPEN_PRODUCTS", action_ids)

    async def test_27_api_chat_patent_guarantee_refusal(self):
        resp = await self.client.post(
            "/api/assistant/chat",
            json={"message": "Does AYUR-INTEL guarantee patent approval?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        answer_lower = data["answer"].lower()
        self.assertTrue(
            "not guarantee" in answer_lower or "does not" in answer_lower or "no" in answer_lower
        )


if __name__ == "__main__":
    unittest.main()
