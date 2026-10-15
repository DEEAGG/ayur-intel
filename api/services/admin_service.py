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
from api.models.security import AuditLog, UserSession
from api.services.audit_service import log_action

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

    yesterday = now_utc - timedelta(hours=24)
    recent_events_count = db.query(AuditLog).filter(AuditLog.created_at >= yesterday).count()

    return {
        "total_users": total_users,
        "online_users": online_users,
        "offline_users": offline_users,
        "active_accounts": active_accounts,
        "deactivated_accounts": deactivated_accounts,
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
        elif s_clean == "inactive":
            q = q.filter(User.is_active == False)

    matching_users = q.all()
    total = len(matching_users)

    now_utc = datetime.now(timezone.utc)
    user_ids = [u.id for u in matching_users]

    sessions_by_user: Dict[int, List[UserSession]] = {uid: [] for uid in user_ids}
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

    processed_users = []
    for u in matching_users:
        user_sessions = sessions_by_user.get(u.id, [])

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
    """Retrieve full safe details and recent sessions for a single user."""
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

    recent_sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .order_by(UserSession.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "id": user.public_id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "email": user.email or "",
        "role": getattr(user, "role", "user") or "user",
        "is_active": bool(user.is_active),
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
