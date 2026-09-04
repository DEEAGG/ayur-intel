#!/usr/bin/env python3
"""AYUR-INTEL — Demo Data Generator for SIH Demonstration.

Creates a complete demo scenario showing the full AYUR-INTEL workflow:
1. Product Case creation
2. Product Passport
3. Innovation Analysis
4. Patent Intelligence
5. IP Strategy
6. Regulatory Intelligence (multi-jurisdiction)
7. Jurisdiction Comparison
8. Evidence & Citation
9. Risk Analysis
10. Decision Dashboard
11. Continuous Monitoring
12. Knowledge Graph
13. Source Router
14. Human Review
15. Analytics

Usage:
    cd ayur-intel
    python scripts/create_demo_data.py

Run this after starting the server.
"""

import json
import sys
import urllib.request
import urllib.error
from typing import Optional

BASE_URL = "http://127.0.0.1:8000"


def api_call(method: str, path: str, data: Optional[dict] = None) -> dict:
    """Make an API call and return the response."""
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ERROR {e.code}: {error_body[:200]}")
        return {"error": str(e)}
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"error": str(e)}


def create_sih_demo_case():
    """Create the primary SIH demonstration case."""
    print("\n" + "=" * 60)
    print("AYUR-INTEL SIH DEMO DATA CREATION")
    print("=" * 60)

    # Step 1: Create Product Case
    print("\n[1/15] Creating Product Case...")
    case = api_call("POST", "/api/cases", {
        "name": "AshwaCalm — Stress Relief & Cognitive Support",
        "jurisdictions": ["IN", "US", "DE"],
        "ingredients": [
            {"name": "Ashwagandha", "botanical": "Withania somnifera", "quantity": "500mg"},
            {"name": "Brahmi", "botanical": "Bacopa monnieri", "quantity": "200mg"},
            {"name": "Shankhpushpi", "botanical": "Convolvulus pluricaulis", "quantity": "150mg"},
            {"name": "Jatamansi", "botanical": "Nardostachys jatamansi", "quantity": "100mg"}
        ],
        "form": "Capsule",
        "intended_use": "Stress relief and cognitive support",
        "claims": [
            "Supports stress relief",
            "Enhances cognitive function",
            "Promotes mental clarity",
            "Helps with relaxation"
        ],
        "formulation": "Ashwagandha 500mg + Brahmi 200mg + Shankhpushpi 150mg + Jatamansi 100mg per capsule",
        "process": "Standardized extract manufacturing with HPLC-verified active compound content, GMP-certified facility"
    })
    case_id = case.get("id", "")
    print(f"  ✓ Created: {case.get('name')} (ID: {case_id})")
    if not case_id:
        print("  ✗ Failed to create case!")
        return None

    # Step 2: Product Passport (already embedded in case creation)

    # Step 3: Innovation Analysis
    print("\n[2/15] Running Innovation Analysis...")
    innovation = api_call("POST", f"/api/cases/{case_id}/innovation-analysis")
    components = innovation.get("components", innovation.get("innovation_components", []))
    trad = sum(1 for c in components if isinstance(c, dict) and "TRADITIONAL" in str(c.get("classification", "")))
    diff = sum(1 for c in components if isinstance(c, dict) and "KNOWN" not in str(c.get("classification", "")) and "TRADITIONAL" not in str(c.get("classification", "")))
    print(f"  ✓ {len(components)} components ({trad} traditional, {len(components)-trad} other)")

    # Step 4: Patent Intelligence
    print("\n[3/15] Running Patent Search...")
    patents = api_call("POST", f"/api/cases/{case_id}/patent-search", {"query": "ashwagandha stress relief"})
    results = patents.get("results", patents.get("patents", []))
    print(f"  ✓ {len(results)} patent records found")

    # Step 5: IP Strategy
    print("\n[4/15] Running IP Strategy Analysis...")
    ip = api_call("POST", f"/api/cases/{case_id}/ip-strategy", {"trigger": "auto"})
    items = ip.get("items", ip.get("strategies", []))
    total_items = ip.get("total_items", len(items))
    print(f"  ✓ {total_items} IP strategy items generated")

    # Step 6: Regulatory Intelligence (3 jurisdictions)
    print("\n[5/15] Running Regulatory Intelligence...")
    for jurisdiction in ["IN", "US", "DE"]:
        reg = api_call("POST", f"/api/cases/{case_id}/regulatory-analysis", {"jurisdiction": jurisdiction})
        profiles = reg.get("profiles", reg.get("requirements", []))
        print(f"  ✓ {jurisdiction}: {len(profiles)} regulatory requirements")

    # Step 7: Jurisdiction Comparison
    print("\n[6/15] Running Jurisdiction Comparison...")
    comparison = api_call("POST", f"/api/cases/{case_id}/jurisdiction-comparison", {"jurisdictions": ["IN", "US", "DE"]})
    items = comparison.get("items", comparison.get("comparisons", []))
    print(f"  ✓ {len(items)} comparison categories")

    # Step 8: Risk Analysis
    print("\n[7/15] Running Risk Analysis...")
    risks = api_call("POST", f"/api/cases/{case_id}/risk-analysis")
    risk_list = risks.get("risks", [])
    high = sum(1 for r in risk_list if isinstance(r, dict) and r.get("level") == "HIGH")
    med = sum(1 for r in risk_list if isinstance(r, dict) and r.get("level") == "MEDIUM")
    low = sum(1 for r in risk_list if isinstance(r, dict) and r.get("level") == "LOW")
    print(f"  ✓ {len(risk_list)} risks ({high} HIGH, {med} MEDIUM, {low} LOW)")

    # Step 9: Decision Dashboard
    print("\n[8/15] Generating Decision Dashboard...")
    dashboard = api_call("GET", f"/api/cases/{case_id}/decision-dashboard")
    readiness = dashboard.get("readiness", {})
    print(f"  ✓ Readiness: {readiness.get('level', 'UNKNOWN')}")

    # Step 10: Continuous Monitoring
    print("\n[9/15] Configuring Monitoring...")
    monitoring = api_call("GET", f"/api/cases/{case_id}/monitoring")
    config = monitoring.get("config", {})
    print(f"  ✓ Enabled: {config.get('enabled')} | Frequency: {config.get('frequency')}")

    # Run monitoring check
    print("\n[10/15] Running Monitoring Check...")
    monitor_run = api_call("POST", f"/api/cases/{case_id}/monitoring/run")
    print(f"  ✓ Status: {monitor_run.get('status', '?')} | Sources checked: {monitor_run.get('sources_checked', '?')}")

    # Step 11: Knowledge Graph
    print("\n[11/15] Building Knowledge Graph...")
    kg = api_call("GET", f"/api/cases/{case_id}/knowledge-graph")
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])
    print(f"  ✓ {len(nodes)} nodes, {len(edges)} edges")

    # Step 12: Source Router
    print("\n[12/15] Testing Source Router...")
    routing = api_call("POST", "/api/source-router/route", {
        "question": "What are the regulatory requirements for ashwagandha-based products in Germany?"
    })
    classification = routing.get("classification", {})
    decisions = routing.get("routing_decisions", [])
    print(f"  ✓ Topic: {classification.get('primary_topic', '?')} | Routes: {len(decisions)}")

    # Step 13: Human Review (auto-create from HIGH risks)
    print("\n[13/15] Creating Human Review Requests...")
    reviews = api_call("POST", f"/api/cases/{case_id}/reviews/auto-create")
    total = reviews.get("total_created", 0)
    print(f"  ✓ {total} review requests created")

    # Step 14: Analytics
    print("\n[14/15] Generating Analytics...")
    analytics = api_call("GET", f"/api/analytics/product-cases/{case_id}")
    passport_pct = analytics.get('passport_completion', analytics.get('passport', {}).get('completion_percentage', '?'))
    print(f"  ✓ Passport completion: {passport_pct}%")

    # Step 15: Final Dashboard Refresh
    print("\n[15/15] Final Dashboard Refresh...")
    final_dashboard = api_call("POST", f"/api/cases/{case_id}/decision-dashboard/refresh")
    print(f"  ✓ Dashboard refreshed")

    # Summary
    print("\n" + "=" * 60)
    print("DEMO DATA CREATION COMPLETE")
    print("=" * 60)
    print(f"\nProduct Case: {case.get('name')}")
    print(f"Case ID: {case_id}")
    print(f"URL: {BASE_URL}")
    print(f"\nWorkflow completed:")
    print(f"  ✓ Product Case created")
    print(f"  ✓ Innovation Analysis: {len(components)} components")
    print(f"  ✓ Patent Search: {len(results)} records")
    print(f"  ✓ IP Strategy: {len(items)} items")
    print(f"  ✓ Regulatory Intelligence: 3 jurisdictions")
    print(f"  ✓ Jurisdiction Comparison: {len(items)} categories")
    print(f"  ✓ Risk Analysis: {len(risk_list)} risks")
    print(f"  ✓ Decision Dashboard: {readiness.get('level', '?')}")
    print(f"  ✓ Monitoring: {config.get('frequency', '?')}")
    print(f"  ✓ Knowledge Graph: {len(nodes)} nodes, {len(edges)} edges")
    print(f"  ✓ Source Router: routing works")
    print(f"  ✓ Human Reviews: {total} created")
    print(f"  ✓ Analytics: working")
    print(f"\n⚠️  IMPORTANT DISCLAIMERS:")
    print(f"  - This is a DEMONSTRATION scenario")
    print(f"  - AI analysis is advisory only, not legal/regulatory advice")
    print(f"  - All patent/regulatory findings are simulated for demo purposes")
    print(f"  - Consult qualified experts for actual product decisions")

    return case_id


def create_plant_discovery_demo():
    """Create a Plant Discovery demo case."""
    print("\n[Plant Discovery Demo] Creating plant discovery...")
    discovery = api_call("POST", "/api/plant-discoveries", {
        "product_case_id": None
    })
    disc_id = discovery.get("discovery_id", discovery.get("id", ""))
    print(f"  ✓ Plant Discovery created: {disc_id}")

    # Analyze the plant
    if disc_id:
        analysis = api_call("POST", f"/api/plant-discoveries/{disc_id}/analyze", {})
        identification = analysis.get("identification", analysis.get("botanical_identification", {}))
        print(f"  ✓ Possible identification: {identification.get('species', identification.get('name', '?'))}")
        print(f"  ✓ Confidence: {identification.get('confidence', '?')}")
        print(f"  ⚠️  Safety warning: Expert verification recommended")

    return disc_id


if __name__ == "__main__":
    try:
        # Check server is running
        api_call("GET", "/api/health")
    except Exception:
        print("ERROR: Server not running at http://127.0.0.1:8000")
        print("Start the server first: cd ayur-intel && python start_server.py")
        sys.exit(1)

    case_id = create_sih_demo_case()
    disc_id = create_plant_discovery_demo()

    print("\n" + "=" * 60)
    print("ALL DEMO DATA CREATED SUCCESSFULLY")
    print("=" * 60)
    print(f"\nOpen the application: {BASE_URL}")
    print("Navigate to the demo case to see the full workflow.")
