"""AYUR-INTEL — Admin Service.

Business logic for administrative console operations:
- Idempotent Admin Bootstrap
- User Listing, Inspection, and Status Management
- Session Inspection and Remote Revocation
- System-Wide Audit Log Queries
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.core.config import settings
from api.models.models import User
from api.models.security import AuditLog, UserSession, AccessRequest
from api.services.audit_service import log_action
from api.services.auth_service import verify_password, create_access_token
import time

logger = logging.getLogger("ayur_intel.admin")


def bootstrap_admin_user(db: Session) -> Optional[User]:
    """Safely and idempotently designate the configured owner account as administrator.

    Security Policies:
    - Only the account matching AYURINTEL_ADMIN_EMAIL is designated.
    - If AYURINTEL_ADMIN_EMAIL is unset or empty, no user is promoted.
    - Never creates a stub or passwordless account.
    - If the user account does not exist, does nothing.
    - Normalizes email with strip() and lower() on both ends.
    - Never logs or exposes the admin email string.
    """
    admin_email = getattr(settings, "AYURINTEL_ADMIN_EMAIL", None)
    if not admin_email or not str(admin_email).strip():
        return None

    clean_email = str(admin_email).strip().lower()

    user = (
        db.query(User)
        .filter(func.lower(func.trim(User.email)) == clean_email)
        .first()
    )

    if not user:
        return None

    if getattr(user, "role", "user") != "admin":
        user.role = "admin"
        db.commit()
        db.refresh(user)
        logger.info("Designated administrator account bootstrapped successfully.")

    return user


def get_admin_metrics(db: Session) -> Dict[str, Any]:
    """Retrieve real-time administrative intelligence and presence metrics."""
    now_utc = datetime.now(timezone.utc)
    total_users = db.query(User).count()
    active_accounts = db.query(User).filter(User.is_active == True).count()
    deactivated_accounts = max(0, total_users - active_accounts)

    active_candidate_sessions = (
        db.query(UserSession)
        .filter(
            UserSession.is_revoked == False,
            UserSession.expires_at > now_utc,
        )
        .all()
    )

    online_user_ids = set()
    valid_sessions_count = 0
    for s in active_candidate_sessions:
        s_created = (
            s.created_at.replace(tzinfo=timezone.utc)
            if s.created_at and s.created_at.tzinfo is None
            else s.created_at
        )
        s_last_active = (
            s.last_active_at.replace(tzinfo=timezone.utc)
            if s.last_active_at and s.last_active_at.tzinfo is None
            else s.last_active_at
        )
        idle_sec = getattr(s, "idle_timeout_seconds", None) or 1800
        max_life_sec = getattr(s, "max_lifetime_seconds", None) or 43200

        if s_created and (now_utc < s_created + timedelta(seconds=max_life_sec)):
            if s_last_active and (now_utc < s_last_active + timedelta(seconds=idle_sec)):
                online_user_ids.add(s.user_id)
                valid_sessions_count += 1

    online_users = len(online_user_ids)
    offline_users = max(0, total_users - online_users)

    pending_access_requests = (
        db.query(AccessRequest).filter(AccessRequest.status == "PENDING").count()
    )

    yesterday = now_utc - timedelta(hours=24)
    recent_events_count = db.query(AuditLog).filter(AuditLog.created_at >= yesterday).count()

    return {
        "total_users": total_users,
        "online_users": online_users,
        "offline_users": offline_users,
        "active_accounts": active_accounts,
        "deactivated_accounts": deactivated_accounts,
        "pending_access_requests": pending_access_requests,
        "total_active_sessions": valid_sessions_count,
        "recent_audit_events_24h": recent_events_count,
    }



def get_admin_users(
    db: Session,
    query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve paginated list of users with presence tracking, online-first ordering, and session durations."""
    q = db.query(User)

    if query and query.strip():
        term = f"%{query.strip().lower()}%"
        q = q.filter(
            (func.lower(User.username).like(term))
            | (func.lower(User.email).like(term))
            | (func.lower(User.display_name).like(term))
        )

    if status and status.strip():
        s_clean = status.strip().lower()
        if s_clean == "active":
            q = q.filter(User.is_active == True)
        elif s_clean in ("inactive", "deactivated"):
            q = q.filter(User.is_active == False)
        elif s_clean in ("pending", "pending_approval"):
            q = q.join(AccessRequest, AccessRequest.user_id == User.id).filter(AccessRequest.status == "PENDING").distinct()

    matching_users = q.all()
    total = len(matching_users)

    now_utc = datetime.now(timezone.utc)
    user_ids = [u.id for u in matching_users]

    sessions_by_user: Dict[int, List[UserSession]] = {uid: [] for uid in user_ids}
    pending_user_ids = set()
    if user_ids:
        # Efficient single batch query for all sessions belonging to the candidate users
        all_sessions = (
            db.query(UserSession)
            .filter(UserSession.user_id.in_(user_ids))
            .order_by(UserSession.created_at.desc())
            .all()
        )
        for s in all_sessions:
            sessions_by_user[s.user_id].append(s)

        pending_rows = (
            db.query(AccessRequest.user_id)
            .filter(AccessRequest.user_id.in_(user_ids), AccessRequest.status == "PENDING")
            .all()
        )
        pending_user_ids = {r[0] for r in pending_rows}

    processed_users = []
    for u in matching_users:
        user_sessions = sessions_by_user.get(u.id, [])
        has_pending = u.id in pending_user_ids
        logins = getattr(u, "login_count", 0) or len(user_sessions)


        active_sessions = []
        ended_sessions = []

        for s in user_sessions:
            s_created = (
                s.created_at.replace(tzinfo=timezone.utc)
                if s.created_at and s.created_at.tzinfo is None
                else s.created_at
            )
            s_last_active = (
                s.last_active_at.replace(tzinfo=timezone.utc)
                if s.last_active_at and s.last_active_at.tzinfo is None
                else s.last_active_at
            )
            s_exp = (
                s.expires_at.replace(tzinfo=timezone.utc)
                if s.expires_at and s.expires_at.tzinfo is None
                else s.expires_at
            )

            idle_sec = getattr(s, "idle_timeout_seconds", None) or 1800
            max_life_sec = getattr(s, "max_lifetime_seconds", None) or 43200

            is_session_online = False
            # Session must not be revoked and must not have surpassed its hard expiration
            if not s.is_revoked and s_exp and now_utc < s_exp:
                # Must not exceed absolute session maximum lifetime
                if s_created and (now_utc < s_created + timedelta(seconds=max_life_sec)):
                    # Must not exceed idle inactivity timeout
                    if s_last_active and (now_utc < s_last_active + timedelta(seconds=idle_sec)):
                        is_session_online = True

            if is_session_online:
                active_sessions.append((s, s_created, s_last_active))
            else:
                ended_sessions.append((s, s_created, s_last_active))

        is_online = len(active_sessions) > 0
        active_sessions_count = len(active_sessions)

        # 1. Last opened timestamp (login / session start)
        last_opened_at_iso: Optional[str] = None
        last_opened_dt: Optional[datetime] = None
        if user_sessions:
            s_latest = user_sessions[0]
            if s_latest.created_at:
                dt_open = (
                    s_latest.created_at.replace(tzinfo=timezone.utc)
                    if s_latest.created_at.tzinfo is None
                    else s_latest.created_at
                )
                last_opened_dt = dt_open
                last_opened_at_iso = dt_open.isoformat()

        # 2. Last active timestamp
        last_active_at_iso: Optional[str] = None
        last_active_dt: Optional[datetime] = None
        if active_sessions:
            # For online users, pick latest active timestamp from active sessions
            active_dts = [la for (_, _, la) in active_sessions if la is not None]
            if active_dts:
                last_active_dt = max(active_dts)
                last_active_at_iso = last_active_dt.isoformat()
        elif user_sessions:
            # For offline users, pick latest active timestamp from all historical sessions
            all_act_dts = [
                (
                    s.last_active_at.replace(tzinfo=timezone.utc)
                    if s.last_active_at.tzinfo is None
                    else s.last_active_at
                )
                for s in user_sessions
                if s.last_active_at is not None
            ]
            if all_act_dts:
                last_active_dt = max(all_act_dts)
                last_active_at_iso = last_active_dt.isoformat()

        # 3. Session durations
        session_started_at_iso: Optional[str] = None
        current_session_duration_sec: Optional[int] = None
        last_session_duration_sec: Optional[int] = None

        if is_online and active_sessions:
            # Latest active session
            latest_active_sess, s_act_created, _ = active_sessions[0]
            if s_act_created:
                session_started_at_iso = s_act_created.isoformat()
                current_session_duration_sec = max(0, int((now_utc - s_act_created).total_seconds()))
        elif ended_sessions:
            # Latest ended session
            latest_ended_sess, s_ended_created, s_ended_last_active = ended_sessions[0]
            if s_ended_created:
                session_started_at_iso = s_ended_created.isoformat()
            if s_ended_created and s_ended_last_active:
                last_session_duration_sec = max(0, int((s_ended_last_active - s_ended_created).total_seconds()))

        u_created_dt = (
            u.created_at.replace(tzinfo=timezone.utc)
            if u.created_at and u.created_at.tzinfo is None
            else u.created_at
        )

        user_data = {
            "id": u.public_id,
            "username": u.username,
            "display_name": u.display_name or u.username,
            "email": u.email or "",
            "role": getattr(u, "role", "user") or "user",
            "is_active": bool(u.is_active),
            "is_online": is_online,
            "active_sessions_count": active_sessions_count,
            "last_opened_at": last_opened_at_iso,
            "last_active_at": last_active_at_iso,
            "session_started_at": session_started_at_iso,
            "current_session_duration_seconds": current_session_duration_sec,
            "last_session_duration_seconds": last_session_duration_sec,
            "session_duration_seconds": current_session_duration_sec if is_online else last_session_duration_sec,
            "login_count": logins,
            "has_pending_request": has_pending,
            "approved_device_hash": getattr(u, "approved_device_hash", None),
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "updated_at": u.updated_at.isoformat() if u.updated_at else "",
            # Internal fields for server-side sorting:
            "_is_online": is_online,
            "_last_active_dt": last_active_dt or last_opened_dt or u_created_dt,
            "_user_created_dt": u_created_dt,
        }
        processed_users.append(user_data)

    # Server-side sorting:
    # 1. Online users first (is_online True -> 0, False -> 1)
    # 2. Most recently active first (descending timestamp)
    # 3. Newest user creation (descending timestamp)
    def user_sort_key(item: Dict[str, Any]):
        online_rank = 0 if item["_is_online"] else 1
        la_ts = item["_last_active_dt"].timestamp() if item["_last_active_dt"] else 0.0
        uc_ts = item["_user_created_dt"].timestamp() if item["_user_created_dt"] else 0.0
        return (online_rank, -la_ts, -uc_ts)

    processed_users.sort(key=user_sort_key)

    # Slice for requested pagination window
    paged_slice = processed_users[offset : offset + limit]

    # Clean internal temporary keys from output payload
    clean_results = []
    for item in paged_slice:
        res = dict(item)
        res.pop("_is_online", None)
        res.pop("_last_active_dt", None)
        res.pop("_user_created_dt", None)
        clean_results.append(res)

    return {
        "users": clean_results,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_admin_user_detail(db: Session, user_id: str) -> Dict[str, Any]:
    """Retrieve full safe details, session history, and access requests for a single user."""
    user = db.query(User).filter(User.public_id == user_id.strip()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now_utc = datetime.now(timezone.utc)
    active_sessions = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user.id,
            UserSession.is_revoked == False,
            UserSession.expires_at > now_utc,
        )
        .count()
    )

    all_user_sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .order_by(UserSession.created_at.desc())
        .all()
    )
    recent_sessions = all_user_sessions[:20]

    user_requests = (
        db.query(AccessRequest)
        .filter(AccessRequest.user_id == user.id)
        .order_by(AccessRequest.created_at.desc())
        .limit(10)
        .all()
    )

    logins = getattr(user, "login_count", 0) or len(all_user_sessions)
    has_pending = any(r.status == "PENDING" for r in user_requests)

    return {
        "id": user.public_id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "email": user.email or "",
        "role": getattr(user, "role", "user") or "user",
        "is_active": bool(user.is_active),
        "login_count": logins,
        "has_pending_request": has_pending,
        "approved_device_hash": getattr(user, "approved_device_hash", None),
        "avatar_url": user.avatar_url or "",
        "active_sessions_count": active_sessions,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "updated_at": user.updated_at.isoformat() if user.updated_at else "",
        "recent_sessions": [
            {
                "id": s.public_id,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "device_info": s.device_info or "Unknown Device",
                "is_revoked": bool(s.is_revoked),
                "created_at": s.created_at.isoformat() if s.created_at else "",
                "last_active_at": s.last_active_at.isoformat() if s.last_active_at else "",
                "expires_at": s.expires_at.isoformat() if s.expires_at else "",
            }
            for s in recent_sessions
        ],
        "access_requests": [
            {
                "id": r.public_id,
                "status": r.status,
                "reason": r.reason,
                "device_info": r.device_info,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                "reviewer_username": r.reviewer_username,
                "review_notes": r.review_notes,
            }
            for r in user_requests
        ],
    }



def update_user_status(
    db: Session,
    admin: User,
    user_id: str,
    is_active: bool,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Activate or deactivate a user account with strict safeguards."""
    target = db.query(User).filter(User.public_id == user_id.strip()).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Safeguard 1: Administrator cannot deactivate their own account
    if admin.id == target.id and not is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate your own administrator account",
        )

    # Safeguard 2: Cannot deactivate the sole active administrator
    if target.role == "admin" and not is_active:
        active_admins = (
            db.query(User)
            .filter(User.role == "admin", User.is_active == True)
            .count()
        )
        if active_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate the sole active administrator account",
            )

    target.is_active = is_active

    # When deactivating, immediately revoke all sessions and bump token_version
    if not is_active:
        db.query(UserSession).filter(
            UserSession.user_id == target.id,
            UserSession.is_revoked == False,
        ).update({"is_revoked": True})
        target.token_version = (target.token_version or 1) + 1

    try:
        log_action(
            db,
            action="STATUS_CHANGE",
            resource_type="USER",
            resource_id=target.public_id,
            user_id=admin.id,
            user_public_id=admin.public_id,
            username=admin.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail=f"User account {'activated' if is_active else 'deactivated'} by administrator",
            metadata={"target_user": target.username, "is_active": is_active},
        )
        db.commit()
        db.refresh(target)
    except Exception as e:
        logger.debug("Failed to record admin status audit log: %s", e)
        db.rollback()
        raise

    logger.info(
        "Admin %s updated status of user %s to is_active=%s",
        admin.username, target.username, is_active,
    )

    return {
        "id": target.public_id,
        "username": target.username,
        "display_name": target.display_name or target.username,
        "email": target.email or "",
        "role": target.role,
        "is_active": target.is_active,
        "message": f"User successfully {'activated' if is_active else 'deactivated'}",
    }


def get_user_sessions(db: Session, user_id: str) -> List[Dict[str, Any]]:
    """Retrieve full session history for a specific user."""
    target = db.query(User).filter(User.public_id == user_id.strip()).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == target.id)
        .order_by(UserSession.created_at.desc())
        .all()
    )

    return [
        {
            "id": s.public_id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "device_info": s.device_info or "Unknown Device",
            "is_revoked": bool(s.is_revoked),
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else "",
            "expires_at": s.expires_at.isoformat() if s.expires_at else "",
        }
        for s in sessions
    ]


def revoke_user_session_admin(
    db: Session,
    admin: User,
    user_id: str,
    session_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Administratively revoke an individual user session."""
    target = db.query(User).filter(User.public_id == user_id.strip()).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    session = (
        db.query(UserSession)
        .filter(
            UserSession.public_id == session_id.strip(),
            UserSession.user_id == target.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_revoked = True

    try:
        log_action(
            db,
            action="SESSION_REVOKE",
            resource_type="SESSION",
            resource_id=session.public_id,
            user_id=admin.id,
            user_public_id=admin.public_id,
            username=admin.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail=f"Session revoked by administrator for user {target.username}",
            metadata={"target_user": target.username, "session_id": session.public_id},
        )
        db.commit()
    except Exception as e:
        logger.debug("Failed to record admin session revoke audit log: %s", e)
        db.rollback()
        raise

    logger.info("Admin %s revoked session %s for user %s", admin.username, session.public_id, target.username)
    return {"message": "Session revoked successfully"}


def revoke_all_user_sessions_admin(
    db: Session,
    admin: User,
    user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Administratively revoke all sessions for a user across all devices."""
    target = db.query(User).filter(User.public_id == user_id.strip()).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    revoked_count = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == target.id,
            UserSession.is_revoked == False,
        )
        .update({"is_revoked": True})
    )
    target.token_version = (target.token_version or 1) + 1

    try:
        log_action(
            db,
            action="LOGOUT_ALL",
            resource_type="USER",
            resource_id=target.public_id,
            user_id=admin.id,
            user_public_id=admin.public_id,
            username=admin.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail=f"All sessions ({revoked_count}) revoked by administrator for user {target.username}",
            metadata={"target_user": target.username, "revoked_count": revoked_count},
        )
        db.commit()
    except Exception as e:
        logger.debug("Failed to record admin logout all audit log: %s", e)
        db.rollback()
        raise

    logger.info("Admin %s revoked all sessions for user %s", admin.username, target.username)
    return {"message": f"Successfully revoked all active sessions for user {target.username}"}


def get_admin_audit_logs(
    db: Session,
    user_query: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve system-wide audit logs with administrative filtering."""
    q = db.query(AuditLog)

    if user_query and user_query.strip():
        term = f"%{user_query.strip().lower()}%"
        q = q.filter(
            (func.lower(AuditLog.username).like(term))
            | (func.lower(AuditLog.user_public_id).like(term))
        )

    if action and action.strip():
        q = q.filter(AuditLog.action == action.strip().upper())

    if resource_type and resource_type.strip():
        q = q.filter(AuditLog.resource_type == resource_type.strip().upper())

    if status and status.strip():
        q = q.filter(AuditLog.status == status.strip().upper())

    total = q.count()
    logs = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "logs": [
            {
                "id": log.public_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "user_public_id": log.user_public_id,
                "username": log.username,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "status": log.status,
                "detail": log.detail,
                "metadata": log.metadata_json,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
            for log in logs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Access / Reactivation Requests Management
# ---------------------------------------------------------------------------

def get_admin_access_requests(
    db: Session,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve paginated access / reactivation requests for administrative review."""
    q = db.query(AccessRequest)
    if status and status.strip() and status.strip().lower() != "all":
        q = q.filter(AccessRequest.status == status.strip().upper())

    total = q.count()
    pending_count = db.query(AccessRequest).filter(AccessRequest.status == "PENDING").count()
    requests = q.order_by(AccessRequest.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "requests": [
            {
                "id": r.public_id,
                "user_id": r.user.public_id if r.user else str(r.user_id),
                "user_email": r.user_email,
                "user_display_name": r.user_display_name or (r.user.display_name if r.user else ""),
                "user_is_active": r.user.is_active if r.user else False,
                "status": r.status,
                "reason": r.reason or "",
                "device_id": r.device_id or "Not provided",
                "device_info": r.device_info or "Unknown Device",
                "ip_address": r.ip_address,
                "reviewer_username": r.reviewer_username,
                "review_notes": r.review_notes,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            }
            for r in requests
        ],
        "total": total,
        "pending_count": pending_count,
        "limit": limit,
        "offset": offset,
    }


def get_admin_access_request_detail(db: Session, request_id: str) -> Dict[str, Any]:
    """Retrieve details for a single access request."""
    req = db.query(AccessRequest).filter(AccessRequest.public_id == request_id.strip()).first()
    if not req:
        raise HTTPException(status_code=404, detail="Access request not found")

    return {
        "id": req.public_id,
        "user_id": req.user.public_id if req.user else str(req.user_id),
        "user_email": req.user_email,
        "user_display_name": req.user_display_name,
        "user_is_active": req.user.is_active if req.user else False,
        "status": req.status,
        "reason": req.reason or "",
        "device_id": req.device_id,
        "device_hash": req.device_hash,
        "device_info": req.device_info or "Unknown Device",
        "ip_address": req.ip_address,
        "user_agent": req.user_agent,
        "reviewer_id": req.reviewer_id,
        "reviewer_username": req.reviewer_username,
        "review_notes": req.review_notes,
        "created_at": req.created_at.isoformat() if req.created_at else "",
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
    }


def approve_access_request_admin(
    db: Session,
    admin: User,
    request_id: str,
    review_notes: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve access request, reactivating the account and binding approved device."""
    req = db.query(AccessRequest).filter(AccessRequest.public_id == request_id.strip()).first()
    if not req:
        raise HTTPException(status_code=404, detail="Access request not found")

    if req.status == "APPROVED":
        raise HTTPException(status_code=400, detail="This request has already been approved")

    now_utc = datetime.now(timezone.utc)
    target = req.user
    if not target:
        raise HTTPException(status_code=404, detail="Target user account not found")

    # Reactivate target user
    target.is_active = True
    if req.device_hash:
        target.approved_device_hash = req.device_hash

    req.status = "APPROVED"
    req.reviewer_id = admin.id
    req.reviewer_username = admin.username
    req.review_notes = (review_notes or "").strip() if review_notes else None
    req.reviewed_at = now_utc

    try:
        log_action(
            db,
            action="ACCESS_REQUEST_APPROVE",
            resource_type="ACCESS_REQUEST",
            resource_id=req.public_id,
            user_id=admin.id,
            user_public_id=admin.public_id,
            username=admin.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail=f"Admin approved access request for user {target.username}. Account reactivated.",
            metadata={"target_user": target.username, "request_id": req.public_id, "device_info": req.device_info},
        )
        db.commit()
        db.refresh(req)
        db.refresh(target)
    except Exception as e:
        logger.debug("Failed to record access request approve audit log: %s", e)
        db.rollback()
        raise

    logger.info("Admin %s approved access request %s for %s", admin.username, req.public_id, target.username)
    return {
        "message": f"Access request approved. Account for {target.username} has been reactivated.",
        "request_id": req.public_id,
        "status": "APPROVED",
        "user_is_active": True,
    }


def reject_access_request_admin(
    db: Session,
    admin: User,
    request_id: str,
    review_notes: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Reject access request. Account remains deactivated."""
    req = db.query(AccessRequest).filter(AccessRequest.public_id == request_id.strip()).first()
    if not req:
        raise HTTPException(status_code=404, detail="Access request not found")

    if req.status == "REJECTED":
        raise HTTPException(status_code=400, detail="This request has already been rejected")

    now_utc = datetime.now(timezone.utc)
    target = req.user

    req.status = "REJECTED"
    req.reviewer_id = admin.id
    req.reviewer_username = admin.username
    req.review_notes = (review_notes or "").strip() if review_notes else None
    req.reviewed_at = now_utc

    try:
        log_action(
            db,
            action="ACCESS_REQUEST_REJECT",
            resource_type="ACCESS_REQUEST",
            resource_id=req.public_id,
            user_id=admin.id,
            user_public_id=admin.public_id,
            username=admin.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail=f"Admin rejected access request for user {target.username if target else req.user_email}",
            metadata={"target_user": target.username if target else req.user_email, "request_id": req.public_id},
        )
        db.commit()
        db.refresh(req)
    except Exception as e:
        logger.debug("Failed to record access request reject audit log: %s", e)
        db.rollback()
        raise

    logger.info("Admin %s rejected access request %s", admin.username, req.public_id)
    return {
        "message": "Access request rejected. Account remains deactivated.",
        "request_id": req.public_id,
        "status": "REJECTED",
    }


# ---------------------------------------------------------------------------
# Admin Console Elevated Unlock Management
# ---------------------------------------------------------------------------

_failed_unlock_attempts: Dict[str, List[float]] = {}


def check_unlock_rate_limit(admin_id: str, ip: str) -> None:
    """Enforce rate limits on failed administrator console unlock attempts."""
    now = time.time()
    key = f"{admin_id}:{ip}"
    attempts = [t for t in _failed_unlock_attempts.get(key, []) if now - t < 300]
    _failed_unlock_attempts[key] = attempts
    if len(attempts) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many failed unlock attempts. Please wait 5 minutes before trying again.",
        )


def record_failed_unlock(admin_id: str, ip: str) -> None:
    """Record timestamp of failed unlock attempt for sliding window rate limit."""
    now = time.time()
    key = f"{admin_id}:{ip}"
    attempts = [t for t in _failed_unlock_attempts.get(key, []) if now - t < 300]
    attempts.append(now)
    _failed_unlock_attempts[key] = attempts


def unlock_admin_console(
    db: Session,
    admin: User,
    session: Optional[UserSession],
    password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-authenticate administrator and issue elevated unlock state for session."""
    check_unlock_rate_limit(admin.public_id, ip_address or "unknown")

    if not admin.hashed_password or not verify_password(password, admin.hashed_password):
        record_failed_unlock(admin.public_id, ip_address or "unknown")
        try:
            log_action(
                db,
                action="ADMIN_UNLOCK_FAILED",
                resource_type="ADMIN_LOCK",
                user_id=admin.id,
                user_public_id=admin.public_id,
                username=admin.username,
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILED",
                detail="Invalid password provided for admin unlock",
            )
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code=401, detail="Invalid administrator password")

    now_utc = datetime.now(timezone.utc)
    unlocked_until = now_utc + timedelta(minutes=15)

    if session:
        session.admin_unlocked_until = unlocked_until
        db.commit()
        db.refresh(session)

    # Issue signed unlock token
    unlock_token = create_access_token(
        {
            "sub": admin.public_id,
            "email": admin.email,
            "sid": session.public_id if session else "",
            "scope": "admin_unlock",
        },
        ttl_seconds=900,
    )

    try:
        log_action(
            db,
            action="ADMIN_UNLOCK",
            resource_type="ADMIN_LOCK",
            user_id=admin.id,
            user_public_id=admin.public_id,
            username=admin.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail="Admin console unlocked with valid password re-authentication",
        )
        db.commit()
    except Exception:
        db.rollback()

    logger.info("Admin console unlocked for %s", admin.username)
    return {
        "unlocked": True,
        "expires_at": unlocked_until.isoformat(),
        "unlock_token": unlock_token,
        "message": "Admin console successfully unlocked",
    }


def lock_admin_console(
    db: Session,
    admin: User,
    session: Optional[UserSession],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Explicitly lock the admin console for the current session."""
    if session:
        session.admin_unlocked_until = None
        db.commit()
        db.refresh(session)

    try:
        log_action(
            db,
            action="ADMIN_LOCK",
            resource_type="ADMIN_LOCK",
            user_id=admin.id,
            user_public_id=admin.public_id,
            username=admin.username,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            detail="Admin console explicitly locked",
        )
        db.commit()
    except Exception:
        db.rollback()

    logger.info("Admin console locked for %s", admin.username)
    return {
        "unlocked": False,
        "message": "Admin console locked successfully",
    }


def get_admin_unlock_status(
    session: Optional[UserSession],
    admin: Optional[User] = None,
) -> Dict[str, Any]:
    """Inspect current elevated unlock status of the session."""
    if not session or not session.admin_unlocked_until:
        return {"unlocked": False, "expires_at": None}

    now_utc = datetime.now(timezone.utc)
    until = session.admin_unlocked_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)

    if now_utc < until:
        return {"unlocked": True, "expires_at": until.isoformat()}
    return {"unlocked": False, "expires_at": None}

