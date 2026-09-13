"""AYUR-INTEL — Monitoring Schemas (Phase 14)."""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class MonitoringConfigResponse(BaseModel):
    id: str
    enabled: bool
    frequency: str
    patent_monitoring: bool
    regulatory_monitoring: bool
    jurisdiction_monitoring: bool
    source_monitoring: bool
    last_checked_at: Optional[str] = None
    last_successful_check_at: Optional[str] = None
    total_alerts: int
    unresolved_alerts: int
    created_at: str
    updated_at: str


class UpdateMonitoringConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    frequency: Optional[str] = None
    patent_monitoring: Optional[bool] = None
    regulatory_monitoring: Optional[bool] = None
    jurisdiction_monitoring: Optional[bool] = None
    source_monitoring: Optional[bool] = None


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    severity: str
    relevance: str
    title: str
    summary: Optional[str] = None
    source_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    status: str
    evidence_id: Optional[str] = None
    risk_id: Optional[str] = None
    detected_at: str
    created_at: str


class UpdateAlertRequest(BaseModel):
    status: str


class MonitoringRunResponse(BaseModel):
    id: str
    status: str
    sources_checked: int
    changes_detected: int
    alerts_created: int
    started_at: str
    completed_at: Optional[str] = None
    errors: Optional[List[str]] = None


class MonitoringSummaryResponse(BaseModel):
    product_case_id: str
    product_name: Optional[str] = None
    config: MonitoringConfigResponse
    recent_alerts: List[AlertResponse]
    recent_runs: List[MonitoringRunResponse]
    total_alerts: int
    new_alerts: int
    high_alerts: int
    medium_alerts: int


class MonitoringHistoryResponse(BaseModel):
    product_case_id: str
    runs: List[MonitoringRunResponse]
    changes: List[dict]
    alerts: List[AlertResponse]
