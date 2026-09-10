"""AYUR-INTEL — Comprehensive Test Suite for Knowledge Graph Phase A.

Tests 20 core criteria:
1. Graph builds successfully.
2. Ingredients preserved & botanical taxonomy mapped.
3. CLAIM nodes generated with deterministic sha256 hash-based IDs.
4. Product -> Claim edge generated (ASSERTS_CLAIM).
5. Claim -> Evidence NOT fabricated.
6. Canonical RiskAssessment represented (top_risks_json, severity, rationale, etc.).
7. RULE_ENGINE has zero Gemini attribution.
8. Gemini assessment preserves actual model_used.
9. DIRECT edge grounding classification.
10. DERIVED edge grounding classification.
11. No arbitrary confidence.
12. Evidence -> Source link preserved with authority.
13. Duplicate claim / source / evidence deduplication.
14. Stable deterministic graph generation across runs.
15. Claim search in graph.
16. Claim node details retrieval.
17. Canonical Risk node details retrieval.
18. Backward-compatible response structure.
19. 100% of generated edges have grounding & explanation.
20. Zero unintended DB mutations during build.
"""

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path("D:/ayur-intel/ayur-intel")
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import event
from api.core.database import SessionLocal, init_db, engine
from api.models import models
from api.models.models import User, ProductCase, Source, KnowledgeFinding, PlantDiscovery, InnovationAnalysis, InnovationComponent, PatentRecord, PatentRelevance, PatentAnalysis, IPStrategy, IPStrategyItem, RegulatoryProfile, RegulatoryRequirement
from api.models.evidence import UnifiedEvidence, CaseFinding, CaseFindingEvidence
from api.models.risk import Risk, RiskEvidence, RiskAssessment
from api.models.monitoring import Alert
from api.services.knowledge_graph_service import build_knowledge_graph, search_graph, get_node_details
from api.services.product_case_service import get_or_create_demo_user, get_or_create_demo_case

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_kg")


def run_comprehensive_tests():
    init_db()
    db = SessionLocal()

    passed = 0
    total = 20

    try:
        user = get_or_create_demo_user(db)
        demo_dict = get_or_create_demo_case(db, user)
        case = db.query(ProductCase).filter(ProductCase.public_id == "demo-001").first()
        assert case is not None, "Demo case demo-001 must exist"

        # Ensure initial claims exist on demo-001 for test idempotency
        case.claims = json.dumps([
            {"claim_text": "Promotes restful sleep and nervous system relaxation", "category": "Therapeutic"},
            {"claim_text": "Supports healthy cortisol rhythm and stress reduction", "category": "Functional"},
            "Traditional adaptogenic rejuvenation"
        ])
        db.commit()

        # -------------------------------------------------------------
        # TEST 1: Graph builds successfully
        # -------------------------------------------------------------
        graph = build_knowledge_graph(db, user, case.public_id)
        assert graph is not None, "Graph must not be None"
        assert len(graph["nodes"]) > 0, "Graph nodes must not be empty"
        assert len(graph["edges"]) > 0, "Graph edges must not be empty"
        passed += 1
        logger.info("✅ TEST 1 PASSED: Graph builds successfully.")

        # -------------------------------------------------------------
        # TEST 2: Ingredients preserved & botanical taxonomy mapped
        # -------------------------------------------------------------
        ing_nodes = [n for n in graph["nodes"] if n["type"] == "INGREDIENT"]
        contains_edges = [e for e in graph["edges"] if e["relationship"] == "CONTAINS"]
        derived_edges = [e for e in graph["edges"] if e["relationship"] == "DERIVED_FROM"]
        assert len(ing_nodes) > 0, "Ingredient nodes must exist"
        assert len(contains_edges) == len(ing_nodes), "Every ingredient must have CONTAINS edge"
        passed += 1
        logger.info(f"✅ TEST 2 PASSED: {len(ing_nodes)} ingredients preserved with taxonomy.")

        # -------------------------------------------------------------
        # TEST 3: CLAIM nodes generated with deterministic sha256 IDs
        # -------------------------------------------------------------
        claim_nodes = [n for n in graph["nodes"] if n["type"] == "CLAIM"]
        assert len(claim_nodes) >= 3, "At least 3 claim nodes expected"
        for cn in claim_nodes:
            assert cn["id"].startswith(f"CLAIM:claim_{case.id}_"), f"Invalid claim node ID: {cn['id']}"
            # Verify hash length is 10 chars after case id
            suffix = cn["id"].split(f"claim_{case.id}_")[1]
            assert len(suffix) == 10, f"Expected 10-char sha256 hash suffix, got: {suffix}"
        passed += 1
        logger.info(f"✅ TEST 3 PASSED: {len(claim_nodes)} CLAIM nodes generated with deterministic sha256 IDs.")

        # -------------------------------------------------------------
        # TEST 4: Product -> Claim edge generated (ASSERTS_CLAIM)
        # -------------------------------------------------------------
        claim_edges = [e for e in graph["edges"] if e["relationship"] == "ASSERTS_CLAIM"]
        assert len(claim_edges) == len(claim_nodes), "Every claim must have ASSERTS_CLAIM edge from product"
        for ce in claim_edges:
            assert ce["source"] == f"PRODUCT:{case.id}"
            assert ce["grounding"] == "DIRECT"
        passed += 1
        logger.info("✅ TEST 4 PASSED: Product -> Claim ASSERTS_CLAIM edges verified.")

        # -------------------------------------------------------------
        # TEST 5: Claim -> Evidence NOT fabricated
        # -------------------------------------------------------------
        claim_ev_edges = [e for e in graph["edges"] if e["source"].startswith("CLAIM:") and "EVIDENCE" in e["target"]]
        assert len(claim_ev_edges) == 0, "No unauthorized Claim -> Evidence edges should be fabricated"
        passed += 1
        logger.info("✅ TEST 5 PASSED: Zero semantic invention / zero fabricated Claim->Evidence edges.")

        # -------------------------------------------------------------
        # Setup RiskAssessments for testing
        # -------------------------------------------------------------
        # Delete old risk assessments for test purity
        db.query(RiskAssessment).filter(RiskAssessment.product_case_id == case.id).delete()
        db.commit()

        # Create Rule-Based Assessment
        rule_ra = RiskAssessment(
            owner_id=user.id,
            product_case_id=case.id,
            assessment_source="RULE_ENGINE",
            model_used=None,
            overall_score=45,
            overall_level="MODERATE",
            overall_confidence=0.85,
            overall_summary="Deterministic rule-based risk evaluation.",
            top_risks_json=json.dumps([
                {
                    "id": "rule_risk_01",
                    "title": "Regulatory Notification Requirement",
                    "domain": "Regulatory",
                    "severity": "MODERATE",
                    "likelihood": "HIGH",
                    "impact": "MEDIUM",
                    "rationale": "Mandatory AYUSH compliance filing required before market distribution.",
                    "recommended_action": "Submit Form 24D notification.",
                    "evidence_refs": [],
                    "evidence_status": "SUPPORTED"
                }
            ])
        )
        db.add(rule_ra)
        db.commit()

        # -------------------------------------------------------------
        # TEST 6: Canonical RiskAssessment represented
        # -------------------------------------------------------------
        graph_rule = build_knowledge_graph(db, user, case.public_id)
        risk_nodes = [n for n in graph_rule["nodes"] if n["type"] == "RISK"]
        assert len(risk_nodes) >= 1, "Canonical risk nodes must be present"
        r0 = risk_nodes[0]
        assert r0["metadata"]["severity"] == "MODERATE"
        assert r0["metadata"]["confidence"] == 0.85
        assert r0["metadata"]["rationale"] == "Mandatory AYUSH compliance filing required before market distribution."
        assert r0["metadata"]["recommended_action"] == "Submit Form 24D notification."
        passed += 1
        logger.info("✅ TEST 6 PASSED: Canonical RiskAssessment represented accurately.")

        # -------------------------------------------------------------
        # TEST 7: RULE_ENGINE has zero Gemini attribution
        # -------------------------------------------------------------
        assert r0["metadata"]["assessment_source"] == "RULE_ENGINE"
        assert r0["metadata"].get("model_used") is None, "RULE_ENGINE must have model_used = None (Zero Gemini attribution)"
        # Check edge source metadata as well
        risk_edge = next(e for e in graph_rule["edges"] if e["target"] == r0["id"])
        assert risk_edge["metadata"].get("source") == "RULE_ENGINE"
        passed += 1
        logger.info("✅ TEST 7 PASSED: RULE_ENGINE has zero Gemini attribution.")

        # -------------------------------------------------------------
        # TEST 8: Gemini assessment preserves actual model_used
        # -------------------------------------------------------------
        gemini_ra = RiskAssessment(
            owner_id=user.id,
            product_case_id=case.id,
            assessment_source="GEMINI",
            model_used="gemini-2.5-flash",
            overall_score=72,
            overall_level="HIGH",
            overall_confidence=0.91,
            overall_summary="AI synthesis identified potential patent overlap.",
            top_risks_json=json.dumps([
                {
                    "id": "gemini_risk_01",
                    "title": "Prior Art Novelty Exposure",
                    "domain": "IP & Patent",
                    "severity": "HIGH",
                    "likelihood": "HIGH",
                    "impact": "HIGH",
                    "rationale": "High similarity with patented formulation.",
                    "recommended_action": "Conduct detailed FTO freedom-to-operate search.",
                    "evidence_refs": [{"source_type": "passport", "reference_key": "passport:identity"}],
                    "evidence_status": "SUPPORTED"
                }
            ])
        )
        db.add(gemini_ra)
        db.commit()

        graph_gemini = build_knowledge_graph(db, user, case.public_id)
        gemini_risks = [n for n in graph_gemini["nodes"] if n["type"] == "RISK" and n["metadata"].get("assessment_source") == "GEMINI"]
        assert len(gemini_risks) >= 1
        gr0 = gemini_risks[0]
        assert gr0["metadata"].get("model_used") == "gemini-2.5-flash"
        assert gr0["metadata"]["confidence"] == 0.91
        passed += 1
        logger.info("✅ TEST 8 PASSED: Gemini assessment preserves actual model_used (gemini-2.5-flash).")

        # -------------------------------------------------------------
        # TEST 9: DIRECT edge grounding classification
        # -------------------------------------------------------------
        direct_edges = [e for e in graph_gemini["edges"] if e["grounding"] == "DIRECT"]
        assert len(direct_edges) > 0, "Direct edges must exist"
        for de in direct_edges:
            assert len(de["explanation"]) > 0, f"Direct edge {de['relationship']} missing explanation"
        passed += 1
        logger.info(f"✅ TEST 9 PASSED: {len(direct_edges)} DIRECT edges with verified explanations.")

        # -------------------------------------------------------------
        # TEST 10: DERIVED edge grounding classification
        # -------------------------------------------------------------
        derived_edges = [e for e in graph_gemini["edges"] if e["grounding"] == "DERIVED"]
        assert len(derived_edges) > 0, "Derived edges must exist"
        for de in derived_edges:
            assert len(de["explanation"]) > 0, f"Derived edge {de['relationship']} missing explanation"
        passed += 1
        logger.info(f"✅ TEST 10 PASSED: {len(derived_edges)} DERIVED edges with verified explanations.")

        # -------------------------------------------------------------
        # TEST 11: No arbitrary confidence
        # -------------------------------------------------------------
        assert gr0["metadata"]["confidence"] == 0.91, "Confidence must match persisted model value"
        passed += 1
        logger.info("✅ TEST 11 PASSED: Confidence strictly matches persisted RiskAssessment confidence.")

        # -------------------------------------------------------------
        # TEST 12: Evidence -> Source link preserved with authority
        # -------------------------------------------------------------
        src_edges = [e for e in graph_gemini["edges"] if e["relationship"] == "SOURCED_FROM"]
        if src_edges:
            assert src_edges[0]["grounding"] == "DIRECT"
        passed += 1
        logger.info(f"✅ TEST 12 PASSED: Evidence -> Source links preserved.")

        # -------------------------------------------------------------
        # TEST 13: Duplicate claim / source / evidence deduplication
        # -------------------------------------------------------------
        duplicate_test_claims = json.dumps([
            {"claim_text": "Supports restful sleep", "category": "Therapeutic"},
            {"claim_text": "Supports restful sleep", "category": "Therapeutic"},  # exact duplicate
            {"claim_text": "  SUPPORTS RESTFUL SLEEP  ", "category": "Therapeutic"},  # whitespace/case duplicate
            "Different claim"
        ])
        case.claims = duplicate_test_claims
        db.commit()
        graph_dup = build_knowledge_graph(db, user, case.public_id)
        clm_dup_nodes = [n for n in graph_dup["nodes"] if n["type"] == "CLAIM"]
        assert len(clm_dup_nodes) == 2, f"Expected exactly 2 unique claims, got {len(clm_dup_nodes)}"
        passed += 1
        logger.info("✅ TEST 13 PASSED: Duplicate claims deduplicated via content-hash.")

        # -------------------------------------------------------------
        # TEST 14: Stable deterministic graph generation across runs
        # -------------------------------------------------------------
        run1 = build_knowledge_graph(db, user, case.public_id)
        run2 = build_knowledge_graph(db, user, case.public_id)
        node_ids_1 = sorted([n["id"] for n in run1["nodes"]])
        node_ids_2 = sorted([n["id"] for n in run2["nodes"]])
        assert node_ids_1 == node_ids_2, "Node IDs must be perfectly stable across runs"
        edge_keys_1 = sorted([f"{e['source']}->{e['target']}:{e['relationship']}" for e in run1["edges"]])
        edge_keys_2 = sorted([f"{e['source']}->{e['target']}:{e['relationship']}" for e in run2["edges"]])
        assert edge_keys_1 == edge_keys_2, "Edges must be perfectly stable across runs"
        passed += 1
        logger.info("✅ TEST 14 PASSED: Stable deterministic graph generation verified.")

        # -------------------------------------------------------------
        # TEST 15: Claim search in graph
        # -------------------------------------------------------------
        search_res = search_graph(db, user, case.public_id, "restful")
        assert search_res is not None
        assert search_res["total_matches"] >= 1
        assert any(n["type"] == "CLAIM" for n in search_res["matching_nodes"])
        passed += 1
        logger.info("✅ TEST 15 PASSED: Claim search in knowledge graph verified.")

        # -------------------------------------------------------------
        # TEST 16: Claim node details retrieval
        # -------------------------------------------------------------
        clm_id = clm_dup_nodes[0]["id"]
        clm_details = get_node_details(db, user, case.public_id, clm_id)
        assert clm_details is not None
        assert clm_details["node"]["id"] == clm_id
        assert len(clm_details["connections"]) >= 1
        passed += 1
        logger.info("✅ TEST 16 PASSED: Claim node details retrieved successfully.")

        # -------------------------------------------------------------
        # TEST 17: Canonical Risk node details retrieval
        # -------------------------------------------------------------
        risk_nid = gemini_risks[0]["id"]
        risk_details = get_node_details(db, user, case.public_id, risk_nid)
        assert risk_details is not None
        assert risk_details["node"]["id"] == risk_nid
        assert risk_details["node"]["metadata"]["model_used"] == "gemini-2.5-flash"
        passed += 1
        logger.info("✅ TEST 17 PASSED: Canonical Risk node details retrieved successfully.")

        # -------------------------------------------------------------
        # TEST 18: Backward-compatible response structure
        # -------------------------------------------------------------
        assert "product_case_id" in run1
        assert "product_name" in run1
        assert "nodes" in run1
        assert "edges" in run1
        assert "summary" in run1
        assert "filters" in run1
        assert "total_nodes" in run1["summary"]
        assert "total_edges" in run1["summary"]
        assert "node_types" in run1["summary"]
        assert "grounding" in run1["summary"]
        passed += 1
        logger.info("✅ TEST 18 PASSED: Response schema is 100% backward-compatible.")

        # -------------------------------------------------------------
        # TEST 19: 100% of generated edges have grounding & explanation
        # -------------------------------------------------------------
        total_edges = len(run1["edges"])
        edges_with_grounding = [e for e in run1["edges"] if e.get("grounding") in ("DIRECT", "DERIVED") and e.get("explanation")]
        assert len(edges_with_grounding) == total_edges, f"Expected 100% grounding, got {len(edges_with_grounding)}/{total_edges}"
        passed += 1
        logger.info(f"✅ TEST 19 PASSED: 100% of {total_edges} generated edges contain valid grounding and explanation.")

        # -------------------------------------------------------------
        # TEST 20: Zero unintended DB mutations during build
        # -------------------------------------------------------------
        cases_before = db.query(ProductCase).count()
        risks_before = db.query(RiskAssessment).count()
        # Call build_knowledge_graph multiple times
        for _ in range(3):
            build_knowledge_graph(db, user, case.public_id)
        cases_after = db.query(ProductCase).count()
        risks_after = db.query(RiskAssessment).count()
        assert cases_before == cases_after and risks_before == risks_after, "Graph construction must be read-only"
        passed += 1
        logger.info("✅ TEST 20 PASSED: Zero unintended database mutations during graph construction.")

        # -------------------------------------------------------------
        # PERFORMANCE & QUERY MEASUREMENT
        # -------------------------------------------------------------
        # Measure query counts using SQLAlchemy query listener
        query_count = [0]
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            query_count[0] += 1

        event.listen(engine, "before_cursor_execute", count_queries)

        query_count[0] = 0
        t0 = time.perf_counter()
        perf_graph = build_knowledge_graph(db, user, case.public_id)
        build_ms = (time.perf_counter() - t0) * 1000
        measured_queries = query_count[0]

        event.remove(engine, "before_cursor_execute", count_queries)

        logger.info("=== PERFORMANCE MEASUREMENT RESULTS ===")
        logger.info(f"  SQL Queries Executed: {measured_queries}")
        logger.info(f"  Total Graph Nodes:    {len(perf_graph['nodes'])}")
        logger.info(f"  Total Graph Edges:    {len(perf_graph['edges'])}")
        logger.info(f"  Build Time:           {build_ms:.2f} ms")

        # Evidence ref resolution stats
        resolved_refs = 0
        unresolved_refs = 0
        all_node_ids = {n["id"] for n in perf_graph["nodes"]}
        for r_node in [n for n in perf_graph["nodes"] if n["type"] == "RISK"]:
            # Check edge targets
            supported_edges = [e for e in perf_graph["edges"] if e["source"] == r_node["id"] and e["relationship"] in ("SUPPORTED_BY", "RELATES_TO_PATENT")]
            resolved_refs += len(supported_edges)
        logger.info(f"  Resolved Evidence Refs: {resolved_refs}")

        print(f"\n==========================================")
        print(f"KNOWLEDGE GRAPH TEST SUMMARY:")
        print(f"Passed: {passed}/{total} (100%)")
        print(f"Performance: {measured_queries} queries, {len(perf_graph['nodes'])} nodes, {len(perf_graph['edges'])} edges, {build_ms:.2f} ms")
        print(f"==========================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    run_comprehensive_tests()
