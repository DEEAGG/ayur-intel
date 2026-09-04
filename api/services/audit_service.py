"""AYUR-INTEL — Audit Logging Service (Phase 17).

Provides structured audit logging for security-critical actions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.security import AuditLog

logger = logging.getLogger("ayur_intel.audit")


def log_action(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    product_case_id: Optional[str] = None,
    user_id: Optional[int] = None,
    user_public_id: Optional[str] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "SUCCESS",
    detail: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AuditLog:
    """Record an audit log entry.

    Args:
        db: Database session.
        action: The action performed (CREATE, UPDATE, DELETE, ACCESS, LOGIN, DENIED).
        resource_type: Type of resource (PRODUCT_CASE, EVIDENCE, RISK, etc.).
        resource_id: Public ID of the specific resource.
        product_case_id: Public ID of the related Product Case.
        user_id: Internal user ID.
        user_public_id: Public user ID.
        username: Username.
        ip_address: Client IP address.
        user_agent: Client user agent string.
        status: Result status (SUCCESS, DENIED, FAILED).
        detail: Safe detail message (no secrets).
        metadata: Additional metadata (must not contain secrets).
    """
    # Sanitize metadata - strip any secret-like keys
    safe_metadata = None
    if metadata:
        secret_keys = {"password", "token", "secret", "api_key", "apikey", "authorization", "credential"}
        safe_metadata = {k: v for k, v in metadata.items() if k.lower() not in secret_keys}

    entry = AuditLog(
        user_id=user_id,
        user_public_id=user_public_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        product_case_id=product_case_id,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        detail=detail,
        metadata_json=json.dumps(safe_metadata) if safe_metadata else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    # Don't commit here - let the caller commit in their transaction
    db.flush()

    # Also log to application logger (sanitized)
    logger.info(
        "AUDIT: %s %s %s by %s [%s] case=%s",
        action, resource_type, resource_id or "-", username or "-", status, product_case_id or "-",
    )

    return entry


def get_audit_logs(
    db: Session,
    *,
    user_id: Optional[int] = None,
    product_case_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Query audit logs with filters."""
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if product_case_id:
        query = query.filter(AuditLog.product_case_id == product_case_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if status:
        query = query.filter(AuditLog.status == status)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "logs": [
            {
                "id": log.public_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "product_case_id": log.product_case_id,
                "username": log.username,
                "status": log.status,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
            for log in logs
        ],
        "total": total,
    }
