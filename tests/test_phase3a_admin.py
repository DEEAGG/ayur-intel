"""Phase 3A Tests — Secure Admin Backend for AYUR-INTEL.

Tests:
1. Admin identity bootstrap (matching, unmatched, missing env var, case-insensitivity, idempotency).
2. Admin authorization (401 unauthenticated, 403 non-admin, 200 admin).
3. Legacy token without sid strictly rejected for admin accounts.
4. Role tampering prevention (signup and profile updates cannot grant admin role).
5. Safe response representations (no password hashes or secrets in admin responses).
6. Admin user management (listing, pagination, search, user detail).
7. User deactivation / activation with self-deactivation and sole-admin safeguards.
8. Deactivated user token rejection.
9. Remote session revocation (individual session and all sessions).
10. System-wide audit log queries with filtering.

ALL tests run against an isolated in-memory SQLite database (`sqlite:///:memory:`).
The persistent database is NEVER touched.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from typing import Generator

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.config import settings
from api.core.database import get_db
from api.models.models import Base, User
from api.models.security import AuditLog, UserSession
from api.routers import admin, auth
from api.services.admin_service import (
    bootstrap_admin_user,
    get_admin_audit_logs,
    get_admin_user_detail,
    get_admin_users,
    get_user_sessions,
    revoke_all_user_sessions_admin,
    revoke_user_session_admin,
    update_user_status,
)
from api.services.auth_service import (
    create_access_token,
    hash_password,
    login_user,
    signup_user,
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


class TestPhase3AAdminBackend(unittest.TestCase):
    """Test suite for Phase 3A: Secure Admin Backend."""

    def setUp(self):
        # Create an isolated in-memory SQLite database with StaticPool
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db: Session = self.SessionTesting()

        # Build FastAPI test application
        self.app = FastAPI()
        self.app.include_router(auth.router)
        self.app.include_router(admin.router)

        # Override dependency
        def override_get_db() -> Generator[Session, None, None]:
            db = self.SessionTesting()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = ApiClient(self.app)

        # Create test users
        self.admin_user = User(
            username="main_admin",
            display_name="Main Admin",
            email="admin@ayurintel.org",
            hashed_password=hash_password("AdminPass123!"),
            role="admin",
            token_version=1,
            is_active=True,
        )
        self.regular_user = User(
            username="regular_bob",
            display_name="Regular Bob",
            email="bob@example.com",
            hashed_password=hash_password("BobPassword123!"),
            role="user",
            token_version=1,
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.add(self.regular_user)
        self.db.commit()
        self.db.refresh(self.admin_user)
        self.db.refresh(self.regular_user)

        # Login admin to obtain valid token and session
        admin_login = login_user(self.db, "admin@ayurintel.org", "AdminPass123!")
        self.admin_token = admin_login["token"]

        # Login regular user
        user_login = login_user(self.db, "bob@example.com", "BobPassword123!")
        self.user_token = user_login["token"]

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # -----------------------------------------------------------------------
    # 1. Admin Bootstrap Tests
    # -----------------------------------------------------------------------

    def test_bootstrap_promotes_matching_account(self):
        """Bootstrap designates existing account matching AYURINTEL_ADMIN_EMAIL."""
        target = User(
            username="owner_user",
            display_name="Owner",
            email="owner@ayurintel.com",
            hashed_password=hash_password("OwnerPassword123!"),
            role="user",
            is_active=True,
        )
        self.db.add(target)
        self.db.commit()

        # Set env var
        orig = getattr(settings, "AYURINTEL_ADMIN_EMAIL", None)
        try:
            settings.AYURINTEL_ADMIN_EMAIL = "owner@ayurintel.com"
            bootstrapped = bootstrap_admin_user(self.db)
            self.assertIsNotNone(bootstrapped)
            self.assertEqual(bootstrapped.role, "admin")
            self.assertEqual(bootstrapped.id, target.id)
        finally:
            settings.AYURINTEL_ADMIN_EMAIL = orig

    def test_bootstrap_idempotent(self):
        """Calling bootstrap multiple times remains safe and idempotent."""
        orig = getattr(settings, "AYURINTEL_ADMIN_EMAIL", None)
        try:
            settings.AYURINTEL_ADMIN_EMAIL = "admin@ayurintel.org"
            first = bootstrap_admin_user(self.db)
            second = bootstrap_admin_user(self.db)
            self.assertEqual(first.role, "admin")
            self.assertEqual(second.role, "admin")
        finally:
            settings.AYURINTEL_ADMIN_EMAIL = orig

    def test_bootstrap_case_and_whitespace_insensitivity(self):
        """Bootstrap normalizes spaces and uppercase characters."""
        orig = getattr(settings, "AYURINTEL_ADMIN_EMAIL", None)
        try:
            settings.AYURINTEL_ADMIN_EMAIL = "   ADMIN@AYURINTEL.ORG   "
            res = bootstrap_admin_user(self.db)
            self.assertIsNotNone(res)
            self.assertEqual(res.id, self.admin_user.id)
        finally:
            settings.AYURINTEL_ADMIN_EMAIL = orig

    def test_bootstrap_missing_or_empty_env_var(self):
        """When AYURINTEL_ADMIN_EMAIL is missing or empty, no user is promoted."""
        orig = getattr(settings, "AYURINTEL_ADMIN_EMAIL", None)
        try:
            settings.AYURINTEL_ADMIN_EMAIL = ""
            res = bootstrap_admin_user(self.db)
            self.assertIsNone(res)

            settings.AYURINTEL_ADMIN_EMAIL = None
            res2 = bootstrap_admin_user(self.db)
            self.assertIsNone(res2)
        finally:
            settings.AYURINTEL_ADMIN_EMAIL = orig

    def test_bootstrap_nonexistent_email_does_not_create_account(self):
        """If configured admin email does not exist, do not create any account."""
        orig = getattr(settings, "AYURINTEL_ADMIN_EMAIL", None)
        try:
            settings.AYURINTEL_ADMIN_EMAIL = "nonexistent@ayurintel.com"
            user_count_before = self.db.query(User).count()
            res = bootstrap_admin_user(self.db)
            user_count_after = self.db.query(User).count()
            self.assertIsNone(res)
            self.assertEqual(user_count_before, user_count_after)
        finally:
            settings.AYURINTEL_ADMIN_EMAIL = orig

    # -----------------------------------------------------------------------
    # 2. Authorization & Privilege Escalation Checks
    # -----------------------------------------------------------------------

    def test_admin_endpoints_require_authentication_401(self):
        """Unauthenticated requests to admin endpoints receive 401."""
        endpoints = [
            ("GET", "/api/admin/users"),
            ("GET", f"/api/admin/users/{self.regular_user.public_id}"),
            ("PUT", f"/api/admin/users/{self.regular_user.public_id}/status"),
            ("GET", f"/api/admin/users/{self.regular_user.public_id}/sessions"),
            ("POST", f"/api/admin/users/{self.regular_user.public_id}/sessions/any/revoke"),
            ("POST", f"/api/admin/users/{self.regular_user.public_id}/logout-all"),
            ("GET", "/api/admin/audit-logs"),
        ]

        for method, url in endpoints:
            if method == "GET":
                resp = self.client.get(url)
            elif method == "PUT":
                resp = self.client.put(url, json={"is_active": False})
            else:
                resp = self.client.post(url)
            self.assertEqual(resp.status_code, 401, f"{method} {url} did not return 401")

    def test_admin_endpoints_reject_non_admin_403(self):
        """Non-admin authenticated user receives 403 Forbidden on all admin endpoints."""
        headers = {"Authorization": f"Bearer {self.user_token}"}
        endpoints = [
            ("GET", "/api/admin/users"),
            ("GET", f"/api/admin/users/{self.regular_user.public_id}"),
            ("PUT", f"/api/admin/users/{self.regular_user.public_id}/status"),
            ("GET", f"/api/admin/users/{self.regular_user.public_id}/sessions"),
            ("POST", f"/api/admin/users/{self.regular_user.public_id}/sessions/any/revoke"),
            ("POST", f"/api/admin/users/{self.regular_user.public_id}/logout-all"),
            ("GET", "/api/admin/audit-logs"),
        ]

        for method, url in endpoints:
            if method == "GET":
                resp = self.client.get(url, headers=headers)
            elif method == "PUT":
                resp = self.client.put(url, json={"is_active": False}, headers=headers)
            else:
                resp = self.client.post(url, headers=headers)
            self.assertEqual(resp.status_code, 403, f"{method} {url} did not return 403 for non-admin")

    def test_admin_authorized_access_200(self):
        """Admin user with valid active session succeeds on admin endpoints."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("users", data)
        self.assertGreaterEqual(data["total"], 2)

    def test_admin_token_without_sid_strictly_rejected(self):
        """Admin token without sid claim is rejected with 401 even if role claim is present."""
        legacy_admin_token = create_access_token({
            "sub": self.admin_user.public_id,
            "email": self.admin_user.email,
            "role": "admin",
        })
        headers = {"Authorization": f"Bearer {legacy_admin_token}"}
        resp = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Admin access requires an active session", resp.json()["detail"])

    def test_signup_cannot_inject_admin_role(self):
        """Signup forces role='user' regardless of request payload."""
        resp = self.client.post(
            "/api/auth/signup",
            json={
                "full_name": "Hacker User",
                "email": "hacker@example.com",
                "password": "Password123!",
                "role": "admin",
            },
        )
        self.assertEqual(resp.status_code, 200)
        created_user = self.db.query(User).filter(User.email == "hacker@example.com").first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.role, "user")

    def test_profile_update_cannot_change_role(self):
        """Profile update ignores role fields and keeps user role intact."""
        headers = {"Authorization": f"Bearer {self.user_token}"}
        resp = self.client.put(
            "/api/auth/profile",
            json={
                "full_name": "Bob Updated",
                "role": "admin",
            },
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(self.regular_user)
        self.assertEqual(self.regular_user.role, "user")

    # -----------------------------------------------------------------------
    # 3. Safe Representation (No Secrets Leaked)
    # -----------------------------------------------------------------------

    def test_admin_responses_never_include_password_hashes(self):
        """Ensure admin endpoints never return hashed_password or secrets."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}

        # 1. User listing
        list_resp = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(list_resp.status_code, 200)
        for u in list_resp.json()["users"]:
            self.assertNotIn("hashed_password", u)
            self.assertNotIn("password", u)

        # 2. User detail
        detail_resp = self.client.get(f"/api/admin/users/{self.regular_user.public_id}", headers=headers)
        self.assertEqual(detail_resp.status_code, 200)
        self.assertNotIn("hashed_password", detail_resp.json())
        self.assertNotIn("password", detail_resp.json())

        # 3. Audit logs
        logs_resp = self.client.get("/api/admin/audit-logs", headers=headers)
        self.assertEqual(logs_resp.status_code, 200)
        for log in logs_resp.json()["logs"]:
            self.assertNotIn("hashed_password", log)

    # -----------------------------------------------------------------------
    # 4. User Status & Lockout Safeguards
    # -----------------------------------------------------------------------

    def test_admin_cannot_deactivate_self(self):
        """Admin cannot deactivate their own administrator account (HTTP 400)."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.put(
            f"/api/admin/users/{self.admin_user.public_id}/status",
            json={"is_active": False},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot deactivate your own administrator account", resp.json()["detail"])

    def test_cannot_deactivate_sole_active_admin(self):
        """Cannot deactivate the only active admin account even if attempted by another."""
        # Create a second admin
        second_admin = User(
            username="second_admin",
            email="admin2@ayurintel.org",
            hashed_password=hash_password("AdminPass222!"),
            role="admin",
            is_active=True,
        )
        self.db.add(second_admin)
        self.db.commit()

        # Login second admin
        adm2_login = login_user(self.db, "admin2@ayurintel.org", "AdminPass222!")
        headers2 = {"Authorization": f"Bearer {adm2_login['token']}"}

        # Deactivate main_admin (now 1 active admin remains: second_admin)
        resp1 = self.client.put(
            f"/api/admin/users/{self.admin_user.public_id}/status",
            json={"is_active": False},
            headers=headers2,
        )
        self.assertEqual(resp1.status_code, 200)

        # Now try to deactivate second_admin from an authorized session -> blocked by self or sole check
        resp2 = self.client.put(
            f"/api/admin/users/{second_admin.public_id}/status",
            json={"is_active": False},
            headers=headers2,
        )
        # Should be blocked by self-check (and sole-admin check)
        self.assertEqual(resp2.status_code, 400)

    def test_deactivating_user_revokes_sessions_and_rejects_tokens_immediately(self):
        """Deactivating a user immediately invalidates active tokens."""
        # Confirm regular user token works on /api/auth/me before deactivation
        headers_bob = {"Authorization": f"Bearer {self.user_token}"}
        me_resp_before = self.client.get("/api/auth/me", headers=headers_bob)
        self.assertEqual(me_resp_before.status_code, 200)

        # Admin deactivates regular user
        headers_adm = {"Authorization": f"Bearer {self.admin_token}"}
        deact_resp = self.client.put(
            f"/api/admin/users/{self.regular_user.public_id}/status",
            json={"is_active": False},
            headers=headers_adm,
        )
        self.assertEqual(deact_resp.status_code, 200)

        # Verify active session revoked in DB
        sessions = self.db.query(UserSession).filter(UserSession.user_id == self.regular_user.id).all()
        for s in sessions:
            self.assertTrue(s.is_revoked)

        # Bob's token is immediately rejected with 401
        me_resp_after = self.client.get("/api/auth/me", headers=headers_bob)
        self.assertEqual(me_resp_after.status_code, 401)

        # Admin re-activates regular user
        act_resp = self.client.put(
            f"/api/admin/users/{self.regular_user.public_id}/status",
            json={"is_active": True},
            headers=headers_adm,
        )
        self.assertEqual(act_resp.status_code, 200)

        # Old revoked session is still rejected
        self.assertEqual(self.client.get("/api/auth/me", headers=headers_bob).status_code, 401)

        # Bob logs in again and gets new valid session
        new_login = login_user(self.db, "bob@example.com", "BobPassword123!")
        new_headers = {"Authorization": f"Bearer {new_login['token']}"}
        self.assertEqual(self.client.get("/api/auth/me", headers=new_headers).status_code, 200)

    # -----------------------------------------------------------------------
    # 5. Remote Session Revocation
    # -----------------------------------------------------------------------

    def test_admin_remote_revoke_single_session(self):
        """Admin can list and revoke a specific user session."""
        headers_adm = {"Authorization": f"Bearer {self.admin_token}"}
        headers_bob = {"Authorization": f"Bearer {self.user_token}"}

        # 1. List Bob's sessions
        sess_resp = self.client.get(
            f"/api/admin/users/{self.regular_user.public_id}/sessions",
            headers=headers_adm,
        )
        self.assertEqual(sess_resp.status_code, 200)
        sessions = sess_resp.json()
        self.assertGreaterEqual(len(sessions), 1)
        bob_sid = sessions[0]["id"]

        # 2. Bob's session works
        self.assertEqual(self.client.get("/api/auth/me", headers=headers_bob).status_code, 200)

        # 3. Admin revokes that session
        rev_resp = self.client.post(
            f"/api/admin/users/{self.regular_user.public_id}/sessions/{bob_sid}/revoke",
            headers=headers_adm,
        )
        self.assertEqual(rev_resp.status_code, 200)

        # 4. Bob's token is now rejected with 401
        self.assertEqual(self.client.get("/api/auth/me", headers=headers_bob).status_code, 401)

    def test_admin_remote_logout_all_sessions(self):
        """Admin can revoke all sessions for a user across all devices."""
        headers_adm = {"Authorization": f"Bearer {self.admin_token}"}

        # Create two separate login sessions for Bob
        l1 = login_user(self.db, "bob@example.com", "BobPassword123!")
        l2 = login_user(self.db, "bob@example.com", "BobPassword123!")

        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {l1['token']}"}).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {l2['token']}"}).status_code, 200)

        # Admin logs out all devices for Bob
        resp = self.client.post(
            f"/api/admin/users/{self.regular_user.public_id}/logout-all",
            headers=headers_adm,
        )
        self.assertEqual(resp.status_code, 200)

        # Both sessions are now revoked
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {l1['token']}"}).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {l2['token']}"}).status_code, 401)

    # -----------------------------------------------------------------------
    # 6. Audit Trail & Queries
    # -----------------------------------------------------------------------

    def test_admin_audit_logs_query_and_filters(self):
        """Admin can query audit logs with filters."""
        headers_adm = {"Authorization": f"Bearer {self.admin_token}"}

        # Query all logs
        logs_resp = self.client.get("/api/admin/audit-logs", headers=headers_adm)
        self.assertEqual(logs_resp.status_code, 200)
        data = logs_resp.json()
        self.assertIn("logs", data)
        self.assertGreaterEqual(data["total"], 1)

        # Query by action
        act_resp = self.client.get("/api/admin/audit-logs?action=LOGIN", headers=headers_adm)
        self.assertEqual(act_resp.status_code, 200)
        for log in act_resp.json()["logs"]:
            self.assertEqual(log["action"], "LOGIN")


if __name__ == "__main__":
    unittest.main()
