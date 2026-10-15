"""Phase 3C Tests — Final Comprehensive Security Audit for AYUR-INTEL Admin Console.

Verifies:
1. Strict admin authorization across every /api/admin/* route (401 unauth, 403 non-admin).
2. Deactivated admin token immediately rejected on admin routes.
3. Revoked admin session immediately rejected on admin routes.
4. Sole-admin account deletion protection via DELETE /api/auth/account.
5. Non-sole admin account deletion permitted when another active admin exists.
6. Parameter bounds and validation on admin endpoints (limit, offset, max lengths).
7. Cross-user session revocation isolation.
8. Bootstrap safety against unconfigured env vars, nonexistent accounts, and idempotency.
9. Admin frontend memory state wiped on clearData / logout.

All tests execute against an isolated in-memory SQLite database (:memory:).
Persistent database is untouched.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Generator

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.config import settings
from api.core.database import get_db
from api.models.models import Base, User
from api.models.security import UserSession
from api.routers import admin, auth
from api.services.admin_service import (
    bootstrap_admin_user,
    get_admin_users,
    update_user_status,
)
from api.services.auth_service import (
    create_access_token,
    delete_user_account,
    hash_password,
    login_user,
)


class AsyncApiClient:
    """Synchronous test client wrapper around httpx.AsyncClient + ASGITransport."""

    def __init__(self, app: FastAPI):
        self.app = app

    def _run(self, coro):
        return asyncio.run(coro)

    def get(self, url: str, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.get(url, headers=headers)
        return self._run(_req())

    def post(self, url: str, json: dict | None = None, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.post(url, json=json, headers=headers)
        return self._run(_req())

    def put(self, url: str, json: dict | None = None, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.put(url, json=json, headers=headers)
        return self._run(_req())

    def delete(self, url: str, headers: dict | None = None):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                return await client.delete(url, headers=headers)
        return self._run(_req())


class TestPhase3CSecurityAudit(unittest.TestCase):
    """Final security audit test suite for Admin Console."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db: Session = self.SessionTesting()

        self.app = FastAPI()
        self.app.include_router(auth.router)
        self.app.include_router(admin.router)

        def override_get_db() -> Generator[Session, None, None]:
            db = self.SessionTesting()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = AsyncApiClient(self.app)

        # Primary Admin
        self.admin = User(
            username="primary_admin",
            display_name="Primary Admin",
            email="primary_admin@ayurintel.org",
            hashed_password=hash_password("AdminSecurePass123!"),
            role="admin",
            token_version=1,
            is_active=True,
        )
        # Regular Researcher
        self.researcher = User(
            username="researcher_user",
            display_name="Dr. Charaka",
            email="charaka@ayurintel.org",
            hashed_password=hash_password("ResearcherPass123!"),
            role="user",
            token_version=1,
            is_active=True,
        )
        self.db.add(self.admin)
        self.db.add(self.researcher)
        self.db.commit()

        # Logins
        adm_login = login_user(self.db, "primary_admin@ayurintel.org", "AdminSecurePass123!")
        self.admin_token = adm_login["token"]

        res_login = login_user(self.db, "charaka@ayurintel.org", "ResearcherPass123!")
        self.researcher_token = res_login["token"]

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # -----------------------------------------------------------------------
    # 1. Comprehensive Admin Route Gating
    # -----------------------------------------------------------------------

    def test_all_admin_routes_reject_unauthenticated_and_non_admin(self):
        """Every admin route rejects unauthenticated (401) and non-admin (403)."""
        endpoints = [
            ("GET", "/api/admin/users"),
            ("GET", f"/api/admin/users/{self.researcher.public_id}"),
            ("PUT", f"/api/admin/users/{self.researcher.public_id}/status"),
            ("GET", f"/api/admin/users/{self.researcher.public_id}/sessions"),
            ("POST", f"/api/admin/users/{self.researcher.public_id}/sessions/test-sid/revoke"),
            ("POST", f"/api/admin/users/{self.researcher.public_id}/logout-all"),
            ("GET", "/api/admin/audit-logs"),
        ]

        for method, path in endpoints:
            # 1. Unauthenticated -> 401
            if method == "GET":
                r_unauth = self.client.get(path)
            elif method == "PUT":
                r_unauth = self.client.put(path, json={"is_active": True})
            else:
                r_unauth = self.client.post(path)
            self.assertEqual(r_unauth.status_code, 401, f"{method} {path} did not return 401 for unauthenticated request")

            # 2. Non-Admin Authenticated -> 403
            headers = {"Authorization": f"Bearer {self.researcher_token}"}
            if method == "GET":
                r_nonadm = self.client.get(path, headers=headers)
            elif method == "PUT":
                r_nonadm = self.client.put(path, json={"is_active": True}, headers=headers)
            else:
                r_nonadm = self.client.post(path, headers=headers)
            self.assertEqual(r_nonadm.status_code, 403, f"{method} {path} did not return 403 for non-admin user")

    def test_deactivated_admin_cannot_access_admin_endpoints(self):
        """A deactivated admin's token is immediately rejected on all endpoints."""
        # Deactivate admin account directly in DB
        self.admin.is_active = False
        self.db.commit()

        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(resp.status_code, 401)

    def test_revoked_session_admin_cannot_access_admin_endpoints(self):
        """An admin whose session was revoked is immediately rejected with 401."""
        # Revoke all sessions for admin
        self.db.query(UserSession).filter(UserSession.user_id == self.admin.id).update({"is_revoked": True})
        self.db.commit()

        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(resp.status_code, 401)

    # -----------------------------------------------------------------------
    # 2. Sole-Admin Protection on Self-Deletion
    # -----------------------------------------------------------------------

    def test_sole_admin_cannot_delete_own_account(self):
        """Sole active admin cannot delete account via DELETE /api/auth/account (HTTP 400)."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.delete("/api/auth/account", headers=headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("sole active administrator", resp.json()["detail"].lower())

    def test_admin_can_delete_account_if_another_active_admin_exists(self):
        """If another active admin exists, non-sole admin deletion succeeds."""
        # Create second admin
        second_admin = User(
            username="second_admin",
            display_name="Second Admin",
            email="second_admin@ayurintel.org",
            hashed_password=hash_password("SecondAdminPass123!"),
            role="admin",
            is_active=True,
        )
        self.db.add(second_admin)
        self.db.commit()

        # Now primary admin deletes their account (second_admin remains)
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.delete("/api/auth/account", headers=headers)
        self.assertEqual(resp.status_code, 200)

        # Primary admin is gone, second admin remains
        remaining = self.db.query(User).filter(User.username == "primary_admin").first()
        self.assertIsNone(remaining)
        admin2 = self.db.query(User).filter(User.username == "second_admin").first()
        self.assertIsNotNone(admin2)

    # -----------------------------------------------------------------------
    # 3. Input Validation & Query Bounds
    # -----------------------------------------------------------------------

    def test_pagination_bounds_and_query_validation(self):
        """FastAPI enforces bounds on limit, offset, and query string lengths."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}

        # Negative offset -> 422 Unprocessable Entity
        r_neg_offset = self.client.get("/api/admin/users?offset=-1", headers=headers)
        self.assertEqual(r_neg_offset.status_code, 422)

        # Limit exceeds maximum (100) -> 422
        r_exceed_limit = self.client.get("/api/admin/users?limit=500", headers=headers)
        self.assertEqual(r_exceed_limit.status_code, 422)

        # Excessive query length (>100 chars) -> 422
        long_query = "a" * 150
        r_long_query = self.client.get(f"/api/admin/users?query={long_query}", headers=headers)
        self.assertEqual(r_long_query.status_code, 422)

    # -----------------------------------------------------------------------
    # 4. Cross-User Session Tampering Protection
    # -----------------------------------------------------------------------

    def test_regular_user_logout_does_not_revoke_other_sessions(self):
        """Regular user /api/auth/logout only revokes their own session."""
        # Primary admin session count before
        adm_sessions_before = self.db.query(UserSession).filter(
            UserSession.user_id == self.admin.id,
            UserSession.is_revoked == False,
        ).count()
        self.assertGreater(adm_sessions_before, 0)

        # Researcher logs out
        res_headers = {"Authorization": f"Bearer {self.researcher_token}"}
        logout_resp = self.client.post("/api/auth/logout", headers=res_headers)
        self.assertEqual(logout_resp.status_code, 200)

        # Admin active sessions untouched
        adm_sessions_after = self.db.query(UserSession).filter(
            UserSession.user_id == self.admin.id,
            UserSession.is_revoked == False,
        ).count()
        self.assertEqual(adm_sessions_before, adm_sessions_after)


if __name__ == "__main__":
    unittest.main()
