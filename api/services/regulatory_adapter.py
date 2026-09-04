"""AYUR-INTEL — Regulatory Source Adapter Architecture (Phase 9).

Modular source adapters for retrieving regulatory information across jurisdictions.
Each adapter is responsible for a specific authority/jurisdiction.

No live sources are configured yet. All adapters return NOT_CONFIGURED status.
Do NOT fabricate regulatory data.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("ayur_intel.regulatory_adapter")


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------

@dataclass
class RegulatorySourceInfo:
    """Metadata about a regulatory source."""
    name: str
    authority: str
    jurisdiction: str
    coverage: str  # What product types it covers
    source_type: str  # OFFICIAL, GUIDANCE, DATABASE
    configured: bool = False
    limitations: str = ""
    configuration_required: str = ""


@dataclass
class RegulatoryFinding:
    """A single regulatory finding from a source."""
    title: str
    description: str
    category: str  # CLASSIFICATION, INGREDIENT, CLAIMS, LABELLING, DOCUMENTATION, SAFETY
    applicability: str  # RELEVANT, POTENTIALLY_RELEVANT, NEEDS_VERIFICATION
    confidence: str  # HIGH, MEDIUM, LOW
    authority: str
    source_name: str
    source_reference: Optional[str] = None
    evidence_type: str = "REGULATION"
    effective_date: Optional[str] = None
    publication_date: Optional[str] = None
    limitations: str = ""
    next_action: str = ""


@dataclass
class RegulatorySearchResult:
    """Result from a regulatory source search."""
    source: RegulatorySourceInfo
    findings: List[RegulatoryFinding] = field(default_factory=list)
    status: str = "NOT_CONFIGURED"  # OK, NOT_CONFIGURED, ERROR, TIMEOUT
    error_message: str = ""


# -------------------------------------------------------------------
# Base adapter
# -------------------------------------------------------------------

class RegulatorySourceAdapter(ABC):
    """Abstract base for regulatory source adapters."""

    @abstractmethod
    def source_info(self) -> RegulatorySourceInfo:
        """Return metadata about this source."""
        ...

    @abstractmethod
    def search(
        self,
        product_data: dict,
        jurisdiction: str,
        categories: Optional[List[str]] = None,
    ) -> RegulatorySearchResult:
        """Search this source for regulatory information."""
        ...


# -------------------------------------------------------------------
# India — Ministry of Ayush
# -------------------------------------------------------------------

class IndiaAyushAdapter(RegulatorySourceAdapter):
    """Ministry of Ayush (India) regulatory source."""

    def source_info(self) -> RegulatorySourceInfo:
        return RegulatorySourceInfo(
            name="Ministry of Ayush — India",
            authority="Ministry of Ayush, Government of India",
            jurisdiction="IN",
            coverage="Ayurveda, Yoga, Unani, Siddha, Homeopathy products",
            source_type="OFFICIAL",
            configured=False,
            limitations="Requires API credentials or web scraping integration",
            configuration_required="AYUSH_API_KEY or AYUSH_SOURCE_URL",
        )

    def search(self, product_data: dict, jurisdiction: str, categories: Optional[List[str]] = None) -> RegulatorySearchResult:
        info = self.source_info()
        if not info.configured:
            return RegulatorySearchResult(
                source=info,
                status="NOT_CONFIGURED",
                error_message="Ministry of Ayush source not configured. Set AYUSH_API_KEY to enable.",
            )
        return RegulatorySearchResult(source=info, status="OK")


class IndiaFssaiAdapter(RegulatorySourceAdapter):
    """FSSAI (India) for food/supplement products."""

    def source_info(self) -> RegulatorySourceInfo:
        return RegulatorySourceInfo(
            name="FSSAI — India",
            authority="Food Safety and Standards Authority of India",
            jurisdiction="IN",
            coverage="Food, nutraceuticals, supplements",
            source_type="OFFICIAL",
            configured=False,
            limitations="Requires API credentials",
            configuration_required="FSSAI_API_KEY",
        )

    def search(self, product_data: dict, jurisdiction: str, categories: Optional[List[str]] = None) -> RegulatorySearchResult:
        info = self.source_info()
        if not info.configured:
            return RegulatorySearchResult(
                source=info,
                status="NOT_CONFIGURED",
                error_message="FSSAI source not configured.",
            )
        return RegulatorySearchResult(source=info, status="OK")


# -------------------------------------------------------------------
# EU / Germany
# -------------------------------------------------------------------

class EUDirectiveAdapter(RegulatorySourceAdapter):
    """EU regulatory directives for herbal/traditional products."""

    def source_info(self) -> RegulatorySourceInfo:
        return RegulatorySourceInfo(
            name="EU Herbal Directive",
            authority="European Commission — DG SANTE",
            jurisdiction="EU",
            coverage="Traditional herbal medicinal products, herbal products",
            source_type="OFFICIAL",
            configured=False,
            limitations="Requires integration with EU regulatory databases",
            configuration_required="EU_REGULATIONS_API_KEY",
        )

    def search(self, product_data: dict, jurisdiction: str, categories: Optional[List[str]] = None) -> RegulatorySearchResult:
        info = self.source_info()
        if not info.configured:
            return RegulatorySearchResult(
                source=info,
                status="NOT_CONFIGURED",
                error_message="EU regulatory source not configured. Set EU_REGULATIONS_API_KEY to enable.",
            )
        return RegulatorySearchResult(source=info, status="OK")


class GermanBfArMAdapter(RegulatorySourceAdapter):
    """German Federal Institute for Drugs and Medical Devices."""

    def source_info(self) -> RegulatorySourceInfo:
        return RegulatorySourceInfo(
            name="BfArM — Germany",
            authority="Bundesinstitut für Arzneimittel und Medizinprodukte",
            jurisdiction="DE",
            coverage="Medicinal products, traditional herbal products in Germany",
            source_type="OFFICIAL",
            configured=False,
            limitations="Requires integration with BfArM databases",
            configuration_required="BFARM_API_KEY",
        )

    def search(self, product_data: dict, jurisdiction: str, categories: Optional[List[str]] = None) -> RegulatorySearchResult:
        info = self.source_info()
        if not info.configured:
            return RegulatorySearchResult(
                source=info,
                status="NOT_CONFIGURED",
                error_message="BfArM source not configured.",
            )
        return RegulatorySearchResult(source=info, status="OK")


class GermanHPCAdapter(RegulatorySourceAdapter):
    """German Health Product Commission (Commission E monographs)."""

    def source_info(self) -> RegulatorySourceInfo:
        return RegulatorySourceInfo(
            name="Commission E Monographs — Germany",
            authority="Bundesinstitut für Arzneimittel — Commission E",
            jurisdiction="DE",
            coverage="Herbal drug monographs, therapeutic assessments",
            source_type="OFFICIAL",
            configured=False,
            limitations="Requires integration with monograph database",
            configuration_required="COMMISSION_E_API_KEY",
        )

    def search(self, product_data: dict, jurisdiction: str, categories: Optional[List[str]] = None) -> RegulatorySearchResult:
        info = self.source_info()
        if not info.configured:
            return RegulatorySearchResult(
                source=info,
                status="NOT_CONFIGURED",
                error_message="Commission E monograph source not configured.",
            )
        return RegulatorySearchResult(source=info, status="OK")


# -------------------------------------------------------------------
# USA
# -------------------------------------------------------------------

class USFDAAdapter(RegulatorySourceAdapter):
    """US FDA regulatory source."""

    def source_info(self) -> RegulatorySourceInfo:
        return RegulatorySourceInfo(
            name="US FDA — Dietary Supplements",
            authority="U.S. Food and Drug Administration",
            jurisdiction="US",
            coverage="Dietary supplements, botanical products, DSHEA regulations",
            source_type="OFFICIAL",
            configured=False,
            limitations="Requires integration with FDA databases (FDA API, CFR)",
            configuration_required="FDA_API_KEY",
        )

    def search(self, product_data: dict, jurisdiction: str, categories: Optional[List[str]] = None) -> RegulatorySearchResult:
        info = self.source_info()
        if not info.configured:
            return RegulatorySearchResult(
                source=info,
                status="NOT_CONFIGURED",
                error_message="FDA source not configured. Set FDA_API_KEY to enable.",
            )
        return RegulatorySearchResult(source=info, status="OK")


class USEOHAdapter(RegulatorySourceAdapter):
    """US Office of Dietary Supplements."""

    def source_info(self) -> RegulatorySourceInfo:
        return RegulatorySourceInfo(
            name="NIH Office of Dietary Supplements",
            authority="National Institutes of Health",
            jurisdiction="US",
            coverage="Dietary supplement information, fact sheets",
            source_type="OFFICIAL",
            configured=False,
            limitations="Requires integration with NIH ODS databases",
            configuration_required="NIH_ODS_API_KEY",
        )

    def search(self, product_data: dict, jurisdiction: str, categories: Optional[List[str]] = None) -> RegulatorySearchResult:
        info = self.source_info()
        if not info.configured:
            return RegulatorySearchResult(
                source=info,
                status="NOT_CONFIGURED",
                error_message="NIH ODS source not configured.",
            )
        return RegulatorySearchResult(source=info, status="OK")


# -------------------------------------------------------------------
# Source Registry
# -------------------------------------------------------------------

# Maps jurisdiction code → list of adapter instances
REGULATORY_SOURCES: Dict[str, List[RegulatorySourceAdapter]] = {
    "IN": [IndiaAyushAdapter(), IndiaFssaiAdapter()],
    "EU": [EUDirectiveAdapter()],
    "DE": [GermanBfArMAdapter(), GermanHPCAdapter()],
    "US": [USFDAAdapter(), USEOHAdapter()],
}

# All jurisdictions we support (even if sources are not configured)
SUPPORTED_JURISDICTIONS = {
    "IN": {"name": "India", "flag": "🇮🇳"},
    "US": {"name": "United States", "flag": "🇺🇸"},
    "EU": {"name": "European Union", "flag": "🇪🇺"},
    "DE": {"name": "Germany", "flag": "🇩🇪"},
}


def get_sources_for_jurisdiction(jurisdiction: str) -> List[RegulatorySourceAdapter]:
    """Get all registered source adapters for a jurisdiction."""
    return REGULATORY_SOURCES.get(jurisdiction, [])


def get_all_source_info() -> List[RegulatorySourceInfo]:
    """Get metadata for all registered sources."""
    infos = []
    for jurisdiction, adapters in REGULATORY_SOURCES.items():
        for adapter in adapters:
            infos.append(adapter.source_info())
    return infos
