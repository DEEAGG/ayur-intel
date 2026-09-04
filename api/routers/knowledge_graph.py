"""AYUR-INTEL — Knowledge Graph API Routes (Phase 15)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User
from api.services.knowledge_graph_service import (
    build_knowledge_graph,
    search_graph,
    get_node_details,
)

logger = logging.getLogger("ayur_intel.routers.knowledge_graph")

router = APIRouter(prefix="/api", tags=["Knowledge Graph"])


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/cases/{case_id}/knowledge-graph")
def get_knowledge_graph(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the knowledge graph for a Product Case."""
    result = build_knowledge_graph(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.get("/cases/{case_id}/knowledge-graph/search")
def search_knowledge_graph(
    case_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search knowledge graph entities."""
    result = search_graph(db, user, case_id, q)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return result


@router.get("/cases/{case_id}/knowledge-graph/{node_id}")
def get_knowledge_graph_node(
    case_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed information for a specific graph node."""
    result = get_node_details(db, user, case_id, node_id)
    if not result:
        raise HTTPException(status_code=404, detail="Node not found")
    return result
