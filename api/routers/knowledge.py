"""AYUR-INTEL — Knowledge Engine API routes.

Handles knowledge search, finding management, and source listing.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.config import settings
from api.models.models import User
from api.schemas.knowledge import (
    KnowledgeFindingListResponse,
    KnowledgeFindingResponse,
    KnowledgeSaveRequest,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    SourceListResponse,
    SourceResponse,
)
from api.services.knowledge_service import (
    get_case_findings,
    get_finding,
    get_source,
    list_sources,
    save_finding,
    search_knowledge,
)
from api.services.product_case_service import get_or_create_demo_user

logger = logging.getLogger("ayur_intel.routers.knowledge")

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Engine"])


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
    "/search",
    response_model=KnowledgeSearchResponse,
    summary="Search for Traditional Knowledge and research findings",
)
def search(
    payload: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search across all registered source adapters for knowledge findings.

    Returns aggregated results from all sources, each clearly labeled
    with authority, jurisdiction, and confidence. Sources that are not
    configured return a clear message.
    """
    try:
        result = search_knowledge(
            db=db,
            query=payload.query,
            plant_name=payload.plant_name,
            botanical_name=payload.botanical_name,
            category=payload.category,
            jurisdiction=payload.jurisdiction,
            limit=payload.limit,
        )
        return result
    except Exception as e:
        logger.error("Knowledge search failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Knowledge search failed")


@router.get(
    "/findings/{finding_id}",
    response_model=KnowledgeFindingResponse,
    responses={404: {"description": "Finding not found"}},
    summary="Get a Knowledge Finding by ID",
)
def get_finding_by_id(
    finding_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single Knowledge Finding. Scoped to the current user."""
    result = get_finding(db=db, owner=user, finding_public_id=finding_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Knowledge Finding not found")
    return result


@router.post(
    "/findings/save",
    response_model=KnowledgeFindingResponse,
    status_code=201,
    responses={404: {"description": "Product Case not found"}},
    summary="Save a knowledge finding to a Product Case",
)
def save_finding_to_case(
    payload: KnowledgeSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save a knowledge finding (from search results) to a Product Case."""
    finding_data = {
        "title": payload.title,
        "summary": payload.summary,
        "category": payload.category,
        "plant_name": payload.plant_name,
        "botanical_name": payload.botanical_name,
        "traditional_name": payload.traditional_name,
        "source_name": payload.source_name,
        "source_authority": payload.source_authority,
        "jurisdiction": payload.jurisdiction,
        "confidence": payload.confidence,
        "relevance": payload.relevance,
        "evidence_locator": payload.evidence_locator,
        "excerpt": payload.excerpt,
        "source_identifier": payload.source_identifier,
        "publication_date": payload.publication_date,
        "retrieval_date": payload.retrieval_date,
        "source_version": payload.source_version,
        "limitations": payload.limitations,
        "is_conflicting": payload.is_conflicting,
        "conflicting_details": payload.conflicting_details,
    }
    result = save_finding(
        db=db,
        owner=user,
        finding_data=finding_data,
        product_case_id=payload.product_case_id,
        plant_discovery_id=payload.plant_discovery_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.get(
    "/sources",
    response_model=SourceListResponse,
    summary="List all registered knowledge sources",
)
def list_all_sources(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all registered source adapters and their configuration status."""
    return list_sources(db=db)


@router.get(
    "/sources/{source_id}",
    response_model=SourceResponse,
    responses={404: {"description": "Source not found"}},
    summary="Get a knowledge source by ID",
)
def get_source_by_id(
    source_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single Source. Includes configuration status."""
    result = get_source(db=db, public_id=source_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


# ---------------------------------------------------------------------------
# Grounded Knowledge Synthesis Endpoints (Phase 3A)
# ---------------------------------------------------------------------------

@router.get(
    "/synthesis/{document_identifier}",
    summary="Get persisted Knowledge Synthesis (0 Gemini Calls)",
)
def get_knowledge_synthesis(
    document_identifier: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """GET-First Persistence Lifecycle. NEVER invokes Gemini implicitly.

    Returns persisted synthesis if valid & matching current evidence fingerprint,
    otherwise returns structured evidence fallback.
    """
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.get_synthesis(db=db, document_identifier=document_identifier)


@router.post(
    "/synthesis/generate",
    summary="Generate Knowledge Synthesis (Calls Gemini on explicit request)",
)
def generate_knowledge_synthesis(
    document_identifier: str = Query(..., description="Document identifier to synthesize"),
    force_regenerate: bool = Query(False, description="Force Gemini re-synthesis"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Explicit POST endpoint to generate grounded AI synthesis for a document."""
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.generate_synthesis(
        db=db,
        document_identifier=document_identifier,
        force_regenerate=force_regenerate,
    )


@router.post(
    "/synthesis/regenerate",
    summary="Regenerate Knowledge Synthesis (Force re-synthesis)",
)
def regenerate_knowledge_synthesis(
    document_identifier: str = Query(..., description="Document identifier to re-synthesize"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Explicit POST endpoint to force regenerate grounded AI synthesis for a document."""
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.generate_synthesis(
        db=db,
        document_identifier=document_identifier,
        force_regenerate=True,
    )


@router.get(
    "/source-analysis/{source_name}/{case_id}",
    summary="Get Product-Specific Source Analysis (0 Gemini Calls)",
)
def get_product_source_analysis(
    source_name: str,
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """GET-first Product-Specific Source Analysis endpoint. 0 Gemini calls on GET."""
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.get_product_source_analysis(
        db=db, source_name=source_name, case_id=case_id
    )


@router.post(
    "/source-analysis/generate",
    summary="Generate Product-Specific Source Analysis (Calls Gemini on explicit request)",
)
def generate_product_source_analysis(
    source_name: str = Query(..., description="Source name (e.g. CHARAKA, PMC, FSSAI)"),
    case_id: str = Query(..., description="Product case ID"),
    force_regenerate: bool = Query(False, description="Force re-analysis"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Explicit POST endpoint to analyze a Knowledge Hub source for a specific Product Case."""
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.generate_product_source_analysis(
        db=db, source_name=source_name, case_id=case_id, force_regenerate=force_regenerate
    )


@router.post(
    "/integrated-search",
    summary="Integrated Search across DRAVYA ~400 plants and Classical Evidence",
)
def integrated_knowledge_search(
    source_name: str = Query("CHARAKA", description="Source name (e.g. CHARAKA, SUSHRUTA)"),
    query: str = Query("", description="Search term (e.g. Ashwagandha, Brahmi)"),
    limit: int = Query(10, description="Max results limit"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Integrated Search returning matched DRAVYA plant profile and matching classical evidence. 0 Gemini calls."""
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.search_integrated_knowledge(
        db=db, source_name=source_name, query=query, limit=limit
    )


@router.get(
    "/plant/{plant_id}",
    summary="Get DRAVYA Plant Profile Details",
)
def get_dravya_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch structured DRAVYA plant profile by plant_id."""
    from api.services.dravya_service import DravyaService
    plant = DravyaService.get_plant_by_id(db, plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant record not found in DRAVYA dataset.")
    return plant


@router.get(
    "/plant-explanation/{source_name}/{plant_id}",
    summary="GET Grounded Plant Research Explanation (GET-First, 0 Gemini Calls)",
)
def get_plant_explanation(
    source_name: str,
    plant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """GET-first Plant Research Explanation endpoint. 0 Gemini calls on GET."""
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.get_plant_explanation(
        db=db, source_name=source_name, plant_id=plant_id
    )


@router.post(
    "/plant-explanation/generate",
    summary="Generate Grounded Plant Research Explanation (Calls Gemini on explicit request)",
)
def generate_plant_explanation(
    source_name: str = Query(..., description="Source name (e.g. CHARAKA, SUSHRUTA)"),
    plant_id: int = Query(..., description="DRAVYA Plant ID"),
    force_regenerate: bool = Query(False, description="Force re-generation"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Explicit POST endpoint to generate AI plant research explanation grounded in evidence."""
    from api.services.knowledge_synthesis_service import KnowledgeSynthesisService
    return KnowledgeSynthesisService.generate_plant_explanation(
        db=db, source_name=source_name, plant_id=plant_id, force_regenerate=force_regenerate
    )
