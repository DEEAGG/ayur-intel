"""AYUR-INTEL — PlantNet Identification Service.

Provides secure server-side integration with the Pl@ntNet API for botanical plant identification.
Includes strict image input validation, structured error handling, timing metrics, and response normalization.
"""

from __future__ import annotations

import io
import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from api.core.config import settings

logger = logging.getLogger("ayur_intel.services.plantnet")

# Constants
PLANTNET_BASE_URL = "https://my-api.plantnet.org/v2/identify"
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PlantNetError(Exception):
    """Base exception for PlantNet service errors."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PlantNetConfigurationError(PlantNetError):
    """Raised when API key is missing or not configured."""
    def __init__(self, message: str = "Plant identification service is not configured."):
        super().__init__(message, status_code=500)


class PlantNetValidationError(PlantNetError):
    """Raised when uploaded image fails validation."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class PlantNetTimeoutError(PlantNetError):
    """Raised when Pl@ntNet API request times out."""
    def __init__(self, message: str = "Plant identification service timed out."):
        super().__init__(message, status_code=504)


class PlantNetAuthError(PlantNetError):
    """Raised on 401/403 from Pl@ntNet."""
    def __init__(self, message: str = "Plant identification service authentication failed."):
        super().__init__(message, status_code=502)


class PlantNetRateLimitError(PlantNetError):
    """Raised on 429 from Pl@ntNet."""
    def __init__(self, message: str = "PlantNet API rate limit exceeded. Please try again later."):
        super().__init__(message, status_code=429)


class PlantNetProviderError(PlantNetError):
    """Raised on 4xx/5xx HTTP errors from Pl@ntNet."""
    def __init__(self, message: str = "Plant identification service is temporarily unavailable.", status_code: int = 502):
        super().__init__(message, status_code=status_code)


class PlantNetParseError(PlantNetError):
    """Raised when Pl@ntNet API returns malformed JSON or unexpected schema."""
    def __init__(self, message: str = "Received invalid response from plant identification provider."):
        super().__init__(message, status_code=502)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_plant_image(file_bytes: bytes, content_type: Optional[str] = None, filename: Optional[str] = None) -> None:
    """Validate uploaded plant image before processing.

    Raises:
        PlantNetValidationError if image fails validation checks.
    """
    if not file_bytes or len(file_bytes) == 0:
        raise PlantNetValidationError("Image file is empty.")

    if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise PlantNetValidationError("Image size exceeds maximum limit of 10MB.")

    # Validate Content-Type if provided
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct and ct not in ALLOWED_MIME_TYPES:
        raise PlantNetValidationError("Unsupported image format. Please use JPG or PNG.")

    # Validate file extension if provided
    if filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise PlantNetValidationError("Unsupported image format. Please use JPG or PNG.")

    # Header / Magic Bytes Validation (Do not trust content-type alone)
    if not (file_bytes.startswith(JPEG_MAGIC) or file_bytes.startswith(PNG_MAGIC)):
        raise PlantNetValidationError("Corrupted or invalid image file. Header bytes do not match JPEG/PNG format.")


# ---------------------------------------------------------------------------
# Confidence Helper
# ---------------------------------------------------------------------------

def _get_confidence_label(confidence_percent: float) -> str:
    """Determine confidence label based on percentage score.
    >= 80.0 -> High confidence
    55.0 - 79.9 -> Likely match
    < 55.0 -> Low confidence
    """
    if confidence_percent >= 80.0:
        return "High confidence"
    elif confidence_percent >= 55.0:
        return "Likely match"
    else:
        return "Low confidence"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_plantnet_response(raw_data: Dict[str, Any], default_organ: str = "leaf") -> Dict[str, Any]:
    """Normalize raw Pl@ntNet API response into stable AYUR-INTEL JSON schema."""
    if not isinstance(raw_data, dict):
        raise PlantNetParseError("Provider response root must be a JSON object.")

    results = raw_data.get("results")
    if not isinstance(results, list) or len(results) == 0:
        return {
            "success": False,
            "message": "We couldn't identify this plant confidently.",
            "provider": "PlantNet",
            "best_match": None,
            "predicted_organ": {
                "organ": default_organ,
                "score": 0.0,
            },
            "alternatives": [],
        }

    # Best match
    best = results[0]
    if not isinstance(best, dict):
        raise PlantNetParseError("Result element must be a dictionary.")

    score = float(best.get("score", 0.0))
    score_rounded = round(score, 5)
    conf_pct = round(score * 100.0, 2)
    conf_label = _get_confidence_label(conf_pct)

    species = best.get("species", {}) or {}
    scientific_name = species.get("scientificNameWithoutAuthor") or species.get("scientificName") or "Unknown species"
    scientific_name_full = species.get("scientificName") or scientific_name
    common_names = species.get("commonNames") or []
    if not isinstance(common_names, list):
        common_names = []

    family_obj = species.get("family") or {}
    family_name = ""
    if isinstance(family_obj, dict):
        family_name = family_obj.get("scientificNameWithoutAuthor") or family_obj.get("scientificName") or ""
    elif isinstance(family_obj, str):
        family_name = family_obj

    if not family_name:
        gbif_obj = best.get("gbif") or {}
        if isinstance(gbif_obj, dict):
            family_name = gbif_obj.get("family") or ""

    genus_obj = species.get("genus") or {}
    genus_name = ""
    if isinstance(genus_obj, dict):
        genus_name = genus_obj.get("scientificNameWithoutAuthor") or genus_obj.get("scientificName") or ""
    elif isinstance(genus_obj, str):
        genus_name = genus_obj

    gbif_data = best.get("gbif") or {}
    gbif_id = str(gbif_data.get("id")) if isinstance(gbif_data, dict) and gbif_data.get("id") else None

    powo_data = best.get("powo") or {}
    powo_id = str(powo_data.get("id")) if isinstance(powo_data, dict) and powo_data.get("id") else None

    iucn_data = best.get("iucn") or {}
    iucn_id = None
    iucn_category = None
    if isinstance(iucn_data, dict):
        iucn_id = str(iucn_data.get("id")) if iucn_data.get("id") else None
        iucn_category = iucn_data.get("category") or None

    best_match = {
        "scientific_name": scientific_name,
        "scientific_name_full": scientific_name_full,
        "common_names": common_names,
        "family": family_name,
        "genus": genus_name,
        "score": score_rounded,
        "confidence_percent": conf_pct,
        "confidence_label": conf_label,
        "gbif_id": gbif_id,
        "powo_id": powo_id,
        "iucn_id": iucn_id,
        "iucn_category": iucn_category,
    }

    # Predicted Organ
    query_obj = raw_data.get("query") or {}
    query_organs = query_obj.get("organs") if isinstance(query_obj, dict) else None
    organ_name = default_organ
    if query_organs and isinstance(query_organs, list) and len(query_organs) > 0:
        organ_name = query_organs[0]
    elif raw_data.get("predictedOrgan"):
        organ_name = str(raw_data.get("predictedOrgan"))

    organ_score = round(score, 5)

    predicted_organ = {
        "organ": organ_name,
        "score": organ_score,
    }

    # Alternatives (up to 3)
    alternatives: List[Dict[str, Any]] = []
    for alt in results[1:4]:
        if not isinstance(alt, dict):
            continue
        alt_score = float(alt.get("score", 0.0))
        alt_score_rounded = round(alt_score, 5)
        alt_conf_pct = round(alt_score * 100.0, 2)

        alt_species = alt.get("species", {}) or {}
        alt_s_name = alt_species.get("scientificNameWithoutAuthor") or alt_species.get("scientificName") or "Unknown"
        alt_commons = alt_species.get("commonNames") or []
        if not isinstance(alt_commons, list):
            alt_commons = []

        alt_fam_obj = alt_species.get("family") or {}
        alt_fam = ""
        if isinstance(alt_fam_obj, dict):
            alt_fam = alt_fam_obj.get("scientificNameWithoutAuthor") or alt_fam_obj.get("scientificName") or ""
        elif isinstance(alt_fam_obj, str):
            alt_fam = alt_fam_obj

        alternatives.append({
            "scientific_name": alt_s_name,
            "common_names": alt_commons,
            "family": alt_fam,
            "score": alt_score_rounded,
            "confidence_percent": alt_conf_pct,
        })

    return {
        "success": True,
        "best_match": best_match,
        "predicted_organ": predicted_organ,
        "alternatives": alternatives,
        "provider": "PlantNet",
    }


# ---------------------------------------------------------------------------
# Core Identification Pipeline
# ---------------------------------------------------------------------------

def identify_plant_with_plantnet(
    file_bytes: bytes,
    content_type: Optional[str] = None,
    filename: Optional[str] = None,
    organ: str = "leaf",
) -> Dict[str, Any]:
    """Execute full PlantNet backend identification pipeline with timing metrics.

    Args:
        file_bytes: Raw binary content of the image.
        content_type: Optional MIME type from request header.
        filename: Optional uploaded file name.
        organ: Plant organ specified (default: 'leaf').

    Returns:
        Normalized AYUR-INTEL plant identification response dictionary.
    """
    t_start = time.perf_counter()

    # Step 1: Input Validation
    t_val_start = time.perf_counter()
    validate_plant_image(file_bytes, content_type=content_type, filename=filename)
    t_val_end = time.perf_counter()
    val_ms = round((t_val_end - t_val_start) * 1000, 2)

    # Step 2: API Key Resolution
    api_key = settings.effective_plantnet_api_key
    if not api_key:
        logger.error("PlantNet API key is missing from configuration.")
        raise PlantNetConfigurationError("Plant identification service is not configured.")

    project = getattr(settings, "AYURINTEL_PLANTNET_PROJECT", "all") or "all"
    url = f"{PLANTNET_BASE_URL}/{project}?api-key={api_key}"

    # Prepare multipart upload
    ext = ".jpg"
    if content_type and "png" in content_type.lower():
        ext = ".png"
    elif filename and filename.lower().endswith(".png"):
        ext = ".png"

    upload_filename = f"plant_upload{ext}"
    mime = "image/png" if ext == ".png" else "image/jpeg"

    files = {
        "images": (upload_filename, io.BytesIO(file_bytes), mime),
    }
    data = {
        "organs": [organ if organ in {"leaf", "flower", "fruit", "bark", "habit", "other"} else "leaf"],
    }

    # Step 3: Server-side API Call
    t_req_start = time.perf_counter()
    try:
        response = requests.post(
            url,
            files=files,
            data=data,
            timeout=(5.0, 15.0),  # (connect_timeout, read_timeout)
        )
        t_req_end = time.perf_counter()
        req_ms = round((t_req_end - t_req_start) * 1000, 2)
    except requests.exceptions.Timeout as e:
        logger.warning("PlantNet API request timed out after 15s.")
        raise PlantNetTimeoutError("Plant identification service timed out.") from e
    except requests.exceptions.ConnectionError as e:
        logger.error("Failed to connect to Pl@ntNet API: %s", e)
        raise PlantNetProviderError("Cannot connect to plant identification service.", status_code=502) from e
    except requests.exceptions.RequestException as e:
        logger.error("PlantNet HTTP request error: %s", e)
        raise PlantNetProviderError("Plant identification service request failed.", status_code=502) from e

    # Step 4: Handle HTTP Status Codes
    if response.status_code == 401 or response.status_code == 403:
        logger.error("PlantNet API returned auth error HTTP %d", response.status_code)
        raise PlantNetAuthError("Plant identification service authentication failed.")

    if response.status_code == 429:
        logger.warning("PlantNet API rate limit reached (HTTP 429).")
        raise PlantNetRateLimitError("PlantNet API rate limit exceeded. Please try again later.")

    if response.status_code >= 400:
        logger.error("PlantNet API returned error HTTP %d: %s", response.status_code, response.text[:200])
        raise PlantNetProviderError(
            f"Plant identification service returned error status {response.status_code}.",
            status_code=502 if response.status_code >= 500 else 400,
        )

    # Step 5: Response Parsing & Normalization
    t_norm_start = time.perf_counter()
    try:
        raw_json = response.json()
    except Exception as e:
        logger.error("Failed to parse Pl@ntNet JSON response: %s", e)
        raise PlantNetParseError("Received invalid response from plant identification provider.") from e

    normalized = normalize_plantnet_response(raw_json, default_organ=organ)
    t_norm_end = time.perf_counter()
    norm_ms = round((t_norm_end - t_norm_start) * 1000, 2)

    t_total_end = time.perf_counter()
    total_ms = round((t_total_end - t_start) * 1000, 2)

    # Telemetry logging
    logger.info(
        "PlantNet Identification Pipeline Completed | Validation: %s ms | Request: %s ms | Normalization: %s ms | Total: %s ms",
        val_ms,
        req_ms,
        norm_ms,
        total_ms,
    )

    return normalized
