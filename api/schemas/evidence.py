"""AYUR-INTEL — Evidence & Citation Schemas (Phase 11)."""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class EvidenceResponse(BaseModel):
    id: str
    evidence_type: str
    title: Optional[str] = None
    reference: Optional[str] = None
    excerpt: Optional[str] = None
    description: Optional[str] = None
    source_name: Optional[str] = None
    authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    quality: Optional[str] = None
    confidence: Optional[str] = None
    data_origin: Optional[str] = None
    publication_date: Optional[str] = None
    version: Optional[str] = None
    retrieved_at: Optional[str] = None
    source_url: Optional[str] = None
    created_at: str


class FindingEvidenceLink(BaseModel):
    id: str
    evidence_id: str
    relationship_type: str
    evidence: EvidenceResponse


class FindingResponse(BaseModel):
    id: str
    finding_type: str
    source_phase: str
    title: str
    content: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    status: str
    confidence: Optional[str] = None
    data_origin: Optional[str] = None
    evidence_count: int
    has_conflicts: bool
    is_unsupported: bool
    citations: List[FindingEvidenceLink]
    created_at: str


class CaseEvidenceSummary(BaseModel):
    total_findings: int
    findings_with_evidence: int
    citation_coverage: float  # percentage
    total_evidence: int
    unsupported_count: int
    conflicting_count: int
    findings: List[FindingResponse]


class CreateEvidenceRequest(BaseModel):
    evidence_type: str
    title: Optional[str] = None
    reference: Optional[str] = None
    excerpt: Optional[str] = None
    description: Optional[str] = None
    source_name: Optional[str] = None
    authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    quality: Optional[str] = None
    confidence: Optional[str] = None
    data_origin: Optional[str] = None
    publication_date: Optional[str] = None


class LinkFindingEvidenceRequest(BaseModel):
    evidence_id: str
    relationship_type: str = "SUPPORTS"


class CreateFindingRequest(BaseModel):
    finding_type: str
    source_phase: str
    title: str
    content: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    data_origin: Optional[str] = None
    confidence: Optional[str] = None
