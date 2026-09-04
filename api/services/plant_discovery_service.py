"""AYUR-INTEL — Plant Discovery Service.

Business logic for Plant Discovery: CRUD, image handling, analysis,
and linking to Product Cases.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from api.core.config import PROJECT_ROOT, settings
from api.models.models import PlantDiscovery, ProductCase, User
from api.services.plant_identification import (
    CandidatePlant,
    IdentificationResult,
    get_plant_identification_provider,
)

logger = logging.getLogger("ayur_intel.plant_discovery_service")

# ---------------------------------------------------------------------------
# Image configuration
# ---------------------------------------------------------------------------

UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads" / "plant_images"
MAX_IMAGE_SIZE_MB = 10
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _ensure_upload_dir():
    """Create the upload directory if it doesn't exist."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deserialize_list(value: str) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _discovery_to_dict(disc: PlantDiscovery) -> dict:
    """Convert a PlantDiscovery ORM object to a dict for API response."""
    alternatives = _deserialize_list(disc.alternative_candidates) if disc.alternative_candidates else []

    return {
        "id": disc.public_id,
        "owner_id": disc.owner.public_id if disc.owner else "",
        "product_case_id": disc.product_case.public_id if disc.product_case else None,
        "image_filename": disc.image_filename,
        "image_url": f"/api/plant-discoveries/{disc.public_id}/image" if disc.image_filename else None,
        "candidate_name": disc.candidate_name,
        "botanical_name": disc.botanical_name,
        "confidence": disc.confidence,
        "alternative_candidates": alternatives,
        "identification_notes": disc.identification_notes,
        "verification_required": disc.verification_required,
        "provider": disc.provider or "none",
        "provider_used": disc.provider or "none",
        "status": disc.status,
        "created_at": disc.created_at.isoformat() if disc.created_at else "",
        "updated_at": disc.updated_at.isoformat() if disc.updated_at else "",
    }


# ---------------------------------------------------------------------------
# Image validation
# ---------------------------------------------------------------------------

def validate_image(content_type: str, filename: str, size_bytes: int) -> Optional[str]:
    """Validate an uploaded image. Returns error message or None if valid."""
    if size_bytes > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        return f"Image too large. Maximum size is {MAX_IMAGE_SIZE_MB}MB."

    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        return f"Unsupported image type: {content_type}. Allowed: JPEG, PNG, WebP."

    ext = Path(filename).suffix.lower() if filename else ""
    if ext and ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file extension: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

    return None


def save_image(file_bytes: bytes, original_filename: str, content_type: str) -> dict:
    """Save an uploaded image to disk. Returns metadata dict."""
    _ensure_upload_dir()

    ext = Path(original_filename).suffix.lower() if original_filename else ".jpg"
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / safe_filename
    file_path.write_bytes(file_bytes)

    logger.info("Saved plant image: %s (%d bytes)", safe_filename, len(file_bytes))

    return {
        "filename": safe_filename,
        "original_filename": original_filename,
        "path": str(file_path),
        "size_bytes": len(file_bytes),
        "content_type": content_type,
    }


def get_image_path(filename: str) -> Optional[Path]:
    """Get the path to an uploaded image."""
    if not filename:
        return None
    path = UPLOAD_DIR / filename
    if path.exists():
        return path
    return None


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def create_discovery(
    db: Session,
    owner: User,
    image_metadata: dict,
) -> dict:
    """Create a new Plant Discovery record with uploaded image metadata."""
    now = datetime.now(timezone.utc)

    disc = PlantDiscovery(
        owner_id=owner.id,
        image_filename=image_metadata.get("filename"),
        image_path=image_metadata.get("path"),
        image_size_bytes=image_metadata.get("size_bytes"),
        image_content_type=image_metadata.get("content_type"),
        status="UPLOADED",
        verification_required=True,
        created_at=now,
        updated_at=now,
    )
    db.add(disc)
    db.commit()
    db.refresh(disc)

    logger.info("Created plant discovery: %s", disc.public_id)
    return _discovery_to_dict(disc)


def list_discoveries(
    db: Session,
    owner: User,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    """List all Plant Discoveries for a user."""
    query = db.query(PlantDiscovery).filter(PlantDiscovery.owner_id == owner.id)
    total = query.count()
    items = (
        query
        .order_by(PlantDiscovery.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "discoveries": [_discovery_to_dict(d) for d in items],
        "total": total,
    }


def get_discovery(db: Session, owner: User, public_id: str) -> Optional[dict]:
    """Get a single Plant Discovery by public ID, scoped to owner."""
    disc = (
        db.query(PlantDiscovery)
        .filter(
            PlantDiscovery.public_id == public_id,
            PlantDiscovery.owner_id == owner.id,
        )
        .first()
    )
    if disc is None:
        return None
    return _discovery_to_dict(disc)


def analyze_discovery(db: Session, owner: User, public_id: str) -> Optional[dict]:
    """Run plant identification analysis on a discovery.

    Uses the configured identification provider. If no provider is
    configured, returns a clear message indicating configuration is needed.
    """
    disc = (
        db.query(PlantDiscovery)
        .filter(
            PlantDiscovery.public_id == public_id,
            PlantDiscovery.owner_id == owner.id,
        )
        .first()
    )
    if disc is None:
        return None

    now = datetime.now(timezone.utc)
    disc.status = "ANALYZING"
    disc.updated_at = now
    db.commit()

    try:
        provider = get_plant_identification_provider()

        if not provider.is_configured():
            # Provider not configured — return clear message
            disc.status = "IDENTIFIED"
            disc.provider = provider.name
            disc.identification_notes = (
                "Plant identification provider is not yet configured. "
                "To enable real plant identification, set the "
                "AYURINTEL_PLANT_ID_PROVIDER environment variable and "
                "configure the corresponding API key."
            )
            disc.verification_required = True
            disc.confidence = None
            disc.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(disc)
            return _discovery_to_dict(disc)

        # Read image bytes
        image_path = get_image_path(disc.image_filename)
        if image_path is None:
            disc.status = "FAILED"
            disc.identification_notes = "Image file not found on disk."
            db.commit()
            db.refresh(disc)
            return _discovery_to_dict(disc)

        image_bytes = image_path.read_bytes()
        content_type = disc.image_content_type or "image/jpeg"

        # Run identification
        result: IdentificationResult = provider.identify(image_bytes, content_type)

        # Populate results
        disc.status = "IDENTIFIED"
        disc.provider = result.provider
        disc.verification_required = result.verification_required
        disc.identification_notes = result.identification_notes

        if result.primary_candidate:
            disc.candidate_name = result.primary_candidate.name
            disc.botanical_name = result.primary_candidate.scientific_name
            disc.confidence = result.primary_candidate.confidence

        # Store alternatives (exclude the primary)
        alternatives = []
        if result.primary_candidate:
            for c in result.candidates:
                if c.name != result.primary_candidate.name:
                    alternatives.append({
                        "name": c.name,
                        "scientific_name": c.scientific_name,
                        "confidence": c.confidence,
                        "notes": c.notes,
                    })
        else:
            for c in result.candidates:
                alternatives.append({
                    "name": c.name,
                    "scientific_name": c.scientific_name,
                    "confidence": c.confidence,
                    "notes": c.notes,
                })

        disc.alternative_candidates = json.dumps(alternatives)
        disc.provider_raw_result = result.provider_raw
        disc.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(disc)
        logger.info("Analyzed plant discovery %s — provider: %s, confidence: %s",
                     disc.public_id, result.provider, result.confidence)
        return _discovery_to_dict(disc)

    except Exception as e:
        logger.error("Analysis failed for %s: %s", public_id, e, exc_info=True)
        disc.status = "FAILED"
        disc.identification_notes = f"Analysis failed: {str(e)}"
        disc.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(disc)
        return _discovery_to_dict(disc)


def link_to_case(
    db: Session,
    owner: User,
    discovery_id: str,
    case_public_id: str,
) -> Optional[dict]:
    """Link a Plant Discovery to a Product Case."""
    disc = (
        db.query(PlantDiscovery)
        .filter(
            PlantDiscovery.public_id == discovery_id,
            PlantDiscovery.owner_id == owner.id,
        )
        .first()
    )
    if disc is None:
        return None, "Discovery not found"

    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == case_public_id,
            ProductCase.owner_id == owner.id,
        )
        .first()
    )
    if case is None:
        return None, "Product Case not found"

    disc.product_case_id = case.id
    disc.status = "SAVED"
    disc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(disc)

    logger.info("Linked plant discovery %s to case %s", discovery_id, case_public_id)
    return _discovery_to_dict(disc), None


def delete_discovery(db: Session, owner: User, public_id: str) -> bool:
    """Delete a Plant Discovery and its uploaded image."""
    disc = (
        db.query(PlantDiscovery)
        .filter(
            PlantDiscovery.public_id == public_id,
            PlantDiscovery.owner_id == owner.id,
        )
        .first()
    )
    if disc is None:
        return False

    # Remove image file
    if disc.image_filename:
        img_path = UPLOAD_DIR / disc.image_filename
        if img_path.exists():
            img_path.unlink()
            logger.info("Deleted image: %s", disc.image_filename)

    db.delete(disc)
    db.commit()
    logger.info("Deleted plant discovery: %s", public_id)
    return True
