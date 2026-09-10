"""Automated verification script for AYUR-INTEL Patent Intelligence Phase."""

from __future__ import annotations

import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.models import Base, PatentSearch, ProductCase, User
from api.services.patent_adapter import get_patent_registry
from api.services.patent_service import (
    _calculate_score_and_category,
    _build_unanalyzed_candidates,
    generate_query_plan,
    get_category_from_score,
    get_or_run_patent_intelligence,
)


def run_tests():
    print("==================================================")
    print("RUNNING PATENT INTELLIGENCE SUITE")
    print("==================================================")

    # 1. Test Score Clamping & Boundary Category Assignments
    print("[1] Testing Score Clamping & Category Assignment Boundaries...")
    assert get_category_from_score(0) == "LOW", "FAIL: 0 must be LOW"
    assert get_category_from_score(34) == "LOW", "FAIL: 34 must be LOW"
    assert get_category_from_score(35) == "MODERATE", "FAIL: 35 must be MODERATE"
    assert get_category_from_score(60) == "MODERATE", "FAIL: 60 MUST be MODERATE!"
    assert get_category_from_score(64) == "MODERATE", "FAIL: 64 must be MODERATE"
    assert get_category_from_score(65) == "HIGH", "FAIL: 65 must be HIGH"
    assert get_category_from_score(79) == "HIGH", "FAIL: 79 must be HIGH"
    assert get_category_from_score(80) == "VERY_HIGH", "FAIL: 80 must be VERY_HIGH"
    assert get_category_from_score(100) == "VERY_HIGH", "FAIL: 100 must be VERY_HIGH"
    print("    Score 60 Category ->", get_category_from_score(60))
    print("    All 9 Boundary Score Categories Verified!")

    breakdown_ing_only = {
        "technological_overlap": 10,
        "ingredient_overlap": 100,
        "formulation_process_overlap": 10,
        "claim_concept_overlap": 10,
    }
    score, category = _calculate_score_and_category(breakdown_ing_only)
    print(f"    Ingredient Match Only -> Score: {score}, Category: {category}")
    assert category != "VERY_HIGH", "FAIL: Ingredient match alone produced VERY_HIGH score!"
    assert score <= 79, "FAIL: Ingredient match alone score was not clamped below 80!"

    breakdown_full = {
        "technological_overlap": 90,
        "ingredient_overlap": 90,
        "formulation_process_overlap": 85,
        "claim_concept_overlap": 80,
    }
    score_full, category_full = _calculate_score_and_category(breakdown_full)
    print(f"    Full Overlap -> Score: {score_full}, Category: {category_full}")
    assert category_full == "VERY_HIGH", "FAIL: High multi-dimensional overlap should produce VERY_HIGH!"
    print("    PASSED!")

    # 2. Test Patent Registry, Provenance & Identifier Separation
    print("[2] Testing Patent Adapter Registry, Provenance & Identifier Normalization...")
    registry = get_patent_registry()
    adapters = registry.get_all()
    print(f"    Registered Adapters: {[a.name for a in adapters]}")
    primary_adapter = registry.get_adapter("EUROPE_PMC_PATENTS")
    assert primary_adapter is not None, "FAIL: EUROPE_PMC_PATENTS adapter missing!"
    assert primary_adapter.name == "EUROPE_PMC_PATENTS", "FAIL: Primary adapter name invalid!"
    assert primary_adapter.authority == "Europe PMC Patent Index", "FAIL: Primary adapter authority invalid!"
    print("    Truthful Provenance Verified!")

    # Test Identifier Separation on adapter output
    pmc_results = primary_adapter.search(query="Ashwagandha").results
    if len(pmc_results) > 0:
        sample_res = pmc_results[0]
        print(f"    Sample Provider Record ID: {sample_res.provider_record_id}")
        print(f"    Sample Publication Number: {sample_res.publication_number}")
        print(f"    Sample Source URL: {sample_res.source_url}")
        assert sample_res.provider_record_id is not None, "FAIL: provider_record_id must be populated!"
        if sample_res.publication_number is None:
            assert "europepmc.org" in sample_res.source_url, "FAIL: Source URL should default to Europe PMC when publication_number is None!"
            assert "patents.google.com" not in sample_res.source_url, "FAIL: Must not build unverified Google Patents URL!"
            print("    Identifier Separation & Safe Verification URL Verified!")

    # 3. Test Gemini Failure Semantics (No Heuristic Score Fallback)
    print("[3] Testing Gemini Failure Semantics...")
    dummy_item = {
        "result": primary_adapter.search(query="Withania somnifera").results[0] if len(primary_adapter.search(query="Withania somnifera").results) > 0 else None,
        "ing_matches": ["withania"],
        "matched_queries": ["Withania somnifera"],
    }
    if dummy_item["result"]:
        unanalyzed = _build_unanalyzed_candidates([dummy_item])
        first_un = unanalyzed[0]
        print(f"    Gemini Failure Record -> Score: {first_un['relevance_score']}, Level: {first_un['relevance_level']}")
        assert first_un["relevance_score"] is None, "FAIL: Score must be None when Gemini fails!"
        assert first_un["relevance_level"] == "NOT_ANALYZED", "FAIL: Level must be NOT_ANALYZED when Gemini fails!"
        assert first_un["result"] is not None, "FAIL: Patent metadata must be retained!"
        assert "temporarily unavailable" in first_un["why_relevant"], "FAIL: Explanation missing unavailability disclosure!"
        print("    Gemini Failure Semantics Verified!")

    # 4. Test DB Persistence & True GET-First Lifecycle
    print("[4] Testing DB Persistence & True GET-First Lifecycle...")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create dummy user & case
    user = User(username="testuser", display_name="Test User", email="test@ayur-intel.com")
    db.add(user)
    db.commit()
    db.refresh(user)

    case = ProductCase(
        public_id="case_test_123",
        owner_id=user.id,
        name="Ashwagandha Skin Rejuvenation Gel",
        form="Topical Gel",
        formulation="Gel Matrix with Supercritical Extract",
        process="Hydro-alcoholic extraction and cold mixing",
        ingredients='[{"name": "Ashwagandha (Withania somnifera)"}, {"name": "Turmeric (Curcuma longa)"}]',
        intended_use="Skin aging and inflammation relief",
        claims='["Synergistic skin elasticity enhancement"]'
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Test Query Plan Generation
    print("    Generating query plan...")
    plan = generate_query_plan(case, [])
    print(f"    Query Plan Count: {len(plan)}")
    assert 5 <= len(plan) <= 10, f"FAIL: Query plan length {len(plan)} not between 5 and 10!"

    # Fresh Case GET -> Must NOT trigger provider or create search row
    print("    Testing Fresh Case GET (Zero search rows created)...")
    fresh_res = get_or_run_patent_intelligence(db=db, owner=user, case_public_id=case.public_id, force_rerun=False)
    assert fresh_res["has_searched"] is False, "FAIL: Fresh case should have has_searched == False!"
    assert fresh_res["search_id"] is None, "FAIL: Fresh case should have search_id None!"
    assert db.query(PatentSearch).count() == 0, "FAIL: Fresh GET created a PatentSearch row!"
    print("    Fresh Case GET Verified (0 Search Rows)!")

    # Explicit User Search Trigger -> Creates 1 search row
    print("    Triggering explicit search run...")
    res1 = get_or_run_patent_intelligence(db=db, owner=user, case_public_id=case.public_id, force_rerun=True)
    assert res1 is not None and res1["has_searched"] is True, "FAIL: Search failed!"
    assert db.query(PatentSearch).count() == 1, "FAIL: Explicit search should create exactly 1 PatentSearch row!"
    first_search_id = res1["search_id"]
    print(f"    Search Public ID: {first_search_id}")
    print(f"    Total Patents Retrieved: {res1['summary_metrics']['total_retrieved']}")

    if len(res1["patents"]) > 0:
        first_patent = res1["patents"][0]["patent"]
        print(f"    Top Patent Provider ID: {first_patent['provider_record_id']} | Canonical Pub Num: {first_patent['publication_number']}")
        assert first_patent["provider_record_id"] is not None, "FAIL: provider_record_id must be populated!"
        assert first_patent["source_name"] == "EUROPE_PMC_PATENTS", "FAIL: Source name must be EUROPE_PMC_PATENTS!"
        if first_patent["publication_number"] is None:
            assert "europepmc.org" in first_patent["open_patent_url"], "FAIL: Missing canonical pub num must default to Europe PMC URL!"
            print("    Europe PMC URL fallback verified for non-canonical provider ID!")
        else:
            assert "patents.google.com" in first_patent["open_patent_url"], "FAIL: Canonical pub num must build Google Patents URL!"
            print("    Google Patents URL verified for canonical publication number!")

    # Test GET Reopen -> 0 new search rows created
    print("    Testing Reopen Module GET (0 new search rows)...")
    res2 = get_or_run_patent_intelligence(db=db, owner=user, case_public_id=case.public_id, force_rerun=False)
    assert res2["search_id"] == first_search_id, "FAIL: GET-First should return existing search!"
    assert db.query(PatentSearch).count() == 1, "FAIL: Reopen created a new search row!"
    print("    GET-First Reopen Verified!")

    # Test Explicit Force Re-Run -> 1 new search row created
    print("    Testing Explicit Force Re-Run...")
    res3 = get_or_run_patent_intelligence(db=db, owner=user, case_public_id=case.public_id, force_rerun=True)
    assert res3["search_id"] != first_search_id, "FAIL: Force re-run should produce a new search ID!"
    assert db.query(PatentSearch).count() == 2, "FAIL: Force re-run should create a 2nd search row!"
    print("    Force Re-Run Verified!")

    print("==================================================")
    print("ALL PATENT INTELLIGENCE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
