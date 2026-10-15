"""AYUR-INTEL — Phase 1 Schema & Model Verification Tests.

Verifies:
1. User model has persistent `role` defaulting to 'user'.
2. User model has persistent `token_version` defaulting to 1.
3. UserSession model has unique public_id, user_id, client context, revocation status, timestamps.
4. User <-> UserSession cascade and relationship integrity.
5. Base.metadata.create_all() creates user_sessions table in isolated in-memory SQLite.
6. Additive migration simulation works cleanly.
7. user_to_dict includes role.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.models
from api.models.models import Base, User
from api.models.security import UserSession
from api.services.auth_service import user_to_dict


class TestPhase1Models(unittest.TestCase):
    """Test suite for Phase 1 Schema and Model changes."""

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

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_user_session_table_created(self):
        """Verify user_sessions table is discovered and created by Base.metadata.create_all()."""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        self.assertIn("user_sessions", tables)
        self.assertIn("users", tables)

        columns = {c["name"]: c for c in inspector.get_columns("user_sessions")}
        self.assertIn("id", columns)
        self.assertIn("public_id", columns)
        self.assertIn("user_id", columns)
        self.assertIn("ip_address", columns)
        self.assertIn("user_agent", columns)
        self.assertIn("device_info", columns)
        self.assertIn("is_revoked", columns)
        self.assertIn("created_at", columns)
        self.assertIn("last_active_at", columns)
        self.assertIn("expires_at", columns)

    def test_user_model_role_and_token_version_defaults(self):
        """Verify User model defaults role to 'user' and token_version to 1."""
        user = User(
            username="test_researcher",
            display_name="Test Researcher",
            email="researcher@ayurintel.org",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        self.assertEqual(user.role, "user")
        self.assertEqual(user.token_version, 1)
        self.assertTrue(user.is_active)

        # Verify user_to_dict includes role
        data = user_to_dict(user)
        self.assertIn("role", data)
        self.assertEqual(data["role"], "user")

    def test_user_session_lifecycle_and_cascade(self):
        """Verify UserSession creation, defaults, relationship, and cascade delete."""
        user = User(
            username="dr_vaidya",
            display_name="Dr. Vaidya",
            email="vaidya@ayurintel.org",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=1)
        session = UserSession(
            user_id=user.id,
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            device_info="Chrome on Windows",
            expires_at=expires,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        self.assertIsNotNone(session.public_id)
        self.assertEqual(len(session.public_id), 12)
        self.assertFalse(session.is_revoked)
        self.assertEqual(session.user_id, user.id)
        self.assertEqual(session.user.username, "dr_vaidya")

        # Verify reverse relationship
        self.assertEqual(len(user.sessions), 1)
        self.assertEqual(user.sessions[0].public_id, session.public_id)

        # Verify cascade delete: deleting user deletes their sessions
        self.db.delete(user)
        self.db.commit()

        remaining_sessions = self.db.query(UserSession).filter(UserSession.user_id == user.id).all()
        self.assertEqual(len(remaining_sessions), 0)

    def test_simulated_additive_migration(self):
        """Verify additive migration SQL alters existing table without errors."""
        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # Create a bare users table simulating an older version before role and token_version
        with test_engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE test_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(100) NOT NULL,
                    email VARCHAR(200)
                )
            """))
            conn.execute(text("INSERT INTO test_users (username, email) VALUES ('legacy_user', 'legacy@ayur.org')"))

        # Run additive migration pattern from init_db
        with test_engine.begin() as conn:
            conn.execute(text("ALTER TABLE test_users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
            conn.execute(text("ALTER TABLE test_users ADD COLUMN token_version INTEGER DEFAULT 1"))

        with test_engine.connect() as conn:
            row = conn.execute(text("SELECT username, role, token_version FROM test_users WHERE username = 'legacy_user'")).fetchone()
            self.assertEqual(row[0], "legacy_user")
            self.assertEqual(row[1], "user")
            self.assertEqual(row[2], 1)


if __name__ == "__main__":
    unittest.main()
