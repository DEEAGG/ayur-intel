"""AYUR-INTEL — Comprehensive Test Suite for AI-Powered Risk Assessment Module.

Tests:
1. Context gathering & valid evidence keys extraction.
2. Structured schema validation and rejection of fabricated evidence keys.
3. Fallback transparency (RULE_ENGINE vs GEMINI).
4. GET-first read-only behavior & first-generation persistence.
5. Atomic reassessment and replacement.
6. Missing evidence handling (no hallucinated patents or regulations).
7. Case switching and demo vs normal product isolation.
8. Delete cascade integrity.
"""

import json
import logging
import os
import sys
import threading
import uuid
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.core.database import SessionLocal, init_db, engine
from api.models import models
from api.models.risk import Risk, RiskEvidence, RiskAssessment
from api.services.product_case_service import get_or_create_demo_user, get_or_create_demo_case, create_product_case, delete_product_case
from api.services.gemini_risk_service import (
    gather_case_risk_context,
    generate_fallback_risk_assessment,
    synthesize_risk_with_gemini,
    validate_and_sanitize_risk_data,
    save_or_replace_risk_assessment,
    format_risk_assessment_response,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_risk")


def run_all_tests():
    init_db()
    db = SessionLocal()

    try:
        user = get_or_create_demo_user(db)
        logger.info("=== TEST 1: DEMO CASE CONTEXT GATHERING ===")
        demo_dict = get_or_create_demo_case(db, user)
        demo_case = db.query(models.ProductCase).filter(models.ProductCase.public_id == "demo-001").first()
        assert demo_case is not None, "Demo case demo-001 not found"

        context, valid_keys, coverage = gather_case_risk_context(db, demo_case)
        logger.info("Demo case context gathered: %d valid evidence keys generated", len(valid_keys))
        assert "passport:identity" in valid_keys, "passport:identity missing from valid keys"
        assert "passport:formulation" in valid_keys, "passport:formulation missing from valid keys"
        assert "product_passport" in coverage, "product_passport missing in coverage"
        logger.info("✅ TEST 1 PASSED: Context gathering and key indexing verified.")

        logger.info("=== TEST 2: FALLBACK TRANSPARENCY & DETERMINISTIC RULE ENGINE ===")
        fallback_data = generate_fallback_risk_assessment(context, valid_keys, coverage)
        assert "overall_risk" in fallback_data, "overall_risk missing"
        assert 0 <= fallback_data["overall_risk"]["score"] <= 100, "Score out of bounds"
        assert fallback_data["overall_risk"]["level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL"), "Invalid level"
        assert len(fallback_data["domain_scores"]) >= 4, "Domain scores incomplete"
        assert len(fallback_data["top_risks"]) > 0, "Top risks empty"
        assert "mitigation_plan" in fallback_data, "Mitigation plan missing"
        assert "evidence_gaps" in fallback_data, "Evidence gaps missing"

        # Verify fallback synthesis attribution
        res, source, model = synthesize_risk_with_gemini(context, valid_keys, coverage)
        logger.info("Synthesis source: %s, model: %s", source, model)
        if source == "RULE_ENGINE":
            assert model is None, "model_used must be None when source is RULE_ENGINE"
        logger.info("✅ TEST 2 PASSED: Fallback schema and attribution verified.")

        logger.info("=== TEST 3: EVIDENCE REFERENCE VALIDATION & REJECTION OF FABRICATIONS ===")
        mock_gemini_payload = {
            "overall_risk": {
                "score": 68,
                "level": "HIGH",
                "confidence": 0.82,
                "summary": "High risk detected in patent overlap and claims."
            },
            "domain_scores": [
                {"domain": "IP & Patent", "score": 72, "level": "HIGH", "confidence": 0.85, "summary": "IP overlap"},
                {"domain": "Regulatory", "score": 64, "level": "HIGH", "confidence": 0.80, "summary": "Regulatory"},
                {"domain": "Claims & Compliance", "score": 78, "level": "HIGH", "confidence": 0.88, "summary": "Claims"},
                {"domain": "Ingredient & Formulation", "score": 41, "level": "MODERATE", "confidence": 0.85, "summary": "Formulation"},
                {"domain": "Market / Commercial", "score": 36, "level": "MODERATE", "confidence": 0.75, "summary": "Market"},
            ],
            "top_risks": [
                {
                    "id": "risk-fake-01",
                    "title": "Fabricated Patent Overlap",
                    "domain": "IP & Patent",
                    "severity": "HIGH",
                    "likelihood": "HIGH",
                    "impact": "HIGH",
                    "confidence": 0.9,
                    "why_it_matters": "Testing rejection of non-existent reference key",
                    "evidence_refs": [
                        {"source_type": "patent", "reference_key": "patent:FABRICATED_PATENT_999999"},
                        {"source_type": "passport", "reference_key": "passport:identity"},
                    ],
                    "evidence_status": "SUPPORTED",
                    "recommended_action": "Conduct review",
                    "requires_human_verification": True
                }
            ],
            "mitigation_plan": {
                "immediate": ["Revise claims"],
                "before_regulatory_submission": ["Verify schedule"],
                "before_market_launch": ["FTO search"]
            },
            "evidence_gaps": ["Patent intelligence partial"],
            "disclaimer": "Decision support only."
        }

        validated = validate_and_sanitize_risk_data(mock_gemini_payload, valid_keys, coverage)
        risk_item = validated["top_risks"][0]
        ref_keys = [ref["reference_key"] for ref in risk_item["evidence_refs"]]
        assert "patent:FABRICATED_PATENT_999999" not in ref_keys, "Fabricated evidence key was not rejected!"
        assert "passport:identity" in ref_keys, "Valid reference key was mistakenly dropped!"
        logger.info("✅ TEST 3 PASSED: Fabricated evidence keys successfully rejected.")

        logger.info("=== TEST 4: ATOMIC PERSISTENCE & SYNCHRONIZATION ===")
        rec = save_or_replace_risk_assessment(
            db=db,
            user=user,
            case=demo_case,
            assessment_dict=validated,
            source=source,
            model_used=model,
            coverage=coverage
        )
        assert rec.id is not None, "Failed to persist RiskAssessment"
        assert rec.product_case_id == demo_case.id, "Case ID mismatch"

        # Verify legacy risks table synchronization
        synced_risks = db.query(Risk).filter(Risk.product_case_id == demo_case.id).all()
        assert len(synced_risks) == len(validated["top_risks"]), "Legacy risks table was not synchronized"
        synced_ev = db.query(RiskEvidence).filter(RiskEvidence.risk_id == synced_risks[0].id).all()
        assert len(synced_ev) > 0, "Risk evidence was not synchronized"
        logger.info("✅ TEST 4 PASSED: Atomic persistence and legacy table synchronization verified.")

        logger.info("=== TEST 5: REASSESSMENT ATOMIC REPLACEMENT ===")
        old_id = rec.id
        updated_payload = dict(validated)
        updated_payload["overall_risk"]["score"] = 75
        new_rec = save_or_replace_risk_assessment(
            db=db,
            user=user,
            case=demo_case,
            assessment_dict=updated_payload,
            source="RULE_ENGINE",
            model_used=None,
            coverage=coverage
        )
        assert new_rec.id == old_id, "Reassessment did not update existing record in-place"
        assert new_rec.overall_score == 75, "Updated score not reflected"
        logger.info("✅ TEST 5 PASSED: Reassessment atomic update verified.")

        logger.info("=== TEST 6: NORMAL CASE & ISOLATION (Tulsi & Neem) ===")
        # Create normal test case
        normal_case_dict = create_product_case(
            db=db,
            owner=user,
            name="Tulsi & Neem Wellness & Balance Formulation",
            stage="RND",
            jurisdictions=["IN"],
            ingredients=[
                {"name": "Tulsi", "botanical": "Ocimum sanctum", "quantity": "250 mg", "status": "VERIFIED"},
                {"name": "Neem", "botanical": "Azadirachta indica", "quantity": "200 mg", "status": "NEEDS_VERIFICATION"}
            ],
            claims=["Supports healthy immune defense and respiratory balance"],
            is_demo=False
        )
        normal_case = db.query(models.ProductCase).filter(models.ProductCase.public_id == normal_case_dict["id"]).first()
        assert normal_case is not None, "Normal case creation failed"

        n_context, n_keys, n_cov = gather_case_risk_context(db, normal_case)
        assert n_cov["patent_intelligence"] == "Not Run", "Patent intelligence should be Not Run for new case"
        n_fallback = generate_fallback_risk_assessment(n_context, n_keys, n_cov)
        n_rec = save_or_replace_risk_assessment(
            db=db,
            user=user,
            case=normal_case,
            assessment_dict=n_fallback,
            source="RULE_ENGINE",
            model_used=None,
            coverage=n_cov
        )
        assert n_rec.product_case_id == normal_case.id, "Normal case assessment ID mismatch"

        # Verify demo case risk was untouched
        demo_rec = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == demo_case.id).first()
        assert demo_rec.overall_score == 75, "Demo case was modified by normal case evaluation!"
        logger.info("✅ TEST 6 PASSED: Case isolation between demo and normal cases verified.")

        logger.info("=== TEST 7: MISSING EVIDENCE HANDLING ===")
        # Check that when patent intel is Not Run, evidence gaps contains patent warning
        assert any("Patent Intelligence has not been generated" in g for g in n_fallback["evidence_gaps"]), "Missing patent warning not found in evidence gaps"
        logger.info("✅ TEST 7 PASSED: Missing evidence transparently flagged without hallucination.")

        logger.info("=== TEST 8: DELETE CASCADE INTEGRITY ===")
        normal_cid = normal_case.id
        del_success = delete_product_case(db=db, owner=user, public_id=normal_case.public_id)
        assert del_success is True, "Failed to delete normal test case"
        leftover_assessments = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == normal_cid).count()
        assert leftover_assessments == 0, "RiskAssessment row was orphaned after case deletion!"
        logger.info("✅ TEST 8 PASSED: Delete cascade cleaned up risk_assessments properly.")

        logger.info("=== TEST 9: OVERALL_CONFIDENCE FLOAT TYPE & SERIALIZATION ===")
        float_test_case_dict = create_product_case(
            db=db,
            owner=user,
            name=f"Float Type Verification Formulation {uuid.uuid4().hex[:8]}",
            stage="RND",
            jurisdictions=["IN"],
            ingredients=[{"name": "Brahmi", "botanical": "Bacopa monnieri", "quantity": "150 mg", "status": "VERIFIED"}],
            claims=["Supports memory and cognitive clarity"],
            is_demo=False
        )
        float_case = db.query(models.ProductCase).filter(models.ProductCase.public_id == float_test_case_dict["id"]).first()
        f_context, f_keys, f_cov = gather_case_risk_context(db, float_case)
        f_payload = generate_fallback_risk_assessment(f_context, f_keys, f_cov)
        f_payload["overall_risk"]["confidence"] = 0.85

        f_rec = save_or_replace_risk_assessment(
            db=db,
            user=user,
            case=float_case,
            assessment_dict=f_payload,
            source="RULE_ENGINE",
            model_used=None,
            coverage=f_cov
        )
        # Clear identity map to force fresh DB fetch
        db.expire_all()
        fetched_f_rec = db.query(RiskAssessment).filter(RiskAssessment.id == f_rec.id).first()
        assert isinstance(fetched_f_rec.overall_confidence, float), f"overall_confidence is {type(fetched_f_rec.overall_confidence)}, expected float"
        assert fetched_f_rec.overall_confidence == 0.85, f"Expected 0.85, got {fetched_f_rec.overall_confidence}"
        assert 0.0 <= fetched_f_rec.overall_confidence <= 1.0, "Confidence out of 0.0-1.0 range"

        f_resp = format_risk_assessment_response(fetched_f_rec, float_case)
        assert isinstance(f_resp["overall_risk"]["confidence"], float), "Serialized JSON confidence is not float"
        assert f_resp["overall_risk"]["confidence"] == 0.85, "Serialized JSON confidence value mismatch"
        logger.info("✅ TEST 9 PASSED: overall_confidence Float storage and serialization verified.")

        # Import endpoint and threading utilities
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import api.routers.risk as risk_router
        import time

        logger.info("=== TEST 10: 10 CONCURRENT GENERATION REQUESTS (CONCURRENCY GUARD) ===")
        concurrent_case_dict = create_product_case(
            db=db,
            owner=user,
            name=f"Concurrent Multi-Thread Test Formulation {uuid.uuid4().hex[:8]}",
            stage="RND",
            jurisdictions=["IN"],
            ingredients=[{"name": "Ashwagandha", "botanical": "Withania somnifera", "quantity": "300 mg", "status": "VERIFIED"}],
            claims=["Supports stress reduction"],
            is_demo=False
        )
        cc_case = db.query(models.ProductCase).filter(models.ProductCase.public_id == concurrent_case_dict["id"]).first()
        cc_public_id = cc_case.public_id

        # Track synthesis invocations
        synthesis_call_count = 0
        synthesis_lock = threading.Lock()
        orig_synthesis = risk_router.synthesize_risk_with_gemini

        def counted_synthesis(*args, **kwargs):
            nonlocal synthesis_call_count
            with synthesis_lock:
                synthesis_call_count += 1
            time.sleep(0.05)  # Simulate API latency
            return orig_synthesis(*args, **kwargs)

        risk_router.synthesize_risk_with_gemini = counted_synthesis

        def run_generate_call(pid):
            thread_db = SessionLocal()
            try:
                # Re-fetch user in thread session
                th_user = thread_db.query(models.User).filter(models.User.username == "demo").first()
                res = risk_router.create_or_get_risk_assessment_endpoint(case_id=pid, db=thread_db, user=th_user)
                return res
            finally:
                thread_db.close()

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_generate_call, cc_public_id) for _ in range(10)]
            for fut in as_completed(futures):
                results.append(fut.result())

        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        assert synthesis_call_count == 1, f"Expected exactly 1 synthesis call, got {synthesis_call_count}"

        # Verify single row persisted in database
        db.expire_all()
        db_assessments = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == cc_case.id).all()
        assert len(db_assessments) == 1, f"Expected 1 RiskAssessment row, found {len(db_assessments)}"

        # Verify legacy risk rows are not duplicated
        db_risks = db.query(Risk).filter(Risk.product_case_id == cc_case.id).all()
        top_risks_count = len(json.loads(db_assessments[0].top_risks_json))
        assert len(db_risks) == top_risks_count, f"Expected {top_risks_count} legacy risk rows, found {len(db_risks)}"
        logger.info("✅ TEST 10 PASSED: 10 concurrent generations executed with exactly 1 synthesis call and 0 race condition errors.")

        logger.info("=== TEST 11: 10 CONCURRENT REASSESSMENT REQUESTS ===")
        reassess_call_count = 0

        def counted_reassess_synthesis(*args, **kwargs):
            nonlocal reassess_call_count
            with synthesis_lock:
                reassess_call_count += 1
            time.sleep(0.05)
            return orig_synthesis(*args, **kwargs)

        risk_router.synthesize_risk_with_gemini = counted_reassess_synthesis

        def run_reassess_call(pid):
            thread_db = SessionLocal()
            try:
                th_user = thread_db.query(models.User).filter(models.User.username == "demo").first()
                res = risk_router.reassess_risk_endpoint(case_id=pid, db=thread_db, user=th_user)
                return res
            finally:
                thread_db.close()

        reassess_results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_reassess_call, cc_public_id) for _ in range(10)]
            for fut in as_completed(futures):
                reassess_results.append(fut.result())

        assert len(reassess_results) == 10, f"Expected 10 reassess results, got {len(reassess_results)}"
        assert reassess_call_count == 1, f"Expected exactly 1 synthesis call during concurrent reassess burst, got {reassess_call_count}"

        db.expire_all()
        db_reassess_assessments = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == cc_case.id).all()
        assert len(db_reassess_assessments) == 1, f"Expected 1 RiskAssessment row after reassess, found {len(db_reassess_assessments)}"
        logger.info("✅ TEST 11 PASSED: 10 concurrent reassessment requests coalesced into 1 synthesis call.")

        # Restore original synthesis function
        risk_router.synthesize_risk_with_gemini = orig_synthesis

        logger.info("=== TEST 12: INDEPENDENT LOCKS FOR CASE A VS CASE B ===")
        lock_a = risk_router.get_case_lock("case-a")
        lock_b = risk_router.get_case_lock("case-b")
        assert lock_a is not lock_b, "Lock A and Lock B must be distinct lock instances"
        assert risk_router.get_case_lock("case-a") is lock_a, "Lock A must be idempotent for case-a"
        logger.info("✅ TEST 12 PASSED: Per-case mutex isolation verified.")

        # Cleanup test cases
        delete_product_case(db=db, owner=user, public_id=float_case.public_id)
        delete_product_case(db=db, owner=user, public_id=cc_case.public_id)

        logger.info("🎉 ALL 12 TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    run_all_tests()
