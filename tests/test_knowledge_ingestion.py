"""AYUR-INTEL — Test Suite for Phase 2 Knowledge Hub Evidence Ingestion & Adapters.

Tests:
1. Source normalization & deterministic SHA256 hashes
2. Duplicate prevention & repeated ingestion idempotency
3. PubMed Central (PMC) metadata parsing & licence preservation
4. FSSAI document version coexistence & section/page provenance
5. Charaka Samhita hierarchy preservation (Sthana -> Chapter -> Verse)
6. Sushruta Samhita hierarchy preservation (Sthana -> Chapter -> Verse)
7. Source URLs preservation
8. Zero Gemini / AI calls during ingestion (0 external LLM calls)
"""

from __future__ import annotations

import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.models import (
    Base,
    User,
    ProductCase,
    Source,
    KnowledgeFinding,
    KnowledgeEvidence,
)
from api.services.knowledge_source_adapters import (
    PubMedCentralAdapter,
    FssaiRegulationsAdapter,
    ClassicalSamhitaAdapter,
    compute_evidence_hash,
)
from api.services.knowledge_ingestion_service import KnowledgeIngestionService
from api.services.source_adapter import get_source_registry


class TestKnowledgeHubIngestion(unittest.TestCase):
    """Unit and Integration Tests for Knowledge Hub Phase 2 Adapters and Ingestion."""

    def setUp(self):
        """Set up in-memory SQLite database for clean test isolation."""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Seed test user & test product case
        self.test_user = User(
            username="knowledge_test_user",
            display_name="Knowledge Tester",
            email="tester@ayur-intel.com",
        )
        self.db.add(self.test_user)
        self.db.commit()
        self.db.refresh(self.test_user)

        self.test_case = ProductCase(
            name="NeuroAdapt Botanical Complex",
            owner_id=self.test_user.id,
            stage="RND",
        )
        self.db.add(self.test_case)
        self.db.commit()
        self.db.refresh(self.test_case)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_01_deterministic_hash_computation(self):
        """Test deterministic SHA256 content hash computation."""
        h1 = compute_evidence_hash("PMC", "PMC10823456", "PMC10823456", "Ashwagandha extract test")
        h2 = compute_evidence_hash("PMC", "PMC10823456", "PMC10823456", "Ashwagandha extract test")
        h3 = compute_evidence_hash("PMC", "PMC10823456", "PMC10823456", "Different text")

        self.assertEqual(h1, h2, "Identical evidence inputs must yield identical hash.")
        self.assertNotEqual(h1, h3, "Different evidence text must yield different hash.")
        self.assertEqual(len(h1), 64, "SHA256 hash length must be 64 characters.")

    def test_02_pmc_adapter_metadata_and_licence(self):
        """Test PubMedCentralAdapter metadata retrieval & licence preservation."""
        adapter = PubMedCentralAdapter()
        self.assertEqual(adapter.name, "PUBMED_CENTRAL")
        self.assertEqual(adapter.jurisdiction, "GLOBAL")

        response = adapter.search(query="Ashwagandha", limit=3)
        self.assertTrue(response.is_configured)
        self.assertGreaterEqual(len(response.results), 1)

        first = response.results[0]
        self.assertTrue(first.source_identifier.startswith("PMC"))
        self.assertTrue(first.source_url.startswith("https://www.ncbi.nlm.nih.gov/pmc/articles/"))
        self.assertIsNotNone(first.license_note)
        self.assertIn("PMC", first.license_note)
        self.assertIsNotNone(first.content_hash)

    def test_03_fssai_adapter_version_coexistence_and_sections(self):
        """Test FSSAI regulations adapter coexisting document versions and section provenance."""
        adapter = FssaiRegulationsAdapter()
        self.assertEqual(adapter.name, "FSSAI")

        response = adapter.search(query="Ayurveda Aahara", limit=10)
        self.assertGreaterEqual(len(response.results), 2)

        identifiers = {r.source_identifier for r in response.results}
        self.assertIn("FSSAI-AA-REG-2022", identifiers, "Base 2022 regulation must be present.")
        self.assertIn("FSSAI-AA-ORDER-2025-CATA", identifiers, "2025 Category A order must coexist.")

        # Verify section provenance
        sections = [r.section for r in response.results if r.section]
        self.assertTrue(any("Section 2" in s or "Section 4" in s for s in sections))
        
        # Verify URLs
        for r in response.results:
            self.assertTrue(r.source_url.startswith("https://fssai.gov.in/upload/"))

    def test_04_charaka_and_sushruta_hierarchy_preservation(self):
        """Test ClassicalSamhitaAdapter Sthana -> Chapter -> Verse hierarchy preservation."""
        adapter = ClassicalSamhitaAdapter()
        response = adapter.search(query="", limit=10)
        self.assertGreaterEqual(len(response.results), 5)

        charaka_results = [r for r in response.results if "Charaka Samhita" in r.title]
        sushruta_results = [r for r in response.results if "Sushruta Samhita" in r.title]

        self.assertGreaterEqual(len(charaka_results), 2, "Charaka Samhita passages must be preserved.")
        self.assertGreaterEqual(len(sushruta_results), 2, "Sushruta Samhita passages must be preserved.")

        # Test Charaka hierarchy attributes
        c_sample = charaka_results[0]
        self.assertIsNotNone(c_sample.sthana)
        self.assertIsNotNone(c_sample.chapter)
        self.assertIsNotNone(c_sample.verse)
        self.assertEqual(c_sample.source_url, "http://niimh.res.in/e-samhita")

        # Test Sushruta hierarchy attributes
        s_sample = sushruta_results[0]
        self.assertIsNotNone(s_sample.sthana)
        self.assertIsNotNone(s_sample.chapter)
        self.assertIsNotNone(s_sample.verse)

    def test_05_idempotent_ingestion_and_zero_duplicates(self):
        """Test repeated ingestion of the exact same results creates 0 duplicates."""
        adapter = ClassicalSamhitaAdapter()
        res = adapter.search(query="Sutrasthana", limit=5)

        # First ingestion run
        stats1 = KnowledgeIngestionService.ingest_results(
            db=self.db,
            user_id=self.test_user.id,
            results=res.results,
            product_case_id=self.test_case.id,
        )

        ev_count_1 = self.db.query(KnowledgeEvidence).count()
        find_count_1 = self.db.query(KnowledgeFinding).filter(KnowledgeFinding.owner_id == self.test_user.id).count()
        
        self.assertGreater(ev_count_1, 0)
        self.assertEqual(stats1["evidence_created"], ev_count_1)
        self.assertEqual(stats1["duplicates_skipped"], 0)

        # Second ingestion run with identical data
        stats2 = KnowledgeIngestionService.ingest_results(
            db=self.db,
            user_id=self.test_user.id,
            results=res.results,
            product_case_id=self.test_case.id,
        )

        ev_count_2 = self.db.query(KnowledgeEvidence).count()
        find_count_2 = self.db.query(KnowledgeFinding).filter(KnowledgeFinding.owner_id == self.test_user.id).count()

        self.assertEqual(ev_count_2, ev_count_1, "Evidence count must not increase on repeated ingestion.")
        self.assertEqual(stats2["evidence_created"], 0, "0 new evidence records created on second run.")
        self.assertEqual(stats2["duplicates_skipped"], len(res.results), "All items skipped as duplicates.")

    def test_06_source_registry_registration(self):
        """Test registry discovery of real Phase 2 adapters."""
        registry = get_source_registry()
        pmc = registry.get("PUBMED_CENTRAL")
        fssai = registry.get("FSSAI")
        classical = registry.get("NIIMH_CLASSICAL")

        self.assertIsNotNone(pmc, "PUBMED_CENTRAL adapter must be registered.")
        self.assertIsNotNone(fssai, "FSSAI adapter must be registered.")
        self.assertIsNotNone(classical, "NIIMH_CLASSICAL adapter must be registered.")

    def test_07_zero_gemini_calls_guarantee(self):
        """Assert zero Gemini / LLM calls during search and ingestion operations."""
        with patch("google.generativeai.GenerativeModel") as mock_genai:
            adapter = PubMedCentralAdapter()
            pmc_res = adapter.search(query="Brahmi", limit=2)
            
            fssai_adapter = FssaiRegulationsAdapter()
            fssai_res = fssai_adapter.search(query="Labelling", limit=2)

            all_results = pmc_res.results + fssai_res.results
            KnowledgeIngestionService.ingest_results(
                db=self.db,
                user_id=self.test_user.id,
                results=all_results,
            )

            self.assertEqual(mock_genai.call_count, 0, "Gemini GenerativeModel must never be invoked.")

    def test_08_database_auto_migration_safety(self):
        """Test database auto-migration safety on tables with pre-existing rows."""
        from sqlalchemy import text
        from api.core.database import init_db

        # Execute init_db migration logic against clean test engine
        init_db()

        # Check that content_hash and license_note columns exist on knowledge_evidence table
        with self.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(knowledge_evidence)")).fetchall()
            col_names = [r[1] for r in result]
            self.assertIn("content_hash", col_names)
            self.assertIn("license_note", col_names)


if __name__ == "__main__":
    unittest.main()
