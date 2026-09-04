"""AYUR-INTEL — Continuous Monitoring Service (Phase 14).

Simulates monitoring checks against configured sources.
Since no live sources are configured, creates demo monitoring runs
with simulated change detection to demonstrate the architecture.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from api.models.models import User, ProductCase, Source
from api.models.monitoring import (
    MonitoringConfig, MonitoringSource, MonitoringRun, ChangeRecord, Alert,
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


def _get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _get_case(db: Session, user: User, case_public_id: str) -> Optional[ProductCase]:
    return (
        db.query(ProductCase)
        .filter(ProductCase.public_id == case_public_id, ProductCase.owner_id == user.id)
        .first()
    )


# ---------------------------------------------------------------------------
# Configuration
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
            source_monitoring=False,
        )
        db.add(config)
        db.flush()

        # Create default monitoring sources
        _setup_default_sources(db, config)

    return config


def _setup_default_sources(db: Session, config: MonitoringConfig):
    """Set up default monitoring sources based on the product case."""
    case = config.product_case
    jurisdictions = _deserialize(case.jurisdictions) if case else []

    # Patent sources
    patent_sources = [
        {"name": "IP India Patents", "type": "PATENT", "jurisdiction": "IN"},
        {"name": "WIPO PatentScope", "type": "PATENT", "jurisdiction": "GLOBAL"},
        {"name": "EPO Open Patent Services", "type": "PATENT", "jurisdiction": "EU"},
        {"name": "USPTO Full-Text", "type": "PATENT", "jurisdiction": "US"},
    ]

    # Regulatory sources
    reg_sources = [
        {"name": "Ministry of Ayush", "type": "REGULATORY", "jurisdiction": "IN"},
        {"name": "EU Herbal Directive", "type": "REGULATORY", "jurisdiction": "EU"},
        {"name": "US FDA Dietary Supplements", "type": "REGULATORY", "jurisdiction": "US"},
        {"name": "BfArM Germany", "type": "REGULATORY", "jurisdiction": "DE"},
    ]

    all_sources = patent_sources + reg_sources
    for src in all_sources:
        ms = MonitoringSource(
            config_id=config.id,
            source_name=src["name"],
            source_type=src["type"],
            jurisdiction=src["jurisdiction"],
            status="ACTIVE",
        )
        db.add(ms)

    db.flush()


def update_config(db: Session, user: User, case_public_id: str, updates: dict) -> Optional[dict]:
    """Update monitoring configuration."""
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    config = get_or_create_config(db, user, case)

    if "enabled" in updates:
        config.enabled = updates["enabled"]
    if "frequency" in updates:
        config.frequency = updates["frequency"]
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


# ---------------------------------------------------------------------------
# Manual monitoring run
# ---------------------------------------------------------------------------

def run_monitoring_check(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Execute a manual monitoring check for a Product Case.

    Since no live sources are configured, this creates a simulated run
    that demonstrates the monitoring architecture.
    """
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    config = get_or_create_config(db, user, case)

    # Create monitoring run
    run = MonitoringRun(
        config_id=config.id,
        product_case_id=case.id,
        started_at=datetime.now(timezone.utc),
        status="RUNNING",
    )
    db.add(run)
    db.flush()

    sources_checked = 0
    changes_detected = 0
    alerts_created = 0
    errors = []

    # Check each monitoring source
    monitoring_sources = db.query(MonitoringSource).filter(
        MonitoringSource.config_id == config.id
    ).all()

    for ms in monitoring_sources:
        sources_checked += 1

        # Check if the source type monitoring is enabled
        if ms.source_type == "PATENT" and not config.patent_monitoring:
            continue
        if ms.source_type == "REGULATORY" and not config.regulatory_monitoring:
            continue

        # Simulate source check — no live sources configured
        # In production, this would query actual patent/regulatory APIs
        try:
            # Mark as checked
            ms.last_checked_at = datetime.now(timezone.utc)
            ms.last_successful_check_at = datetime.now(timezone.utc)
            ms.status = "ACTIVE"

            # Simulate: no changes detected from unconfigured sources
            # The architecture is ready for live source integration

        except Exception as e:
            ms.status = "ERROR"
            errors.append(f"Error checking {ms.source_name}: {str(e)}")

            # Create monitoring failure alert
            alert = Alert(
                owner_id=user.id,
                product_case_id=case.id,
                alert_type="MONITORING_FAILURE",
                severity="LOW",
                relevance="UNKNOWN",
                title=f"Source check failed: {ms.source_name}",
                summary=f"Unable to verify source update for {ms.source_name}. Source may be unavailable or not configured.",
                source_name=ms.source_name,
                jurisdiction=ms.jurisdiction,
                status="NEW",
            )
            db.add(alert)
            alerts_created += 1

    # Update run
    run.completed_at = datetime.now(timezone.utc)
    run.status = "SUCCESS" if not errors else ("PARTIAL" if errors else "SUCCESS")
    run.sources_checked = sources_checked
    run.changes_detected = changes_detected
    run.alerts_created = alerts_created
    run.errors = json.dumps(errors) if errors else None

    # Update config timestamps
    config.last_checked_at = datetime.now(timezone.utc)
    config.last_successful_check_at = datetime.now(timezone.utc)
    config.total_alerts += alerts_created

    # Count unresolved alerts
    unresolved = db.query(Alert).filter(
        Alert.product_case_id == case.id,
        Alert.status.in_(["NEW", "SEEN", "UNDER_REVIEW"]),
    ).count()
    config.unresolved_alerts = unresolved

    db.commit()

    return {
        "run_id": run.public_id,
        "status": run.status,
        "sources_checked": sources_checked,
        "changes_detected": changes_detected,
        "alerts_created": alerts_created,
        "errors": errors,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


# ---------------------------------------------------------------------------
# Alert management
# ---------------------------------------------------------------------------

def get_monitoring_summary(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Get monitoring summary for a Product Case."""
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    config = get_or_create_config(db, user, case)

    # Get recent alerts
    alerts = (
        db.query(Alert)
        .filter(Alert.product_case_id == case.id)
        .order_by(Alert.created_at.desc())
        .limit(20)
        .all()
    )

    # Get recent runs
    runs = (
        db.query(MonitoringRun)
        .filter(MonitoringRun.product_case_id == case.id)
        .order_by(MonitoringRun.created_at.desc())
        .limit(10)
        .all()
    )

    # Count alerts
    all_alerts = db.query(Alert).filter(Alert.product_case_id == case.id).all()
    new_count = sum(1 for a in all_alerts if a.status == "NEW")
    high_count = sum(1 for a in all_alerts if a.severity == "HIGH")
    medium_count = sum(1 for a in all_alerts if a.severity == "MEDIUM")

    return {
        "product_case_id": case.public_id,
        "product_name": case.name,
        "config": _config_to_dict(config),
        "recent_alerts": [_alert_to_dict(a) for a in alerts],
        "recent_runs": [_run_to_dict(r) for r in runs],
        "total_alerts": len(all_alerts),
        "new_alerts": new_count,
        "high_alerts": high_count,
        "medium_alerts": medium_count,
    }


def get_monitoring_history(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Get monitoring history for a Product Case."""
    case = _get_case(db, user, case_public_id)
    if not case:
        return None

    runs = (
        db.query(MonitoringRun)
        .filter(MonitoringRun.product_case_id == case.id)
        .order_by(MonitoringRun.created_at.desc())
        .limit(50)
        .all()
    )

    changes = (
        db.query(ChangeRecord)
        .filter(ChangeRecord.product_case_id == case.id)
        .order_by(ChangeRecord.detected_at.desc())
        .limit(50)
        .all()
    )

    alerts = (
        db.query(Alert)
        .filter(Alert.product_case_id == case.id)
        .order_by(Alert.created_at.desc())
        .limit(50)
        .all()
    )

    return {
        "product_case_id": case.public_id,
        "runs": [_run_to_dict(r) for r in runs],
        "changes": [{
            "id": c.public_id,
            "source_name": c.source_name,
            "change_type": c.change_type,
            "relevance": c.relevance,
            "change_description": c.change_description,
            "detected_at": c.detected_at.isoformat() if c.detected_at else "",
        } for c in changes],
        "alerts": [_alert_to_dict(a) for a in alerts],
    }


def update_alert_status(db: Session, user: User, alert_public_id: str, status: str) -> Optional[dict]:
    """Update an alert's status."""
    alert = db.query(Alert).filter(Alert.public_id == alert_public_id).first()
    if not alert:
        return None
    if alert.owner_id != user.id:
        return None

    alert.status = status
    alert.updated_at = datetime.now(timezone.utc)
    db.commit()

    # Update config unresolved count
    config = db.query(MonitoringConfig).filter(
        MonitoringConfig.product_case_id == alert.product_case_id
    ).first()
    if config:
        unresolved = db.query(Alert).filter(
            Alert.product_case_id == alert.product_case_id,
            Alert.status.in_(["NEW", "SEEN", "UNDER_REVIEW"]),
        ).count()
        config.unresolved_alerts = unresolved
        db.commit()

    return {"id": alert.public_id, "status": alert.status, "message": f"Alert status updated to {status}"}


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
