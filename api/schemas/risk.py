"""AYUR-INTEL — Risk + Self-Extension Schemas (Phase 12)."""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class RiskEvidenceResponse(BaseModel):
    id: str
    evidence_type: Optional[str] = None
    evidence_title: Optional[str] = None
    evidence_reference: Optional[str] = None
    evidence_description: Optional[str] = None
    evidence_source_name: Optional[str] = None
    evidence_authority: Optional[str] = None
    evidence_jurisdiction: Optional[str] = None
    relationship_type: str


class RiskResponse(BaseModel):
    id: str
    category: str
    level: str
    title: str
    description: Optional[str] = None
    affected_component_type: Optional[str] = None
    affected_component_label: Optional[str] = None
    confidence: Optional[str] = None
    data_origin: Optional[str] = None
    evidence_summary: Optional[str] = None
    missing_information: Optional[str] = None
    next_action: Optional[str] = None
    source_phase: Optional[str] = None
    status: str
    evidence: List[RiskEvidenceResponse]
    created_at: str
    updated_at: str


class SelfExtensionResponse(BaseModel):
    id: str
    type: str
    title: str
    description: Optional[str] = None
    why_needed: Optional[str] = None
    priority: str
    status: str
    related_component_type: Optional[str] = None
    suggested_action: Optional[str] = None
    resolve_url: Optional[str] = None
    created_at: str


class AnalysisHealthResponse(BaseModel):
    product_completeness: str  # GOOD, PARTIAL, LIMITED
    evidence_coverage: float
    patent_analysis: str
    regulatory_coverage: str
    jurisdiction_coverage: str
    overall_health: str


class RiskAnalysisResponse(BaseModel):
    product_case_id: str
    product_name: Optional[str] = None
    risks: List[RiskResponse]
    self_extensions: List[SelfExtensionResponse]
    analysis_health: AnalysisHealthResponse
    total_risks: int
    high_count: int
    medium_count: int
    low_count: int
    unknown_count: int
    open_count: int
    total_extensions: int
    created_at: str


class UpdateRiskStatusRequest(BaseModel):
    status: str
    note: Optional[str] = None


class UpdateExtensionStatusRequest(BaseModel):
    status: str


class EvidenceRef(BaseModel):
    source_type: str  # passport | patent | regulatory | knowledge | innovation
    reference_key: str
    label: Optional[str] = None


class OverallRisk(BaseModel):
    score: int  # 0-100
    level: str  # LOW | MODERATE | HIGH | CRITICAL
    confidence: float  # 0.0 - 1.0
    summary: str


class DomainScore(BaseModel):
    domain: str  # IP & Patent | Regulatory | Claims & Compliance | Ingredient & Formulation | Market / Commercial | Validation
    score: int
    level: str
    confidence: float
    summary: str


class TopRiskItem(BaseModel):
    id: str
    title: str
    domain: str
    severity: str  # LOW | MODERATE | HIGH | CRITICAL
    likelihood: str  # LOW | MEDIUM | HIGH
    impact: str  # LOW | MEDIUM | HIGH
    confidence: float
    why_it_matters: str
    evidence_refs: List[EvidenceRef] = []
    evidence_status: str  # SUPPORTED | PARTIAL | INFERRED | MISSING
    recommended_action: str
    requires_human_verification: bool = True


class MitigationPlan(BaseModel):
    immediate: List[str] = []
    before_regulatory_submission: List[str] = []
    before_market_launch: List[str] = []


class EvidenceCoverageStatus(BaseModel):
    product_passport: str = "Complete"
    patent_intelligence: str = "Not Run"
    regulatory_pathways: str = "Not Run"
    knowledge_evidence: str = "Not Run"
    innovation_analysis: str = "Not Run"


class RiskAssessmentResponse(BaseModel):
    id: str
    product_case_id: str
    product_name: Optional[str] = None
    assessment_source: str = "GEMINI"  # GEMINI | RULE_ENGINE
    model_used: Optional[str] = None
    schema_version: int = 1
    overall_risk: OverallRisk
    domain_scores: List[DomainScore] = []
    top_risks: List[TopRiskItem] = []
    mitigation_plan: MitigationPlan
    evidence_gaps: List[str] = []
    evidence_coverage: EvidenceCoverageStatus
    disclaimer: str
    created_at: str
    updated_at: str
