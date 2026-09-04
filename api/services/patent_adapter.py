"""AYUR-INTEL — Patent Source Adapter Interface & Registry.

Defines the contract for patent source adapters. Each adapter connects
to one patent database/authority and exposes search capabilities.

NEVER fabricate patent results. If no source is configured, clearly
indicate that the source requires configuration.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("ayur_intel.patent_adapter")


# -------------------------------------------------------------------
# Result data structures
# -------------------------------------------------------------------

@dataclass
class PatentResult:
    """A single patent result from a source adapter search."""

    title: Optional[str] = None
    abstract: Optional[str] = None
    applicant: Optional[str] = None
    inventors: Optional[List[str]] = None

    # Identifiers
    publication_number: Optional[str] = None
    application_number: Optional[str] = None
    patent_type: Optional[str] = None  # APPLICATION, PUBLICATION, GRANTED

    # Dates
    priority_date: Optional[str] = None
    filing_date: Optional[str] = None
    publication_date: Optional[str] = None

    # Status
    status: Optional[str] = None

    # Source metadata
    source_name: str = ""
    authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    source_url: Optional[str] = None

    # Relevance (populated by the service layer)
    relevance_level: str = "LOW"
    relevance_score: int = 0
    explanation: Optional[str] = None


@dataclass
class PatentSearchResponse:
    """Response from a patent source adapter search."""

    results: List[PatentResult] = field(default_factory=list)
    total: int = 0
    source_name: str = ""
    authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    is_configured: bool = True
    message: Optional[str] = None
    retrieval_date: str = ""


# -------------------------------------------------------------------
# Patent source adapter interface
# -------------------------------------------------------------------

class PatentSourceAdapter(abc.ABC):
    """Abstract interface for patent source adapters."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def authority(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def jurisdiction(self) -> str:
        ...

    @property
    def source_type(self) -> str:
        return "PATENT"

    @property
    @abc.abstractmethod
    def capabilities(self) -> List[str]:
        ...

    @abc.abstractmethod
    def search(
        self,
        query: str,
        keywords: Optional[List[str]] = None,
        jurisdiction: Optional[str] = None,
        limit: int = 20,
    ) -> PatentSearchResponse:
        ...

    def is_configured(self) -> bool:
        return True

    def description(self) -> str:
        return f"{self.name} ({self.authority}, {self.jurisdiction})"


# -------------------------------------------------------------------
# Unconfigured placeholder adapter
# -------------------------------------------------------------------

class UnconfiguredPatentAdapter(PatentSourceAdapter):
    """Placeholder adapter that returns no results."""

    def __init__(self, source_name: str = "unconfigured", authority: str = "Unknown",
                 jurisdiction: str = "GLOBAL"):
        self._name = source_name
        self._authority = authority
        self._jurisdiction = jurisdiction

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
    def capabilities(self) -> List[str]:
        return []

    def is_configured(self) -> bool:
        return False

    def search(self, query: str, **kwargs) -> PatentSearchResponse:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return PatentSearchResponse(
            results=[], total=0,
            source_name=self.name, source_authority=self.authority,
            jurisdiction=self.jurisdiction, is_configured=False,
            message=(
                f"Patent source '{self.name}' ({self.authority}) is not yet configured. "
                f"To enable patent search, configure the corresponding adapter "
                f"and API credentials in the environment variables."
            ),
            retrieval_date=now,
        )


# -------------------------------------------------------------------
# Patent Source Registry
# -------------------------------------------------------------------

class PatentSourceRegistry:
    """Registry of all available patent source adapters."""

    def __init__(self):
        self._adapters: Dict[str, PatentSourceAdapter] = {}

    def register(self, adapter: PatentSourceAdapter) -> None:
        self._adapters[adapter.name] = adapter
        logger.info("Registered patent adapter: %s (%s, %s)",
                     adapter.name, adapter.authority, adapter.jurisdiction)

    def get_all(self) -> List[PatentSourceAdapter]:
        return list(self._adapters.values())

    def get_by_jurisdiction(self, jurisdiction: str) -> List[PatentSourceAdapter]:
        return [
            a for a in self._adapters.values()
            if a.jurisdiction in (jurisdiction, "GLOBAL")
        ]

    def search_all(
        self,
        query: str,
        keywords: Optional[List[str]] = None,
        jurisdictions: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[PatentSearchResponse]:
        """Search all relevant adapters."""
        adapters = self._adapters.values()
        if jurisdictions:
            adapters = [
                a for a in adapters
                if a.jurisdiction in jurisdictions or a.jurisdiction == "GLOBAL"
            ]

        responses = []
        for adapter in adapters:
            try:
                resp = adapter.search(
                    query=query, keywords=keywords,
                    jurisdiction=adapter.jurisdiction, limit=limit,
                )
                responses.append(resp)
            except Exception as e:
                logger.error("Patent source %s search failed: %s", adapter.name, e)
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                responses.append(PatentSearchResponse(
                    results=[], total=0,
                    source_name=adapter.name, authority=adapter.authority,
                    jurisdiction=adapter.jurisdiction,
                    is_configured=adapter.is_configured(),
                    message=f"Search failed: {str(e)}",
                    retrieval_date=now,
                ))
        return responses


# -------------------------------------------------------------------
# Singleton registry
# -------------------------------------------------------------------

_registry: Optional[PatentSourceRegistry] = None


def get_patent_registry() -> PatentSourceRegistry:
    global _registry
    if _registry is not None:
        return _registry

    _registry = PatentSourceRegistry()

    # Register placeholder adapters for each jurisdiction
    _registry.register(UnconfiguredPatentAdapter(
        source_name="IP_INDIA_PATENTS", authority="IP India", jurisdiction="IN"))
    _registry.register(UnconfiguredPatentAdapter(
        source_name="WIPO_PATENTSCO", authority="WIPO", jurisdiction="GLOBAL"))
    _registry.register(UnconfiguredPatentAdapter(
        source_name="EPO_OPENPATENTS", authority="EPO", jurisdiction="EU"))
    _registry.register(UnconfiguredPatentAdapter(
        source_name="USPTO_PUBFULL", authority="USPTO", jurisdiction="US"))
    _registry.register(UnconfiguredPatentAdapter(
        source_name="DPMA_PATENTS", authority="DPMA", jurisdiction="DE"))

    logger.info("Patent registry initialized with %d adapters", len(_registry.get_all()))
    return _registry
