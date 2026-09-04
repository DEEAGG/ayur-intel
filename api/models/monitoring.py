"""AYUR-INTEL — Continuous Monitoring Engine Models (Phase 14).

Monitoring configuration, change detection, alerts, and monitoring runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from api.models.models import Base, _uuid, _now_utc


class MonitoringConfig(Base):
    """Monitoring configuration for a Product Case."""

    __tablename__ = "monitoring_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    enabled = Column(Boolean, nullable=False, default=True)
    frequency = Column(String(20), nullable=False, default="WEEKLY")
    # DAILY, WEEKLY, MONTHLY

    # Monitoring scope
    patent_monitoring = Column(Boolean, nullable=False, default=True)
    regulatory_monitoring = Column(Boolean, nullable=False, default=True)
    jurisdiction_monitoring = Column(Boolean, nullable=False, default=True)
    source_monitoring = Column(Boolean, nullable=False, default=False)

    # State
    last_checked_at = Column(DateTime, nullable=True)
    last_successful_check_at = Column(DateTime, nullable=True)
    total_alerts = Column(Integer, nullable=False, default=0)
    unresolved_alerts = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
    sources = relationship("MonitoringSource", back_populates="config", lazy="selectin")
    runs = relationship("MonitoringRun", back_populates="config", lazy="selectin")


class MonitoringSource(Base):
    """A source being monitored for a Product Case."""

    __tablename__ = "monitoring_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    config_id = Column(Integer, ForeignKey("monitoring_configs.id"), nullable=False)
    source_name = Column(String(200), nullable=False)
    source_type = Column(String(50), nullable=False)
    # PATENT, REGULATORY, JURISDICTION, TK, SCIENTIFIC
    jurisdiction = Column(String(50), nullable=True)

    # State tracking
    last_checked_at = Column(DateTime, nullable=True)
    last_successful_check_at = Column(DateTime, nullable=True)
    last_known_version = Column(String(100), nullable=True)
    last_known_hash = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    # ACTIVE, UNAVAILABLE, ERROR

    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    config = relationship("MonitoringConfig", back_populates="sources")


class MonitoringRun(Base):
    """A single monitoring run for a Product Case."""

    __tablename__ = "monitoring_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    config_id = Column(Integer, ForeignKey("monitoring_configs.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    started_at = Column(DateTime, nullable=False, default=_now_utc)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="RUNNING")
    # RUNNING, SUCCESS, PARTIAL, FAILED

    sources_checked = Column(Integer, nullable=False, default=0)
    changes_detected = Column(Integer, nullable=False, default=0)
    alerts_created = Column(Integer, nullable=False, default=0)
    errors = Column(Text, nullable=True)  # JSON list of error messages

    created_at = Column(DateTime, nullable=False, default=_now_utc)

    config = relationship("MonitoringConfig", back_populates="runs")
    changes = relationship("ChangeRecord", back_populates="run", lazy="selectin")


class ChangeRecord(Base):
    """A detected change in a monitored source."""

    __tablename__ = "change_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    run_id = Column(Integer, ForeignKey("monitoring_runs.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)

    source_name = Column(String(200), nullable=True)
    source_type = Column(String(50), nullable=True)
    jurisdiction = Column(String(50), nullable=True)

    change_type = Column(String(50), nullable=False)
    # NEW_PUBLICATION, VERSION_UPDATE, STATUS_CHANGE, CONTENT_CHANGE,
    # REGULATORY_AMENDMENT, NEW_REGULATION, SOURCE_UNAVAILABLE

    previous_state = Column(Text, nullable=True)  # JSON snapshot
    current_state = Column(Text, nullable=True)  # JSON snapshot
    change_description = Column(Text, nullable=True)

    relevance = Column(String(20), nullable=False, default="UNKNOWN")
    # HIGH, MEDIUM, LOW, NOT_RELEVANT, UNKNOWN
    relevance_explanation = Column(Text, nullable=True)

    detected_at = Column(DateTime, nullable=False, default=_now_utc)
    created_at = Column(DateTime, nullable=False, default=_now_utc)

    run = relationship("MonitoringRun", back_populates="changes")


class Alert(Base):
    """An alert generated from a detected change."""

    __tablename__ = "monitoring_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_case_id = Column(Integer, ForeignKey("product_cases.id"), nullable=False)
    change_record_id = Column(Integer, ForeignKey("change_records.id"), nullable=True)

    # Alert classification
    alert_type = Column(String(50), nullable=False)
    # NEW_PATENT, PATENT_UPDATE, REGULATORY_UPDATE,
    # JURISDICTION_UPDATE, SOURCE_UPDATE, MONITORING_FAILURE
    severity = Column(String(10), nullable=False, default="INFO")
    # HIGH, MEDIUM, LOW, INFO
    relevance = Column(String(20), nullable=False, default="UNKNOWN")
    # HIGH, MEDIUM, LOW, NOT_RELEVANT, UNKNOWN

    # Content
    title = Column(String(300), nullable=False)
    summary = Column(Text, nullable=True)
    source_name = Column(String(200), nullable=True)
    jurisdiction = Column(String(50), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="NEW")
    # NEW, SEEN, UNDER_REVIEW, RESOLVED, DISMISSED

    # Links
    evidence_id = Column(String(100), nullable=True)  # public_id of UnifiedEvidence
    risk_id = Column(String(100), nullable=True)  # public_id of Risk

    detected_at = Column(DateTime, nullable=False, default=_now_utc)
    created_at = Column(DateTime, nullable=False, default=_now_utc)
    updated_at = Column(DateTime, nullable=False, default=_now_utc, onupdate=_now_utc)

    owner = relationship("User", lazy="selectin")
    product_case = relationship("ProductCase", lazy="selectin")
