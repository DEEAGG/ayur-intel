"""AYUR-INTEL — Continuous Monitoring Service.

Provides real, evidence-backed monitoring signal detection, deduplication, summary counts,
and state-driven action timelines for selected product cases.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.models.models import User, ProductCase, KnowledgeEvidence, PatentSearch, PatentRelevance, PatentRecord
from api.models.monitoring import (
    MonitoringConfig, MonitoringSource, MonitoringRun, Alert,
)

logger = logging.getLogger("ayur_intel.monitoring_service")


def _deserialize(value) -> list:
    if not value:
        return []
    try:
        result = json.loads(value) if isinstance(value, str) else value
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _get_case(db: Session, user: User, case_public_id: str) -> Optional[ProductCase]:
    """Retrieve ProductCase with owner or demo access check."""
    conds = [ProductCase.public_id == case_public_id]
    if str(case_public_id).isdigit():
        conds.append(ProductCase.id == int(case_public_id))
    return (
        db.query(ProductCase)
        .filter(
            or_(*conds),
            or_(
                ProductCase.owner_id == user.id,
                ProductCase.is_demo == True,
                ProductCase.public_id == "demo-001",
            ),
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Configuration Management
# ---------------------------------------------------------------------------

def get_or_create_config(db: Session, user: User, case: ProductCase) -> MonitoringConfig:
    """Get or create monitoring configuration for a Product Case."""
    config = (
        db.query(MonitoringConfig)
        .filter(
            MonitoringConfig.product_case_id == case.id,
            MonitoringConfig.owner_id == user.id,
        )
        .first()
    )
    if not config:
        config = MonitoringConfig(
            owner_id=user.id,
            product_case_id=case.id,
            enabled=True,
            frequency="WEEKLY",
            patent_monitoring=True,
            regulatory_monitoring=True,
            jurisdiction_monitoring=True,
            source_monitoring=True,
        )
        db.add(config)
        db.flush()
    return config


def update_config(db: Session, user: User, case_public_id: str, updates: dict) -> Optional[dict]:
    """Update monitoring configuration."""
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    config = get_or_create_config(db, user, case)

    if "enabled" in updates:
        config.enabled = updates["enabled"]
    if "patent_monitoring" in updates:
        config.patent_monitoring = updates["patent_monitoring"]
    if "regulatory_monitoring" in updates:
        config.regulatory_monitoring = updates["regulatory_monitoring"]
    if "jurisdiction_monitoring" in updates:
        config.jurisdiction_monitoring = updates["jurisdiction_monitoring"]
    if "source_monitoring" in updates:
        config.source_monitoring = updates["source_monitoring"]

    config.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _config_to_dict(config)


def _config_to_dict(config: MonitoringConfig) -> dict:
    return {
        "id": config.public_id,
        "enabled": config.enabled,
        "patent_monitoring": config.patent_monitoring,
        "regulatory_monitoring": config.regulatory_monitoring,
        "jurisdiction_monitoring": config.jurisdiction_monitoring,
        "source_monitoring": config.source_monitoring,
        "last_checked_at": config.last_checked_at.isoformat() if config.last_checked_at else None,
        "unresolved_alerts": config.unresolved_alerts,
    }


# ---------------------------------------------------------------------------
# Signal Detection & Synchronization Logic
# ---------------------------------------------------------------------------

def _sync_monitoring_signals(db: Session, user: User, case: ProductCase, config: MonitoringConfig) -> int:
    """Detect new, un-alerted evidence records for the selected product and create Alerts."""
    created_count = 0

    # 1. Patent Literature Signals
    if config.patent_monitoring:
        patent_relevances = (
            db.query(PatentRelevance)
            .filter(PatentRelevance.product_case_id == case.id)
            .all()
        )
        for rel in patent_relevances:
            pat = rel.patent_record
            if not pat:
                continue
            pat_num = pat.publication_number or pat.application_number or pat.provider_record_id or f"PAT-{pat.id}"
            if not pat_num:
                continue

            # Check if alert already exists for this case + patent
            existing = (
                db.query(Alert)
                .filter(
                    Alert.product_case_id == case.id,
                    Alert.alert_type == "PATENT",
                    or_(Alert.evidence_id == pat_num, Alert.title.ilike(f"%{pat_num}%")),
                )
                .first()
            )
            if not existing:
                score = rel.relevance_score or 70
                pat_title = pat.title or "Prior Art Patent Record"
                assignee = pat.applicant or pat.jurisdiction or "verified patent evidence"
                abstract = pat.abstract or "Disclosed patent specification relating to formulation."

                alert = Alert(
                    owner_id=user.id,
                    product_case_id=case.id,
                    alert_type="PATENT",
                    severity="HIGH" if score >= 80 else "MEDIUM",
                    relevance="HIGH" if score >= 80 else "MEDIUM",
                    title=f"Potentially relevant patent record detected: {pat_num}",
                    summary=f"{pat_title} — {abstract[:140]}...",
                    source_name=f"{assignee}",
                    jurisdiction=pat.jurisdiction or "IN",
                    status="NEW",
                    evidence_id=pat_num,
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(alert)
                created_count += 1

    # Extract ingredient names for research matching
    raw_ings = _deserialize(case.ingredients)
    ing_names = []
    for ing in raw_ings:
        if isinstance(ing, str):
            ing_names.append(ing.strip())
        elif isinstance(ing, dict):
            n = ing.get("name") or ing.get("input_name") or ing.get("botanical_name")
            if n:
                ing_names.append(str(n).strip())

    if not ing_names:
        ing_names = [case.name or "Ayurvedic Formulation"]

    # 2. Research Evidence Signals
    if config.source_monitoring or config.patent_monitoring or config.regulatory_monitoring:
        filters = []
        for name in ing_names[:4]:
            filters.append(KnowledgeEvidence.excerpt.ilike(f"%{name}%"))
            filters.append(KnowledgeEvidence.title.ilike(f"%{name}%"))

        if filters:
            ev_records = (
                db.query(KnowledgeEvidence)
                .filter(or_(*filters))
                .limit(5)
                .all()
            )
            for ev in ev_records:
                existing = (
                    db.query(Alert)
                    .filter(
                        Alert.product_case_id == case.id,
                        Alert.alert_type == "RESEARCH",
                        Alert.evidence_id == str(ev.public_id or ev.id),
                    )
                    .first()
                )
                if not existing:
                    alert = Alert(
                        owner_id=user.id,
                        product_case_id=case.id,
                        alert_type="RESEARCH",
                        severity="INFO",
                        relevance="HIGH",
                        title=f"Research evidence record available: {ev.title or 'Scientific Monograph'}",
                        summary=f"Excerpt: {(ev.excerpt or '')[:140]}...",
                        source_name=ev.source_identifier or "AYUR-INTEL Hub",
                        status="NEW",
                        evidence_id=str(ev.public_id or ev.id),
                        detected_at=datetime.now(timezone.utc),
                    )
                    db.add(alert)
                    created_count += 1

    # 3. Regulatory Signals
    if config.regulatory_monitoring:
        reg_records = (
            db.query(KnowledgeEvidence)
            .filter(
                or_(
                    KnowledgeEvidence.title.ilike("%AYUSH%"),
                    KnowledgeEvidence.title.ilike("%FSSAI%"),
                    KnowledgeEvidence.excerpt.ilike("%AYUSH%"),
                    KnowledgeEvidence.excerpt.ilike("%FSSAI%"),
                )
            )
            .limit(3)
            .all()
        )
        for reg in reg_records:
            existing = (
                db.query(Alert)
                .filter(
                    Alert.product_case_id == case.id,
                    Alert.alert_type == "REGULATORY",
                    Alert.evidence_id == str(reg.public_id or reg.id),
                )
                .first()
            )
            if not existing:
                alert = Alert(
                    owner_id=user.id,
                    product_case_id=case.id,
                    alert_type="REGULATORY",
                    severity="INFO",
                    relevance="HIGH",
                    title=f"Relevant regulatory guidance source available: {reg.title or 'AYUSH Regulatory Document'}",
                    summary=f"Excerpt: {(reg.excerpt or '')[:140]}...",
                    source_name=reg.source_identifier or "Ministry of Ayush / FSSAI",
                    status="NEW",
                    evidence_id=str(reg.public_id or reg.id),
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(alert)
                created_count += 1

    if created_count > 0:
        db.flush()
    return created_count


# ---------------------------------------------------------------------------
# Manual Check for Updates
# ---------------------------------------------------------------------------

def run_monitoring_check(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Execute a manual monitoring check for the selected Product Case."""
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    config = get_or_create_config(db, user, case)

    # Sync signals against current persisted evidence
    created_count = _sync_monitoring_signals(db, user, case, config)

    # Record monitoring run
    run = MonitoringRun(
        config_id=config.id,
        product_case_id=case.id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status="SUCCESS",
        sources_checked=3,
        changes_detected=created_count,
        alerts_created=created_count,
    )
    db.add(run)

    config.last_checked_at = datetime.now(timezone.utc)
    config.last_successful_check_at = datetime.now(timezone.utc)
    config.total_alerts = db.query(Alert).filter(Alert.product_case_id == case.id).count()
    config.unresolved_alerts = db.query(Alert).filter(
        Alert.product_case_id == case.id,
        Alert.status.in_(["NEW", "SEEN", "UNDER_REVIEW"]),
    ).count()

    db.commit()

    return {
        "success": True,
        "run_id": run.public_id,
        "status": "SUCCESS",
        "sources_checked": 3,
        "changes_detected": created_count,
        "alerts_created": created_count,
        "completed_at": run.completed_at.isoformat(),
        "summary": get_monitoring_summary(db, user, case_public_id),
    }


# ---------------------------------------------------------------------------
# Monitoring Summary & Next Action Timeline
# ---------------------------------------------------------------------------

def _alert_to_dict(alert: Alert) -> dict:
    next_step = "Review source details and evidence."
    if alert.alert_type == "PATENT":
        next_step = "Review overlap and evidence in Patent Intelligence."
    elif alert.alert_type == "RESEARCH":
        next_step = "Review source evidence and relevance in Knowledge Hub."
    elif alert.alert_type == "REGULATORY":
        next_step = "Review the official source before making product/regulatory decisions."

    return {
        "id": alert.public_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "summary": alert.summary,
        "source_name": alert.source_name or "AYUR-INTEL Source",
        "jurisdiction": alert.jurisdiction or "IN",
        "status": alert.status or "NEW",
        "evidence_id": alert.evidence_id,
        "next_step": next_step,
        "detected_at": alert.detected_at.isoformat() if alert.detected_at else "",
    }


def _build_next_actions_timeline(case: ProductCase, patent_search_done: bool, alerts: List[Alert]) -> List[dict]:
    """Generate deterministic vertical timeline for selected product state."""
    raw_ings = _deserialize(case.ingredients)
    passport_complete = bool(raw_ings and len(raw_ings) > 0)

    unreviewed_patent = sum(1 for a in alerts if a.alert_type == "PATENT" and a.status == "NEW")
    total_patent = sum(1 for a in alerts if a.alert_type == "PATENT")

    unreviewed_research = sum(1 for a in alerts if a.alert_type == "RESEARCH" and a.status == "NEW")
    total_research = sum(1 for a in alerts if a.alert_type == "RESEARCH")

    unreviewed_reg = sum(1 for a in alerts if a.alert_type == "REGULATORY" and a.status == "NEW")
    total_reg = sum(1 for a in alerts if a.alert_type == "REGULATORY")

    timeline = []

    # 1. Product Passport
    timeline.append({
        "step": 1,
        "title": "Product Passport",
        "desc": "Define botanical ingredients, dosage form, and intended use.",
        "status": "Completed" if passport_complete else "Next",
        "action": "Open Passport" if not passport_complete else None,
        "module": "passport-wizard",
    })

    # 2. Patent Intelligence Screening
    step2_status = "Completed" if patent_search_done else ("Next" if passport_complete else "Pending")
    timeline.append({
        "step": 2,
        "title": "Patent Intelligence Screening",
        "desc": "Screen Indian and international patent literature for prior art.",
        "status": step2_status,
        "action": "Run Patent Search" if step2_status == "Next" else None,
        "module": "patent-intelligence",
    })

    # 3. Review Patent Signals
    if unreviewed_patent > 0:
        step3_status = "Next"
    elif total_patent > 0 and unreviewed_patent == 0:
        step3_status = "Completed"
    else:
        step3_status = "Pending"

    timeline.append({
        "step": 3,
        "title": "Review Patent Signals",
        "desc": f"{unreviewed_patent} unreviewed patent signal(s) detected." if unreviewed_patent else "Assess potential prior art disclosures and patent overlaps.",
        "status": step3_status,
        "action": "Open Patent Intelligence" if step3_status != "Pending" else None,
        "module": "patent-intelligence",
    })

    # 4. Review Research Evidence
    if unreviewed_research > 0:
        step4_status = "Next"
    elif total_research > 0 and unreviewed_research == 0:
        step4_status = "Completed"
    else:
        step4_status = "Pending"

    timeline.append({
        "step": 4,
        "title": "Review Research Evidence",
        "desc": f"{unreviewed_research} unreviewed supporting evidence record(s)." if unreviewed_research else "Evaluate classical literature and scientific evidence in Knowledge Hub.",
        "status": step4_status,
        "action": "Open Knowledge Hub" if step4_status != "Pending" else None,
        "module": "knowledge-hub",
    })

    # 5. Confirm Regulatory Pathway
    if unreviewed_reg > 0:
        step5_status = "Next"
    elif total_reg > 0 and unreviewed_reg == 0:
        step5_status = "Completed"
    else:
        step5_status = "Pending"

    timeline.append({
        "step": 5,
        "title": "Confirm Regulatory Pathway",
        "desc": "Review AYUSH and FSSAI pharmacopoeial standards.",
        "status": step5_status,
        "action": "Review Guidance" if step5_status != "Pending" else None,
        "module": "case-detail",
    })

    # 6. Check for Future Updates
    all_done = passport_complete and patent_search_done and unreviewed_patent == 0 and unreviewed_research == 0 and unreviewed_reg == 0
    timeline.append({
        "step": 6,
        "title": "Check for Future Updates",
        "desc": "Run periodic checks for newly published patents or regulatory updates.",
        "status": "Next" if all_done else "Pending",
        "action": "Check for Updates" if all_done else None,
        "module": "monitoring-center",
    })

    return timeline


def get_monitoring_summary(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Get monitoring summary for a Product Case."""
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    config = get_or_create_config(db, user, case)

    # Auto-seed initial signals if none exist yet
    alerts = (
        db.query(Alert)
        .filter(Alert.product_case_id == case.id)
        .order_by(Alert.detected_at.desc(), Alert.created_at.desc())
        .all()
    )
    if not alerts:
        _sync_monitoring_signals(db, user, case, config)
        db.commit()
        alerts = (
            db.query(Alert)
            .filter(Alert.product_case_id == case.id)
            .order_by(Alert.detected_at.desc(), Alert.created_at.desc())
            .all()
        )

    patent_search = (
        db.query(PatentSearch)
        .filter(PatentSearch.product_case_id == case.id)
        .first()
    )
    patent_search_done = patent_search is not None

    # Real counts
    new_count = sum(1 for a in alerts if a.status == "NEW")
    patent_count = sum(1 for a in alerts if a.alert_type == "PATENT")
    research_count = sum(1 for a in alerts if a.alert_type == "RESEARCH")
    regulatory_count = sum(1 for a in alerts if a.alert_type == "REGULATORY")

    timeline = _build_next_actions_timeline(case, patent_search_done, alerts)

    return {
        "product_case_id": case.public_id,
        "product_name": case.name or "Unnamed Product",
        "config": _config_to_dict(config),
        "signals": [_alert_to_dict(a) for a in alerts],
        "total_signals": len(alerts),
        "new_signals": new_count,
        "patent_signals": patent_count,
        "research_signals": research_count,
        "regulatory_signals": regulatory_count,
        "timeline": timeline,
    }


def get_monitoring_history(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Get monitoring history for a Product Case."""
    return get_monitoring_summary(db, user, case_public_id)


def update_alert_status(db: Session, user: User, alert_public_id: str, status: str) -> Optional[dict]:
    """Update an alert's status (e.g. REVIEWED, SEEN)."""
    alert = db.query(Alert).filter(Alert.public_id == alert_public_id).first()
    if not alert:
        return None

    # Access check on case
    case = db.query(ProductCase).filter(ProductCase.id == alert.product_case_id).first()
    if case and not (case.owner_id == user.id or case.is_demo or case.public_id == "demo-001"):
        return None

    alert.status = status.upper()
    alert.updated_at = datetime.now(timezone.utc)

    # Update config unresolved count
    if case:
        config = get_or_create_config(db, user, case)
        config.unresolved_alerts = db.query(Alert).filter(
            Alert.product_case_id == case.id,
            Alert.status.in_(["NEW", "SEEN", "UNDER_REVIEW"]),
        ).count()

    db.commit()
    return _alert_to_dict(alert)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _config_to_dict(config: MonitoringConfig) -> dict:
    return {
        "id": config.public_id,
        "enabled": config.enabled,
        "frequency": config.frequency,
        "patent_monitoring": config.patent_monitoring,
        "regulatory_monitoring": config.regulatory_monitoring,
        "jurisdiction_monitoring": config.jurisdiction_monitoring,
        "source_monitoring": config.source_monitoring,
        "last_checked_at": config.last_checked_at.isoformat() if config.last_checked_at else None,
        "last_successful_check_at": config.last_successful_check_at.isoformat() if config.last_successful_check_at else None,
        "total_alerts": config.total_alerts,
        "unresolved_alerts": config.unresolved_alerts,
        "created_at": config.created_at.isoformat() if config.created_at else "",
        "updated_at": config.updated_at.isoformat() if config.updated_at else "",
    }


def _alert_to_dict(alert: Alert) -> dict:
    return {
        "id": alert.public_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "relevance": alert.relevance,
        "title": alert.title,
        "summary": alert.summary,
        "source_name": alert.source_name,
        "jurisdiction": alert.jurisdiction,
        "status": alert.status,
        "evidence_id": alert.evidence_id,
        "risk_id": alert.risk_id,
        "detected_at": alert.detected_at.isoformat() if alert.detected_at else "",
        "created_at": alert.created_at.isoformat() if alert.created_at else "",
    }


def _run_to_dict(run: MonitoringRun) -> dict:
    errors = None
    if run.errors:
        try:
            errors = json.loads(run.errors)
        except (json.JSONDecodeError, TypeError):
            errors = [run.errors]

    return {
        "id": run.public_id,
        "status": run.status,
        "sources_checked": run.sources_checked,
        "changes_detected": run.changes_detected,
        "alerts_created": run.alerts_created,
        "started_at": run.started_at.isoformat() if run.started_at else "",
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "errors": errors,
    }
