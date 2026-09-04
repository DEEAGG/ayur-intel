"""AYUR-INTEL — Analytics + Impact Intelligence Service (Phase 19).

Aggregates metrics from existing database tables.
No new database tables required — reuses audit_logs, risks, evidence,
reviews, monitoring, innovation, patent, regulatory, etc.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.models import (
    ProductCase, User,
    InnovationAnalysis, InnovationComponent,
    PatentSearch, PatentRelevance, PatentAnalysis,
    IPStrategy, IPStrategyItem,
    RegulatoryProfile, RegulatoryRequirement,
)
from api.models.evidence import UnifiedEvidence, CaseFinding
from api.models.risk import Risk, SelfExtensionRequest
from api.models.review import ReviewRequest, ReviewDecision
from api.models.monitoring import MonitoringConfig, MonitoringRun, Alert
from api.models.jurisdiction_comparison import JurisdictionComparison
from api.models.security import AuditLog

logger = logging.getLogger("ayur_intel.analytics")


def get_product_analytics(db: Session, user: User, case_public_id: str) -> Optional[dict]:
    """Get analytics for a single Product Case."""
    case = db.query(ProductCase).filter(
        ProductCase.public_id == case_public_id,
        ProductCase.owner_id == user.id,
    ).first()
    if not case:
        return None

    case_id = case.id

    # Product completeness
    passport_fields = {
        "name": bool(case.name),
        "ingredients": bool(case.ingredients and case.ingredients != "[]"),
        "form": bool(case.form),
        "intended_use": bool(case.intended_use),
        "claims": bool(case.claims and case.claims != "[]"),
        "formulation": bool(case.formulation),
        "process": bool(case.process),
        "brand": bool(case.brand),
        "packaging": bool(case.packaging),
    }
    filled = sum(1 for v in passport_fields.values() if v)
    total_fields = len(passport_fields)
    passport_completion = round((filled / total_fields) * 100) if total_fields > 0 else 0

    # Innovation
    innovation_count = db.query(InnovationAnalysis).filter(
        InnovationAnalysis.product_case_id == case_id,
    ).count()
    latest_innovation = db.query(InnovationAnalysis).filter(
        InnovationAnalysis.product_case_id == case_id,
    ).order_by(InnovationAnalysis.created_at.desc()).first()

    components_traditional = 0
    components_differentiated = 0
    if latest_innovation:
        components_traditional = latest_innovation.traditional_count or 0
        components_differentiated = latest_innovation.differentiated_count or 0

    # Patents
    patent_searches = db.query(PatentSearch).filter(
        PatentSearch.product_case_id == case_id,
    ).count()
    patent_relevances = db.query(PatentRelevance).filter(
        PatentRelevance.product_case_id == case_id,
    ).count()
    patent_analyses = db.query(PatentAnalysis).filter(
        PatentAnalysis.product_case_id == case_id,
    ).count()

    # IP Strategy
    ip_items = db.query(IPStrategyItem).join(IPStrategy).filter(
        IPStrategy.product_case_id == case_id,
    ).count()

    # Regulatory
    regulatory_profiles = db.query(RegulatoryProfile).filter(
        RegulatoryProfile.product_case_id == case_id,
    ).count()
    regulatory_requirements = 0
    for profile in db.query(RegulatoryProfile).filter(
        RegulatoryProfile.product_case_id == case_id,
    ).all():
        regulatory_requirements += db.query(RegulatoryRequirement).filter(
            RegulatoryRequirement.profile_id == profile.id,
        ).count()

    # Jurisdiction Comparison
    comparisons = db.query(JurisdictionComparison).filter(
        JurisdictionComparison.product_case_id == case_id,
    ).count()

    # Evidence
    evidence_count = db.query(CaseFinding).filter(
        CaseFinding.product_case_id == case_id,
    ).count()

    # Risks
    risk_count = db.query(Risk).filter(Risk.product_case_id == case_id).count()
    high_risks = db.query(Risk).filter(
        Risk.product_case_id == case_id, Risk.level == "HIGH",
    ).count()
    medium_risks = db.query(Risk).filter(
        Risk.product_case_id == case_id, Risk.level == "MEDIUM",
    ).count()
    low_risks = db.query(Risk).filter(
        Risk.product_case_id == case_id, Risk.level == "LOW",
    ).count()
    open_risks = db.query(Risk).filter(
        Risk.product_case_id == case_id, Risk.status == "OPEN",
    ).count()

    # Self-Extension
    extensions_total = db.query(SelfExtensionRequest).filter(
        SelfExtensionRequest.product_case_id == case_id,
    ).count()
    extensions_open = db.query(SelfExtensionRequest).filter(
        SelfExtensionRequest.product_case_id == case_id,
        SelfExtensionRequest.status == "OPEN",
    ).count()
    extensions_resolved = db.query(SelfExtensionRequest).filter(
        SelfExtensionRequest.product_case_id == case_id,
        SelfExtensionRequest.status == "RESOLVED",
    ).count()

    # Reviews
    reviews_total = db.query(ReviewRequest).filter(
        ReviewRequest.product_case_id == case_id,
    ).count()
    reviews_pending = db.query(ReviewRequest).filter(
        ReviewRequest.product_case_id == case_id,
        ReviewRequest.status.in_(["PENDING", "ASSIGNED"]),
    ).count()
    reviews_completed = db.query(ReviewRequest).filter(
        ReviewRequest.product_case_id == case_id,
        ReviewRequest.status == "COMPLETED",
    ).count()

    # Monitoring
    monitoring = db.query(MonitoringConfig).filter(
        MonitoringConfig.product_case_id == case_id,
    ).first()
    monitoring_runs = db.query(MonitoringRun).filter(
        MonitoringRun.product_case_id == case_id,
    ).count()
    monitoring_alerts = db.query(Alert).filter(
        Alert.product_case_id == case_id,
    ).count()

    # Audit log entries for this case
    audit_entries = db.query(AuditLog).filter(
        AuditLog.product_case_id == case_public_id,
    ).count()

    # Workflow funnel
    funnel = _compute_funnel(case)

    return {
        "case_id": case_public_id,
        "case_name": case.name,
        "status": case.status,
        "created_at": case.created_at.isoformat() if case.created_at else "",
        "updated_at": case.updated_at.isoformat() if case.updated_at else "",

        # Passport
        "passport": {
            "completion_percent": passport_completion,
            "filled_fields": filled,
            "total_fields": total_fields,
            "fields": passport_fields,
        },

        # Innovation
        "innovation": {
            "analyses_run": innovation_count,
            "total_components": latest_innovation.total_components if latest_innovation else 0,
            "traditional_count": components_traditional,
            "differentiated_count": components_differentiated,
        },

        # Patents
        "patents": {
            "searches_run": patent_searches,
            "relevant_found": patent_relevances,
            "deep_analyses": patent_analyses,
        },

        # IP Strategy
        "ip_strategy": {
            "items": ip_items,
        },

        # Regulatory
        "regulatory": {
            "profiles_generated": regulatory_profiles,
            "requirements_found": regulatory_requirements,
        },

        # Jurisdiction Comparison
        "jurisdiction_comparison": {
            "comparisons_run": comparisons,
        },

        # Evidence
        "evidence": {
            "total_items": evidence_count,
            "status": "GOOD" if evidence_count >= 5 else "PARTIAL" if evidence_count > 0 else "LIMITED",
        },

        # Risks
        "risks": {
            "total": risk_count,
            "high": high_risks,
            "medium": medium_risks,
            "low": low_risks,
            "open": open_risks,
            "status": "ATTENTION_REQUIRED" if high_risks > 0 else "WATCH" if medium_risks > 0 else "CLEAR",
        },

        # Self-Extension
        "self_extension": {
            "total": extensions_total,
            "open": extensions_open,
            "resolved": extensions_resolved,
        },

        # Reviews
        "reviews": {
            "total": reviews_total,
            "pending": reviews_pending,
            "completed": reviews_completed,
        },

        # Monitoring
        "monitoring": {
            "configured": monitoring is not None,
            "enabled": monitoring.enabled if monitoring else False,
            "runs_completed": monitoring_runs,
            "alerts_generated": monitoring_alerts,
        },

        # Activity
        "activity": {
            "audit_entries": audit_entries,
        },

        # Funnel
        "funnel": funnel,
    }


def get_platform_analytics(db: Session, user: User) -> dict:
    """Get platform-wide analytics (aggregated, non-sensitive)."""
    # All cases for this user
    cases = db.query(ProductCase).filter(ProductCase.owner_id == user.id).all()
    total_cases = len(cases)
    active_cases = sum(1 for c in cases if c.status not in ("ARCHIVED",))

    # Passport completion averages
    completions = []
    for c in cases:
        fields = [c.name, c.ingredients, c.form, c.intended_use, c.claims, c.formulation, c.process]
        filled = sum(1 for f in fields if f and f != "[]")
        completions.append(round((filled / len(fields)) * 100))
    avg_completion = round(sum(completions) / len(completions)) if completions else 0

    # Innovation
    total_innovations = db.query(InnovationAnalysis).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()

    # Patents
    total_patent_searches = db.query(PatentSearch).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()
    total_patent_analyses = db.query(PatentAnalysis).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()

    # Regulatory
    total_regulatory_profiles = db.query(RegulatoryProfile).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()

    # Comparisons
    total_comparisons = db.query(JurisdictionComparison).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()

    # Evidence
    total_evidence = db.query(CaseFinding).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()

    # Risks
    total_risks = db.query(Risk).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()
    high_risks = db.query(Risk).join(ProductCase).filter(
        ProductCase.owner_id == user.id, Risk.level == "HIGH",
    ).count()

    # Self-Extension
    total_extensions = db.query(SelfExtensionRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()
    resolved_extensions = db.query(SelfExtensionRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id, SelfExtensionRequest.status == "RESOLVED",
    ).count()

    # Reviews
    total_reviews = db.query(ReviewRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()
    completed_reviews = db.query(ReviewRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id, ReviewRequest.status == "COMPLETED",
    ).count()

    # Monitoring
    active_monitoring = db.query(MonitoringConfig).join(ProductCase).filter(
        ProductCase.owner_id == user.id, MonitoringConfig.enabled == True,
    ).count()
    total_monitoring_runs = db.query(MonitoringRun).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()
    total_monitoring_alerts = db.query(Alert).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    ).count()

    # Risk distribution
    risk_distribution = {}
    for level in ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]:
        risk_distribution[level] = db.query(Risk).join(ProductCase).filter(
            ProductCase.owner_id == user.id, Risk.level == level,
        ).count()

    # Review decision distribution
    decision_dist = {}
    for d in ["CONFIRMED", "REJECTED", "MORE_INFORMATION_REQUIRED", "ESCALATED", "NO_ACTION"]:
        decision_dist[d] = db.query(ReviewDecision).join(ReviewRequest).join(ProductCase).filter(
            ProductCase.owner_id == user.id, ReviewDecision.decision == d,
        ).count()

    return {
        "overview": {
            "total_cases": total_cases,
            "active_cases": active_cases,
            "avg_passport_completion": avg_completion,
        },
        "analysis": {
            "innovation_analyses": total_innovations,
            "patent_searches": total_patent_searches,
            "patent_deep_analyses": total_patent_analyses,
            "regulatory_profiles": total_regulatory_profiles,
            "jurisdiction_comparisons": total_comparisons,
        },
        "evidence": {
            "total_items": total_evidence,
            "status": "GOOD" if total_evidence >= 10 else "PARTIAL" if total_evidence > 0 else "LIMITED",
        },
        "risks": {
            "total": total_risks,
            "distribution": risk_distribution,
        },
        "self_extension": {
            "total": total_extensions,
            "resolved": resolved_extensions,
            "resolution_rate": round((resolved_extensions / total_extensions * 100)) if total_extensions > 0 else 0,
        },
        "reviews": {
            "total": total_reviews,
            "completed": completed_reviews,
            "decision_distribution": decision_dist,
        },
        "monitoring": {
            "active_cases": active_monitoring,
            "total_runs": total_monitoring_runs,
            "total_alerts": total_monitoring_alerts,
        },
    }


def get_funnel_analytics(db: Session, user: User) -> dict:
    """Get workflow funnel analytics across all user's cases."""
    cases = db.query(ProductCase).filter(ProductCase.owner_id == user.id).all()
    total = len(cases)

    if total == 0:
        return {"total_cases": 0, "stages": []}

    case_ids = [c.id for c in cases]

    # Funnel stages (use distinct case counts, not total records)
    def _distinct_case_count(query):
        """Count distinct product_case_ids from a query."""
        from sqlalchemy import distinct
        return query.with_entities(func.count(distinct(query.column_descriptions()[0]['expr']))).scalar() if case_ids else 0

    stages = [
        {
            "name": "Product Created",
            "count": total,
            "percent": 100,
        },
        {
            "name": "Passport Started",
            "count": sum(1 for c in cases if c.ingredients and c.ingredients != "[]"),
            "percent": 0,
        },
        {
            "name": "Innovation Analysis",
            "count": db.query(InnovationAnalysis.product_case_id).filter(
                InnovationAnalysis.product_case_id.in_(case_ids),
            ).distinct().count() if case_ids else 0,
            "percent": 0,
        },
        {
            "name": "Patent Search",
            "count": db.query(PatentSearch.product_case_id).filter(
                PatentSearch.product_case_id.in_(case_ids),
            ).distinct().count() if case_ids else 0,
            "percent": 0,
        },
        {
            "name": "Regulatory Analysis",
            "count": db.query(RegulatoryProfile.product_case_id).filter(
                RegulatoryProfile.product_case_id.in_(case_ids),
            ).distinct().count() if case_ids else 0,
            "percent": 0,
        },
        {
            "name": "Evidence Available",
            "count": db.query(CaseFinding.product_case_id).filter(
                CaseFinding.product_case_id.in_(case_ids),
            ).distinct().count() if case_ids else 0,
            "percent": 0,
        },
        {
            "name": "Risk Assessment",
            "count": db.query(Risk.product_case_id).filter(
                Risk.product_case_id.in_(case_ids),
            ).distinct().count() if case_ids else 0,
            "percent": 0,
        },
        {
            "name": "Decision Dashboard",
            "count": db.query(ProductCase.id).filter(
                ProductCase.id.in_(case_ids),
                ProductCase.status == "COMPLETED",
            ).distinct().count() if case_ids else 0,
            "percent": 0,
        },
    ]

    # Calculate percentages
    for stage in stages:
        stage["percent"] = round((stage["count"] / total) * 100) if total > 0 else 0

    return {
        "total_cases": total,
        "stages": stages,
    }


def get_trend_analytics(
    db: Session,
    user: User,
    days: int = 30,
) -> dict:
    """Get trend analytics over a date range."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Cases created in period
    cases_created = db.query(ProductCase).filter(
        ProductCase.owner_id == user.id,
        ProductCase.created_at >= since,
    ).count()

    # Analyses run in period
    innovations = db.query(InnovationAnalysis).filter(
        InnovationAnalysis.owner_id == user.id,
        InnovationAnalysis.created_at >= since,
    ).count()

    patent_searches = db.query(PatentSearch).filter(
        PatentSearch.owner_id == user.id,
        PatentSearch.created_at >= since,
    ).count()

    risks_created = db.query(Risk).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
        Risk.created_at >= since,
    ).count()

    reviews_created = db.query(ReviewRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
        ReviewRequest.created_at >= since,
    ).count()

    reviews_completed = db.query(ReviewRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
        ReviewRequest.status == "COMPLETED",
        ReviewRequest.updated_at >= since,
    ).count()

    monitoring_runs = db.query(MonitoringRun).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
        MonitoringRun.started_at >= since,
    ).count()

    alerts = db.query(Alert).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
        Alert.created_at >= since,
    ).count()

    return {
        "period_days": days,
        "since": since.isoformat(),
        "metrics": {
            "cases_created": cases_created,
            "innovation_analyses": innovations,
            "patent_searches": patent_searches,
            "risks_created": risks_created,
            "reviews_created": reviews_created,
            "reviews_completed": reviews_completed,
            "monitoring_runs": monitoring_runs,
            "monitoring_alerts": alerts,
        },
    }


def get_risk_analytics(db: Session, user: User, case_public_id: Optional[str] = None) -> dict:
    """Get risk analytics, optionally for a specific case."""
    query = db.query(Risk).join(ProductCase).filter(ProductCase.owner_id == user.id)
    if case_public_id:
        query = query.filter(ProductCase.public_id == case_public_id)

    total = query.count()
    distribution = {}
    for level in ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]:
        distribution[level] = query.filter(Risk.level == level).count()

    category_dist = {}
    for cat in ["PATENT_IP", "REGULATORY", "INGREDIENT_PRODUCT_INFO", "CLAIMS",
                "TK_PRIOR_ART", "DATA_EVIDENCE_GAP", "JURISDICTION_UNCERTAINTY"]:
        category_dist[cat] = query.filter(Risk.category == cat).count()

    status_dist = {}
    for s in ["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"]:
        status_dist[s] = query.filter(Risk.status == s).count()

    return {
        "total": total,
        "level_distribution": distribution,
        "category_distribution": category_dist,
        "status_distribution": status_dist,
    }


def get_review_analytics(db: Session, user: User) -> dict:
    """Get review analytics."""
    base = db.query(ReviewRequest).join(ProductCase).filter(ProductCase.owner_id == user.id)

    total = base.count()
    pending = base.filter(ReviewRequest.status.in_(["PENDING", "ASSIGNED"])).count()
    in_review = base.filter(ReviewRequest.status == "IN_REVIEW").count()
    completed = base.filter(ReviewRequest.status == "COMPLETED").count()
    cancelled = base.filter(ReviewRequest.status == "CANCELLED").count()

    # Decision distribution
    decisions = db.query(ReviewDecision).join(ReviewRequest).join(ProductCase).filter(
        ProductCase.owner_id == user.id,
    )
    decision_dist = {}
    for d in ["CONFIRMED", "REJECTED", "MORE_INFORMATION_REQUIRED", "ESCALATED", "NO_ACTION"]:
        decision_dist[d] = decisions.filter(ReviewDecision.decision == d).count()

    # Trigger distribution
    trigger_dist = {}
    for t in ["HIGH_RISK", "LOW_CONFIDENCE", "SOURCE_CONFLICT", "CRITICAL_EVIDENCE_GAP",
              "IMPORTANT_REGULATORY_CHANGE", "IMPORTANT_PATENT_FINDING", "USER_REQUESTED"]:
        trigger_dist[t] = base.filter(ReviewRequest.trigger_type == t).count()

    return {
        "total": total,
        "pending": pending,
        "in_review": in_review,
        "completed": completed,
        "cancelled": cancelled,
        "decision_distribution": decision_dist,
        "trigger_distribution": trigger_dist,
    }


def _compute_funnel(case: ProductCase) -> dict:
    """Compute funnel stages for a single case."""
    stages = [
        {"name": "Product Created", "completed": True},
        {"name": "Passport Completed", "completed": bool(case.formulation and case.process)},
        {"name": "Analysis Started", "completed": case.status in ("ANALYZING", "COMPLETED")},
        {"name": "Decision Dashboard", "completed": case.status == "COMPLETED"},
    ]
    return {"stages": stages}
