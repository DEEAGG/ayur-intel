from datetime import datetime, timezone
import logging
import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import User, ProductCase
from api.models.risk import Risk, SelfExtensionRequest, RiskAssessment
from api.schemas.risk import (
    RiskAnalysisResponse,
    RiskAssessmentResponse,
    UpdateRiskStatusRequest,
    UpdateExtensionStatusRequest,
)
from api.services.risk_service import (
    generate_risk_analysis,
    update_risk_status,
    update_extension_status,
)
from api.services.gemini_risk_service import (
    gather_case_risk_context,
    synthesize_risk_with_gemini,
    save_or_replace_risk_assessment,
    format_risk_assessment_response,
)
from api.services.audit_service import log_action

logger = logging.getLogger("ayur_intel.routers.risk")

router = APIRouter(prefix="/api", tags=["Risk & Self-Extension"])

# Process-level thread-safe per-case locks for generation & reassessment
_case_locks_guard = threading.Lock()
_case_locks: dict[str, threading.Lock] = {}


def get_case_lock(case_id: str) -> threading.Lock:
    """Retrieve or initialize a per-case mutex lock."""
    with _case_locks_guard:
        if case_id not in _case_locks:
            _case_locks[case_id] = threading.Lock()
        return _case_locks[case_id]


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(username="demo", display_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# AI Risk Assessment Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/cases/{case_id}/risk-assessment",
    response_model=RiskAssessmentResponse,
    summary="Get existing saved AI Risk Assessment",
)
def get_risk_assessment_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve the latest saved Risk Assessment for a Product Case."""
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_id,
        (ProductCase.owner_id == user.id) | (ProductCase.is_demo == True),
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Product Case not found")

    record = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == case.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="No Risk Assessment generated yet for this case")

    return format_risk_assessment_response(record, case)


@router.post(
    "/cases/{case_id}/risk-assessment",
    response_model=RiskAssessmentResponse,
    summary="Generate or retrieve AI Risk Assessment",
)
def create_or_get_risk_assessment_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate structured AI Risk Assessment, or return saved if already exists (thread-safe)."""
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_id,
        (ProductCase.owner_id == user.id) | (ProductCase.is_demo == True),
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Product Case not found")

    # Fast check before lock acquisition
    existing = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == case.id).first()
    if existing:
        return format_risk_assessment_response(existing, case)

    # Per-case concurrency lock
    lock = get_case_lock(case.public_id)
    with lock:
        # Double-check inside lock after re-querying fresh state
        db.expire_all()
        existing = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == case.id).first()
        if existing:
            return format_risk_assessment_response(existing, case)

        # Gather case context and synthesize
        context, valid_keys, coverage = gather_case_risk_context(db, case)
        assessment_data, source, model_used = synthesize_risk_with_gemini(context, valid_keys, coverage)

        record = save_or_replace_risk_assessment(
            db=db,
            user=user,
            case=case,
            assessment_dict=assessment_data,
            source=source,
            model_used=model_used,
            coverage=coverage,
        )

        log_action(
            db, action="CREATE", resource_type="RISK_ASSESSMENT",
            product_case_id=case.public_id, user_id=user.id,
            user_public_id=user.public_id, username=user.username,
        )

        return format_risk_assessment_response(record, case)


@router.post(
    "/cases/{case_id}/risk-assessment/reassess",
    response_model=RiskAssessmentResponse,
    summary="Force refresh / regenerate AI Risk Assessment",
)
def reassess_risk_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Explicitly regenerate Risk Assessment with fresh Gemini AI synthesis (thread-safe)."""
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_id,
        (ProductCase.owner_id == user.id) | (ProductCase.is_demo == True),
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Product Case not found")

    req_time = datetime.now(timezone.utc)
    lock = get_case_lock(case.public_id)
    with lock:
        db.expire_all()
        # Coalesce burst concurrent reassess calls that arrived while another reassessment was in-flight
        existing = db.query(RiskAssessment).filter(RiskAssessment.product_case_id == case.id).first()
        if existing and existing.updated_at:
            updated_dt = existing.updated_at if existing.updated_at.tzinfo else existing.updated_at.replace(tzinfo=timezone.utc)
            if (updated_dt - req_time).total_seconds() >= -0.05:
                return format_risk_assessment_response(existing, case)

        context, valid_keys, coverage = gather_case_risk_context(db, case)
        assessment_data, source, model_used = synthesize_risk_with_gemini(context, valid_keys, coverage)

        record = save_or_replace_risk_assessment(
            db=db,
            user=user,
            case=case,
            assessment_dict=assessment_data,
            source=source,
            model_used=model_used,
            coverage=coverage,
        )

        log_action(
            db, action="UPDATE", resource_type="RISK_ASSESSMENT",
            product_case_id=case.public_id, user_id=user.id,
            user_public_id=user.public_id, username=user.username,
        )

        return format_risk_assessment_response(record, case)


# ---------------------------------------------------------------------------
# Legacy Analysis & Status Routes
# ---------------------------------------------------------------------------



@router.post("/cases/{case_id}/risk-analysis")
def create_risk_analysis(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate risk analysis and self-extension for a Product Case."""
    result = generate_risk_analysis(db, user, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product Case not found")
    log_action(db, action="CREATE", resource_type="RISK_ANALYSIS",
               product_case_id=case_id, user_id=user.id,
               user_public_id=user.public_id, username=user.username)
    db.commit()
    return result


@router.get("/cases/{case_id}/risks")
def list_risks(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all risks for a Product Case."""
    from api.models.models import ProductCase
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Product Case not found")

    risks = db.query(Risk).filter(Risk.product_case_id == case.id).order_by(Risk.created_at.desc()).all()
    return {
        "risks": [{
            "id": r.public_id,
            "category": r.category,
            "level": r.level,
            "title": r.title,
            "status": r.status,
            "source_phase": r.source_phase,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        } for r in risks]
    }


@router.patch("/risks/{risk_id}")
def patch_risk(
    risk_id: str,
    body: UpdateRiskStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a risk's status."""
    result = update_risk_status(db, user, risk_id, body.status, body.note)
    if not result:
        raise HTTPException(status_code=404, detail="Risk not found")
    return result


@router.patch("/self-extension/{ext_id}")
def patch_extension(
    ext_id: str,
    body: UpdateExtensionStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a self-extension request's status."""
    result = update_extension_status(db, user, ext_id, body.status)
    if not result:
        raise HTTPException(status_code=404, detail="Extension request not found")
    return result
