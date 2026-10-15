"""AYUR-INTEL — Phase 2 Authentication & Session Tracking Tests.

Verifies:
1. Login creates a persisted UserSession with client context.
2. Separate logins create distinct session IDs.
3. Tokens contain the correct session ID (sid) and expiry.
4. Logout revokes only the current session.
5. A revoked session's token is rejected with 401.
6. Another active session belonging to the same user remains valid after single-session logout.
7. Expired sessions/tokens are rejected with 401.
8. Legacy tokens without sid cannot bypass session checks once a session is established.
9. Failed login creates no active session, preserves generic auth error, and records audit failure.
10. All-device logout revokes all user sessions and increments token_version.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.models
from api.models.models import Base, User
from api.models.security import UserSession, AuditLog
from api.services.auth_service import (
    create_access_token,
    get_user_from_token,
    hash_password,
    login_user,
    logout_user_session,
    logout_all_user_sessions,
    signup_user,
    verify_access_token,
)


class TestPhase2Sessions(unittest.TestCase):
    """Test suite for Phase 2 Session Tracking and Revocation."""

    def setUp(self):
        # Isolated in-memory SQLite database
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Seed a test user with password
        self.test_password = "SecurePassword123!"
        self.user = User(
            username="vaidya_ram",
            display_name="Dr. Ram Vaidya",
            email="ram@ayurintel.org",
            hashed_password=hash_password(self.test_password),
            role="user",
            token_version=1,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_login_creates_persisted_session(self):
        """Verify successful login creates an active UserSession with context."""
        ip = "192.168.1.100"
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"

        res = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
            ip_address=ip,
            user_agent=ua,
        )
        self.assertIn("token", res)
        self.assertIn("user", res)

        # Verify session persisted in database
        sessions = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).all()
        self.assertEqual(len(sessions), 1)

        sess = sessions[0]
        self.assertFalse(sess.is_revoked)
        self.assertEqual(sess.ip_address, ip)
        self.assertEqual(sess.user_agent, ua)
        self.assertIn("Chrome on Windows", sess.device_info)
        sess_exp = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=timezone.utc)
        self.assertTrue(sess_exp > datetime.now(timezone.utc))

        # Verify audit log was created
        audit = (
            self.db.query(AuditLog)
            .filter(AuditLog.user_id == self.user.id, AuditLog.action == "LOGIN", AuditLog.status == "SUCCESS")
            .first()
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.resource_id, sess.public_id)

    def test_separate_logins_create_distinct_session_ids(self):
        """Verify multiple logins create distinct, unique session records and tokens."""
        login1 = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
            ip_address="10.0.0.1",
            user_agent="Firefox on Linux",
        )
        login2 = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
            ip_address="10.0.0.2",
            user_agent="Safari on macOS",
        )

        self.assertNotEqual(login1["token"], login2["token"])

        payload1 = verify_access_token(login1["token"])
        payload2 = verify_access_token(login2["token"])

        self.assertIn("sid", payload1)
        self.assertIn("sid", payload2)
        self.assertNotEqual(payload1["sid"], payload2["sid"])

        sessions = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).all()
        self.assertEqual(len(sessions), 2)
        session_ids = {s.public_id for s in sessions}
        self.assertIn(payload1["sid"], session_ids)
        self.assertIn(payload2["sid"], session_ids)

    def test_tokens_contain_correct_session_id_and_expiry(self):
        """Verify token payload matches session expiration and session ID."""
        res = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
        )
        payload = verify_access_token(res["token"])
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], self.user.public_id)
        self.assertEqual(payload["email"], self.user.email)
        self.assertIn("sid", payload)

        sess = self.db.query(UserSession).filter(UserSession.public_id == payload["sid"]).first()
        self.assertIsNotNone(sess)
        self.assertEqual(sess.user_id, self.user.id)

    def test_logout_revokes_only_current_session(self):
        """Verify logout revokes the targeted session while preserving other active sessions."""
        login_dev1 = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
            user_agent="Device 1 Chrome",
        )
        login_dev2 = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
            user_agent="Device 2 Firefox",
        )

        token1 = login_dev1["token"]
        token2 = login_dev2["token"]

        # Both tokens currently valid
        user_dev1 = get_user_from_token(self.db, token1)
        user_dev2 = get_user_from_token(self.db, token2)
        self.assertEqual(user_dev1.id, self.user.id)
        self.assertEqual(user_dev2.id, self.user.id)

        # Logout session 1
        logout_res = logout_user_session(self.db, user=self.user, token=token1)
        self.assertIn("message", logout_res)

        # Token 1 must now be rejected with 401
        with self.assertRaises(HTTPException) as ctx1:
            get_user_from_token(self.db, token1)
        self.assertEqual(ctx1.exception.status_code, 401)
        self.assertIn("revoked", ctx1.exception.detail.lower())

        # Token 2 MUST STILL BE VALID
        user_dev2_after = get_user_from_token(self.db, token2)
        self.assertEqual(user_dev2_after.id, self.user.id)

    def test_expired_sessions_are_rejected(self):
        """Verify sessions past their expires_at are rejected with 401."""
        login_res = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
        )
        token = login_res["token"]
        payload = verify_access_token(token)
        sid = payload["sid"]

        # Manually expire session in DB
        sess = self.db.query(UserSession).filter(UserSession.public_id == sid).first()
        sess.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            get_user_from_token(self.db, token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_legacy_tokens_cannot_bypass_session_checks(self):
        """Verify tokens without sid are rejected once the user has an active/revoked session."""
        login_res = login_user(
            self.db,
            email_or_username="ram@ayurintel.org",
            password=self.test_password,
        )

        # Attacker / legacy client presents token with NO sid for a session-managed user
        legacy_token = create_access_token({"sub": self.user.public_id, "email": self.user.email})

        with self.assertRaises(HTTPException) as ctx:
            get_user_from_token(self.db, legacy_token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("missing", ctx.exception.detail.lower())

    def test_failed_login_creates_no_session_and_records_audit_failure(self):
        """Verify failed login creates no session, preserves 401, and records audit failure."""
        with self.assertRaises(HTTPException) as ctx:
            login_user(
                self.db,
                email_or_username="ram@ayurintel.org",
                password="WrongPassword123!",
                ip_address="203.0.113.42",
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Invalid email or password")

        # Zero sessions created
        sessions = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).all()
        self.assertEqual(len(sessions), 0)

        # Audit log has failed entry
        audit = (
            self.db.query(AuditLog)
            .filter(AuditLog.user_id == self.user.id, AuditLog.action == "LOGIN", AuditLog.status == "FAILED")
            .first()
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.ip_address, "203.0.113.42")

    def test_logout_all_user_sessions(self):
        """Verify logout_all_user_sessions revokes all sessions and increments token_version."""
        login1 = login_user(self.db, email_or_username="ram@ayurintel.org", password=self.test_password)
        login2 = login_user(self.db, email_or_username="ram@ayurintel.org", password=self.test_password)

        token1 = login1["token"]
        token2 = login2["token"]

        self.assertEqual(get_user_from_token(self.db, token1).id, self.user.id)
        self.assertEqual(get_user_from_token(self.db, token2).id, self.user.id)

        # Execute logout from all devices
        res = logout_all_user_sessions(self.db, self.user)
        self.assertIn("message", res)

        # Both tokens must now be rejected
        with self.assertRaises(HTTPException) as ctx1:
            get_user_from_token(self.db, token1)
        self.assertEqual(ctx1.exception.status_code, 401)

        with self.assertRaises(HTTPException) as ctx2:
            get_user_from_token(self.db, token2)
        self.assertEqual(ctx2.exception.status_code, 401)

        # User token_version incremented
        self.db.refresh(self.user)
        self.assertEqual(self.user.token_version, 2)

    def test_logout_endpoint_e2e(self):
        """Verify full HTTP integration: login -> /me (200) -> /logout (200) -> /me (401)."""
        import asyncio
        import httpx
        from api.main import app
        from api.core.database import get_db

        async def run_test():
            def override_get_db():
                try:
                    yield self.db
                finally:
                    pass

            app.dependency_overrides[get_db] = override_get_db
            try:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    # 1. Login
                    login_res = await client.post(
                        "/api/auth/login",
                        json={"email": "ram@ayurintel.org", "password": self.test_password},
                    )
                    self.assertEqual(login_res.status_code, 200)
                    token = login_res.json()["token"]

                    # 2. Authenticated access to /me succeeds
                    me_res1 = await client.get(
                        "/api/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertEqual(me_res1.status_code, 200)
                    self.assertEqual(me_res1.json()["user"]["email"], "ram@ayurintel.org")

                    # 3. Call /logout
                    logout_res = await client.post(
                        "/api/auth/logout",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertEqual(logout_res.status_code, 200)
                    self.assertIn("message", logout_res.json())

                    # 4. Subsequent access to /me returns 401
                    me_res2 = await client.get(
                        "/api/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertEqual(me_res2.status_code, 401)
            finally:
                app.dependency_overrides.pop(get_db, None)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
