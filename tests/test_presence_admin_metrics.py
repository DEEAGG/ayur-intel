"""Tests for Admin Console presence tracking, online-first ordering, session durations, and metrics.

Covers:
- Online users appearing before offline users.
- Secondary ordering by most recently active.
- Accurate session duration calculation for active and ended sessions.
- Inactive, expired, and revoked sessions correctly marked offline.
- Multi-session user presence resolution.
- Safe fallbacks for users with missing historical data.
- /api/admin/metrics endpoint security and accuracy.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from typing import Generator

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.database import get_db
from api.models.models import Base, User
from api.models.security import UserSession
from api.routers import admin, auth
from api.services.admin_service import get_admin_metrics, get_admin_users
from api.services.auth_service import hash_password, login_user
from tests.test_phase3a_admin import ApiClient


class TestPresenceAndAdminMetrics(unittest.TestCase):
    """Test suite for presence determination, ordering, durations, and metrics."""

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

        # Admin user
        self.admin = User(
            username="admin_vaidya",
            display_name="Admin Vaidya",
            email="admin@ayurintel.org",
            hashed_password=hash_password("AdminSecurePass123!"),
            role="admin",
            token_version=1,
            is_active=True,
        )
        self.db.add(self.admin)
        self.db.commit()

        login_resp = login_user(self.db, "admin@ayurintel.org", "AdminSecurePass123!")
        self.admin_token = login_resp["token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_online_users_appear_first_in_user_listing(self):
        """Users with valid active sessions must appear above offline users."""
        now = datetime.now(timezone.utc)

        # User 1: Offline (no session)
        u1 = User(username="user_offline_none", email="u1@ayur.org", hashed_password="h", is_active=True)
        # User 2: Online (active session)
        u2 = User(username="user_online_a", email="u2@ayur.org", hashed_password="h", is_active=True)
        # User 3: Offline (revoked session)
        u3 = User(username="user_offline_revoked", email="u3@ayur.org", hashed_password="h", is_active=True)
        # User 4: Online (active session, active recently)
        u4 = User(username="user_online_b", email="u4@ayur.org", hashed_password="h", is_active=True)

        self.db.add_all([u1, u2, u3, u4])
        self.db.commit()

        # Session for u2 (active, last active 10 min ago)
        s2 = UserSession(
            user_id=u2.id,
            is_revoked=False,
            created_at=now - timedelta(minutes=30),
            last_active_at=now - timedelta(minutes=10),
            expires_at=now + timedelta(hours=10),
            idle_timeout_seconds=1800,
            max_lifetime_seconds=43200,
        )
        # Session for u3 (revoked)
        s3 = UserSession(
            user_id=u3.id,
            is_revoked=True,
            created_at=now - timedelta(hours=2),
            last_active_at=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=8),
        )
        # Session for u4 (active, last active 2 min ago)
        s4 = UserSession(
            user_id=u4.id,
            is_revoked=False,
            created_at=now - timedelta(minutes=20),
            last_active_at=now - timedelta(minutes=2),
            expires_at=now + timedelta(hours=10),
            idle_timeout_seconds=1800,
            max_lifetime_seconds=43200,
        )
        self.db.add_all([s2, s3, s4])
        self.db.commit()

        resp = self.client.get("/api/admin/users", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        users = data["users"]

        # Filter out the admin user for clarity in assertion
        test_users = [u for u in users if u["username"].startswith("user_")]
        self.assertEqual(len(test_users), 4)

        # First 2 must be online: u4 then u2 (u4 was active 2 min ago, u2 10 min ago)
        self.assertTrue(test_users[0]["is_online"])
        self.assertEqual(test_users[0]["username"], "user_online_b")

        self.assertTrue(test_users[1]["is_online"])
        self.assertEqual(test_users[1]["username"], "user_online_a")

        # Next 2 must be offline
        self.assertFalse(test_users[2]["is_online"])
        self.assertFalse(test_users[3]["is_online"])

    def test_session_inactivity_timeout_marks_user_offline(self):
        """User whose idle timeout expired without explicit logout is treated as offline."""
        now = datetime.now(timezone.utc)
        u = User(username="idle_user", email="idle@ayur.org", hashed_password="h", is_active=True)
        self.db.add(u)
        self.db.commit()

        # Session last active 40 minutes ago with 30 min idle timeout
        s = UserSession(
            user_id=u.id,
            is_revoked=False,
            created_at=now - timedelta(hours=1),
            last_active_at=now - timedelta(minutes=40),
            expires_at=now + timedelta(hours=10),
            idle_timeout_seconds=1800,  # 30 min
            max_lifetime_seconds=43200,
        )
        self.db.add(s)
        self.db.commit()

        data = get_admin_users(self.db, query="idle_user")
        self.assertEqual(len(data["users"]), 1)
        user_res = data["users"][0]
        self.assertFalse(user_res["is_online"])
        self.assertEqual(user_res["active_sessions_count"], 0)

    def test_session_max_lifetime_timeout_marks_user_offline(self):
        """User whose session exceeded absolute max lifetime is treated as offline."""
        now = datetime.now(timezone.utc)
        u = User(username="max_life_user", email="maxlife@ayur.org", hashed_password="h", is_active=True)
        self.db.add(u)
        self.db.commit()

        # Session created 13 hours ago with 12 hour max lifetime
        s = UserSession(
            user_id=u.id,
            is_revoked=False,
            created_at=now - timedelta(hours=13),
            last_active_at=now - timedelta(minutes=5),  # recently active, but exceeded max lifetime!
            expires_at=now + timedelta(hours=5),
            idle_timeout_seconds=1800,
            max_lifetime_seconds=43200,  # 12h
        )
        self.db.add(s)
        self.db.commit()

        data = get_admin_users(self.db, query="max_life_user")
        self.assertEqual(len(data["users"]), 1)
        user_res = data["users"][0]
        self.assertFalse(user_res["is_online"])

    def test_session_durations_active_and_ended(self):
        """Active sessions calculate elapsed time from start; ended sessions calculate duration between start and end."""
        now = datetime.now(timezone.utc)

        # Online user (started 45 minutes ago)
        u_online = User(username="online_dur", email="on_dur@ayur.org", hashed_password="h", is_active=True)
        # Offline user (started 3 hours ago, ended 2 hours ago = 1 hour duration)
        u_offline = User(username="offline_dur", email="off_dur@ayur.org", hashed_password="h", is_active=True)
        # User with no sessions
        u_empty = User(username="empty_dur", email="empty_dur@ayur.org", hashed_password="h", is_active=True)

        self.db.add_all([u_online, u_offline, u_empty])
        self.db.commit()

        s_online = UserSession(
            user_id=u_online.id,
            is_revoked=False,
            created_at=now - timedelta(minutes=45),
            last_active_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=8),
            idle_timeout_seconds=1800,
            max_lifetime_seconds=43200,
        )
        s_offline = UserSession(
            user_id=u_offline.id,
            is_revoked=True,
            created_at=now - timedelta(hours=3),
            last_active_at=now - timedelta(hours=2),  # 60 min session duration
            expires_at=now + timedelta(hours=5),
        )
        self.db.add_all([s_online, s_offline])
        self.db.commit()

        # Check online user
        res_online = get_admin_users(self.db, query="online_dur")["users"][0]
        self.assertTrue(res_online["is_online"])
        self.assertIsNotNone(res_online["current_session_duration_seconds"])
        self.assertGreaterEqual(res_online["current_session_duration_seconds"], 45 * 60)
        self.assertLess(res_online["current_session_duration_seconds"], 46 * 60)
        self.assertIsNotNone(res_online["session_started_at"])

        # Check offline user
        res_offline = get_admin_users(self.db, query="offline_dur")["users"][0]
        self.assertFalse(res_offline["is_online"])
        self.assertIsNone(res_offline["current_session_duration_seconds"])
        self.assertIsNotNone(res_offline["last_session_duration_seconds"])
        # Expected around 3600 seconds (1 hour)
        self.assertAlmostEqual(res_offline["last_session_duration_seconds"], 3600, delta=5)

        # Check empty user
        res_empty = get_admin_users(self.db, query="empty_dur")["users"][0]
        self.assertFalse(res_empty["is_online"])
        self.assertIsNone(res_empty["last_opened_at"])
        self.assertIsNone(res_empty["last_session_duration_seconds"])
        self.assertIsNone(res_empty["current_session_duration_seconds"])

    def test_multi_session_user_presence(self):
        """User with 1 revoked session and 1 active session is online with active_sessions_count=1."""
        now = datetime.now(timezone.utc)
        u = User(username="multi_sess", email="multi@ayur.org", hashed_password="h", is_active=True)
        self.db.add(u)
        self.db.commit()

        s_revoked = UserSession(
            user_id=u.id,
            is_revoked=True,
            created_at=now - timedelta(days=1),
            last_active_at=now - timedelta(hours=20),
            expires_at=now + timedelta(hours=2),
        )
        s_active = UserSession(
            user_id=u.id,
            is_revoked=False,
            created_at=now - timedelta(minutes=15),
            last_active_at=now - timedelta(minutes=2),
            expires_at=now + timedelta(hours=6),
            idle_timeout_seconds=1800,
            max_lifetime_seconds=43200,
        )
        self.db.add_all([s_revoked, s_active])
        self.db.commit()

        res = get_admin_users(self.db, query="multi_sess")["users"][0]
        self.assertTrue(res["is_online"])
        self.assertEqual(res["active_sessions_count"], 1)

    def test_admin_metrics_endpoint(self):
        """GET /api/admin/metrics returns real presence and account totals."""
        now = datetime.now(timezone.utc)

        # Active user with online session
        u_on = User(username="u_metric_on", email="on@metric.org", hashed_password="h", is_active=True)
        # Deactivated user with revoked session
        u_off = User(username="u_metric_off", email="off@metric.org", hashed_password="h", is_active=False)

        self.db.add_all([u_on, u_off])
        self.db.commit()

        s_on = UserSession(
            user_id=u_on.id,
            is_revoked=False,
            created_at=now - timedelta(minutes=10),
            last_active_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=8),
            idle_timeout_seconds=1800,
            max_lifetime_seconds=43200,
        )
        self.db.add(s_on)
        self.db.commit()

        # Admin request
        resp = self.client.get("/api/admin/metrics", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        metrics = resp.json()

        self.assertIn("total_users", metrics)
        self.assertIn("online_users", metrics)
        self.assertIn("offline_users", metrics)
        self.assertIn("active_accounts", metrics)
        self.assertIn("deactivated_accounts", metrics)
        self.assertIn("total_active_sessions", metrics)

        # At least admin + u_on are online
        self.assertGreaterEqual(metrics["online_users"], 2)
        # At least u_off is deactivated
        self.assertGreaterEqual(metrics["deactivated_accounts"], 1)
        self.assertEqual(metrics["total_users"], metrics["active_accounts"] + metrics["deactivated_accounts"])

    def test_metrics_rejects_unauthenticated_and_non_admin(self):
        """Metrics route requires admin authentication."""
        # Unauthenticated -> 401
        r_unauth = self.client.get("/api/admin/metrics")
        self.assertEqual(r_unauth.status_code, 401)

        # Regular user -> 403
        reg = User(username="reg_user", email="reg@metric.org", hashed_password=hash_password("Pass123!"), role="user", is_active=True)
        self.db.add(reg)
        self.db.commit()
        reg_login = login_user(self.db, "reg@metric.org", "Pass123!")

        r_forbidden = self.client.get("/api/admin/metrics", headers={"Authorization": f"Bearer {reg_login['token']}"})
        self.assertEqual(r_forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main()
