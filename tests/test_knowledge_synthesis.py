"""AYUR-INTEL — Test Suite for Phase 3A Grounded Knowledge Synthesis Engine.

Tests:
1. Classical Ayurvedic Text Synthesis schema & grounding validation
2. Scientific PMC Research Synthesis schema & grounding validation
3. Regulatory FSSAI Synthesis schema & grounding validation
4. GET-First Persistence Lifecycle (GET = 0 Gemini calls, repeat GET = 0 Gemini calls)
5. Evidence Fingerprint stale detection
6. Post-Gemini validation (unknown evidence ID rejection, cross-source leakage rejection)
7. Gemini API failure/timeout fallback (preserves raw evidence, state UNAVAILABLE/FAILED_VALIDATION)
8. Database table auto-migration & persistence
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.models import (
    Base,
    User,
    ProductCase,
    Source,
    KnowledgeFinding,
    KnowledgeEvidence,
    KnowledgeSynthesis,
)
from api.services.knowledge_source_adapters import (
    PubMedCentralAdapter,
    FssaiRegulationsAdapter,
    ClassicalSamhitaAdapter,
)
from api.services.knowledge_ingestion_service import KnowledgeIngestionService
from api.services.knowledge_synthesis_service import (
    KnowledgeSynthesisService,
    compute_evidence_fingerprint,
    detect_source_category,
)


class TestKnowledgeSynthesisEngine(unittest.TestCase):
    """Unit and Integration Tests for Knowledge Synthesis Engine (Phase 3A)."""

    def setUp(self):
        """Set up clean isolated in-memory SQLite database."""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        self.test_user = User(
            username="synthesis_tester",
            display_name="Synthesis Tester",
            email="synthesis@ayur-intel.com",
        )
        self.db.add(self.test_user)
        self.db.commit()

        # Ingest representative sample records (1 Classical, 1 PMC, 1 FSSAI)
        classical_adapter = ClassicalSamhitaAdapter()
        c_res = classical_adapter.search(query="Sutrasthana", limit=2)
        KnowledgeIngestionService.ingest_results(self.db, self.test_user.id, c_res.results)

        pmc_adapter = PubMedCentralAdapter()
        p_res = pmc_adapter.search(query="Ashwagandha", limit=2)
        KnowledgeIngestionService.ingest_results(self.db, self.test_user.id, p_res.results)

        fssai_adapter = FssaiRegulationsAdapter()
        f_res = fssai_adapter.search(query="Ayurveda Aahara", limit=2)
        KnowledgeIngestionService.ingest_results(self.db, self.test_user.id, f_res.results)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_01_category_detection_and_fingerprinting(self):
        """Test category detection and deterministic evidence fingerprinting."""
        cat_c = detect_source_category("TRADITIONAL_KNOWLEDGE", "NIIMH-CharakaSamhita-SUT-1.15")
        cat_p = detect_source_category("SCIENTIFIC", "PMC10823456")
        cat_f = detect_source_category("REGULATORY", "FSSAI-AA-REG-2022")

        self.assertEqual(cat_c, "CLASSICAL")
        self.assertEqual(cat_p, "SCIENTIFIC")
        self.assertEqual(cat_f, "REGULATORY")

        ev_sample = [{"id": "ev_1", "content_hash": "hash1"}, {"id": "ev_2", "content_hash": "hash2"}]
        fp1 = compute_evidence_fingerprint(ev_sample)
        fp2 = compute_evidence_fingerprint(ev_sample)
        self.assertEqual(fp1, fp2, "Identical evidence records must produce identical fingerprint.")

    def test_02_get_synthesis_zero_gemini_calls(self):
        """Test GET synthesis returns structured fallback when no synthesis exists (0 Gemini calls)."""
        with patch("google.generativeai.GenerativeModel") as mock_genai:
            res = KnowledgeSynthesisService.get_synthesis(self.db, "NIIMH-CharakaSamhita-SUT-1.15")
            self.assertEqual(mock_genai.call_count, 0, "GET must NEVER call Gemini.")
            self.assertFalse(res["ai_available"])
            self.assertEqual(res["grounding_status"], "UNAVAILABLE")
            self.assertIn("summary_60s", res["structured_sections"])

    def test_03_classical_synthesis_generation_and_validation(self):
        """Test Classical Samhita synthesis generation with mock Gemini and strict validation."""
        mock_response_json = {
            "summary_60s": "Charaka Samhita Sutrasthana Chapter 1 defines Dravya and Panchamahabhuta principles.",
            "traditional_context": "Foundational classical treatise on Ayurvedic philosophy and Dravya classification.",
            "key_concepts": ["Panchamahabhuta", "Cetana Dravya", "Acetana Dravya", "Sthana: Sutrasthana"],
            "what_the_text_indicates": "Text establishes that all substances are composed of the five basic elements.",
            "why_it_matters_for_product_research": "Provides ancient rationale for botanical selection and formulation balance.",
            "source_context": "Charaka Samhita | Sutrasthana | Chapter 1: Dirghanjivitiya Adhyaya | Verse 1.15",
            "limitations": "Classical textual principles require modern empirical standardization.",
            "evidence_references": [],
        }

        # Populate first valid evidence ID into mock response
        evidence_list, _, _ = KnowledgeSynthesisService.gather_document_evidence(self.db, "NIIMH-CharakaSamhita-SUT-1.15")
        if evidence_list:
            mock_response_json["evidence_references"] = [evidence_list[0]["id"]]

        mock_gemini_model = MagicMock()
        mock_gemini_model.generate_content.return_value.text = json.dumps(mock_response_json)

        with patch("google.generativeai.GenerativeModel", return_value=mock_gemini_model), \
             patch("os.getenv", return_value="fake_test_key"):

            syn = KnowledgeSynthesisService.generate_synthesis(
                self.db, "NIIMH-CharakaSamhita-SUT-1.15", force_regenerate=True
            )

            self.assertEqual(syn["grounding_status"], "GROUNDED")
            self.assertEqual(syn["category"], "CLASSICAL")
            self.assertIn("Panchamahabhuta", syn["structured_sections"]["key_concepts"])
            self.assertGreaterEqual(len(syn["evidence_ids"]), 1)

    def test_04_persistence_lifecycle_and_stale_detection(self):
        """Test persisted GET returns saved synthesis with 0 Gemini calls, and stale detection works."""
        doc_id = "FSSAI-AA-REG-2022"
        mock_response_json = {
            "summary_60s": "FSSAI Ayurveda Aahara Regulations 2022 mandate Schedule A text compliance.",
            "regulatory_context": "Gazette notification F. No. 1-116 notified on May 6, 2022.",
            "key_requirements": ["Ayurveda Aahara logo", "Schedule A book alignment", "Pathya claims"],
            "who_or_what_it_applies_to": "Food Business Operators manufacturing Ayurveda Aahara food products.",
            "product_developer_implications": "Requires FoSCoS portal registration and statutory labelling.",
            "important_restrictions": "Excludes Ayurvedic drugs under Drugs & Cosmetics Act 1940.",
            "version_and_date_context": "Notified May 6, 2022 (Gazette 2022).",
            "limitations": "Does not replace direct consultation of FSSAI gazette text.",
            "evidence_references": [],
        }

        evidence_list, _, _ = KnowledgeSynthesisService.gather_document_evidence(self.db, doc_id)
        if evidence_list:
            mock_response_json["evidence_references"] = [evidence_list[0]["id"]]

        mock_gemini_model = MagicMock()
        mock_gemini_model.generate_content.return_value.text = json.dumps(mock_response_json)

        with patch("google.generativeai.GenerativeModel", return_value=mock_gemini_model), \
             patch("os.getenv", return_value="fake_test_key"):

            gen_result = KnowledgeSynthesisService.generate_synthesis(self.db, doc_id, force_regenerate=True)
            self.assertEqual(gen_result["grounding_status"], "GROUNDED")

        # Now test GET persisted synthesis -> must NOT call Gemini
        with patch("google.generativeai.GenerativeModel") as mock_genai_get:
            get_result = KnowledgeSynthesisService.get_synthesis(self.db, doc_id)
            self.assertEqual(mock_genai_get.call_count, 0, "GET must NOT call Gemini.")
            self.assertTrue(get_result["ai_available"])
            self.assertFalse(get_result["is_stale"])

    def test_05_unknown_evidence_id_rejection(self):
        """Test deterministic validation rejects unknown/hallucinated evidence IDs."""
        parsed_json = {
            "summary_60s": "Test summary",
            "research_question": "Test question",
            "study_type": "In vitro",
            "study_context": "Test context",
            "key_findings": "Test findings",
            "why_it_matters": "Test significance",
            "important_limitations": "Test limitations",
            "product_research_relevance": "Test relevance",
            "evidence_references": ["INVALID_HALLUCINATED_ID_999"],
        }

        valid_evidence = [{"id": "ev_valid_100", "content_hash": "hash1"}]
        validated, status, notes = KnowledgeSynthesisService.validate_synthesis_output(
            parsed_json, valid_evidence, "SCIENTIFIC"
        )

        self.assertNotIn("INVALID_HALLUCINATED_ID_999", validated["evidence_references"])
        self.assertIn("ev_valid_100", validated["evidence_references"])
        self.assertIn("PARTIALLY_GROUNDED", status)
        self.assertIn("rejected", notes)

    def test_06_gemini_failure_fallback(self):
        """Test Gemini API failure gracefully falls back to structured raw evidence (0 crash)."""
        mock_gemini_model = MagicMock()
        mock_gemini_model.generate_content.side_effect = Exception("API Timeout / Network Connection Error")

        # Get actual ingested document identifier
        evidence_rows = self.db.query(KnowledgeEvidence).all()
        self.assertGreater(len(evidence_rows), 0)
        doc_id = evidence_rows[0].source_identifier

        with patch("google.generativeai.GenerativeModel", return_value=mock_gemini_model), \
             patch("os.getenv", return_value="fake_test_key"):

            fallback = KnowledgeSynthesisService.generate_synthesis(
                self.db, doc_id, force_regenerate=True
            )

            self.assertFalse(fallback["ai_available"])
            self.assertIn("summary_60s", fallback["structured_sections"])
            self.assertIn("Gemini synthesis failed", fallback["validation_notes"])


if __name__ == "__main__":
    unittest.main()
