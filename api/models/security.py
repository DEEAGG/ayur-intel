"""AYUR-INTEL — Security Models (Phase 17).

AuditLog: records important user/system actions for security auditing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from api.models.models import Base


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """Audit log entry for tracking important actions.

    Records who did what, when, and to which resource.
    Metadata must not contain secrets.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid)

    # Who
    user_id = Column(Integer, nullable=True)
    user_public_id = Column(String(32), nullable=True)
    username = Column(String(100), nullable=True)

    # What
    action = Column(String(100), nullable=False)  # CREATE, UPDATE, DELETE, ACCESS, LOGIN, DENIED
    resource_type = Column(String(100), nullable=False)  # PRODUCT_CASE, EVIDENCE, RISK, etc.
    resource_id = Column(String(100), nullable=True)

    # Context
    product_case_id = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(300), nullable=True)

    # Result
    status = Column(String(20), nullable=False, default="SUCCESS")  # SUCCESS, DENIED, FAILED
    detail = Column(Text, nullable=True)

    # Metadata (JSON, no secrets)
    metadata_json = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=_now_utc)
