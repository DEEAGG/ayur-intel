"""AYUR-INTEL — Source Adapter Interface & Registry.

Defines the contract for knowledge source adapters. Each adapter connects
to one source (TK database, government registry, scientific literature, etc.)
and exposes search/fetch/metadata capabilities.

NEVER fabricate source results. If no source is configured, clearly indicate
that the source requires configuration.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("ayur_intel.source_adapter")


# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------

@dataclass
class SourceResult:
    """A single result from a source adapter search."""

    title: str
    summary: Optional[str] = None
    plant_name: Optional[str] = None
    botanical_name: Optional[str] = None
    traditional_name: Optional[str] = None
    category: Optional[str] = None  # e.g. TRADITIONAL_USE, PREPARATION, SAFETY

    # Source metadata
    source_name: str = ""
    source_authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    source_url: Optional[str] = None
    source_identifier: Optional[str] = None  # DOI, URL, document ID

    # Evidence
    confidence: str = "UNKNOWN"  # HIGH, MODERATE, LOW, CONFLICTING, UNKNOWN
    relevance: str = "MODERATE"  # HIGH, MODERATE, LOW
    evidence_locator: Optional[str] = None  # section, page, clause
    excerpt: Optional[str] = None  # quoted text if legally permitted

    # Dates
    publication_date: Optional[str] = None
    retrieval_date: Optional[str] = None
    source_version: Optional[str] = None

    # Limitations
    limitations: Optional[str] = None
    is_conflicting: bool = False
    conflicting_details: Optional[str] = None  # JSON — other sources' positions

    # Provenance & Hierarchy (Phase 2)
    license_note: Optional[str] = None
    content_hash: Optional[str] = None
    sthana: Optional[str] = None
    chapter: Optional[str] = None
    verse: Optional[str] = None
    section: Optional[str] = None
    document_type: Optional[str] = None


@dataclass
class SourceSearchResponse:
    """Response from a source adapter search."""

    results: List[SourceResult] = field(default_factory=list)
    total: int = 0
    source_name: str = ""
    source_authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    is_configured: bool = True
    message: Optional[str] = None  # Error/info message if applicable
    retrieval_date: str = ""


# ---------------------------------------------------------------------------
# Source adapter interface (abstract base class)
# ---------------------------------------------------------------------------

class SourceAdapter(abc.ABC):
    """Abstract interface for knowledge source adapters.

    Each adapter must:
    - Identify itself by name, authority, and jurisdiction
    - Expose search() that returns SourceSearchResponse
    - Handle errors gracefully (never crash the application)
    - Clearly indicate if not configured
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Source name (e.g. 'AYUSH_TK_DB', 'WHO_IRIS', 'PubMed')."""
        ...

    @property
    @abc.abstractmethod
    def authority(self) -> str:
        """Source authority (e.g. 'AYUSH', 'WHO', 'NIH')."""
        ...

    @property
    @abc.abstractmethod
    def jurisdiction(self) -> str:
        """Primary jurisdiction (e.g. 'IN', 'US', 'EU', 'GLOBAL')."""
        ...

    @property
    @abc.abstractmethod
    def source_type(self) -> str:
        """Source type (e.g. 'TK', 'GOV', 'SCIENTIFIC', 'PHARMACOPOEIAL')."""
        ...

    @property
    @abc.abstractmethod
    def capabilities(self) -> List[str]:
        """What this source can provide (e.g. ['traditional_uses', 'preparations'])."""
        ...

    @abc.abstractmethod
    def search(
        self,
        query: str,
        plant_name: Optional[str] = None,
        botanical_name: Optional[str] = None,
        category: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        limit: int = 20,
    ) -> SourceSearchResponse:
        """Search the source for knowledge findings.

        Args:
            query: Free-text search query.
            plant_name: Common plant name filter.
            botanical_name: Scientific name filter.
            category: Knowledge category filter.
            jurisdiction: Jurisdiction filter.
            limit: Max results.

        Returns:
            SourceSearchResponse with results and metadata.
        """
        ...

    def is_configured(self) -> bool:
        """Whether this source has the necessary credentials/config."""
        return True

    def description(self) -> str:
        """Human-readable description of this source."""
        return f"{self.name} ({self.authority}, {self.jurisdiction})"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SourceAdapterError(Exception):
    """Raised when a source adapter fails."""
    pass


class SourceNotConfiguredError(SourceAdapterError):
    """Raised when the source is not configured."""
    pass


# ---------------------------------------------------------------------------
# Unconfigured adapter (used when no real source is available)
# ---------------------------------------------------------------------------

class UnconfiguredSourceAdapter(SourceAdapter):
    """Placeholder adapter that returns no results.

    Used when no real source API is configured.
    Always returns a result indicating the source is not available.
    """

    def __init__(self, source_name: str = "unconfigured", authority: str = "Unknown",
                 jurisdiction: str = "GLOBAL", source_type: str = "UNKNOWN"):
        self._name = source_name
        self._authority = authority
        self._jurisdiction = jurisdiction
        self._source_type = source_type

    @property
    def name(self) -> str:
        return self._name

    @property
    def authority(self) -> str:
        return self._authority

    @property
    def jurisdiction(self) -> str:
        return self._jurisdiction

    @property
    def source_type(self) -> str:
        return self._source_type

    @property
    def capabilities(self) -> List[str]:
        return []

    def is_configured(self) -> bool:
        return False

    def search(self, query: str, **kwargs) -> SourceSearchResponse:
        """Always returns a result indicating no source is available."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return SourceSearchResponse(
            results=[],
            total=0,
            source_name=self.name,
            source_authority=self.authority,
            jurisdiction=self.jurisdiction,
            is_configured=False,
            message=(
                f"Source '{self.name}' ({self.authority}) is not yet configured. "
                f"To enable this source, configure the corresponding adapter "
                f"and API credentials in the environment variables."
            ),
            retrieval_date=now,
        )


# ---------------------------------------------------------------------------
# Source Registry
# ---------------------------------------------------------------------------

class SourceRegistry:
    """Registry of all available source adapters.

    Adapters are registered at startup. The registry selects which adapters
    to query based on jurisdiction, source type, and capabilities.
    """

    def __init__(self):
        self._adapters: Dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        """Register a source adapter."""
        self._adapters[adapter.name] = adapter
        logger.info("Registered source adapter: %s (%s, %s)",
                     adapter.name, adapter.authority, adapter.jurisdiction)

    def get(self, name: str) -> Optional[SourceAdapter]:
        """Get a specific adapter by name."""
        return self._adapters.get(name)

    def get_all(self) -> List[SourceAdapter]:
        """Get all registered adapters."""
        return list(self._adapters.values())

    def get_configured(self) -> List[SourceAdapter]:
        """Get all configured (ready to use) adapters."""
        return [a for a in self._adapters.values() if a.is_configured()]

    def get_by_jurisdiction(self, jurisdiction: str) -> List[SourceAdapter]:
        """Get adapters matching a jurisdiction (or GLOBAL)."""
        return [
            a for a in self._adapters.values()
            if a.jurisdiction in (jurisdiction, "GLOBAL")
        ]

    def get_by_type(self, source_type: str) -> List[SourceAdapter]:
        """Get adapters of a specific type."""
        return [a for a in self._adapters.values() if a.source_type == source_type]

    def search_all(
        self,
        query: str,
        plant_name: Optional[str] = None,
        botanical_name: Optional[str] = None,
        category: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        limit: int = 10,
    ) -> List[SourceSearchResponse]:
        """Search all configured adapters (or all if none configured).

        If jurisdiction is specified, prioritize matching adapters.
        """
        adapters = self._adapters.values()
        if jurisdiction:
            # Prefer jurisdiction-specific, include GLOBAL
            adapters = [
                a for a in adapters
                if a.jurisdiction in (jurisdiction, "GLOBAL")
            ]

        responses = []
        for adapter in adapters:
            try:
                resp = adapter.search(
                    query=query,
                    plant_name=plant_name,
                    botanical_name=botanical_name,
                    category=category,
                    jurisdiction=jurisdiction,
                    limit=limit,
                )
                responses.append(resp)
            except Exception as e:
                logger.error("Source %s search failed: %s", adapter.name, e)
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                responses.append(SourceSearchResponse(
                    results=[],
                    total=0,
                    source_name=adapter.name,
                    source_authority=adapter.authority,
                    jurisdiction=adapter.jurisdiction,
                    is_configured=adapter.is_configured(),
                    message=f"Search failed: {str(e)}",
                    retrieval_date=now,
                ))

        return responses


# ---------------------------------------------------------------------------
# Singleton registry
# ---------------------------------------------------------------------------

_registry: Optional[SourceRegistry] = None


def get_source_registry() -> SourceRegistry:
    """Get or create the global source registry.

    Registers available adapters based on environment configuration.
    """
    global _registry
    if _registry is not None:
        return _registry

    _registry = SourceRegistry()

    # Import and register Phase 2 production adapters
    try:
        from api.services.knowledge_source_adapters import (
            PubMedCentralAdapter,
            FssaiRegulationsAdapter,
            ClassicalSamhitaAdapter,
            AyushGuidelinesAdapter,
            DrugsActAdapter,
        )
        _registry.register(PubMedCentralAdapter())
        _registry.register(FssaiRegulationsAdapter())
        _registry.register(ClassicalSamhitaAdapter())
        _registry.register(AyushGuidelinesAdapter())
        _registry.register(DrugsActAdapter())
    except Exception as e:
        logger.warning("Failed to register real knowledge adapters: %s", e)

    # Always register unconfigured placeholders
    _registry.register(UnconfiguredSourceAdapter(
        source_name="AYUSH_TK_DB",
        authority="AYUSH",
        jurisdiction="IN",
        source_type="TK",
    ))

    _registry.register(UnconfiguredSourceAdapter(
        source_name="WHO_IRIS",
        authority="WHO",
        jurisdiction="GLOBAL",
        source_type="SCIENTIFIC",
    ))

    _registry.register(UnconfiguredSourceAdapter(
        source_name="USPTO_PATENT_DB",
        authority="USPTO",
        jurisdiction="US",
        source_type="GOV",
    ))

    _registry.register(UnconfiguredSourceAdapter(
        source_name="IP_INDIA_TK",
        authority="IP India",
        jurisdiction="IN",
        source_type="TK",
    ))

    logger.info("Source registry initialized with %d adapters", len(_registry.get_all()))
    return _registry
