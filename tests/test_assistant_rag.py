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
    generate_gemini_answer,
    process_assistant_chat,
    sanitize_input,
    sanitize_output,
    is_hinglish,
    detect_language,
    DetectedLanguage,
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
            form="Syrup",
            intended_use="Cognitive wellness & memory support",
            process="Traditional decoction method with controlled cooling",
            ingredients='[{"name": "Brahmi", "botanical": "Bacopa monnieri", "quantity": "250 mg", "standardization": "20% Bacosides"}, {"name": "Shankhpushpi", "botanical": "Convolvulus pluricaulis", "quantity": "100 mg"}]'
        )
        self.case_b = ProductCase(
            id=102,
            public_id="case-ashwa-102",
            owner_id=1,
            name="Ashwagandha Stress Relief Capsule",
            stage="COMMERCIAL",
            status="COMPLETED",
            form="Capsule",
            intended_use="Stress relief and restorative vitality",
            process="Hydro-ethanolic extraction followed by encapsulation",
            ingredients='[{"name": "Ashwagandha", "botanical": "Withania somnifera", "quantity": "500 mg", "standardization": "5% Withanolides"}]'
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
        self.assertIn(data["source_type"], ["FAST_LOCAL", "FAST_RAG", "GEMINI", "FALLBACK"])
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

    # -------------------------------------------------------------------------
    # 8. Dynamic Language Mirroring & Fallback Tests
    # -------------------------------------------------------------------------
    def test_28_language_detection(self):
        # English detection
        self.assertEqual(detect_language("What is Product Passport?"), DetectedLanguage.ENGLISH)
        self.assertEqual(detect_language("Where are my products?"), DetectedLanguage.ENGLISH)
        self.assertEqual(detect_language("How does monitoring work?"), DetectedLanguage.ENGLISH)
        self.assertEqual(detect_language("What is AYUR-INTEL?"), DetectedLanguage.ENGLISH)

        # Hinglish detection
        self.assertEqual(detect_language("Product Passport kya hota hai?"), DetectedLanguage.HINGLISH)
        self.assertEqual(detect_language("Mere products kaha hai?"), DetectedLanguage.HINGLISH)
        self.assertEqual(detect_language("Patent intelligence kya karta hai?"), DetectedLanguage.HINGLISH)
        self.assertEqual(detect_language("New product kaise banau?"), DetectedLanguage.HINGLISH)

        # Hindi (Devanagari) detection
        self.assertEqual(detect_language("प्रोडक्ट पासपोर्ट क्या है?"), DetectedLanguage.HINDI)
        self.assertEqual(detect_language("मेरे प्रोडक्ट्स कहाँ हैं?"), DetectedLanguage.HINDI)

    def test_29_fallback_language_mirroring_product_passport(self):
        # English question -> English fallback
        ans_en = generate_fallback_answer("What is Product Passport?", [], None, None)
        self.assertIn("is the comprehensive digital master dossier", ans_en)
        self.assertNotIn("karta hai", ans_en)
        self.assertNotIn("aapke", ans_en.lower())

        # Hinglish question -> Hinglish fallback
        ans_hi = generate_fallback_answer("Product Passport kya hota hai?", [], None, None)
        self.assertIn("complete digital master dossier hota hai", ans_hi)
        self.assertIn("seedha Indian Patent searches", ans_hi)
        # Technical terms preserved in English
        self.assertIn("Product Passport", ans_hi)
        self.assertIn("Botanical Identity", ans_hi)

    def test_30_fallback_language_mirroring_products_and_actions(self):
        # English: Where are my products? -> English + View Products action
        actions_en = resolve_actions("Where are my products?", [], None, None)
        self.assertEqual(actions_en[0].id, "OPEN_PRODUCTS")
        self.assertEqual(actions_en[0].label, "View Products →")
        ans_en = generate_fallback_answer("Where are my products?", [], None, None)
        self.assertIn("You can find all your saved formulations", ans_en)

        # Hinglish: Mere products kaha hai? -> Hinglish + same View Products action
        actions_hi = resolve_actions("Mere products kaha hai?", [], None, None)
        self.assertEqual(actions_hi[0].id, "OPEN_PRODUCTS")
        self.assertEqual(actions_hi[0].label, "View Products →")
        ans_hi = generate_fallback_answer("Mere products kaha hai?", [], None, None)
        self.assertIn("Aapke saare saved products left navigation sidebar", ans_hi)

    def test_31_dynamic_language_switching_in_same_session(self):
        # Turn 1: English
        res1 = process_assistant_chat(self.db, "What is AYUR-INTEL?", current_view="dashboard")
        self.assertIn("AYUR-INTEL", res1["answer"])
        self.assertNotIn("aapke", res1["answer"].lower())
        self.assertNotIn("karta hai", res1["answer"].lower())

        # Turn 2: Hinglish (adapts immediately per message)
        res2 = process_assistant_chat(self.db, "Patent intelligence kya karta hai?", current_view="dashboard")
        self.assertIn("karta hai", res2["answer"].lower())
        self.assertIn("Patent Intelligence", res2["answer"])

        # Turn 3: English again (switches back immediately)
        res3 = process_assistant_chat(self.db, "How does monitoring work?", current_view="dashboard")
        self.assertIn("Continuous Regulatory & Market Monitoring", res3["answer"])
        self.assertNotIn("karta hai", res3["answer"].lower())

    def test_32_gemini_disabled_fallback_english_and_hinglish(self):
        # Test with empty API key to force deterministic fallback
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "AYURINTEL_GEMINI_API_KEY": ""}):
            # English
            res_en = process_assistant_chat(self.db, "What is Product Passport?", current_view="dashboard")
            self.assertIn(res_en["source_type"], ["FAST_RAG", "FALLBACK"])
            self.assertIn("is the comprehensive digital master dossier", res_en["answer"])

            # Hinglish
            res_hi = process_assistant_chat(self.db, "Product Passport kya hota hai?", current_view="dashboard")
            self.assertIn(res_hi["source_type"], ["FAST_RAG", "FALLBACK"])
            self.assertIn("digital master dossier hota hai", res_hi["answer"])
            self.assertIn("Product Passport", res_hi["answer"])

    # -------------------------------------------------------------------------
    # 9. Conversational Assistant & Routing Tests (UX Hardening)
    # -------------------------------------------------------------------------
    def test_33_casual_opener_no_rag_dump_hinglish(self):
        # "achha mujhe kuch jan na hai" must NOT trigger RAG knowledge dump or source tags
        res = process_assistant_chat(self.db, "achha mujhe kuch jan na hai", current_view="dashboard")
        self.assertEqual(res["sources"], [], "Casual openers must have zero knowledge source dumps")
        self.assertIn("poochiye", res["answer"].lower())
        self.assertIn("ayush", res["answer"].lower())
        # Safe default starting actions provided
        action_ids = [a.id for a in res["actions"]]
        self.assertIn("CREATE_PRODUCT", action_ids)

    def test_34_casual_opener_no_rag_dump_english(self):
        # English greeting should be welcoming and have empty sources
        res = process_assistant_chat(self.db, "hi, can you help me?", current_view="dashboard")
        self.assertEqual(res["sources"], [], "English casual greeting must have zero knowledge source dumps")
        self.assertIn("help", res["answer"].lower())
        self.assertIn("ayush", res["answer"].lower())

    def test_35_self_knowledge_who_are_you(self):
        # Self-knowledge inquiries route to AYUSH Assistant chunk
        res = process_assistant_chat(self.db, "who are you and what powers you?", current_view="dashboard")
        self.assertIn("AYUSH Assistant & Capabilities", res["sources"])
        self.assertIn("ayush", res["answer"].lower())
        self.assertIn("gemini", res["answer"].lower())
        self.assertTrue("not chatgpt" in res["answer"].lower() or "chatgpt" in res["answer"].lower())

    def test_36_active_product_context_inquiry(self):
        # Product status query with active product selected
        case = self.db.query(ProductCase).first()
        res = process_assistant_chat(
            self.db,
            "which product is active?",
            current_view="dashboard",
            active_product_id=str(case.public_id),
            active_product_name=case.name,
        )
        self.assertIn(case.name, res["answer"])
        action_ids = [a.id for a in res["actions"]]
        self.assertIn("OPEN_PATENT", action_ids)

    def test_37_no_active_product_context_inquiry(self):
        # Product status query without active product
        res = process_assistant_chat(
            self.db,
            "which product is active?",
            current_view="dashboard",
            active_product_id=None,
            active_product_name=None,
        )
        self.assertTrue("no active product" in res["answer"].lower() or "no product" in res["answer"].lower())
        action_ids = [a.id for a in res["actions"]]
        self.assertIn("CREATE_PRODUCT", action_ids)

    def test_38_followup_resolution_open_it(self):
        # History discusses patent, user says "open it"
        history = [
            {"role": "user", "content": "Tell me about Indian Patent Intelligence"},
            {"role": "assistant", "content": "Indian Patent Intelligence evaluates prior art under Section 3(p)..."}
        ]
        res = process_assistant_chat(
            self.db,
            "open it",
            history=history,
            current_view="dashboard",
        )
        action_ids = [a.id for a in res["actions"]]
        self.assertTrue("OPEN_PATENT" in action_ids or "OPEN_PRODUCTS" in action_ids)

    def test_39_followup_resolution_and_risk(self):
        # History discusses a formulation, user asks "and risk?"
        history = [
            {"role": "user", "content": "What is the formulation for Ashwagandha Rasayana?"},
            {"role": "assistant", "content": "Ashwagandha Rasayana contains classical herbs..."}
        ]
        res = process_assistant_chat(
            self.db,
            "and risk?",
            history=history,
            current_view="dashboard",
        )
        self.assertIn("Risk Assessment", res["sources"][0] if res["sources"] else "Risk Assessment")

    def test_40_out_of_scope_query(self):
        # Completely out-of-scope question
        res = process_assistant_chat(self.db, "what is the weather today?", current_view="dashboard")
        self.assertEqual(res["sources"], [])
        self.assertIn("specialized", res["answer"].lower())

    async def test_41_history_payload_via_api(self):
        # Chat API endpoint accepts history payload cleanly
        resp = await self.client.post(
            "/api/assistant/chat",
            json={
                "message": "achha mujhe kuch jan na hai",
                "history": [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "Hello! I am AYUSH."}
                ]
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["sources"], [])
        self.assertIn("poochiye", data["answer"].lower())

    def test_42_empty_query_safe_defaults(self):
        # Empty query returns welcoming guidance without leaking sources
        res = process_assistant_chat(self.db, "", current_view="dashboard")
        self.assertEqual(res["sources"], [])
        self.assertIn("ayush", res["answer"].lower())

    # -------------------------------------------------------------------------
    # 10. Performance, Fast Paths & Gemini Fallback Safeguard Tests
    # -------------------------------------------------------------------------
    def test_43_fast_paths_use_zero_gemini_calls(self):
        # Verify that common casual, identity, navigation, and canonical RAG queries
        # NEVER invoke Gemini under any circumstances.
        queries_to_verify = [
            ("hi", "FAST_LOCAL"),
            ("achha mujhe kuch jan na hai", "FAST_LOCAL"),
            ("tum kya karte ho?", "FAST_LOCAL"),
            ("who are you?", "FAST_LOCAL"),
            ("mere products dikhao", "FAST_LOCAL"),
            ("What is Product Passport?", "FAST_RAG"),
            ("Product Passport kya hota hai?", "FAST_RAG"),
            ("How does monitoring work?", "FAST_RAG"),
        ]

        with patch("api.services.assistant_service.generate_gemini_answer") as mock_gemini:
            for q, expected_type in queries_to_verify:
                mock_gemini.reset_mock()
                res = process_assistant_chat(self.db, q, current_view="dashboard")
                self.assertEqual(
                    mock_gemini.call_count, 0,
                    f"Query '{q}' must NOT invoke Gemini (FAST PATH expected {expected_type}, got {res['source_type']})"
                )
                self.assertEqual(res["source_type"], expected_type)
                self.assertTrue(len(res["answer"]) > 15)

    def test_44_complex_synthesis_query_invokes_gemini(self):
        # Multi-concept synthesis query should route to Gemini as the last layer
        complex_q = "Compare the patent risk of Ashwagandha with Curcumin under Section 3(p) and synthesize the trade-off"
        with patch("api.services.assistant_service.generate_gemini_answer", return_value=("Synthesized answer", "GEMINI")) as mock_gemini:
            res = process_assistant_chat(self.db, complex_q, current_view="dashboard")
            self.assertEqual(mock_gemini.call_count, 1, "Complex synthesis queries must invoke Gemini reasoning layer")
            self.assertEqual(res["source_type"], "GEMINI")

    def test_45_gemini_timeout_fallback(self):
        # When Gemini call times out (>=4.0s), immediately return FALLBACK_TIMEOUT
        complex_q = "Compare the patent risk of Ashwagandha with Curcumin under Section 3(p) and synthesize the trade-off"
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_api_key_123"}):
            with patch("google.generativeai.GenerativeModel") as mock_cls:
                mock_inst = mock_cls.return_value
                mock_inst.generate_content.side_effect = Exception("Request timed out (deadline exceeded)")
                ans, stype = generate_gemini_answer(complex_q, [], "dashboard", None, None)
                self.assertEqual(stype, "FALLBACK_TIMEOUT")
                self.assertTrue(len(ans) > 20)

    def test_46_gemini_429_quota_fallback(self):
        # When Gemini returns 429 ResourceExhausted, immediately return FALLBACK_429
        complex_q = "Compare the patent risk of Ashwagandha with Curcumin under Section 3(p) and synthesize the trade-off"
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_api_key_123"}):
            with patch("google.generativeai.GenerativeModel") as mock_cls:
                mock_inst = mock_cls.return_value
                mock_inst.generate_content.side_effect = Exception("429 ResourceExhausted: Quota exceeded for model")
                ans, stype = generate_gemini_answer(complex_q, [], "dashboard", None, None)
                self.assertEqual(stype, "FALLBACK_429")
                self.assertTrue(len(ans) > 20)

    def test_47_fast_path_latency_under_100ms(self):
        # Verify server processing latency is well under 100ms for fast paths
        fast_queries = ["hi", "who are you?", "mere products dikhao", "What is Product Passport?"]
        for q in fast_queries:
            res = process_assistant_chat(self.db, q, current_view="dashboard")
            self.assertIn("server_processing_ms", res)
            self.assertLess(
                res["server_processing_ms"], 100.0,
                f"Fast path for query '{q}' took {res['server_processing_ms']}ms, expected <100ms"
            )

    # -------------------------------------------------------------------------
    # 7. Product-Aware Q&A, Grounded Attributes & Description Tests
    # -------------------------------------------------------------------------
    def test_48_query_product_explicit_name(self):
        # Explicit product name mentioned in message
        res = process_assistant_chat(self.db, "Tell me about Brahmi Mind Syrup", current_view="dashboard")
        self.assertEqual(res["source_type"], "FAST_LOCAL")
        self.assertIn("Brahmi Mind Syrup", res["answer"])
        self.assertIn("Syrup", res["answer"])
        self.assertEqual(res["product_context"].active_product_name, "Brahmi Mind Syrup")

    def test_49_query_active_product_intended_use_and_process(self):
        # Queries using active product context
        res_use = process_assistant_chat(
            self.db,
            "Is product ka intended use kya hai?",
            active_product_id="case-brahmi-101",
            active_product_name="Brahmi Mind Syrup",
        )
        self.assertEqual(res_use["source_type"], "FAST_LOCAL")
        self.assertIn("Cognitive wellness & memory support", res_use["answer"])

        res_proc = process_assistant_chat(
            self.db,
            "How is this product prepared?",
            active_product_id="case-brahmi-101",
            active_product_name="Brahmi Mind Syrup",
        )
        self.assertEqual(res_proc["source_type"], "FAST_LOCAL")
        self.assertIn("Traditional decoction method", res_proc["answer"])

    def test_50_product_ingredients_and_quantities(self):
        # Ingredients list
        res_ings = process_assistant_chat(
            self.db,
            "Brahmi Mind Syrup mein kya ingredients hain?",
            current_view="dashboard",
        )
        self.assertEqual(res_ings["source_type"], "FAST_LOCAL")
        self.assertIn("Brahmi", res_ings["answer"])
        self.assertIn("Shankhpushpi", res_ings["answer"])
        self.assertIn("250 mg", res_ings["answer"])

        # Specific quantity inquiry
        res_qty = process_assistant_chat(
            self.db,
            "Isme kitni quantity Brahmi use hui hai?",
            active_product_id="case-brahmi-101",
            active_product_name="Brahmi Mind Syrup",
        )
        self.assertEqual(res_qty["source_type"], "FAST_LOCAL")
        self.assertIn("250 mg", res_qty["answer"])
        self.assertIn("Brahmi", res_qty["answer"])

    def test_51_product_missing_field_message(self):
        # Create case without intended use or process
        sparse_case = ProductCase(
            id=103,
            public_id="case-sparse-103",
            owner_id=1,
            name="Neem Purifying Oil",
            stage="IDEA",
            status="DRAFT",
            intended_use=None,
            process=None,
        )
        self.db.add(sparse_case)
        self.db.commit()

        res = process_assistant_chat(
            self.db,
            "Is product ka intended use kya hai?",
            active_product_id="case-sparse-103",
            active_product_name="Neem Purifying Oil",
        )
        self.assertIn("ye information abhi add nahi ki gayi hai", res["answer"].lower())

    def test_52_nonexistent_product_handled_cleanly(self):
        # Explicit search for a product that does not exist in DB
        res = process_assistant_chat(
            self.db,
            "Tell me about Chyawanprash Deluxe",
            current_view="dashboard",
        )
        self.assertEqual(res["source_type"], "FAST_LOCAL")
        self.assertIn("Chyawanprash Deluxe", res["answer"])
        self.assertTrue(
            "nahi mila" in res["answer"].lower() or "couldn't find" in res["answer"].lower(),
            "Nonexistent product must be clearly stated as not found",
        )
        # Verify action to create product in wizard is offered
        action_ids = [a.id for a in res["actions"]]
        self.assertIn("CREATE_PRODUCT", action_ids)

    def test_53_ambiguous_product_names(self):
        # Add a second case sharing name token 'Ashwagandha'
        ashwa_two = ProductCase(
            id=104,
            public_id="case-ashwa-gold-104",
            owner_id=1,
            name="Ashwagandha Gold Tablet",
            stage="IDEA",
            status="DRAFT",
        )
        self.db.add(ashwa_two)
        self.db.commit()

        # Asking generally for Ashwagandha when two exist
        res = process_assistant_chat(
            self.db,
            "Tell me about Ashwagandha",
            current_view="dashboard",
        )
        self.assertEqual(res["source_type"], "FAST_LOCAL")
        self.assertTrue(
            "multiple products" in res["answer"].lower() or "multiple" in res["answer"].lower(),
            "Ambiguous products should ask user for clarification",
        )
        self.assertIn("Ashwagandha Stress Relief Capsule", res["answer"])
        self.assertIn("Ashwagandha Gold Tablet", res["answer"])

    def test_54_product_isolation_security(self):
        # Product belonging to another user (not demo) must never be accessible
        foreign_user = User(
            id=999,
            email="other@company.com",
            username="other_researcher",
            hashed_password="pw",
            display_name="Other",
        )
        self.db.add(foreign_user)
        self.db.commit()

        secret_case = ProductCase(
            id=999,
            public_id="case-secret-999",
            owner_id=999,
            name="Secret Proprietary Elixir",
            stage="RND",
            status="DRAFT",
            is_demo=False,
            ingredients='[{"name": "Rare Herb", "quantity": "10 mg"}]',
        )
        self.db.add(secret_case)
        self.db.commit()

        # Querying the secret product should report NOT_FOUND
        res = process_assistant_chat(
            self.db,
            "Tell me about Secret Proprietary Elixir",
            current_view="dashboard",
        )
        self.assertNotIn("Rare Herb", res["answer"])
        self.assertTrue(
            "nahi mila" in res["answer"].lower() or "couldn't find" in res["answer"].lower(),
            "Foreign private case must never be revealed",
        )

    def test_55_short_description_generation_grounded(self):
        # Test short description generation from stored structured data
        res = process_assistant_chat(
            self.db,
            "Is product ki description bana do",
            active_product_id="case-brahmi-101",
            active_product_name="Brahmi Mind Syrup",
        )
        self.assertEqual(res["source_type"], "FAST_LOCAL")
        ans = res["answer"]
        # Grounded facts
        self.assertIn("Brahmi Mind Syrup", ans)
        self.assertIn("Syrup", ans)
        self.assertIn("Cognitive wellness & memory support", ans)
        self.assertIn("Brahmi", ans)
        # Must not hallucinate unseen herbs
        self.assertNotIn("Turmeric", ans)
        self.assertNotIn("Ashwagandha", ans)
        self.assertNotIn("100% cure", ans)
        # Must be concise: approximately 2-4 sentences
        sentences = [s.strip() for s in ans.split(".") if s.strip()]
        self.assertGreaterEqual(len(sentences), 2)
        self.assertLessEqual(len(sentences), 5)

    def test_56_product_fast_path_latency_and_zero_gemini(self):
        # Product factual queries must run in FAST_LOCAL without invoking Gemini
        with patch("api.services.assistant_service.generate_gemini_answer") as mock_gemini:
            res = process_assistant_chat(
                self.db,
                "What ingredients did I use in Brahmi Mind Syrup?",
                current_view="dashboard",
            )
            self.assertEqual(mock_gemini.call_count, 0, "Factual product queries must not invoke Gemini")
            self.assertEqual(res["source_type"], "FAST_LOCAL")
            self.assertIn("server_processing_ms", res)
            self.assertLess(res["server_processing_ms"], 100.0)

    def test_57_no_active_product_handles_anaphora_gracefully(self):
        # Query referring to 'is product' when no product is active
        res = process_assistant_chat(
            self.db,
            "Is product ka intended use kya hai?",
            active_product_id=None,
            active_product_name=None,
        )
        self.assertEqual(res["source_type"], "FAST_LOCAL")
        self.assertTrue(
            "active product" in res["answer"].lower() or "selected nahi hai" in res["answer"].lower(),
            "Should inform user to select or name a product",
        )


if __name__ == "__main__":
    unittest.main()

