"""AYUR-INTEL — Plant Discovery API routes.

Handles image upload, analysis, saving, and linking to Product Cases.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.schemas.plant_discovery import (
    AnalysisStatusResponse,
    PlantDiscoveryLinkCase,
    PlantDiscoveryListResponse,
    PlantDiscoveryResponse,
)
from api.services.plant_discovery_service import (
    analyze_discovery as svc_analyze,
    create_discovery as svc_create,
    delete_discovery as svc_delete,
    get_discovery as svc_get,
    get_image_path as svc_get_image,
    link_to_case as svc_link,
    list_discoveries as svc_list,
    save_image as svc_save,
    validate_image as svc_validate,
)
from api.services.product_case_service import get_or_create_demo_user

logger = logging.getLogger("ayur_intel.routers.plant_discovery")

router = APIRouter(prefix="/api/plant-discoveries", tags=["Plant Discovery"])


# ---------------------------------------------------------------------------
# Dependency: get current user
# ---------------------------------------------------------------------------

def get_current_user(db: Session = Depends(get_db)) -> User:
    """Get the current user. Phase 1 demo mode."""
    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)
    raise HTTPException(status_code=401, detail="Authentication required")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=PlantDiscoveryResponse,
    status_code=201,
    summary="Upload a plant image and create a discovery",
)
async def upload_plant_image(
    file: UploadFile = File(..., description="Plant image (JPEG, PNG, WebP)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a plant image to create a new Plant Discovery.

    The image is validated (type, size) and stored.
    Analysis is not started automatically — call the analyze endpoint separately.
    """
    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload.jpg"

    # Read file bytes
    file_bytes = await file.read()
    size_bytes = len(file_bytes)

    # Validate
    error = svc_validate(content_type, filename, size_bytes)
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Save image
    image_meta = svc_save(file_bytes, filename, content_type)

    # Create discovery record
    discovery = svc_create(db=db, owner=user, image_metadata=image_meta)
    return discovery


@router.get(
    "",
    response_model=PlantDiscoveryListResponse,
    summary="List all Plant Discoveries",
)
def list_all(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all Plant Discoveries for the current user."""
    return svc_list(db=db, owner=user, skip=skip, limit=limit)


@router.get(
    "/{discovery_id}",
    response_model=PlantDiscoveryResponse,
    responses={404: {"description": "Discovery not found"}},
    summary="Get a Plant Discovery by ID",
)
def get_one(
    discovery_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single Plant Discovery. Scoped to the current user."""
    disc = svc_get(db=db, owner=user, public_id=discovery_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="Plant Discovery not found")
    return disc


@router.get(
    "/{discovery_id}/image",
    summary="Get the uploaded plant image",
)
def get_image(
    discovery_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve the uploaded image for a Plant Discovery."""
    disc = svc_get(db=db, owner=user, public_id=discovery_id)
    if disc is None:
        raise HTTPException(status_code=404, detail="Plant Discovery not found")

    if not disc.get("image_filename"):
        raise HTTPException(status_code=404, detail="No image attached")

    image_path = svc_get_image(disc["image_filename"])
    if image_path is None:
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    # Determine content type from extension
    ext = image_path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }
    media_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(str(image_path), media_type=media_type)


@router.post(
    "/{discovery_id}/analyze",
    response_model=PlantDiscoveryResponse,
    responses={404: {"description": "Discovery not found"}},
    summary="Analyze a plant image for identification",
)
def analyze(
    discovery_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run plant identification analysis on an uploaded image.

    Uses the configured identification provider. If no provider is
    configured, returns a clear indication that configuration is needed.
    """
    result = svc_analyze(db=db, owner=user, public_id=discovery_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Plant Discovery not found")
    return result


@router.post(
    "/{discovery_id}/link-case",
    response_model=PlantDiscoveryResponse,
    responses={404: {"description": "Discovery or Case not found"}},
    summary="Link a discovery to a Product Case",
)
def link(
    discovery_id: str,
    payload: PlantDiscoveryLinkCase,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Link a Plant Discovery to an existing Product Case."""
    result, error = svc_link(
        db=db,
        owner=user,
        discovery_id=discovery_id,
        case_public_id=payload.product_case_id,
    )
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@router.delete(
    "/{discovery_id}",
    status_code=204,
    responses={404: {"description": "Discovery not found"}},
    summary="Delete a Plant Discovery",
)
def delete(
    discovery_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a Plant Discovery and its uploaded image."""
    deleted = svc_delete(db=db, owner=user, public_id=discovery_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plant Discovery not found")
    return None
