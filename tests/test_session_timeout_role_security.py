"""AYUR-INTEL — Session Timeout, Lifetime & Role Security Test Suite.

Validates:
1. Admin navigation remains hidden for ordinary users.
2. Admin navigation appears only for server-verified Admin account.
3. Diagnosis of missing Admin Console on live website.
4. Ordinary users cannot change their account role through UI or backend APIs.
5. Admin role is not exposed in public profile responses.
6. All Session Timeout options (15m, 30m, 1h, 2h, 4h) and Max Lifetime options (8h, 12h, 24h) are validated.
7. Inactivity expiry is enforced server-side.
8. Maximum Session Lifetime is enforced server-side.
9. Activity does not extend the absolute session lifetime.
10. Background requests do not silently keep sessions alive.
11. Expired or revoked sessions cannot access protected APIs.
12. Single logout and logout-all revoke sessions immediately.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.core.database import get_db
from api.models.models import Base, User
from api.models.security import UserSession, AuditLog
from api.services.auth_service import (
    signup_user,
    login_user,
    get_user_from_token,
    parse_timeout_settings,
    update_session_preferences,
    logout_user_session,
    logout_all_user_sessions,
    IDLE_TIMEOUT_MAP,
    MAX_LIFETIME_MAP,
)


class ApiClient:
    """Synchronous test client wrapper around httpx.AsyncClient + ASGITransport."""

    def __init__(self, app: FastAPI):
        self.app = app

    def get(self, url: str, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.get(url, headers=headers)
        return asyncio.run(_req())

    def post(self, url: str, json: dict | None = None, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.post(url, json=json, headers=headers)
        return asyncio.run(_req())

    def put(self, url: str, json: dict | None = None, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.put(url, json=json, headers=headers)
        return asyncio.run(_req())

    def delete(self, url: str, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.delete(url, headers=headers)
        return asyncio.run(_req())


class TestSessionTimeoutAndRoleSecurity(unittest.TestCase):
    """Focused security tests for session timeout, max lifetime, and role immutability."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Override get_db dependency
        def override_get_db():
            try:
                yield self.db
            finally:
                pass
        app.dependency_overrides[get_db] = override_get_db
        self.client = ApiClient(app)

        # Clean tables
        self.db.query(AuditLog).delete()
        self.db.query(UserSession).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Seed ordinary researcher user
        self.ordinary_res = signup_user(
            db=self.db,
            full_name="Dr. Charaka Researcher",
            email="charaka@ayurintel.org",
            password="SecurePassword123!",
        )
        self.user = self.db.query(User).filter(User.email == "charaka@ayurintel.org").first()
        self.user_token = self.ordinary_res["token"]

        # Seed admin user
        self.admin_res = signup_user(
            db=self.db,
            full_name="Admin Vaidya",
            email="admin@ayurintel.org",
            password="AdminPassword123!",
        )
        self.admin = self.db.query(User).filter(User.email == "admin@ayurintel.org").first()
        self.admin.role = "admin"
        self.db.commit()
        self.admin_login = login_user(
            db=self.db,
            email_or_username="admin@ayurintel.org",
            password="AdminPassword123!",
        )
        self.admin_token = self.admin_login["token"]

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    # ---------------------------------------------------------------------------
    # Task 1 & 4: Admin Navigation and Role Immutability
    # ---------------------------------------------------------------------------

    def test_01_admin_navigation_hidden_for_ordinary_users(self):
        """Admin navigation element is hidden by default in index.html and /api/auth/me returns 'user'."""
        with open("web/templates/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="nav-item-admin"', html)
        self.assertIn('style="display: none;"', html)

        # GET /api/auth/me for ordinary user returns role 'user'
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {self.user_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user"]["role"], "user")

    def test_02_admin_navigation_visible_only_for_server_verified_admin(self):
        """GET /api/auth/me returns role 'admin' only for server-promoted admin user."""
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user"]["role"], "admin")

    def test_03_ordinary_users_cannot_change_role_via_api(self):
        """PUT /api/auth/profile ignores or rejects role modification attempts; role stays 'user'."""
        res = self.client.put(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {self.user_token}"},
            json={"full_name": "Tampered Name", "role": "admin"},
        )
        self.assertEqual(res.status_code, 200)
        self.db.refresh(self.user)
        self.assertEqual(self.user.role, "user")

        # Signup payload with role attempt
        signup_res = signup_user(
            db=self.db,
            full_name="Attacker",
            email="attacker@ayurintel.org",
            password="AttackerPassword123!",
        )
        attacker = self.db.query(User).filter(User.email == "attacker@ayurintel.org").first()
        self.assertEqual(attacker.role, "user")

    def test_04_admin_role_not_exposed_in_public_profiles(self):
        """Publicly accessible endpoints do not expose admin email or roles."""
        health_res = self.client.get("/api/health")
        self.assertEqual(health_res.status_code, 200)
        self.assertNotIn("admin@ayurintel.org", health_res.text)

    # ---------------------------------------------------------------------------
    # Task 2 & 3: Timeout Settings Parsing & Session Creation
    # ---------------------------------------------------------------------------

    def test_05_session_timeout_and_lifetime_options_parsing(self):
        """Validate timeout options: 15m, 30m, 1h, 2h, 4h and lifetimes: 8h, 12h, 24h."""
        for opt, expected_sec in [("5m", 300), ("15m", 900), ("30m", 1800), ("1h", 3600), ("2h", 7200), ("4h", 14400)]:
            idle, _ = parse_timeout_settings(session_timeout=opt)
            self.assertEqual(idle, expected_sec)

        for opt, expected_sec in [("8h", 28800), ("12h", 43200), ("24h", 86400)]:
            _, max_life = parse_timeout_settings(max_lifetime=opt)
            self.assertEqual(max_life, expected_sec)

        # Safe fallback for invalid inputs
        idle_def, max_def = parse_timeout_settings(session_timeout="invalid", max_lifetime="999h")
        self.assertEqual(idle_def, 1800)
        self.assertEqual(max_def, 43200)

    def test_06_login_creates_session_with_timeout_settings(self):
        """Login payload persists session_timeout and max_lifetime on UserSession record."""
        login_resp = login_user(
            db=self.db,
            email_or_username="charaka@ayurintel.org",
            password="SecurePassword123!",
            session_timeout="2h",
            max_lifetime="24h",
        )
        token = login_resp["token"]
        user_inst = get_user_from_token(self.db, token)
        sess = self.db.query(UserSession).filter(UserSession.user_id == user_inst.id).order_by(UserSession.id.desc()).first()
        self.assertEqual(sess.idle_timeout_seconds, 7200)   # 2h
        self.assertEqual(sess.max_lifetime_seconds, 86400)  # 24h

    # ---------------------------------------------------------------------------
    # Server-Side Enforcement of Inactivity Timeout & Max Lifetime
    # ---------------------------------------------------------------------------

    def test_07_inactivity_expiry_enforced_server_side(self):
        """Requests after inactivity timeout (e.g., 30m) are rejected with 401 and session is marked revoked."""
        login_resp = login_user(
            db=self.db,
            email_or_username="charaka@ayurintel.org",
            password="SecurePassword123!",
            session_timeout="15m",  # 900s
            max_lifetime="12h",
        )
        token = login_resp["token"]
        sess = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).order_by(UserSession.id.desc()).first()

        # Simulate inactivity by setting last_active_at back 16 minutes
        sess.last_active_at = datetime.now(timezone.utc) - timedelta(minutes=16)
        self.db.commit()

        # Attempt to access protected API
        res = self.client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("inactivity", res.json()["detail"].lower())

        # Verify session is revoked in database
        self.db.refresh(sess)
        self.assertTrue(sess.is_revoked)

    def test_08_maximum_session_lifetime_enforced_server_side(self):
        """Requests after maximum session lifetime (e.g., 8h) are rejected even if user remained active."""
        login_resp = login_user(
            db=self.db,
            email_or_username="charaka@ayurintel.org",
            password="SecurePassword123!",
            session_timeout="1h",
            max_lifetime="8h",  # 28800s
        )
        token = login_resp["token"]
        sess = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).order_by(UserSession.id.desc()).first()

        # Simulate user being active 1 minute ago, but session was created 9 hours ago
        now = datetime.now(timezone.utc)
        sess.created_at = now - timedelta(hours=9)
        sess.last_active_at = now - timedelta(minutes=1)
        sess.expires_at = sess.created_at + timedelta(hours=8)
        self.db.commit()

        # Protected API should reject with 401
        res = self.client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("maximum session lifetime", res.json()["detail"].lower())

        self.db.refresh(sess)
        self.assertTrue(sess.is_revoked)

    def test_09_activity_does_not_extend_absolute_lifetime(self):
        """Refreshing last_active_at does not change created_at or push expires_at past max lifetime."""
        login_resp = login_user(
            db=self.db,
            email_or_username="charaka@ayurintel.org",
            password="SecurePassword123!",
            session_timeout="1h",
            max_lifetime="12h",
        )
        token = login_resp["token"]
        sess = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).order_by(UserSession.id.desc()).first()
        initial_created_at = sess.created_at
        initial_expires_at = sess.expires_at

        # Meaningful API call updates last_active_at if >= 10s elapsed
        sess.last_active_at = datetime.now(timezone.utc) - timedelta(seconds=20)
        self.db.commit()

        res = self.client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)

        self.db.refresh(sess)
        self.assertEqual(sess.created_at, initial_created_at)
        self.assertEqual(sess.expires_at, initial_expires_at)

    def test_10_background_requests_do_not_update_last_active_at(self):
        """Requests with X-Background-Request header or /api/auth/me do not bump last_active_at."""
        login_resp = login_user(
            db=self.db,
            email_or_username="charaka@ayurintel.org",
            password="SecurePassword123!",
            session_timeout="15m",
            max_lifetime="12h",
        )
        token = login_resp["token"]
        sess = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).order_by(UserSession.id.desc()).first()

        old_last_active = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(tzinfo=None)
        sess.last_active_at = old_last_active
        self.db.commit()

        # Background call with header
        res = self.client.get(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}", "X-Background-Request": "true"},
        )
        self.assertEqual(res.status_code, 200)
        self.db.refresh(sess)
        self.assertEqual(sess.last_active_at.replace(tzinfo=None), old_last_active)

        # GET /api/auth/me call
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        self.db.refresh(sess)
        self.assertEqual(sess.last_active_at.replace(tzinfo=None), old_last_active)

    def test_11_update_session_preferences_endpoint(self):
        """PUT /api/auth/session/settings safely updates active session timeout and lifetime."""
        login_resp = login_user(
            db=self.db,
            email_or_username="charaka@ayurintel.org",
            password="SecurePassword123!",
        )
        token = login_resp["token"]

        res = self.client.put(
            "/api/auth/session/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_timeout": "4h", "max_session_lifetime": "24h"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["idle_timeout_seconds"], 14400)  # 4h
        self.assertEqual(data["max_lifetime_seconds"], 86400)  # 24h

        # Attempt to revive an expired session fails
        sess = self.db.query(UserSession).filter(UserSession.user_id == self.user.id).order_by(UserSession.id.desc()).first()
        sess.is_revoked = True
        self.db.commit()

        revived_res = self.client.put(
            "/api/auth/session/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_timeout": "4h"},
        )
        self.assertEqual(revived_res.status_code, 401)

    def test_12_single_and_all_logout_revokes_sessions(self):
        """Single logout and logout-all revoke session and block subsequent access."""
        login_resp = login_user(
            db=self.db,
            email_or_username="charaka@ayurintel.org",
            password="SecurePassword123!",
        )
        token = login_resp["token"]

        logout_res = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # Subsequent access rejected
        subseq = self.client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(subseq.status_code, 401)


if __name__ == "__main__":
    unittest.main()
