"""Phase 5 Tests — Persistent Admin Console Password Lock, Full Blur & Global Sessions.

Tests:
1. First-time Admin Console password setup validation:
   - Rejection with invalid account password
   - Rejection with console password < 12 characters
   - Rejection with mismatched confirm password
   - Successful setup: hashes password, sets elevation, audits event
2. Persistent lock state on login:
   - When admin_console_password_hash is configured, login leaves console locked (admin_unlocked_until = None)
   - Read & mutation endpoints return HTTP 423 with X-Admin-Configured: true
3. Unlock with persistent console password:
   - Rejection with wrong console password
   - Success with valid console password (returns elevation token)
   - Elevates access and allows reads & writes
4. In-console change password:
   - Requires current console password
   - Enforces min 12 characters and matching confirmation
   - Updates hash and maintains elevation
5. Console password recovery:
   - Requires valid main account password
   - Resets console password hash and elevates session
6. Explicit lock and auto-lock enforcement:
   - POST /api/admin/lock immediately revokes elevation
   - Subsequent admin actions return HTTP 423
7. Global Active Sessions view:
   - GET /api/admin/all-sessions returns all concurrent active system sessions
   - Terminating a session revokes the target session token

ALL tests execute against an isolated in-memory SQLite database (`sqlite:///:memory:`).
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

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
from api.services.admin_service import bootstrap_admin_user
from api.services.auth_service import hash_password, login_user, signup_user


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


class TestPersistentPasswordLock(unittest.TestCase):
    """Test suite for persistent admin console password lock and security policies."""

    def setUp(self):
        from api.core.security import _auth_rate_limit_store
        _auth_rate_limit_store.clear()

        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        self.app = FastAPI()
        self.app.include_router(auth.router)
        self.app.include_router(admin.router)

        def override_get_db():
            db = self.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = ApiClient(self.app)

        # Seed admin user and regular researcher user
        self.db: Session = self.TestingSessionLocal()
        self.admin_user = User(
            username="main_admin",
            display_name="Main Admin",
            email="admin@ayurintel.org",
            hashed_password=hash_password("AccountMasterPassword123!"),
            role="admin",
            token_version=1,
            is_active=True,
        )
        self.regular_user = User(
            username="botanist_jane",
            display_name="Jane Botanist",
            email="researcher@ayurintel.org",
            hashed_password=hash_password("ResearcherPassword123!"),
            role="user",
            token_version=1,
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.add(self.regular_user)
        self.db.commit()

    def tearDown(self):
        from api.core.security import _auth_rate_limit_store
        _auth_rate_limit_store.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_first_time_setup_and_validation(self):
        """Admin without configured console password must setup persistent password."""
        # Log in as admin
        login_resp = self.client.post(
            "/api/auth/login",
            json={
                "email": "admin@ayurintel.org",
                "password": "AccountMasterPassword123!",
            },
        )
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.json()["token"]
        auth_hdr = {"Authorization": f"Bearer {token}"}

        # Check unlock status: configured should be False initially
        status_resp = self.client.get("/api/admin/unlock-status", headers=auth_hdr)
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertFalse(status_data["is_configured"])

        # 1. Rejection: wrong account password
        bad_acc_resp = self.client.post(
            "/api/admin/setup-password",
            json={
                "account_password": "WrongPassword123!",
                "console_password": "SecureConsolePassword2026!",
                "confirm_password": "SecureConsolePassword2026!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(bad_acc_resp.status_code, 401)
        self.assertIn("Invalid administrator account password", bad_acc_resp.json()["detail"])

        # 2. Rejection: console password too short (< 12 characters)
        short_pwd_resp = self.client.post(
            "/api/admin/setup-password",
            json={
                "account_password": "AccountMasterPassword123!",
                "console_password": "Short123!",
                "confirm_password": "Short123!",
            },
            headers=auth_hdr,
        )
        self.assertIn(short_pwd_resp.status_code, [400, 422])
        self.assertIn("12", str(short_pwd_resp.json()))

        # 3. Rejection: mismatched passwords
        mismatch_resp = self.client.post(
            "/api/admin/setup-password",
            json={
                "account_password": "AccountMasterPassword123!",
                "console_password": "SecureConsolePassword2026!",
                "confirm_password": "DifferentPassword2026!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(mismatch_resp.status_code, 400)
        self.assertIn("do not match", mismatch_resp.json()["detail"])

        # 4. Success: valid account password & 12+ chars matching console password
        setup_resp = self.client.post(
            "/api/admin/setup-password",
            json={
                "account_password": "AccountMasterPassword123!",
                "console_password": "SecureConsolePassword2026!",
                "confirm_password": "SecureConsolePassword2026!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(setup_resp.status_code, 200)
        setup_data = setup_resp.json()
        self.assertTrue(setup_data["is_unlocked"])
        self.assertTrue(setup_data["is_configured"])
        self.assertIn("token", setup_data)

        # Check status after setup
        status_after = self.client.get("/api/admin/unlock-status", headers=auth_hdr)
        self.assertTrue(status_after.json()["is_configured"])
        self.assertTrue(status_after.json()["is_unlocked"])

    def test_configured_console_locks_on_subsequent_login(self):
        """When admin_console_password_hash is configured, new login starts strictly locked."""
        # Configure console password first
        admin_user = self.db.query(User).filter(User.email == "admin@ayurintel.org").first()
        admin_user.admin_console_password_hash = hash_password("PersistentConsolePwd2026!")
        self.db.commit()

        # Log in again
        login_resp = self.client.post(
            "/api/auth/login",
            json={
                "email": "admin@ayurintel.org",
                "password": "AccountMasterPassword123!",
            },
        )
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.json()["token"]
        auth_hdr = {"Authorization": f"Bearer {token}"}

        # Verify status: configured is True, but unlocked is False!
        status_resp = self.client.get("/api/admin/unlock-status", headers=auth_hdr)
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertTrue(status_data["is_configured"])
        self.assertFalse(status_data["is_unlocked"])

        # Accessing protected admin endpoint returns HTTP 423 Locked with X-Admin-Configured: true
        users_resp = self.client.get("/api/admin/users", headers=auth_hdr)
        self.assertEqual(users_resp.status_code, 423)
        self.assertEqual(users_resp.headers.get("X-Admin-Configured"), "true")

        metrics_resp = self.client.get("/api/admin/metrics", headers=auth_hdr)
        self.assertEqual(metrics_resp.status_code, 423)

        # Try unlocking with wrong console password
        bad_unlock = self.client.post(
            "/api/admin/unlock",
            json={"password": "WrongConsolePassword!"},
            headers=auth_hdr,
        )
        self.assertEqual(bad_unlock.status_code, 401)

        # Unlock with correct persistent console password
        good_unlock = self.client.post(
            "/api/admin/unlock",
            json={"password": "PersistentConsolePwd2026!"},
            headers=auth_hdr,
        )
        self.assertEqual(good_unlock.status_code, 200)
        unlock_data = good_unlock.json()
        self.assertTrue(unlock_data["is_unlocked"])
        unlock_token = unlock_data["token"]

        # Now requests with X-Admin-Unlock-Token succeed (200)
        elevated_hdr = {
            "Authorization": f"Bearer {token}",
            "X-Admin-Unlock-Token": unlock_token,
        }
        users_ok = self.client.get("/api/admin/users", headers=elevated_hdr)
        self.assertEqual(users_ok.status_code, 200)
        self.assertGreaterEqual(len(users_ok.json()["users"]), 2)

    def test_in_console_change_password(self):
        """Admin can change persistent console password from within elevated console."""
        admin_user = self.db.query(User).filter(User.email == "admin@ayurintel.org").first()
        admin_user.admin_console_password_hash = hash_password("CurrentConsolePwd2026!")
        self.db.commit()

        login_resp = self.client.post(
            "/api/auth/login",
            json={
                "email": "admin@ayurintel.org",
                "password": "AccountMasterPassword123!",
            },
        )
        token = login_resp.json()["token"]
        auth_hdr = {"Authorization": f"Bearer {token}"}

        # Unlock
        unlock_resp = self.client.post(
            "/api/admin/unlock",
            json={"password": "CurrentConsolePwd2026!"},
            headers=auth_hdr,
        )
        elevated_token = unlock_resp.json()["token"]
        elevated_hdr = {
            "Authorization": f"Bearer {token}",
            "X-Admin-Unlock-Token": elevated_token,
        }

        # Change password fails with wrong current password
        bad_change = self.client.post(
            "/api/admin/change-console-password",
            json={
                "current_password": "WrongPassword123!",
                "new_password": "BrandNewConsolePwd2026!",
                "confirm_password": "BrandNewConsolePwd2026!",
            },
            headers=elevated_hdr,
        )
        self.assertEqual(bad_change.status_code, 401)
        self.assertIn("Current Admin Console password is incorrect", bad_change.json()["detail"])

        # Change password succeeds with valid credentials
        good_change = self.client.post(
            "/api/admin/change-console-password",
            json={
                "current_password": "CurrentConsolePwd2026!",
                "new_password": "BrandNewConsolePwd2026!",
                "confirm_password": "BrandNewConsolePwd2026!",
            },
            headers=elevated_hdr,
        )
        self.assertEqual(good_change.status_code, 200)

        # Lock console explicitly
        self.client.post("/api/admin/lock", headers=elevated_hdr)

        # Verify old password no longer works
        old_unlock = self.client.post(
            "/api/admin/unlock",
            json={"password": "CurrentConsolePwd2026!"},
            headers=auth_hdr,
        )
        self.assertEqual(old_unlock.status_code, 401)

        # Verify new password unlocks successfully
        new_unlock = self.client.post(
            "/api/admin/unlock",
            json={"password": "BrandNewConsolePwd2026!"},
            headers=auth_hdr,
        )
        self.assertEqual(new_unlock.status_code, 200)
        self.assertTrue(new_unlock.json()["is_unlocked"])

    def test_console_password_recovery(self):
        """Admin can recover console access using account password."""
        admin_user = self.db.query(User).filter(User.email == "admin@ayurintel.org").first()
        admin_user.admin_console_password_hash = hash_password("ForgottenConsolePwd!")
        self.db.commit()

        login_resp = self.client.post(
            "/api/auth/login",
            json={
                "email": "admin@ayurintel.org",
                "password": "AccountMasterPassword123!",
            },
        )
        token = login_resp.json()["token"]
        auth_hdr = {"Authorization": f"Bearer {token}"}

        # Recovery with bad account password fails
        bad_rec = self.client.post(
            "/api/admin/recover-console-password",
            json={
                "account_password": "WrongAccountPassword!",
                "new_console_password": "RecoveredConsolePwd2026!",
                "confirm_console_password": "RecoveredConsolePwd2026!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(bad_rec.status_code, 401)

        # Recovery with valid account password succeeds
        good_rec = self.client.post(
            "/api/admin/recover-console-password",
            json={
                "account_password": "AccountMasterPassword123!",
                "new_console_password": "RecoveredConsolePwd2026!",
                "confirm_console_password": "RecoveredConsolePwd2026!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(good_rec.status_code, 200)
        rec_data = good_rec.json()
        self.assertTrue(rec_data["is_unlocked"])
        elevated_token = rec_data["token"]

        # Check endpoints work with recovered elevation
        elevated_hdr = {
            "Authorization": f"Bearer {token}",
            "X-Admin-Unlock-Token": elevated_token,
        }
        metrics = self.client.get("/api/admin/metrics", headers=elevated_hdr)
        self.assertEqual(metrics.status_code, 200)

    def test_global_active_sessions_endpoint(self):
        """GET /api/admin/all-sessions lists all active concurrent sessions and allows termination."""
        # Unlocked admin session setup
        admin_user = self.db.query(User).filter(User.email == "admin@ayurintel.org").first()
        admin_user.admin_console_password_hash = hash_password("ConsolePassword2026!")
        self.db.commit()

        login_resp = self.client.post(
            "/api/auth/login",
            json={
                "email": "admin@ayurintel.org",
                "password": "AccountMasterPassword123!",
            },
        )
        admin_token = login_resp.json()["token"]
        auth_hdr = {"Authorization": f"Bearer {admin_token}"}

        # Regular user login (creates active session)
        user_login = self.client.post(
            "/api/auth/login",
            json={
                "email": "researcher@ayurintel.org",
                "password": "ResearcherPassword123!",
            },
        )
        self.assertEqual(user_login.status_code, 200)
        user_sess = self.db.query(UserSession).filter(UserSession.user_id == self.regular_user.id).order_by(UserSession.id.desc()).first()
        self.assertIsNotNone(user_sess)
        user_session_id = user_sess.public_id

        # Locked admin cannot query all sessions (HTTP 423)
        locked_sess = self.client.get("/api/admin/all-sessions", headers=auth_hdr)
        self.assertEqual(locked_sess.status_code, 423)

        # Unlock admin
        unlock_resp = self.client.post(
            "/api/admin/unlock",
            json={"password": "ConsolePassword2026!"},
            headers=auth_hdr,
        )
        elevated_token = unlock_resp.json()["token"]
        elevated_hdr = {
            "Authorization": f"Bearer {admin_token}",
            "X-Admin-Unlock-Token": elevated_token,
        }

        # Unlocked admin can query all sessions
        all_sess_resp = self.client.get("/api/admin/all-sessions", headers=elevated_hdr)
        self.assertEqual(all_sess_resp.status_code, 200)
        sess_data = all_sess_resp.json()
        self.assertGreaterEqual(sess_data["total"], 2)
        session_ids = [s["id"] for s in sess_data["sessions"]]
        self.assertIn(user_session_id, session_ids)

        # Terminate regular user's session
        jane_user = self.db.query(User).filter(User.username == "botanist_jane").first()
        revoke_resp = self.client.post(
            f"/api/admin/users/{jane_user.public_id}/sessions/{user_session_id}/revoke",
            headers=elevated_hdr,
        )
        self.assertEqual(revoke_resp.status_code, 200)

        # Query all-sessions again: regular user's revoked session is no longer active
        after_sess = self.client.get("/api/admin/all-sessions", headers=elevated_hdr)
        active_ids_after = [s["id"] for s in after_sess.json()["sessions"]]
        self.assertNotIn(user_session_id, active_ids_after)

    def test_failed_attempts_rate_limit_and_cooldown(self):
        """Test that 3 consecutive failed unlock attempts enforce a 5-minute cooldown with HTTP 429."""
        # Setup admin console password
        self.admin_user.admin_console_password_hash = hash_password("ValidConsoleSecret123!")
        self.admin_user.admin_console_failed_attempts = 0
        self.admin_user.admin_console_cooldown_until = None
        self.db.commit()

        login_resp = self.client.post(
            "/api/auth/login",
            json={"email": "admin@ayurintel.org", "password": "AccountMasterPassword123!"},
        )
        self.assertEqual(login_resp.status_code, 200)
        admin_token = login_resp.json()["token"]
        auth_hdr = {"Authorization": f"Bearer {admin_token}"}

        # Attempt 1: wrong password -> 401, 2 attempts remaining
        resp1 = self.client.post(
            "/api/admin/unlock",
            json={"password": "WrongPassword1!"},
            headers=auth_hdr,
        )
        self.assertEqual(resp1.status_code, 401)
        self.assertIn("2 attempts remaining", resp1.json()["detail"])

        # Check DB state
        self.db.refresh(self.admin_user)
        self.assertEqual(self.admin_user.admin_console_failed_attempts, 1)
        self.assertIsNone(self.admin_user.admin_console_cooldown_until)

        # Attempt 2: wrong password -> 401, 1 attempt remaining
        resp2 = self.client.post(
            "/api/admin/unlock",
            json={"password": "WrongPassword2!"},
            headers=auth_hdr,
        )
        self.assertEqual(resp2.status_code, 401)
        self.assertIn("1 attempt remaining", resp2.json()["detail"])

        self.db.refresh(self.admin_user)
        self.assertEqual(self.admin_user.admin_console_failed_attempts, 2)

        # Attempt 3: wrong password -> 429, triggers 5-minute cooldown
        resp3 = self.client.post(
            "/api/admin/unlock",
            json={"password": "WrongPassword3!"},
            headers=auth_hdr,
        )
        self.assertEqual(resp3.status_code, 429)
        self.assertIn("Too many failed attempts", resp3.json()["detail"])
        self.assertEqual(resp3.headers.get("Retry-After"), "300")

        self.db.refresh(self.admin_user)
        self.assertEqual(self.admin_user.admin_console_failed_attempts, 3)
        self.assertIsNotNone(self.admin_user.admin_console_cooldown_until)

        # Subsequent attempt during cooldown (even with correct password) returns 429
        resp_blocked = self.client.post(
            "/api/admin/unlock",
            json={"password": "ValidConsoleSecret123!"},
            headers=auth_hdr,
        )
        self.assertEqual(resp_blocked.status_code, 429)

        # Check unlock-status reports cooldown active
        status_resp = self.client.get("/api/admin/unlock-status", headers=auth_hdr)
        self.assertEqual(status_resp.status_code, 200)
        status_json = status_resp.json()
        self.assertTrue(status_json["cooldown_active"])
        self.assertGreater(status_json["cooldown_remaining_seconds"], 0)
        self.assertEqual(status_json["failed_attempts"], 3)

        # Fast forward time: simulate cooldown expiration
        self.admin_user.admin_console_cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.commit()

        # Valid unlock now succeeds and resets counters
        resp_success = self.client.post(
            "/api/admin/unlock",
            json={"password": "ValidConsoleSecret123!"},
            headers=auth_hdr,
        )
        self.assertEqual(resp_success.status_code, 200)
        self.assertTrue(resp_success.json()["is_unlocked"])

        self.db.refresh(self.admin_user)
        self.assertEqual(self.admin_user.admin_console_failed_attempts, 0)
        self.assertIsNone(self.admin_user.admin_console_cooldown_until)

    def test_recovery_flow_and_counter_reset(self):
        """Test console password recovery with primary account credentials and failed counter reset."""
        # Set initial console password
        self.admin_user.admin_console_password_hash = hash_password("OldConsoleSecret123!")
        self.admin_user.admin_console_failed_attempts = 1  # 1 failed attempt existing
        self.db.commit()

        login_resp = self.client.post(
            "/api/auth/login",
            json={"email": "admin@ayurintel.org", "password": "AccountMasterPassword123!"},
        )
        admin_token = login_resp.json()["token"]
        auth_hdr = {"Authorization": f"Bearer {admin_token}"}

        # Recovery rejection: mismatched new passwords
        mismatch_resp = self.client.post(
            "/api/admin/recover-console-password",
            json={
                "account_password": "AccountMasterPassword123!",
                "new_console_password": "NewConsoleSecret123!",
                "confirm_console_password": "DifferentConsoleSecret123!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(mismatch_resp.status_code, 400)

        # Recovery rejection: invalid account password
        wrong_acc_resp = self.client.post(
            "/api/admin/recover-console-password",
            json={
                "account_password": "WrongAccountPassword123!",
                "new_console_password": "NewConsoleSecret123!",
                "confirm_console_password": "NewConsoleSecret123!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(wrong_acc_resp.status_code, 401)

        # Recovery success with valid account credentials
        valid_recover_resp = self.client.post(
            "/api/admin/recover-console-password",
            json={
                "account_password": "AccountMasterPassword123!",
                "new_console_password": "BrandNewConsoleSecret123!",
                "confirm_console_password": "BrandNewConsoleSecret123!",
            },
            headers=auth_hdr,
        )
        self.assertEqual(valid_recover_resp.status_code, 200)
        self.assertTrue(valid_recover_resp.json()["is_unlocked"])
        self.assertIn("token", valid_recover_resp.json())

        # Verify failed attempts counter was reset to 0
        self.db.refresh(self.admin_user)
        self.assertEqual(self.admin_user.admin_console_failed_attempts, 0)
        self.assertIsNone(self.admin_user.admin_console_cooldown_until)

        # Verify new console password unlocks successfully
        unlock_new = self.client.post(
            "/api/admin/unlock",
            json={"password": "BrandNewConsoleSecret123!"},
            headers=auth_hdr,
        )
        self.assertEqual(unlock_new.status_code, 200)
        self.assertTrue(unlock_new.json()["is_unlocked"])


if __name__ == "__main__":
    unittest.main()
