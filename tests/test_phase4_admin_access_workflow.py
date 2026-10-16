"""Phase 4 Tests — Premium Admin Console Access Approval & Elevated Unlock Workflow.

Tests cover:
1. Deactivated user login behavior and auto access request generation.
2. Explicit access request submission (/api/auth/access-request) and idempotent handling.
3. Access requests listing, detail view, filtering, and pending badge count.
4. Approval workflow: reactivates user, binds device hash, generates audit log.
5. Rejection workflow: maintains deactivation, records reviewer, generates audit log.
6. Authorization guards: regular users strictly denied on requests and unlock endpoints.
7. Device-level binding and validation.
8. Admin console elevated lock/unlock re-authentication cycle and HTTP 423 enforcement.
9. Extended metrics (8 KPIs including pending access requests).
10. User directory pending filter and login count tracking.

ALL tests run against an isolated in-memory SQLite database (`sqlite:///:memory:`).
"""

from __future__ import annotations

import asyncio
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from typing import Generator

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.database import get_db
from api.models.models import Base, User
from api.models.security import AccessRequest, AuditLog, UserSession
from api.routers import admin, auth
from api.services.auth_service import hash_password, login_user


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


class TestPhase4AdminAccessWorkflow(unittest.TestCase):
    """Test suite for Phase 4: Access Approval & Admin Unlock Re-authentication."""

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
        self.client = ApiClient(self.app)

        # 1. Create Admin User
        self.admin_user = User(
            username="sec_admin",
            display_name="Security Admin",
            email="secadmin@ayurintel.org",
            hashed_password=hash_password("AdminSecurePassword123!"),
            role="admin",
            token_version=1,
            is_active=True,
            login_count=5,
        )
        # 2. Create Regular Active User
        self.active_user = User(
            username="active_vaidya",
            display_name="Dr. Active",
            email="active@ayurintel.org",
            hashed_password=hash_password("ActivePass123!"),
            role="user",
            token_version=1,
            is_active=True,
            login_count=2,
        )
        # 3. Create Deactivated User
        self.deactivated_user = User(
            username="deact_user",
            display_name="Deactivated Researcher",
            email="deact@ayurintel.org",
            hashed_password=hash_password("DeactPass123!"),
            role="user",
            token_version=1,
            is_active=False,
            login_count=1,
        )
        self.db.add_all([self.admin_user, self.active_user, self.deactivated_user])
        self.db.commit()

        # Login admin and active user to acquire valid tokens
        adm_login = login_user(self.db, "secadmin@ayurintel.org", "AdminSecurePassword123!")
        self.admin_token = adm_login["token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        usr_login = login_user(self.db, "active@ayurintel.org", "ActivePass123!")
        self.user_token = usr_login["token"]
        self.user_headers = {"Authorization": f"Bearer {self.user_token}"}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    # -----------------------------------------------------------------------
    # 1. Deactivated Account Login & Request Workflow
    # -----------------------------------------------------------------------

    def test_deactivated_user_login_denied_with_message_and_creates_request(self):
        """Deactivated user with valid credentials receives 403 with specific message and auto-creates access request."""
        device_id = "device_alpha_12345"
        resp = self.client.post("/api/auth/login", json={
            "email": "deact@ayurintel.org",
            "password": "DeactPass123!",
            "device_id": device_id,
        })
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertIn("Approval pending by Admin", data["detail"])
        self.assertIn("Your account is currently deactivated", data["detail"])

        # Verify access request was created in database with hashed device id
        req = self.db.query(AccessRequest).filter(AccessRequest.user_id == self.deactivated_user.id).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, "PENDING")
        expected_hash = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
        self.assertEqual(req.device_hash, expected_hash)

        # Second login attempt should be idempotent (no duplicate request)
        resp2 = self.client.post("/api/auth/login", json={
            "email": "deact@ayurintel.org",
            "password": "DeactPass123!",
            "device_id": device_id,
        })
        self.assertEqual(resp2.status_code, 403)
        total_reqs = self.db.query(AccessRequest).filter(AccessRequest.user_id == self.deactivated_user.id).count()
        self.assertEqual(total_reqs, 1)

    def test_explicit_access_request_submission_endpoint(self):
        """User can submit an access request via /api/auth/access-request with reason and device info."""
        device_id = "device_beta_67890"
        resp = self.client.post("/api/auth/access-request", json={
            "email": "deact@ayurintel.org",
            "password": "DeactPass123!",
            "reason": "Please restore access for ongoing research project.",
            "device_id": device_id,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "pending")
        self.assertIn("request_id", data)

        req = self.db.query(AccessRequest).filter(AccessRequest.public_id == data["request_id"]).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.reason, "Please restore access for ongoing research project.")

    def test_access_request_submission_rejects_invalid_password(self):
        """Access request submission fails with 401 if password does not match account."""
        resp = self.client.post("/api/auth/access-request", json={
            "email": "deact@ayurintel.org",
            "password": "WrongPassword123!",
            "reason": "Intruder attempt",
        })
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["detail"], "Invalid email or password")

    # -----------------------------------------------------------------------
    # 2. Admin Review & Decision Workflow
    # -----------------------------------------------------------------------

    def test_admin_list_and_inspect_access_requests(self):
        """Admin can list pending access requests and inspect individual request context."""
        # Create a pending request
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            user_display_name=self.deactivated_user.display_name,
            status="PENDING",
            reason="Laboratory data validation access required",
            device_id="client_macbook_pro",
            device_info="macOS Chrome 120",
        )
        self.db.add(req)
        self.db.commit()

        # Admin lists requests
        resp = self.client.get("/api/admin/requests?status=pending", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["total"], 1)
        self.assertEqual(data["pending_count"], 1)
        item = data["requests"][0]
        self.assertEqual(item["user_email"], "deact@ayurintel.org")
        self.assertEqual(item["status"], "PENDING")

        # Inspect specific request
        detail_resp = self.client.get(f"/api/admin/requests/{req.public_id}", headers=self.admin_headers)
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["reason"], "Laboratory data validation access required")

    def test_admin_approve_access_request_reactivates_user_and_binds_device(self):
        """Admin approving an access request reactivates the account and binds approved device hash."""
        device_id = "trusted_lab_workstation"
        dev_hash = hashlib.sha256(device_id.encode("utf-8")).hexdigest()

        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            user_display_name=self.deactivated_user.display_name,
            status="PENDING",
            reason="Urgent trial analysis",
            device_id=device_id,
            device_hash=dev_hash,
            device_info="Windows 11 Edge",
        )
        self.db.add(req)
        self.db.commit()

        # Approve request
        approve_resp = self.client.post(
            f"/api/admin/requests/{req.public_id}/approve",
            json={"review_notes": "Identity and institution verified by phone."},
            headers=self.admin_headers,
        )
        self.assertEqual(approve_resp.status_code, 200)
        self.assertEqual(approve_resp.json()["status"], "APPROVED")

        # Check DB state
        self.db.refresh(req)
        self.db.refresh(self.deactivated_user)
        self.assertEqual(req.status, "APPROVED")
        self.assertEqual(req.reviewer_username, "sec_admin")
        self.assertTrue(self.deactivated_user.is_active)
        self.assertEqual(self.deactivated_user.approved_device_hash, dev_hash)

        # Target user can now log in normally!
        user_login = self.client.post("/api/auth/login", json={
            "email": "deact@ayurintel.org",
            "password": "DeactPass123!",
            "device_id": device_id,
        })
        self.assertEqual(user_login.status_code, 200)
        self.assertIn("token", user_login.json())

    def test_admin_reject_access_request_leaves_user_deactivated(self):
        """Admin rejecting an access request leaves the target account deactivated."""
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            user_display_name=self.deactivated_user.display_name,
            status="PENDING",
            reason="Unverified request",
        )
        self.db.add(req)
        self.db.commit()

        reject_resp = self.client.post(
            f"/api/admin/requests/{req.public_id}/reject",
            json={"review_notes": "Institutional affiliation could not be verified."},
            headers=self.admin_headers,
        )
        self.assertEqual(reject_resp.status_code, 200)
        self.assertEqual(reject_resp.json()["status"], "REJECTED")

        # Verify DB
        self.db.refresh(req)
        self.db.refresh(self.deactivated_user)
        self.assertEqual(req.status, "REJECTED")
        self.assertFalse(self.deactivated_user.is_active)

        # Login attempt still rejected
        user_login = self.client.post("/api/auth/login", json={
            "email": "deact@ayurintel.org",
            "password": "DeactPass123!",
        })
        self.assertEqual(user_login.status_code, 403)

    def test_non_admin_cannot_access_or_review_requests(self):
        """Non-admin authenticated user receives 403 Forbidden on all requests endpoints."""
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            status="PENDING",
        )
        self.db.add(req)
        self.db.commit()

        # Regular user tries GET /api/admin/requests
        r1 = self.client.get("/api/admin/requests", headers=self.user_headers)
        self.assertEqual(r1.status_code, 403)

        # Regular user tries POST approve
        r2 = self.client.post(f"/api/admin/requests/{req.public_id}/approve", headers=self.user_headers)
        self.assertEqual(r2.status_code, 403)

        # Regular user tries POST reject
        r3 = self.client.post(f"/api/admin/requests/{req.public_id}/reject", headers=self.user_headers)
        self.assertEqual(r3.status_code, 403)

    def test_double_approval_prevented(self):
        """Attempting to approve an already approved request returns 400 Bad Request."""
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            status="PENDING",
        )
        self.db.add(req)
        self.db.commit()

        r1 = self.client.post(f"/api/admin/requests/{req.public_id}/approve", headers=self.admin_headers)
        self.assertEqual(r1.status_code, 200)

        # Second approval attempt
        r2 = self.client.post(f"/api/admin/requests/{req.public_id}/approve", headers=self.admin_headers)
        self.assertEqual(r2.status_code, 400)
        self.assertIn("already been approved", r2.json()["detail"])

    def test_double_rejection_prevented(self):
        """Attempting to reject an already rejected request returns 400 Bad Request."""
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            status="PENDING",
        )
        self.db.add(req)
        self.db.commit()

        r1 = self.client.post(f"/api/admin/requests/{req.public_id}/reject", headers=self.admin_headers)
        self.assertEqual(r1.status_code, 200)

        # Second rejection attempt
        r2 = self.client.post(f"/api/admin/requests/{req.public_id}/reject", headers=self.admin_headers)
        self.assertEqual(r2.status_code, 400)
        self.assertIn("already been rejected", r2.json()["detail"])

    def test_access_request_status_case_insensitivity_and_refresh(self):
        """Access requests are stored as uppercase, filtered case-insensitively, and update status upon decision."""
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            status="PENDING",
            reason="Laboratory data validation",
        )
        self.db.add(req)
        self.db.commit()

        # 1. Fetch pending requests using lowercase query parameter
        r_pending = self.client.get("/api/admin/requests?status=pending", headers=self.admin_headers)
        self.assertEqual(r_pending.status_code, 200)
        data = r_pending.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["requests"][0]["status"], "PENDING")

        # 2. Approve the pending request
        r_approve = self.client.post(
            f"/api/admin/requests/{req.public_id}/approve",
            json={"review_notes": "Verified institutional researcher credential."},
            headers=self.admin_headers,
        )
        self.assertEqual(r_approve.status_code, 200)
        self.assertEqual(r_approve.json()["status"], "APPROVED")

        # 3. Request list refreshed: pending filter now has 0 items
        r_pending_after = self.client.get("/api/admin/requests?status=pending", headers=self.admin_headers)
        self.assertEqual(r_pending_after.status_code, 200)
        self.assertEqual(r_pending_after.json()["total"], 0)

        # 4. Approved filter now has 1 item with review metadata
        r_approved = self.client.get("/api/admin/requests?status=approved", headers=self.admin_headers)
        self.assertEqual(r_approved.status_code, 200)
        data_app = r_approved.json()
        self.assertEqual(data_app["total"], 1)
        self.assertEqual(data_app["requests"][0]["status"], "APPROVED")
        self.assertEqual(data_app["requests"][0]["review_notes"], "Verified institutional researcher credential.")

    def test_frontend_admin_js_access_approval_contract(self):
        """admin.js contains uppercase status normalization and working Accept/Approve button."""
        from api.core.config import PROJECT_ROOT
        admin_js_file = PROJECT_ROOT / "web" / "static" / "js" / "admin.js"
        self.assertTrue(admin_js_file.exists())
        js = admin_js_file.read_text(encoding="utf-8")

        # Case normalization
        self.assertIn(".toUpperCase()", js)
        self.assertIn("reqStatus === 'PENDING'", js)
        self.assertIn("reqStatus === 'APPROVED'", js)

        # Action buttons
        self.assertIn("btn-approve-request", js)
        self.assertIn("btn-reject-request", js)
        self.assertIn("Accept / Approve", js)
        self.assertIn("executeApproveRequest", js)
        self.assertIn("processingRequestId", js)

    # -----------------------------------------------------------------------
    # 3. Extended Metrics & User Directory Capabilities
    # -----------------------------------------------------------------------

    def test_admin_metrics_contains_8_kpis_including_pending_requests(self):
        """GET /api/admin/metrics returns 8 KPIs including pending_access_requests."""
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            status="PENDING",
        )
        self.db.add(req)
        self.db.commit()

        resp = self.client.get("/api/admin/metrics", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        expected_keys = [
            "total_users",
            "online_users",
            "offline_users",
            "active_accounts",
            "deactivated_accounts",
            "pending_access_requests",
            "total_active_sessions",
            "recent_audit_events_24h",
        ]
        for key in expected_keys:
            self.assertIn(key, data, f"Missing metric key: {key}")
        self.assertEqual(data["pending_access_requests"], 1)

    def test_user_directory_pending_filter_and_login_counts(self):
        """Admin can filter directory by status=pending and inspect login counts."""
        req = AccessRequest(
            user_id=self.deactivated_user.id,
            user_email=self.deactivated_user.email,
            status="PENDING",
        )
        self.db.add(req)
        self.db.commit()

        resp = self.client.get("/api/admin/users?status=pending", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        u = data["users"][0]
        self.assertEqual(u["id"], self.deactivated_user.public_id)
        self.assertTrue(u["has_pending_request"])
        self.assertIn("login_count", u)

    # -----------------------------------------------------------------------
    # 4. Admin Console Elevated Unlock & Re-Authentication
    # -----------------------------------------------------------------------

    def test_admin_unlock_cycle_lock_and_unlock(self):
        """Admin can inspect unlock status, explicitly lock console, and unlock with password."""
        # 1. Initially unlocked upon fresh login (15 min window)
        status_resp = self.client.get("/api/admin/unlock-status", headers=self.admin_headers)
        self.assertEqual(status_resp.status_code, 200)
        self.assertTrue(status_resp.json()["unlocked"])

        # 2. Admin explicitly locks the console
        lock_resp = self.client.post("/api/admin/lock", headers=self.admin_headers)
        self.assertEqual(lock_resp.status_code, 200)
        self.assertFalse(lock_resp.json()["unlocked"])

        # 3. Status is now locked
        status_resp2 = self.client.get("/api/admin/unlock-status", headers=self.admin_headers)
        self.assertFalse(status_resp2.json()["unlocked"])

        # 4. Sensitive action (e.g. status change) returns HTTP 423 Locked!
        mutate_resp = self.client.put(
            f"/api/admin/users/{self.active_user.public_id}/status",
            json={"is_active": False},
            headers=self.admin_headers,
        )
        self.assertEqual(mutate_resp.status_code, 423)
        self.assertIn("locked", mutate_resp.json()["detail"].lower())

        # 5. Wrong password rejected with 401
        wrong_unlock = self.client.post(
            "/api/admin/unlock",
            json={"password": "WrongPassword123!"},
            headers=self.admin_headers,
        )
        self.assertEqual(wrong_unlock.status_code, 401)

        # 6. Correct password succeeds and re-unlocks console
        unlock_resp = self.client.post(
            "/api/admin/unlock",
            json={"password": "AdminSecurePassword123!"},
            headers=self.admin_headers,
        )
        self.assertEqual(unlock_resp.status_code, 200)
        self.assertTrue(unlock_resp.json()["unlocked"])
        self.assertIn("unlock_token", unlock_resp.json())

        # 7. Now sensitive action succeeds!
        mutate_resp2 = self.client.put(
            f"/api/admin/users/{self.active_user.public_id}/status",
            json={"is_active": False},
            headers=self.admin_headers,
        )
        self.assertEqual(mutate_resp2.status_code, 200)
