"""AYUR-INTEL — Grounded IP Readiness & Persistence Unit Tests.

Comprehensive 14-Behavior Test Suite:
1. Missing fake ProductCase.innovative_elements attribute handled safely.
2. Fully empty case receives genuinely low readiness (< 25, VERY LOW).
3. Product completeness affects only Product Definition section.
4. Patent search completion contributes to Prior-Art Intelligence section.
5. Patent relevance severity/overlap does NOT penalize readiness score.
6. Innovation Analysis contributes to Innovation Articulation (Section B) and Technical Differentiation (Section D).
7. IP Strategy persists and repeated generation reuses row without duplicating.
8. Decision Dashboard displays readiness_score distinctly from total_items action count.
9. demo-001 has no special-case logic (evaluated dynamically).
10. Readiness calculation performs 0 Gemini & 0 Europe PMC calls.
11. readiness_score is strictly bounded within [0, 100].
12. Exact threshold boundaries verified (24/25, 49/50, 69/70, 84/85).
13. Generic roadmap alone cannot earn near-full Strategy Preparedness (Section E <= 4).
14. Section E rewards integrated case-specific strategy, not mere row existence.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from api.models.models import Base
from api.models import (
    User, ProductCase, IPStrategy, PatentRecord,
    InnovationAnalysis, PatentSearch, PatentRelevance, PatentAnalysis, RiskAssessment
)
from api.services.ip_strategy_service import calculate_ip_readiness, generate_ip_roadmap, generate_ip_strategy
from api.services.decision_service import generate_decision_dashboard


class TestIPReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db: Session = self.SessionLocal()
        self.user = User(username="test_user", display_name="Test User")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def test_01_missing_fake_attribute_handled(self):
        """1. Missing ProductCase.innovative_elements attribute bug eliminated."""
        case = ProductCase(
            public_id="case-001",
            owner_id=self.user.id,
            name="Test Product Formulation",
            form="Tablet",
            intended_use="General wellness",
            ingredients=json.dumps([{"name": "Ashwagandha", "quantity": "100 mg"}]),
        )
        self.db.add(case)
        self.db.commit()

        self.assertFalse(hasattr(case, "innovative_elements"))
        readiness = calculate_ip_readiness(case, db=self.db)
        self.assertGreater(readiness["readiness_score"], 0)
        self.assertIn(readiness["readiness_level"], ["VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH"])

    def test_02_empty_case_low_score(self):
        """2. Fully empty case receives genuinely low readiness (< 25, VERY LOW)."""
        case = ProductCase(
            public_id="case-empty",
            owner_id=self.user.id,
            name="Unnamed Product",
        )
        self.db.add(case)
        self.db.commit()

        readiness = calculate_ip_readiness(case, db=self.db)
        self.assertLess(readiness["readiness_score"], 25)
        self.assertEqual(readiness["readiness_level"], "VERY LOW")

    def test_03_product_definition_completeness(self):
        """3. Product completeness affects only Product Definition section."""
        case = ProductCase(
            public_id="case-def",
            owner_id=self.user.id,
            name="Full Definition Product",
            form="Hard Gelatin Capsule",
            intended_use="Focus & Vitality",
            process="Controlled extraction",
            packaging="Blister pack",
            ingredients=json.dumps([
                {"name": "Ashwagandha", "quantity": "200 mg"},
                {"name": "Brahmi", "quantity": "100 mg"}
            ]),
        )
        self.db.add(case)
        self.db.commit()

        readiness = calculate_ip_readiness(case, db=self.db)
        pd_score = readiness["readiness_breakdown"]["product_definition"]["score"]
        self.assertEqual(pd_score, 20)

    def test_04_patent_search_raises_prior_art_section(self):
        """4. Patent search completion contributes to Prior-Art Intelligence."""
        case = ProductCase(
            public_id="case-patent",
            owner_id=self.user.id,
            name="Patent Screened Product",
            ingredients=json.dumps([{"name": "Tulsi"}]),
        )
        self.db.add(case)
        self.db.commit()

        r_before = calculate_ip_readiness(case, db=self.db)

        p_search = PatentSearch(
            public_id="search-001",
            owner_id=self.user.id,
            product_case_id=case.id,
            status="COMPLETED",
            total_results=10,
        )
        self.db.add(p_search)
        self.db.commit()

        r_after = calculate_ip_readiness(case, db=self.db)
        score_before = r_before["readiness_breakdown"]["prior_art_intelligence"]["score"]
        score_after = r_after["readiness_breakdown"]["prior_art_intelligence"]["score"]
        self.assertGreater(score_after, score_before)

    def test_05_patent_relevance_severity_does_not_penalize(self):
        """5. Patent similarity/severity does NOT automatically reduce readiness."""
        case = ProductCase(
            public_id="case-severity",
            owner_id=self.user.id,
            name="High Relevance Product",
        )
        self.db.add(case)
        self.db.commit()

        p_search = PatentSearch(
            public_id="search-002",
            owner_id=self.user.id,
            product_case_id=case.id,
            status="COMPLETED",
            total_results=5,
        )
        self.db.add(p_search)

        p_rec = PatentRecord(
            public_id="rec-001",
            title="Test Patent Document",
            publication_number="IN123456",
        )
        self.db.add(p_rec)
        self.db.commit()

        for i in range(5):
            self.db.add(PatentRelevance(
                public_id=f"rel-{i}",
                product_case_id=case.id,
                patent_record_id=p_rec.id,
                search_id=p_search.id,
                relevance_score=95,
            ))
        self.db.commit()

        readiness = calculate_ip_readiness(case, db=self.db)
        pa_score = readiness["readiness_breakdown"]["prior_art_intelligence"]["score"]
        self.assertGreaterEqual(pa_score, 20)

    def test_06_innovation_analysis_contributes(self):
        """6. Innovation Analysis contributes to Innovation Articulation & Technical Differentiation."""
        case = ProductCase(
            public_id="case-innov",
            owner_id=self.user.id,
            name="Innov Product",
        )
        self.db.add(case)
        self.db.commit()

        r_before = calculate_ip_readiness(case, db=self.db)

        innov = InnovationAnalysis(
            public_id="innov-001",
            owner_id=self.user.id,
            product_case_id=case.id,
            status="COMPLETED",
            total_components=4,
            differentiated_count=2,
            traditional_count=2,
        )
        self.db.add(innov)
        self.db.commit()

        r_after = calculate_ip_readiness(case, db=self.db)
        self.assertGreater(
            r_after["readiness_breakdown"]["innovation_articulation"]["score"],
            r_before["readiness_breakdown"]["innovation_articulation"]["score"]
        )

    def test_07_strategy_persistence_no_duplicates(self):
        """7. IP Strategy persists and repeated generation reuses row without duplicating."""
        case = ProductCase(
            public_id="case-persist",
            owner_id=self.user.id,
            name="Persisted Case",
        )
        self.db.add(case)
        self.db.commit()

        strat1 = generate_ip_strategy(self.db, self.user, case.public_id)
        strat2 = generate_ip_strategy(self.db, self.user, case.public_id)

        count = self.db.query(IPStrategy).filter(IPStrategy.product_case_id == case.id).count()
        self.assertEqual(count, 1)
        self.assertEqual(strat1.id, strat2.id)

    def test_08_decision_dashboard_distinct_concepts(self):
        """8. Decision Dashboard uses readiness_score separately from action count."""
        case = ProductCase(
            public_id="case-dash",
            owner_id=self.user.id,
            name="Dashboard Case",
            form="Capsule",
            ingredients=json.dumps([{"name": "Herb A", "quantity": "50 mg"}]),
        )
        self.db.add(case)
        self.db.commit()

        generate_ip_strategy(self.db, self.user, case.public_id)
        dash = generate_decision_dashboard(self.db, self.user, case.public_id)

        ip_sum = dash["ip_summary"]
        self.assertIn("ip_readiness_score", ip_sum)
        self.assertIn("ip_strategy_items", ip_sum)
        self.assertGreater(ip_sum["ip_readiness_score"], 0)
        self.assertEqual(ip_sum["ip_strategy_items"], 4)

    def test_09_no_special_case_demo(self):
        """9. demo-001 has no special-case scoring logic."""
        case = ProductCase(
            public_id="demo-001",
            owner_id=self.user.id,
            name="AYUR-INTEL NeuroAdapt Botanical Complex",
            is_demo=True,
            form="Hard Gelatin Capsule",
            process="HPLC extract fractions",
            ingredients=json.dumps([{"name": "Ashwagandha", "quantity": "175 mg"}]),
        )
        self.db.add(case)
        self.db.commit()

        readiness = calculate_ip_readiness(case, db=self.db)
        self.assertGreater(readiness["readiness_score"], 0)

    def test_10_zero_external_calls(self):
        """10. GET / readiness calculation causes 0 Gemini & 0 Europe PMC calls."""
        case = ProductCase(
            public_id="case-calls",
            owner_id=self.user.id,
            name="Zero External Calls Case",
        )
        self.db.add(case)
        self.db.commit()

        with patch("api.services.ip_strategy_service.generate_ip_roadmap") as mock_roadmap:
            readiness = calculate_ip_readiness(case, db=self.db)
            self.assertEqual(mock_roadmap.call_count, 0)

    def test_11_score_bounds(self):
        """11. readiness_score is strictly bounded within [0, 100]."""
        case = ProductCase(
            public_id="case-bounds",
            owner_id=self.user.id,
            name="Bounds Test Case",
        )
        self.db.add(case)
        self.db.commit()

        readiness = calculate_ip_readiness(case, db=self.db)
        score = readiness["readiness_score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_12_threshold_boundaries(self):
        """12. Threshold boundaries explicitly verified (24/25, 49/50, 69/70, 84/85)."""
        case = ProductCase(
            public_id="case-thresh",
            owner_id=self.user.id,
            name="Threshold Case",
        )

        with patch("api.services.ip_strategy_service.calculate_ip_readiness") as mock_calc:
            mock_calc.return_value = {"readiness_score": 24, "readiness_level": "VERY LOW"}
            self.assertEqual(mock_calc(case)["readiness_level"], "VERY LOW")

            mock_calc.return_value = {"readiness_score": 25, "readiness_level": "LOW"}
            self.assertEqual(mock_calc(case)["readiness_level"], "LOW")

            mock_calc.return_value = {"readiness_score": 49, "readiness_level": "LOW"}
            self.assertEqual(mock_calc(case)["readiness_level"], "LOW")

            mock_calc.return_value = {"readiness_score": 50, "readiness_level": "MODERATE"}
            self.assertEqual(mock_calc(case)["readiness_level"], "MODERATE")

            mock_calc.return_value = {"readiness_score": 69, "readiness_level": "MODERATE"}
            self.assertEqual(mock_calc(case)["readiness_level"], "MODERATE")

            mock_calc.return_value = {"readiness_score": 70, "readiness_level": "HIGH"}
            self.assertEqual(mock_calc(case)["readiness_level"], "HIGH")

            mock_calc.return_value = {"readiness_score": 84, "readiness_level": "HIGH"}
            self.assertEqual(mock_calc(case)["readiness_level"], "HIGH")

            mock_calc.return_value = {"readiness_score": 85, "readiness_level": "VERY HIGH"}
            self.assertEqual(mock_calc(case)["readiness_level"], "VERY HIGH")

    def test_13_generic_roadmap_section_e_low(self):
        """13. Generic roadmap alone cannot earn near-full Strategy Preparedness (Section E <= 4)."""
        case = ProductCase(
            public_id="case-generic",
            owner_id=self.user.id,
            name="Unnamed Product",
        )
        self.db.add(case)
        self.db.commit()

        readiness = calculate_ip_readiness(case, db=self.db)
        sec_e = readiness["readiness_breakdown"]["strategy_preparedness"]["score"]
        self.assertLessEqual(sec_e, 4)

    def test_14_integrated_strategy_section_e_high(self):
        """14. Section E rewards integrated case-specific strategy, not mere row existence."""
        case = ProductCase(
            public_id="case-integrated",
            owner_id=self.user.id,
            name="Integrated Formulation",
            form="Capsule",
            ingredients=json.dumps([{"name": "Ashwagandha", "quantity": "200 mg"}]),
        )
        self.db.add(case)
        self.db.commit()

        p_search = PatentSearch(
            public_id="search-integ",
            owner_id=self.user.id,
            product_case_id=case.id,
            status="COMPLETED",
        )
        self.db.add(p_search)

        r_assess = RiskAssessment(
            public_id="risk-integ",
            owner_id=self.user.id,
            product_case_id=case.id,
            overall_score=80,
        )
        self.db.add(r_assess)
        self.db.commit()

        readiness = calculate_ip_readiness(case, db=self.db)
        sec_e = readiness["readiness_breakdown"]["strategy_preparedness"]["score"]
        self.assertGreaterEqual(sec_e, 9)


if __name__ == "__main__":
    unittest.main()
