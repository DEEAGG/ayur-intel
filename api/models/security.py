"""AYUR-INTEL — Security Models (Phase 17).

AuditLog: records important user/system actions for security auditing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

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


class UserSession(Base):
    """User active session record for login history and remote revocation."""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid, index=True)

    # User reference
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Client / Device context
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_info = Column(String(200), nullable=True)

    # Revocation & Activity
    is_revoked = Column(Boolean, nullable=False, default=False, index=True)

    # Inactivity and Maximum Lifetime settings (in seconds)
    idle_timeout_seconds = Column(Integer, nullable=False, default=1800)
    max_lifetime_seconds = Column(Integer, nullable=False, default=43200)

    # Admin Console Unlock State (Elevated Access)
    admin_unlocked_until = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_now_utc)
    last_active_at = Column(DateTime, nullable=False, default=_now_utc)
    expires_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions", lazy="select")


class AccessRequest(Base):
    """Access / Reactivation request for deactivated accounts.

    Tracks device-level enrollment, client context, and administrator decisions.
    """

    __tablename__ = "access_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(32), unique=True, nullable=False, default=_uuid, index=True)

    # Requester
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_email = Column(String(200), nullable=False, index=True)
    user_display_name = Column(String(200), nullable=False, default="")

    # Status: PENDING, APPROVED, REJECTED
    status = Column(String(20), nullable=False, default="PENDING", index=True)

    # Request details
    reason = Column(Text, nullable=True)

    # Device binding (cryptographically hashed)
    device_id = Column(String(100), nullable=True)  # Client-supplied opaque ID (sanitized)
    device_hash = Column(String(64), nullable=True, index=True)  # SHA-256 of persistent device token
    device_info = Column(String(200), nullable=True)  # Parsed Browser / OS
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Review metadata
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_username = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_now_utc, index=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="access_requests")

