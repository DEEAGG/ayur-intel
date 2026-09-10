"""AYUR-INTEL — Knowledge Graph Service (Phase 15).

Dynamically constructs graph data from existing database entities.
No duplicate storage — builds nodes and edges on the fly.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from api.models.models import (
    User, ProductCase,
    PlantDiscovery,
    Source, KnowledgeFinding, KnowledgeEvidence,
    InnovationAnalysis, InnovationComponent,
    PatentRecord, PatentSearch, PatentRelevance, PatentAnalysis,
    IPStrategy, IPStrategyItem,
    RegulatoryProfile, RegulatoryRequirement,
)
from api.models.evidence import UnifiedEvidence, CaseFinding, CaseFindingEvidence
from api.models.risk import Risk, RiskEvidence, SelfExtensionRequest, RiskAssessment
from api.models.monitoring import MonitoringConfig, Alert

logger = logging.getLogger("ayur_intel.knowledge_graph")


def _deserialize(value):
    if not value:
        return []
    try:
        result = json.loads(value) if isinstance(value, str) else value
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _get_case(db: Session, user: User, case_public_id: str) -> Optional[ProductCase]:
    return (
        db.query(ProductCase)
        .filter(ProductCase.public_id == case_public_id, ProductCase.owner_id == user.id)
        .first()
    )


# -------------------------------------------------------------------
# Node type colors for visualization
# -------------------------------------------------------------------
NODE_COLORS = {
    "PRODUCT": "#2d4a3e",
    "INGREDIENT": "#4caf50",
    "PLANT": "#66bb6a",
    "CLAIM": "#00bcd4",
    "FORMULATION": "#81c784",
    "PROCESS": "#a5d6a7",
    "TRADITIONAL_KNOWLEDGE": "#ff9800",
    "PATENT": "#f44336",
    "PATENT_FAMILY": "#ef5350",
    "INNOVATION_COMPONENT": "#9c27b0",
    "IP_STRATEGY": "#7b1fa2",
    "REGULATION": "#2196f3",
    "JURISDICTION": "#1565c0",
    "EVIDENCE": "#607d8b",
    "SOURCE": "#455a64",
    "RISK": "#ff5722",
    "ALERT": "#ff9800",
    "CASE_FINDING": "#795548",
}

NODE_ICONS = {
    "PRODUCT": "science",
    "INGREDIENT": "eco",
    "PLANT": "park",
    "CLAIM": "verified_user",
    "FORMULATION": "science",
    "PROCESS": "settings",
    "TRADITIONAL_KNOWLEDGE": "menu_book",
    "PATENT": "gavel",
    "PATENT_FAMILY": "group",
    "INNOVATION_COMPONENT": "hub",
    "IP_STRATEGY": "analytics",
    "REGULATION": "policy",
    "JURISDICTION": "public",
    "EVIDENCE": "verified",
    "SOURCE": "source",
    "RISK": "warning",
    "ALERT": "notifications_active",
    "CASE_FINDING": "search",
}


# -------------------------------------------------------------------
# Graph builder
# -------------------------------------------------------------------

def build_knowledge_graph(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Build a complete knowledge graph for a Product Case.

    Dynamically constructs nodes and edges from existing entities.
    """
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    nodes = []
    edges = []
    node_ids = set()
    edge_keys = set()

    def add_node(node_type, entity_id, label, metadata=None):
        nid = f"{node_type}:{entity_id}"
        if nid in node_ids:
            return nid
        node_ids.add(nid)
        nodes.append({
            "id": nid,
            "type": node_type,
            "entity_id": str(entity_id),
            "label": label,
            "color": NODE_COLORS.get(node_type, "#757575"),
            "icon": NODE_ICONS.get(node_type, "circle"),
            "metadata": metadata or {},
        })
        return nid

    def add_edge(source_id, target_id, relationship, metadata=None, grounding="DIRECT", explanation=""):
        ek = f"{source_id}->{target_id}:{relationship}"
        if ek in edge_keys:
            return
        edge_keys.add(ek)
        meta = dict(metadata or {})
        meta["grounding"] = meta.get("grounding") or grounding
        meta["explanation"] = meta.get("explanation") or explanation
        edges.append({
            "source": source_id,
            "target": target_id,
            "relationship": relationship,
            "grounding": meta["grounding"],
            "explanation": meta["explanation"],
            "metadata": meta,
        })

    # Batch query all sources for fast O(1) lookup without N+1 queries
    sources_map = {s.id: s for s in db.query(Source).all()}

    # -------------------------------------------------------------------
    # 1. Product (center node)
    # -------------------------------------------------------------------
    product_nid = add_node("PRODUCT", case.id, case.name, {
        "stage": case.stage,
        "status": case.status,
        "form": case.form,
        "intended_use": case.intended_use,
        "brand": case.brand,
    })

    # -------------------------------------------------------------------
    # 2. Ingredients
    # -------------------------------------------------------------------
    ingredients = _deserialize(case.ingredients)
    for ing in ingredients:
        if isinstance(ing, dict):
            ing_name = ing.get("name", "Unknown")
            ing_id = f"ing_{case.id}_{ing_name}"
            ing_nid = add_node("INGREDIENT", ing_id, ing_name, {
                "botanical_name": ing.get("botanical_name"),
                "quantity": ing.get("quantity"),
                "form": ing.get("form"),
                "status": ing.get("status"),
            })
            add_edge(product_nid, ing_nid, "CONTAINS", {"label": "contains"},
                     grounding="DIRECT", explanation="Declared product ingredient in product passport.")

            # Ingredient -> Plant (if botanical)
            if ing.get("botanical_name"):
                plant_id = f"plant_{ing.get('botanical_name')}"
                plant_nid = add_node("PLANT", plant_id, ing.get("botanical_name"), {
                    "common_name": ing_name,
                })
                add_edge(ing_nid, plant_nid, "DERIVED_FROM", {"label": "derived from"},
                         grounding="DIRECT", explanation="Botanical taxonomy mapped directly from declared botanical name.")
        elif isinstance(ing, str) and ing.strip():
            ing_name = ing.strip()
            ing_id = f"ing_{case.id}_{ing_name}"
            ing_nid = add_node("INGREDIENT", ing_id, ing_name, {})
            add_edge(product_nid, ing_nid, "CONTAINS", {"label": "contains"},
                     grounding="DIRECT", explanation="Declared product ingredient in product passport.")

    # -------------------------------------------------------------------
    # 3. Claims (Product Formulation & Market Claims)
    # -------------------------------------------------------------------
    claims = _deserialize(case.claims)
    seen_claims = set()
    for clm in claims:
        if not clm:
            continue
        if isinstance(clm, dict):
            clm_text = clm.get("claim_text") or clm.get("text") or clm.get("claim") or clm.get("title") or ""
            if not isinstance(clm_text, str) or not clm_text.strip():
                continue
            normalized = clm_text.strip().lower()
            if normalized in seen_claims:
                continue
            seen_claims.add(normalized)
            hash_suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
            clm_id = f"claim_{case.id}_{hash_suffix}"
            clm_nid = add_node("CLAIM", clm_id, clm_text.strip()[:60], {
                "full_text": clm_text.strip(),
                "category": clm.get("category") or clm.get("claim_type") or "Product Claim",
                "status": clm.get("status", "ACTIVE"),
            })
            add_edge(product_nid, clm_nid, "ASSERTS_CLAIM", {"label": "asserts claim"},
                     grounding="DIRECT", explanation="Direct therapeutic or functional claim declared in product case passport.")
        elif isinstance(clm, str) and clm.strip():
            clm_text = clm.strip()
            normalized = clm_text.lower()
            if normalized in seen_claims:
                continue
            seen_claims.add(normalized)
            hash_suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
            clm_id = f"claim_{case.id}_{hash_suffix}"
            clm_nid = add_node("CLAIM", clm_id, clm_text[:60], {
                "full_text": clm_text,
                "category": "Product Claim",
            })
            add_edge(product_nid, clm_nid, "ASSERTS_CLAIM", {"label": "asserts claim"},
                     grounding="DIRECT", explanation="Direct therapeutic or functional claim declared in product case passport.")

    # -------------------------------------------------------------------
    # 4. Formulation
    # -------------------------------------------------------------------
    if case.formulation:
        form_id = f"formulation_{case.id}"
        form_nid = add_node("FORMULATION", form_id, "Product Formulation", {
            "value": case.formulation[:200],
        })
        add_edge(product_nid, form_nid, "HAS_FORMULATION", {"label": "has formulation"},
                 grounding="DIRECT", explanation="Formulation specification declared in product case.")

    # -------------------------------------------------------------------
    # 5. Process
    # -------------------------------------------------------------------
    if case.process:
        proc_id = f"process_{case.id}"
        proc_nid = add_node("PROCESS", proc_id, "Manufacturing Process", {
            "value": case.process[:200],
        })
        add_edge(product_nid, proc_nid, "HAS_PROCESS", {"label": "has process"},
                 grounding="DIRECT", explanation="Manufacturing process declared in product case.")

    # -------------------------------------------------------------------
    # 6. Jurisdictions
    # -------------------------------------------------------------------
    jurisdictions = _deserialize(case.jurisdictions)
    jur_names = {"IN": "India", "US": "United States", "EU": "European Union", "DE": "Germany"}
    for jur in jurisdictions:
        jur_id = f"jurisdiction_{jur}"
        jur_nid = add_node("JURISDICTION", jur_id, jur_names.get(jur, jur), {
            "code": jur,
        })
        add_edge(product_nid, jur_nid, "TARGETS", {"label": "targets"},
                 grounding="DIRECT", explanation="Target commercial jurisdiction declared in product case.")

    # -------------------------------------------------------------------
    # 7. Knowledge Findings (TK)
    # -------------------------------------------------------------------
    findings = (
        db.query(KnowledgeFinding)
        .filter(KnowledgeFinding.product_case_id == case.id)
        .all()
    )
    for f in findings:
        tk_nid = add_node("TRADITIONAL_KNOWLEDGE", f.id, f.title, {
            "category": f.category,
            "confidence": f.confidence,
            "plant_name": f.plant_name,
            "botanical_name": f.botanical_name,
        })
        add_edge(product_nid, tk_nid, "HAS_TRADITIONAL_USE", {"label": "TK finding"},
                 grounding="DIRECT", explanation="Traditional knowledge finding retrieved for product case.")

        # TK -> Source
        if f.source_id:
            src = sources_map.get(f.source_id)
            if src:
                src_nid = add_node("SOURCE", src.id, src.name, {
                    "authority": src.authority,
                    "source_type": src.source_type,
                    "jurisdiction": src.jurisdiction,
                })
                add_edge(tk_nid, src_nid, "SOURCED_FROM", {"label": "source"},
                         grounding="DIRECT", explanation="Primary source authority for traditional knowledge finding.")

        # TK -> Plant
        if f.botanical_name:
            plant_id = f"plant_{f.botanical_name}"
            plant_nid = add_node("PLANT", plant_id, f.botanical_name, {
                "common_name": f.plant_name,
            })
            add_edge(tk_nid, plant_nid, "ABOUT_PLANT", {"label": "about"},
                     grounding="DIRECT", explanation="Botanical species referenced in traditional knowledge finding.")

    # -------------------------------------------------------------------
    # 8. Plant Discoveries
    # -------------------------------------------------------------------
    plants = (
        db.query(PlantDiscovery)
        .filter(PlantDiscovery.product_case_id == case.id)
        .all()
    )
    for pd in plants:
        if pd.botanical_name:
            plant_id = f"plant_{pd.botanical_name}"
            plant_nid = add_node("PLANT", plant_id, pd.botanical_name, {
                "common_name": pd.candidate_name,
                "confidence": pd.confidence,
                "verification_required": pd.verification_required,
            })
            add_edge(product_nid, plant_nid, "IDENTIFIED_AS", {"label": "identified"},
                     grounding="DERIVED", explanation="Plant taxonomy entity identified during botanical discovery.")

    # -------------------------------------------------------------------
    # 9. Innovation Analysis & Components
    # -------------------------------------------------------------------
    analyses = (
        db.query(InnovationAnalysis)
        .filter(InnovationAnalysis.product_case_id == case.id)
        .all()
    )
    for analysis in analyses:
        ia_nid = add_node("INNOVATION_COMPONENT", f"analysis_{analysis.id}",
                          f"Innovation Analysis ({analysis.total_components} components)",
                          {
                              "total": analysis.total_components,
                              "traditional": analysis.traditional_count,
                              "differentiated": analysis.differentiated_count,
                              "investigation": analysis.investigation_count,
                          })
        add_edge(product_nid, ia_nid, "HAS_ANALYSIS", {"label": "innovation analysis"},
                 grounding="DERIVED", explanation="Innovation decomposition analysis generated for product.")

        for comp in analysis.components:
            comp_nid = add_node("INNOVATION_COMPONENT", comp.id, comp.component_label, {
                "type": comp.component_type,
                "classification": comp.classification,
                "ip_route": comp.potential_ip_route,
                "confidence": comp.confidence,
            })
            add_edge(ia_nid, comp_nid, "DECOMPOSES_TO", {"label": "component"},
                     grounding="DERIVED", explanation="Decomposed innovation component generated from formulation analysis.")

            # Component -> Ingredient (if type is ingredient)
            if comp.component_type == "INGREDIENT" and comp.component_value:
                for ing in ingredients:
                    if isinstance(ing, dict) and ing.get("name") == comp.component_value:
                        ing_id = f"ing_{case.id}_{ing['name']}"
                        ing_nid = f"INGREDIENT:{ing_id}"
                        if ing_nid in node_ids:
                            add_edge(comp_nid, ing_nid, "MAPS_TO", {"label": "maps to"},
                                     grounding="DIRECT", explanation="Innovation component directly mapped to declared product ingredient.")

    # -------------------------------------------------------------------
    # 10. Patent Records & Relevances
    # -------------------------------------------------------------------
    relevances = (
        db.query(PatentRelevance)
        .filter(PatentRelevance.product_case_id == case.id)
        .all()
    )
    for rel in relevances:
        pr = rel.patent_record
        if pr:
            patent_nid = add_node("PATENT", pr.id, pr.title or pr.publication_number or "Patent", {
                "publication_number": pr.publication_number,
                "applicant": pr.applicant,
                "jurisdiction": pr.jurisdiction,
                "status": pr.status,
                "relevance_level": rel.relevance_level,
            })
            add_edge(product_nid, patent_nid, "APPEARS_IN", {
                "label": "patent relevance",
                "relevance": rel.relevance_level,
            }, grounding="DIRECT", explanation="Prior art patent record identified in case patent search.")

            # Patent -> Jurisdiction
            if pr.jurisdiction:
                jur_id = f"jurisdiction_{pr.jurisdiction}"
                jur_nid = f"JURISDICTION:{jur_id}"
                if jur_nid not in node_ids:
                    jur_nid = add_node("JURISDICTION", jur_id,
                                       jur_names.get(pr.jurisdiction, pr.jurisdiction),
                                       {"code": pr.jurisdiction})
                add_edge(patent_nid, jur_nid, "FILED_IN", {"label": "filed in"},
                         grounding="DIRECT", explanation="Jurisdiction where patent application/grant is registered.")

            # Patent -> Ingredient
            if rel.overlap_component and rel.overlap_component == "INGREDIENT":
                for ing in ingredients:
                    if isinstance(ing, dict):
                        ing_id = f"ing_{case.id}_{ing.get('name', '')}"
                        ing_nid = f"INGREDIENT:{ing_id}"
                        if ing_nid in node_ids:
                            add_edge(patent_nid, ing_nid, "RELATED_TO", {
                                "label": "potential overlap",
                            }, grounding="DERIVED", explanation="Patent relevance overlap mapped to ingredient component.")

    # -------------------------------------------------------------------
    # 11. Patent Deep Analysis
    # -------------------------------------------------------------------
    patent_analyses = (
        db.query(PatentAnalysis)
        .filter(PatentAnalysis.product_case_id == case.id)
        .all()
    )
    for pa in patent_analyses:
        if pa.patent_record:
            patent_nid = f"PATENT:{pa.patent_record_id}"
            if patent_nid in node_ids:
                analysis_nid = add_node("CASE_FINDING", f"pa_{pa.id}",
                                        f"Deep Analysis: {pa.overall_relevance}",
                                        {
                                            "overall_relevance": pa.overall_relevance,
                                            "confidence": pa.overall_confidence,
                                            "summary": pa.summary,
                                        })
                add_edge(patent_nid, analysis_nid, "HAS_ANALYSIS", {"label": "deep analysis"},
                         grounding="DERIVED", explanation="Deep patent claim and FTO analysis generated for patent record.")

    # -------------------------------------------------------------------
    # 12. IP Strategy
    # -------------------------------------------------------------------
    strategies = (
        db.query(IPStrategy)
        .filter(IPStrategy.product_case_id == case.id)
        .all()
    )
    for strat in strategies:
        strat_nid = add_node("IP_STRATEGY", strat.id, "IP Strategy Map", {
            "total_items": strat.total_items,
            "high_priority": strat.high_priority_count,
        })
        add_edge(product_nid, strat_nid, "HAS_IP_STRATEGY", {"label": "IP strategy"},
                 grounding="DERIVED", explanation="Strategic IP protection recommendation roadmap generated for product.")

        for item in strat.items:
            item_nid = add_node("IP_STRATEGY", f"item_{item.id}", item.component_label, {
                "ip_category": item.ip_category,
                "priority": item.priority,
                "next_action": item.next_action,
            })
            add_edge(strat_nid, item_nid, "RECOMMENDS", {"label": "recommends"},
                     grounding="DERIVED", explanation="Actionable IP protection recommendation item.")

    # -------------------------------------------------------------------
    # 13. Regulatory Profiles
    # -------------------------------------------------------------------
    profiles = (
        db.query(RegulatoryProfile)
        .filter(RegulatoryProfile.product_case_id == case.id)
        .all()
    )
    for rp in profiles:
        reg_nid = add_node("REGULATION", rp.id,
                           f"Regulatory: {jur_names.get(rp.jurisdiction, rp.jurisdiction)}",
                           {
                               "jurisdiction": rp.jurisdiction,
                               "potential_category": rp.potential_category,
                               "total_requirements": rp.total_requirements,
                               "category_confidence": rp.category_confidence,
                           })
        add_edge(product_nid, reg_nid, "APPLIES_TO", {"label": "regulatory profile"},
                 grounding="DIRECT", explanation="Regulatory profile applicable to target market jurisdiction.")

        # Regulation -> Jurisdiction
        jur_id = f"jurisdiction_{rp.jurisdiction}"
        jur_nid = f"JURISDICTION:{jur_id}"
        if jur_nid not in node_ids:
            jur_nid = add_node("JURISDICTION", jur_id,
                               jur_names.get(rp.jurisdiction, rp.jurisdiction),
                               {"code": rp.jurisdiction})
        add_edge(reg_nid, jur_nid, "IN_JURISDICTION", {"label": "in jurisdiction"},
                 grounding="DIRECT", explanation="Jurisdiction governing regulatory profile.")

        # Requirements
        for req in rp.requirements[:5]:
            req_nid = add_node("REGULATION", req.id, req.title, {
                "category": req.category,
                "applicability": req.applicability,
                "authority": req.authority,
                "confidence": req.confidence,
            })
            add_edge(reg_nid, req_nid, "HAS_REQUIREMENT", {"label": "requirement"},
                     grounding="DIRECT", explanation="Specific statutory compliance requirement under regulatory framework.")

    # -------------------------------------------------------------------
    # 14. Evidence
    # -------------------------------------------------------------------
    findings_ev = (
        db.query(CaseFinding)
        .filter(CaseFinding.product_case_id == case.id)
        .all()
    )
    for cf in findings_ev:
        cf_nid = add_node("CASE_FINDING", cf.id, cf.title, {
            "finding_type": cf.finding_type,
            "source_phase": cf.source_phase,
            "confidence": cf.confidence,
            "data_origin": cf.data_origin,
        })
        add_edge(product_nid, cf_nid, "HAS_FINDING", {"label": "finding"},
                 grounding="DIRECT", explanation="Evidence intelligence finding captured for product case.")

        for link in cf.evidence_links:
            ev = link.evidence
            if ev:
                ev_nid = add_node("EVIDENCE", ev.id, ev.title or ev.evidence_type, {
                    "evidence_type": ev.evidence_type,
                    "source_name": ev.source_name,
                    "authority": ev.authority,
                    "jurisdiction": ev.jurisdiction,
                    "confidence": ev.confidence,
                    "data_origin": ev.data_origin,
                })
                add_edge(cf_nid, ev_nid, "HAS_EVIDENCE", {"label": "evidence"},
                         grounding="DIRECT", explanation="Direct evidentiary record supporting case finding.")

                # Evidence -> Source
                if ev.source_id:
                    src = sources_map.get(ev.source_id)
                    if src:
                        src_nid = add_node("SOURCE", src.id, src.name, {
                            "authority": src.authority,
                            "source_type": src.source_type,
                            "jurisdiction": src.jurisdiction,
                        })
                        add_edge(ev_nid, src_nid, "SOURCED_FROM", {"label": "source"},
                                 grounding="DIRECT", explanation="Primary source authority backing evidence record.")

    # -------------------------------------------------------------------
    # 15. Risks (Canonical RiskAssessment or fallback to legacy Risk)
    # -------------------------------------------------------------------
    risk_assessment = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.product_case_id == case.id)
        .order_by(RiskAssessment.created_at.desc())
        .first()
    )
    if risk_assessment:
        top_risks = _deserialize(risk_assessment.top_risks_json)
        for idx, r in enumerate(top_risks):
            if isinstance(r, dict):
                risk_id = r.get("id") or f"risk_{risk_assessment.id}_{idx+1}"
                risk_title = r.get("title") or f"Risk Item {idx+1}"
                sev = str(r.get("severity") or r.get("level") or "MODERATE").upper()
                risk_meta = {
                    "category": r.get("category", "GENERAL"),
                    "severity": sev,
                    "likelihood": r.get("likelihood", "MEDIUM"),
                    "impact": r.get("impact", "MEDIUM"),
                    "rationale": r.get("rationale") or r.get("why_it_matters") or "",
                    "recommended_action": r.get("recommended_action", ""),
                    "assessment_source": risk_assessment.assessment_source,
                    "confidence": risk_assessment.overall_confidence,
                    "evidence_status": r.get("evidence_status", "UNKNOWN"),
                }
                if risk_assessment.assessment_source == "GEMINI" and risk_assessment.model_used:
                    risk_meta["model_used"] = risk_assessment.model_used
                elif risk_assessment.assessment_source == "RULE_ENGINE":
                    risk_meta["model_used"] = None

                risk_nid = add_node("RISK", risk_id, risk_title, risk_meta)
                add_edge(product_nid, risk_nid, "CREATES_RISK", {
                    "label": "risk",
                    "severity": sev,
                    "source": risk_assessment.assessment_source,
                }, grounding="DERIVED", explanation=f"Multi-domain risk assessed via {risk_assessment.assessment_source}.")

                # Grounded evidence references from RiskAssessment
                for ev_ref in (r.get("evidence_refs") or []):
                    ref_key = None
                    if isinstance(ev_ref, dict):
                        ref_key = ev_ref.get("id") or ev_ref.get("reference_key")
                    elif isinstance(ev_ref, (str, int)):
                        ref_key = str(ev_ref)

                    if not ref_key:
                        continue

                    ref_str = str(ref_key).strip()

                    # Exact deterministic lookup only — no fuzzy matching
                    if ref_str in node_ids:
                        if ref_str.startswith("EVIDENCE:"):
                            add_edge(risk_nid, ref_str, "SUPPORTED_BY", {"label": "evidence"},
                                     grounding="DIRECT", explanation="Direct evidence record cited in risk assessment.")
                        elif ref_str.startswith("PATENT:"):
                            add_edge(risk_nid, ref_str, "RELATES_TO_PATENT", {"label": "patent context"},
                                     grounding="DIRECT", explanation="Direct patent prior-art reference cited in risk assessment.")
                        continue

                    target_ev = f"EVIDENCE:{ref_str}"
                    if target_ev in node_ids:
                        add_edge(risk_nid, target_ev, "SUPPORTED_BY", {"label": "evidence"},
                                 grounding="DIRECT", explanation="Direct evidence record cited in risk assessment.")
                        continue

                    target_pat = f"PATENT:{ref_str}"
                    if target_pat in node_ids:
                        add_edge(risk_nid, target_pat, "RELATES_TO_PATENT", {"label": "patent context"},
                                 grounding="DIRECT", explanation="Direct patent prior-art reference cited in risk assessment.")
                        continue
    else:
        risks = (
            db.query(Risk)
            .filter(Risk.product_case_id == case.id)
            .all()
        )
        for risk in risks:
            risk_nid = add_node("RISK", risk.id, risk.title, {
                "category": risk.category,
                "level": risk.level,
                "status": risk.status,
                "confidence": risk.confidence,
                "source_phase": risk.source_phase,
                "assessment_source": "RULE_ENGINE",
            })
            add_edge(product_nid, risk_nid, "CREATES_RISK", {"label": "risk"},
                     grounding="DERIVED", explanation="Rule-based risk factor identified for product case.")

            # Risk -> Evidence
            for link in risk.evidence_links:
                if link.evidence_id:
                    ev_nid = f"EVIDENCE:{link.evidence_id}"
                    if ev_nid in node_ids:
                        add_edge(risk_nid, ev_nid, "SUPPORTED_BY", {"label": "evidence"},
                                 grounding="DIRECT", explanation="Evidence link supporting legacy risk factor.")

    # -------------------------------------------------------------------
    # 16. Alerts
    # -------------------------------------------------------------------
    alerts = (
        db.query(Alert)
        .filter(Alert.product_case_id == case.id)
        .order_by(Alert.created_at.desc())
        .limit(10)
        .all()
    )
    for alert in alerts:
        alert_nid = add_node("ALERT", alert.id, alert.title, {
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "relevance": alert.relevance,
        })
        add_edge(product_nid, alert_nid, "HAS_ALERT", {"label": "alert"},
                 grounding="DERIVED", explanation="Active monitoring alert triggered for product case.")

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    node_type_counts = {}
    for n in nodes:
        t = n["type"]
        node_type_counts[t] = node_type_counts.get(t, 0) + 1

    grounding_counts = {"DIRECT": 0, "DERIVED": 0}
    for e in edges:
        g = e.get("grounding", "DIRECT")
        grounding_counts[g] = grounding_counts.get(g, 0) + 1

    return {
        "product_case_id": case.public_id,
        "product_name": case.name,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": node_type_counts,
            "grounding": grounding_counts,
        },
        "filters": list(NODE_COLORS.keys()),
    }


# -------------------------------------------------------------------
# Search
# -------------------------------------------------------------------

def search_graph(db: Session, user: User, case_public_id: str, query: str) -> Optional[dict]:
    """Search graph entities by query string."""
    graph = build_knowledge_graph(db, user, case_public_id)
    if not graph:
        return None

    q = query.lower()
    matching_nodes = [
        n for n in graph["nodes"]
        if q in (n.get("label", "") or "").lower()
        or q in str(n.get("metadata", {})).lower()
    ]

    # Get edges connecting matching nodes
    matching_ids = {n["id"] for n in matching_nodes}
    matching_edges = [
        e for e in graph["edges"]
        if e["source"] in matching_ids or e["target"] in matching_ids
    ]

    # Also include connected nodes
    connected_ids = set()
    for e in matching_edges:
        connected_ids.add(e["source"])
        connected_ids.add(e["target"])

    all_relevant = [n for n in graph["nodes"] if n["id"] in matching_ids or n["id"] in connected_ids]

    return {
        "query": query,
        "matching_nodes": matching_nodes,
        "all_relevant_nodes": all_relevant,
        "matching_edges": matching_edges,
        "total_matches": len(matching_nodes),
    }


# -------------------------------------------------------------------
# Node details
# -------------------------------------------------------------------

def get_node_details(db: Session, user: User, case_public_id: str, node_id: str) -> Optional[dict]:
    """Get detailed information for a specific graph node."""
    graph = build_knowledge_graph(db, user, case_public_id)
    if not graph:
        return None

    node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if not node:
        return None

    # Find connected edges
    connected_edges = [
        e for e in graph["edges"]
        if e["source"] == node_id or e["target"] == node_id
    ]

    # Get connected nodes
    connected_node_ids = set()
    for e in connected_edges:
        connected_node_ids.add(e["source"])
        connected_node_ids.add(e["target"])
    connected_node_ids.discard(node_id)

    connected_nodes = [
        n for n in graph["nodes"] if n["id"] in connected_node_ids
    ]

    return {
        "node": node,
        "connections": connected_edges,
        "connected_nodes": connected_nodes,
    }
