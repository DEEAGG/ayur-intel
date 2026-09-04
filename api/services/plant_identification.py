"""AYUR-INTEL — Plant Identification Service Interface.

Defines the contract for plant identification providers.
No actual provider is configured in Phase 2 — the interface is built
so that any vision/plant-identification API can be plugged in later.

NEVER fabricate identification results. If no provider is configured,
the system must clearly indicate that identification requires configuration.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("ayur_intel.plant_identification")


# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------

@dataclass
class CandidatePlant:
    """A single candidate plant identification."""

    name: str  # Common name
    scientific_name: Optional[str] = None  # Botanical/scientific name
    confidence: int = 0  # 0-100
    notes: Optional[str] = None


@dataclass
class IdentificationResult:
    """Result from a plant identification provider.

    All fields are optional because the provider may not return everything.
    The service layer handles validation and safety checks.
    """

    candidates: List[CandidatePlant] = field(default_factory=list)
    primary_candidate: Optional[CandidatePlant] = None
    identification_notes: Optional[str] = None
    verification_required: bool = True
    provider: str = "unknown"
    provider_raw: Optional[str] = None  # Raw response for debugging
    fallback_reason: Optional[str] = None  # Why fallback occurred

    @property
    def confidence(self) -> Optional[int]:
        """Confidence of the primary candidate, or None."""
        if self.primary_candidate:
            return self.primary_candidate.confidence
        return None

    @property
    def has_candidates(self) -> bool:
        return len(self.candidates) > 0


# ---------------------------------------------------------------------------
# Provider interface (abstract base class)
# ---------------------------------------------------------------------------

class PlantIdentificationProvider(abc.ABC):
    """Abstract interface for plant identification providers.

    Implement this interface to integrate a real vision/plant-ID API.
    Each provider must:
    - Accept an image (bytes + content type)
    - Return IdentificationResult
    - Handle errors gracefully (never crash the application)
    - Identify itself by name
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'plantnet', 'custom_model', 'openai_vision')."""
        ...

    @abc.abstractmethod
    def identify(self, image_bytes: bytes, content_type: str) -> IdentificationResult:
        """Identify plants in the given image.

        Args:
            image_bytes: Raw image file bytes.
            content_type: MIME type (e.g., 'image/jpeg').

        Returns:
            IdentificationResult with candidates and confidence.

        Raises:
            ProviderError: If the provider fails.
        """
        ...

    def is_configured(self) -> bool:
        """Whether this provider has the necessary credentials/config."""
        return True


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Raised when a plant identification provider fails."""
    pass


class ProviderNotConfiguredError(ProviderError):
    """Raised when the provider is not configured."""
    pass


# ---------------------------------------------------------------------------
# No-op provider (used when no real provider is configured)
# ---------------------------------------------------------------------------

class UnconfiguredProvider(PlantIdentificationProvider):
    """Placeholder provider that returns no identification.

    Used when no real vision/plant-ID API is configured.
    Always returns a result indicating provider is not available.
    """

    @property
    def name(self) -> str:
        return "unconfigured"

    def is_configured(self) -> bool:
        return False

    def identify(self, image_bytes: bytes, content_type: str) -> IdentificationResult:
        """Always returns a result indicating no provider is available."""
        return IdentificationResult(
            candidates=[],
            primary_candidate=None,
            identification_notes=(
                "Plant identification provider is not configured. "
                "To enable real plant identification, configure a provider "
                "in the AYURINTEL_PLANT_ID_PROVIDER environment variable."
            ),
            verification_required=True,
            provider="unconfigured",
            provider_raw=None,
        )


class DemoProvider(PlantIdentificationProvider):
    """Demo provider that returns simulated plant identification results.

    Used in demo mode for SIH demonstrations.
    Always returns a plausible identification with a clear safety warning.
    NEVER claim this is real identification — it is simulated.
    """

    # Simulated plant database for demo
    DEMO_PLANTS = [
        {
            "name": "Ashwagandha",
            "scientific_name": "Withania somnifera",
            "confidence": 72,
            "notes": "Simulated identification based on visual特征. Expert verification strongly recommended.",
            "alternatives": [
                {"name": "Tulsi", "scientific_name": "Ocimum tenuiflorum", "confidence": 12},
                {"name": "Brahmi", "scientific_name": "Bacopa monnieri", "confidence": 8},
            ]
        },
        {
            "name": "Neem",
            "scientific_name": "Azadirachta indica",
            "confidence": 68,
            "notes": "Simulated identification. This is NOT a verified botanical identification.",
            "alternatives": [
                {"name": "Curry Leaf", "scientific_name": "Murraya koenigii", "confidence": 15},
                {"name": "Margosa", "scientific_name": "Azadirachta indica", "confidence": 10},
            ]
        },
        {
            "name": "Turmeric",
            "scientific_name": "Curcuma longa",
            "confidence": 75,
            "notes": "Simulated identification for demonstration purposes only.",
            "alternatives": [
                {"name": "Ginger", "scientific_name": "Zingiber officinale", "confidence": 11},
                {"name": "Galangal", "scientific_name": "Alpinia galanga", "confidence": 7},
            ]
        },
    ]

    @property
    def name(self) -> str:
        return "demo"

    def is_configured(self) -> bool:
        return True

    def identify(self, image_bytes: bytes, content_type: str) -> IdentificationResult:
        """Return a simulated identification for demo purposes."""
        import hashlib
        # Pick a consistent plant based on image hash so same image = same result
        img_hash = hashlib.md5(image_bytes[:1024]).hexdigest()
        plant_idx = int(img_hash[:8], 16) % len(self.DEMO_PLANTS)
        plant = self.DEMO_PLANTS[plant_idx]

        primary = CandidatePlant(
            name=plant["name"],
            scientific_name=plant["scientific_name"],
            confidence=plant["confidence"],
            notes=plant["notes"],
        )
        alternatives = [
            CandidatePlant(name=a["name"], scientific_name=a["scientific_name"], confidence=a["confidence"])
            for a in plant["alternatives"]
        ]

        return IdentificationResult(
            candidates=[primary] + alternatives,
            primary_candidate=primary,
            identification_notes=(
                "⚠️ SIMULATED IDENTIFICATION — This is a demo result, NOT real botanical identification. "
                "Expert verification is required before any use. "
                "Never consume an unidentified plant based on AI identification."
            ),
            verification_required=True,
            provider="demo",
            provider_raw=None,
        )
# ---------------------------------------------------------------------------
# PlantNet Provider (real API integration)
# ---------------------------------------------------------------------------

class PlantNetProvider(PlantIdentificationProvider):
    """PlantNet API provider for real botanical identification.

    Uses the Pl@ntNet REST API (https://my.plantnet.org) to identify plants
    from uploaded images. Requires:
        AYURINTEL_PLANTNET_API_KEY  — your PlantNet API key
        AYURINTEL_PLANTNET_PROJECT  — optional, defaults to 'all'

    Free tier: 500 identifications/day.
    """

    API_BASE = "https://my-api.plantnet.org/v2/identify"

    # Map content types to organ guesses for better accuracy
    ORGAN_HINTS = {
        "image/jpeg": "leaf",
        "image/png": "leaf",
        "image/webp": "leaf",
    }

    def __init__(self):
        from api.core.config import settings
        self._api_key = settings.AYURINTEL_PLANTNET_API_KEY
        self._project = settings.AYURINTEL_PLANTNET_PROJECT

    @property
    def name(self) -> str:
        return "plantnet"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def identify(self, image_bytes: bytes, content_type: str) -> IdentificationResult:
        """Identify a plant using the PlantNet API."""
        import io
        import json
        try:
            import requests
        except ImportError:
            raise ProviderError("'requests' library is required for PlantNet. Install with: pip install requests")

        if not self._api_key:
            raise ProviderNotConfiguredError(
                "PlantNet API key not configured. "
                "Set AYURINTEL_PLANTNET_API_KEY environment variable. "
                "Get a free key at https://my.plantnet.org/"
            )

        url = f"{self.API_BASE}/{self._project}?api-key={self._api_key}"

        # Determine organ type from content type
        organ = self.ORGAN_HINTS.get(content_type, "leaf")

        # Build multipart form data
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"

        filename = f"upload{ext}"
        files = {
            "images": (filename, io.BytesIO(image_bytes), content_type),
        }
        data = {
            "organs": [organ],
        }

        logger.info("PlantNet: identifying image (%d bytes, organ=%s, project=%s)",
                     len(image_bytes), organ, self._project)

        try:
            response = requests.post(url, files=files, data=data, timeout=(10, 20))
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise ProviderError("PlantNet API request timed out")
        except requests.exceptions.ConnectionError:
            raise ProviderError("Cannot connect to PlantNet API. Check your internet connection.")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body = ""
            if e.response is not None:
                try:
                    body = e.response.text[:200]
                except Exception:
                    pass
            if status == 401:
                raise ProviderError("PlantNet API key is invalid or expired. Check AYURINTEL_PLANTNET_API_KEY.")
            if status == 403:
                raise ProviderError("PlantNet API quota exceeded or access forbidden.")
            raise ProviderError(f"PlantNet API error {status}: {body}")
        except Exception as e:
            raise ProviderError(f"PlantNet API request failed: {e}")

        # Parse response
        try:
            result = response.json()
        except Exception:
            raise ProviderError("PlantNet API returned invalid JSON")

        logger.info("PlantNet: raw response has %d results", len(result.get("results", [])))

        # Extract candidates
        candidates = []
        primary = None
        for r in result.get("results", []):
            species = r.get("species", {})
            common_names = species.get("commonNames", [])
            scientific_name = species.get("scientificNameWithoutAuthor", "")
            common_name = common_names[0] if common_names else scientific_name
            confidence = int(round(r.get("score", 0) * 100))

            candidate = CandidatePlant(
                name=common_name,
                scientific_name=scientific_name,
                confidence=confidence,
                notes=r.get("gbif", {}).get("family", None),
            )
            candidates.append(candidate)
            if primary is None:
                primary = candidate

        # Build notes
        notes_parts = []
        if result.get("query", {}).get("project"):
            notes_parts.append(f"PlantNet project: {result['query']['project']}")
        if result.get("query", {}).get("organ"):
            notes_parts.append(f"Organ detected: {result['query']['organ']}")
        if not notes_parts:
            notes_parts.append("Identified via PlantNet AI vision model")

        # Detect if expert verification is needed (low confidence)
        verification_needed = True
        if primary and primary.confidence >= 80:
            verification_needed = True  # Always require verification for safety

        return IdentificationResult(
            candidates=candidates,
            primary_candidate=primary,
            identification_notes=" ".join(notes_parts) + ". Expert verification recommended.",
            verification_required=verification_needed,
            provider="plantnet",
            provider_raw=json.dumps(result, indent=2) if len(json.dumps(result)) < 5000 else json.dumps(result)[:5000],
        )


class FallbackProvider(PlantIdentificationProvider):
    """Provider that tries a primary provider and falls back to a secondary."""

    def __init__(self, primary: PlantIdentificationProvider, fallback: PlantIdentificationProvider, fallback_reason: str = ""):
        self._primary = primary
        self._fallback = fallback
        self._fallback_reason = fallback_reason

    @property
    def name(self) -> str:
        return f"{self._primary.name}+fallback({self._fallback.name})"

    def is_configured(self) -> bool:
        return True

    def identify(self, image_bytes: bytes, content_type: str) -> IdentificationResult:
        try:
            result = self._primary.identify(image_bytes, content_type)
            # Check if the primary actually returned useful results
            if result.has_candidates:
                result.identification_notes = (
                    f"Identified via {self._primary.name}. " +
                    (result.identification_notes or "")
                )
                return result
            else:
                # Primary returned no candidates — try fallback
                logger.warning("PlantNet returned no candidates, falling back to %s", self._fallback.name)
        except ProviderError as e:
            logger.warning("Primary provider (%s) failed: %s — falling back to %s",
                           self._primary.name, e, self._fallback.name)
        except Exception as e:
            logger.warning("Primary provider (%s) error: %s — falling back to %s",
                           self._primary.name, e, self._fallback.name)

        # Use fallback
        result = self._fallback.identify(image_bytes, content_type)
        result.fallback_reason = self._fallback_reason
        if result.identification_notes:
            result.identification_notes = (
                f"⚠️ {self._fallback_reason}. Using simulated results. " +
                result.identification_notes
            )
        else:
            result.identification_notes = (
                f"⚠️ {self._fallback_reason}. Using simulated results."
            )
        return result


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------
def get_plant_identification_provider() -> PlantIdentificationProvider:
    """Get the configured plant identification provider.

    Priority:
        1. If AYURINTEL_PLANT_ID_PROVIDER=plantnet AND key is set → PlantNet with fallback to demo
        2. If demo mode (no provider configured) → DemoProvider
        3. Otherwise → UnconfiguredProvider
    """
    from api.core.config import settings
    provider_name = settings.AYURINTEL_PLANT_ID_PROVIDER
    api_key = settings.AYURINTEL_PLANTNET_API_KEY

    # Explicit PlantNet configuration — wrap with fallback to demo
    if provider_name == "plantnet" or (api_key and provider_name == "unconfigured"):
        pn = PlantNetProvider()
        if pn.is_configured():
            logger.info("Plant identification: using PlantNet API with demo fallback (project=%s)", pn._project)
            return FallbackProvider(
                primary=pn,
                fallback=DemoProvider(),
                fallback_reason="PlantNet API is unreachable from this network"
            )
        else:
            logger.warning("PlantNet requested but API key not set. Falling back.")

    # In demo mode, use the simulated provider
    if provider_name == "unconfigured" and settings.AYURINTEL_DEMO_MODE:
        logger.info("Plant identification: using demo provider (simulated results)")
        return DemoProvider()

    if provider_name == "unconfigured":
        logger.info("Plant identification: using unconfigured provider (no real ID)")
        return UnconfiguredProvider()

    logger.warning("Unknown plant ID provider '%s', falling back to unconfigured", provider_name)
    return UnconfiguredProvider()
