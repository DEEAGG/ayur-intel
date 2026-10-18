"""Automated Test Suite for Mandatory New-User Access Approval Workflow & Email Notifications.

Covers:
1. New user submits a request and appears in the Admin Console.
2. New user cannot access protected resources before approval.
3. Repeated login attempts do not create duplicate pending requests.
4. Admin approval grants the intended access.
5. Rejection keeps the user blocked.
6. Existing active users continue working normally.
7. Deactivated users remain blocked until correctly reactivated.
8. Unauthorized users cannot approve requests.
9. A new request triggers an administrator email notification to india.deepanshaggarwal@gmail.com.
10. A failed email attempt does not discard the request or grant access.
11. Repeated login attempts do not generate duplicate notification emails for the same pending request.
12. Existing authentication, session, and admin tests continue to pass.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Generator

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.database import get_db
from api.core.config import settings
from api.models.models import Base, User
from api.models.security import AccessRequest, UserSession
from api.routers import admin, auth
from api.services.auth_service import hash_password, login_user
from api.services.email_service import (
    clear_test_outbox,
    format_datetime_ist,
    get_test_outbox,
    set_test_email_hook,
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


class TestNewUserAccessApprovalWorkflow(unittest.TestCase):
    """Automated tests for Mandatory New-User Access Approval & Admin Email Notifications."""

    def setUp(self):
        clear_test_outbox()
        # By default in tests, email hook records outgoing email and returns True
        set_test_email_hook(lambda msg: True)

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

        # 1. Administrator User
        self.admin_user = User(
            username="main_admin",
            display_name="Deepansh Admin",
            email="india.deepanshaggarwal@gmail.com",
            hashed_password=hash_password("AdminSecurePassword123!"),
            role="admin",
            token_version=1,
            is_active=True,
            is_approved=True,
            login_count=10,
        )
        # 2. Existing Active Regular User
        self.active_user = User(
            username="existing_vaidya",
            display_name="Dr. Existing Vaidya",
            email="existing@ayurintel.org",
            hashed_password=hash_password("ActivePass123!"),
            role="user",
            token_version=1,
            is_active=True,
            is_approved=True,
            login_count=3,
        )
        # 3. Existing Deactivated User
        self.deactivated_user = User(
            username="deactivated_vaidya",
            display_name="Dr. Deactivated",
            email="deactivated@ayurintel.org",
            hashed_password=hash_password("DeactPass123!"),
            role="user",
            token_version=1,
            is_active=False,
            is_approved=True,
            login_count=1,
        )

        self.db.add_all([self.admin_user, self.active_user, self.deactivated_user])
        self.db.commit()

        # Login admin and active user
        adm_login = login_user(self.db, "india.deepanshaggarwal@gmail.com", "AdminSecurePassword123!")
        self.admin_token = adm_login["token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        usr_login = login_user(self.db, "existing@ayurintel.org", "ActivePass123!")
        self.user_token = usr_login["token"]
        self.user_headers = {"Authorization": f"Bearer {self.user_token}"}

        # Clear outbox after setup logins
        clear_test_outbox()

    def tearDown(self):
        set_test_email_hook(None)
        clear_test_outbox()
        self.db.close()
        self.engine.dispose()

    # -------------------------------------------------------------------------
    # 1. New user registration & appearance in Admin Console
    # -------------------------------------------------------------------------
    def test_01_new_user_submits_request_and_appears_in_admin_console(self):
        """New user registers, account is created pending approval, and request appears in Admin Console."""
        resp = self.client.post("/api/auth/signup", json={
            "full_name": "Dr. Charaka Applicant",
            "email": "applicant@ayurintel.org",
            "password": "ApplicantPass123!",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "pending_approval")
        self.assertNotIn("token", data)
        self.assertIn("request_id", data)

        # Verify User state in DB: is_active=False, is_approved=False
        new_user = self.db.query(User).filter(User.email == "applicant@ayurintel.org").first()
        self.assertIsNotNone(new_user)
        self.assertFalse(new_user.is_active)
        self.assertFalse(new_user.is_approved)

        # Verify Admin Console sees request under /api/admin/requests
        admin_resp = self.client.get("/api/admin/requests?status=pending", headers=self.admin_headers)
        self.assertEqual(admin_resp.status_code, 200)
        admin_data = admin_resp.json()
        matching = [r for r in admin_data["requests"] if r["user_email"] == "applicant@ayurintel.org"]
        self.assertEqual(len(matching), 1)
        req = matching[0]
        self.assertEqual(req["user_display_name"], "Dr. Charaka Applicant")
        self.assertEqual(req["status"], "PENDING")
        self.assertIn(req["request_type"], ("NEW_USER", "New User"))
        self.assertEqual(req["request_type_display"], "New User")

    # -------------------------------------------------------------------------
    # 2. New user cannot access protected resources before approval
    # -------------------------------------------------------------------------
    def test_02_new_user_cannot_access_protected_resources_before_approval(self):
        """Unapproved new user cannot log in or call protected endpoints."""
        self.client.post("/api/auth/signup", json={
            "full_name": "Unapproved Applicant",
            "email": "unapproved@ayurintel.org",
            "password": "Password12345!",
        })

        # Login attempt fails with 403 Forbidden
        login_resp = self.client.post("/api/auth/login", json={
            "email": "unapproved@ayurintel.org",
            "password": "Password12345!",
        })
        self.assertEqual(login_resp.status_code, 403)
        self.assertIn("Approval pending by Admin", login_resp.json()["detail"])
        self.assertIn("pending administrator approval", login_resp.json()["detail"])

        # Attempt to access protected endpoint with dummy/forged token fails with 401
        dummy_token = "invalid.token.structure"
        resp = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {dummy_token}"})
        self.assertEqual(resp.status_code, 401)

    # -------------------------------------------------------------------------
    # 3. Repeated login attempts do not create duplicate pending requests
    # -------------------------------------------------------------------------
    def test_03_repeated_login_attempts_do_not_create_duplicate_requests(self):
        """Multiple sign-in attempts by an unapproved user do not produce duplicate AccessRequest rows."""
        self.client.post("/api/auth/signup", json={
            "full_name": "Retry User",
            "email": "retry@ayurintel.org",
            "password": "Password12345!",
        })

        u = self.db.query(User).filter(User.email == "retry@ayurintel.org").first()
        initial_count = self.db.query(AccessRequest).filter(AccessRequest.user_id == u.id).count()
        self.assertEqual(initial_count, 1)

        # Retry login 3 times
        for _ in range(3):
            r = self.client.post("/api/auth/login", json={
                "email": "retry@ayurintel.org",
                "password": "Password12345!",
            })
            self.assertEqual(r.status_code, 403)

        final_count = self.db.query(AccessRequest).filter(AccessRequest.user_id == u.id).count()
        self.assertEqual(final_count, 1, "Duplicate access requests were improperly created on retry login")

    # -------------------------------------------------------------------------
    # 4. Admin approval grants intended access
    # -------------------------------------------------------------------------
    def test_04_admin_approval_grants_intended_access(self):
        """Admin approving the pending request activates the account and permits full application access."""
        signup_resp = self.client.post("/api/auth/signup", json={
            "full_name": "Future Active User",
            "email": "future_active@ayurintel.org",
            "password": "Password12345!",
        })
        req_id = signup_resp.json()["request_id"]

        # Approve request as admin
        app_resp = self.client.post(
            f"/api/admin/requests/{req_id}/approve",
            json={"review_notes": "Verified institutional credentials."},
            headers=self.admin_headers,
        )
        self.assertEqual(app_resp.status_code, 200)
        self.assertEqual(app_resp.json()["status"], "APPROVED")

        # User logs in successfully
        login_resp = self.client.post("/api/auth/login", json={
            "email": "future_active@ayurintel.org",
            "password": "Password12345!",
        })
        self.assertEqual(login_resp.status_code, 200)
        new_token = login_resp.json()["token"]

        # User accesses protected API
        me_resp = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["user"]["email"], "future_active@ayurintel.org")

    # -------------------------------------------------------------------------
    # 5. Rejection keeps user blocked
    # -------------------------------------------------------------------------
    def test_05_rejection_keeps_user_blocked(self):
        """Admin rejecting request keeps account blocked and prevents login with rejection notice."""
        signup_resp = self.client.post("/api/auth/signup", json={
            "full_name": "Rejected Applicant",
            "email": "rejected@ayurintel.org",
            "password": "Password12345!",
        })
        req_id = signup_resp.json()["request_id"]

        # Reject request as admin
        rej_resp = self.client.post(
            f"/api/admin/requests/{req_id}/reject",
            json={"review_notes": "Incomplete application details."},
            headers=self.admin_headers,
        )
        self.assertEqual(rej_resp.status_code, 200)

        # User attempts login: receives 403 explaining access was not approved
        login_resp = self.client.post("/api/auth/login", json={
            "email": "rejected@ayurintel.org",
            "password": "Password12345!",
        })
        self.assertEqual(login_resp.status_code, 403)
        self.assertIn("Access not approved", login_resp.json()["detail"])

        # No duplicate pending request is created for a rejected user on login
        u = self.db.query(User).filter(User.email == "rejected@ayurintel.org").first()
        pending_count = self.db.query(AccessRequest).filter(
            AccessRequest.user_id == u.id, AccessRequest.status == "PENDING"
        ).count()
        self.assertEqual(pending_count, 0)

    # -------------------------------------------------------------------------
    # 6. Existing active users continue working normally
    # -------------------------------------------------------------------------
    def test_06_existing_active_users_continue_working_normally(self):
        """Active users created before or approved can sign in and call APIs without hindrance."""
        login_resp = self.client.post("/api/auth/login", json={
            "email": "existing@ayurintel.org",
            "password": "ActivePass123!",
        })
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.json()["token"]

        me_resp = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["user"]["email"], "existing@ayurintel.org")

    # -------------------------------------------------------------------------
    # 7. Deactivated users remain blocked until reactivated
    # -------------------------------------------------------------------------
    def test_07_deactivated_users_remain_blocked_until_reactivated(self):
        """Deactivated user login auto-creates reactivation request and requires reactivation approval."""
        login_resp = self.client.post("/api/auth/login", json={
            "email": "deactivated@ayurintel.org",
            "password": "DeactPass123!",
        })
        self.assertEqual(login_resp.status_code, 403)
        self.assertIn("currently deactivated", login_resp.json()["detail"])

        # Check request in DB: request_type == 'REACTIVATION'
        req = self.db.query(AccessRequest).filter(
            AccessRequest.user_id == self.deactivated_user.id,
            AccessRequest.status == "PENDING"
        ).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.request_type, "REACTIVATION")

        # Admin approves reactivation
        app_resp = self.client.post(
            f"/api/admin/requests/{req.public_id}/approve",
            json={"review_notes": "Reactivation approved."},
            headers=self.admin_headers,
        )
        self.assertEqual(app_resp.status_code, 200)

        # Deactivated user can now log in
        login_success = self.client.post("/api/auth/login", json={
            "email": "deactivated@ayurintel.org",
            "password": "DeactPass123!",
        })
        self.assertEqual(login_success.status_code, 200)

    # -------------------------------------------------------------------------
    # 8. Unauthorized users cannot approve requests
    # -------------------------------------------------------------------------
    def test_08_unauthorized_users_cannot_approve_requests(self):
        """Anonymous and regular users are strictly forbidden from approving access requests."""
        signup_resp = self.client.post("/api/auth/signup", json={
            "full_name": "Target Applicant",
            "email": "target@ayurintel.org",
            "password": "Password12345!",
        })
        req_id = signup_resp.json()["request_id"]

        # Anonymous call -> 401
        anon_resp = self.client.post(f"/api/admin/requests/{req_id}/approve")
        self.assertEqual(anon_resp.status_code, 401)

        # Regular user call -> 403
        reg_resp = self.client.post(
            f"/api/admin/requests/{req_id}/approve",
            headers=self.user_headers,
        )
        self.assertEqual(reg_resp.status_code, 403)

        # Request remains PENDING
        req = self.db.query(AccessRequest).filter(AccessRequest.public_id == req_id).first()
        self.assertEqual(req.status, "PENDING")

    # -------------------------------------------------------------------------
    # 9. Email notification sent on genuinely new access request
    # -------------------------------------------------------------------------
    def test_09_new_request_triggers_admin_email_notification(self):
        """New access request creation dispatches an email notification to administrator."""
        captured = []
        set_test_email_hook(lambda msg: (captured.append(msg), True)[1])

        resp = self.client.post("/api/auth/signup", json={
            "full_name": "Vaidya Sushruta",
            "email": "sushruta@ayurintel.org",
            "password": "SecurePassword123!",
        })
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(captured), 1)
        msg = captured[0]
        self.assertEqual(msg["recipient"], "india.deepanshaggarwal@gmail.com")
        self.assertEqual(msg["subject"], "[AYUR-INTEL] New Access Approval Request")
        self.assertEqual(msg["applicant_name"], "Vaidya Sushruta")
        self.assertEqual(msg["applicant_email"], "sushruta@ayurintel.org")
        self.assertEqual(msg["request_type"], "New User")
        self.assertIn("IST", msg["created_ist"])
        self.assertIn("https://ayur-intel.onrender.com/", msg["text"])
        self.assertIn("#admin", msg["text"])
        self.assertNotIn("password", msg["text"].lower())
        self.assertNotIn("hash", msg["text"].lower())

    # -------------------------------------------------------------------------
    # 10. Failed email attempt does not discard request or grant access
    # -------------------------------------------------------------------------
    def test_10_failed_email_attempt_does_not_discard_request_or_grant_access(self):
        """When email provider fails or is unreachable, request remains safely stored in DB and access is blocked."""
        # Simulate email failure
        set_test_email_hook(lambda msg: False)

        resp = self.client.post("/api/auth/signup", json={
            "full_name": "Offline Mail User",
            "email": "offline_mail@ayurintel.org",
            "password": "Password12345!",
        })
        self.assertEqual(resp.status_code, 200)
        req_id = resp.json()["request_id"]

        # Request is preserved in DB
        req = self.db.query(AccessRequest).filter(AccessRequest.public_id == req_id).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, "PENDING")
        self.assertFalse(req.notification_sent)
        self.assertIsNotNone(req.notification_error)

        # User is STILL not allowed to log in
        login_resp = self.client.post("/api/auth/login", json={
            "email": "offline_mail@ayurintel.org",
            "password": "Password12345!",
        })
        self.assertEqual(login_resp.status_code, 403)

    # -------------------------------------------------------------------------
    # 11. Repeated login attempts do not generate duplicate notification emails
    # -------------------------------------------------------------------------
    def test_11_repeated_login_attempts_do_not_generate_duplicate_emails(self):
        """Subsequent login attempts while a request is already pending do NOT trigger extra emails."""
        outbox = get_test_outbox()
        self.assertEqual(len(outbox), 0)

        # Signup sends 1 email
        self.client.post("/api/auth/signup", json={
            "full_name": "Single Alert User",
            "email": "single_alert@ayurintel.org",
            "password": "Password12345!",
        })
        self.assertEqual(len(get_test_outbox()), 1)

        # User retries login 4 times
        for _ in range(4):
            self.client.post("/api/auth/login", json={
                "email": "single_alert@ayurintel.org",
                "password": "Password12345!",
            })

        # Outbox must still contain only 1 email
        self.assertEqual(len(get_test_outbox()), 1, "Repeated login attempts generated duplicate emails")

    # -------------------------------------------------------------------------
    # 12. IST Datetime formatting
    # -------------------------------------------------------------------------
    def test_12_ist_datetime_formatting(self):
        """format_datetime_ist correctly converts UTC time to IST (UTC+05:30)."""
        utc_dt = datetime(2026, 10, 18, 7, 19, 51, tzinfo=timezone.utc)
        ist_str = format_datetime_ist(utc_dt)
        # 07:19 UTC + 05:30 = 12:49 PM IST
        self.assertIn("18 Oct 2026", ist_str)
        self.assertIn("12:49 PM IST", ist_str)


if __name__ == "__main__":
    unittest.main()
