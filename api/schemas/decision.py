"""AYUR-INTEL — Decision Dashboard Schemas (Phase 13)."""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class DashboardProductSnapshot(BaseModel):
    name: str
    stage: Optional[str] = None
    status: Optional[str] = None
    form: Optional[str] = None
    intended_use: Optional[str] = None
    ingredients_count: int
    jurisdictions: List[str]
    brand: Optional[str] = None


class DashboardDecisionSummary(BaseModel):
    ip_status: str
    ip_reason: Optional[str] = None
    regulatory_status: str
    regulatory_reason: Optional[str] = None
    evidence_status: str
    evidence_coverage: float
    risk_status: str
    high_risks: int
    product_completeness_status: str
    product_completeness_pct: float


class DashboardKeyFinding(BaseModel):
    title: str
    description: Optional[str] = None
    source_phase: Optional[str] = None
    evidence_available: bool
    category: Optional[str] = None


class DashboardRiskSummary(BaseModel):
    level: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None


class DashboardInfoGap(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str
    suggested_action: Optional[str] = None


class DashboardRecommendedAction(BaseModel):
    priority: str
    title: str
    description: Optional[str] = None
    action_label: str
    action_view: Optional[str] = None


class DashboardIPSummary(BaseModel):
    innovation_components: int
    differentiated_count: int
    patent_review_status: str
    ip_strategy_items: int


class DashboardRegulatorySummary(BaseModel):
    jurisdictions_analyzed: int
    categories: List[str]
    total_requirements: int
    gaps: int


class DashboardJurisdictionItem(BaseModel):
    jurisdiction: str
    flag: Optional[str] = None
    regulatory_coverage: str
    evidence_coverage: str
    key_issue: Optional[str] = None


class DashboardReadiness(BaseModel):
    level: str  # NOT_READY, PARTIALLY_READY, REVIEW_REQUIRED, READY_FOR_NEXT_STEP
    explanation: List[str]
    next_steps: List[str]


class DecisionDashboardResponse(BaseModel):
    product_case_id: str
    product_name: Optional[str] = None
    dashboard_status: str
    last_updated: str

    product_snapshot: DashboardProductSnapshot
    decision_summary: DashboardDecisionSummary
    key_findings: List[DashboardKeyFinding]
    top_risks: List[DashboardRiskSummary]
    information_gaps: List[DashboardInfoGap]
    recommended_actions: List[DashboardRecommendedAction]
    ip_summary: DashboardIPSummary
    regulatory_summary: DashboardRegulatorySummary
    jurisdictions: List[DashboardJurisdictionItem]
    readiness: DashboardReadiness
