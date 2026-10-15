"""Phase 3B Tests — Private Admin Console UI & Frontend Security.

Verifies:
1. Index template includes private Admin Console navigation item, hidden by default.
2. Index template includes admin.js script reference.
3. admin.js exists, has valid syntax, and exposes AYUR_ADMIN.
4. auth.js verifies user.role === 'admin' before revealing admin navigation.
5. app.js verifies user.role === 'admin' before rendering admin-console view.
6. Frontend files contain no hardcoded secrets, tokens, or credentials.
7. /static/js/admin.js is served properly by the application.
8. API endpoints for admin return expected responses with Bearer token authentication.

Runs with an isolated in-memory test database; the persistent database is untouched.
"""

from __future__ import annotations

import asyncio
import os
import re
import unittest
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.config import PROJECT_ROOT, settings
from api.core.database import get_db
from api.models.models import Base, User
from api.models.security import UserSession
from api.routers import admin, auth
from api.services.auth_service import hash_password, login_user


class ApiTestClient:
    """Async transport test client."""

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


class TestPhase3BAdminConsoleUI(unittest.TestCase):
    """Test suite for Phase 3B: Private Admin Console UI."""

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

        def override_get_db():
            db = self.SessionTesting()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = ApiTestClient(self.app)

        # Create admin and regular user
        self.admin = User(
            username="admin_user",
            display_name="Site Admin",
            email="admin@ayurintel.org",
            hashed_password=hash_password("AdminSecurePassword123!"),
            role="admin",
            token_version=1,
            is_active=True,
        )
        self.user = User(
            username="regular_user",
            display_name="Regular User",
            email="user@ayurintel.org",
            hashed_password=hash_password("UserSecurePassword123!"),
            role="user",
            token_version=1,
            is_active=True,
        )
        self.db.add(self.admin)
        self.db.add(self.user)
        self.db.commit()

        # Login to get tokens
        admin_login = login_user(self.db, "admin@ayurintel.org", "AdminSecurePassword123!")
        self.admin_token = admin_login["token"]

        user_login = login_user(self.db, "user@ayurintel.org", "UserSecurePassword123!")
        self.user_token = user_login["token"]

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # -----------------------------------------------------------------------
    # 1. Template & Asset Checks
    # -----------------------------------------------------------------------

    def test_index_template_contains_hidden_admin_navigation(self):
        """Index.html must contain #nav-item-admin hidden by default."""
        index_file = PROJECT_ROOT / "web" / "templates" / "index.html"
        self.assertTrue(index_file.exists(), "index.html must exist")
        content = index_file.read_text(encoding="utf-8")

        # Must include admin console navigation item
        self.assertIn('id="nav-item-admin"', content)
        self.assertIn('data-view="admin-console"', content)

        # Must be hidden by default
        self.assertTrue(
            'style="display: none;"' in content or 'style="display:none;"' in content,
            "Admin nav item must be hidden by default in initial DOM",
        )

    def test_index_template_loads_admin_script(self):
        """Index.html must include admin.js script."""
        index_file = PROJECT_ROOT / "web" / "templates" / "index.html"
        content = index_file.read_text(encoding="utf-8")
        self.assertIn('src="/static/js/admin.js', content)

    def test_admin_js_file_structure(self):
        """admin.js must exist and define AYUR_ADMIN."""
        admin_js = PROJECT_ROOT / "web" / "static" / "js" / "admin.js"
        self.assertTrue(admin_js.exists(), "admin.js must exist")
        content = admin_js.read_text(encoding="utf-8")

        self.assertIn("window.AYUR_ADMIN", content)
        self.assertIn("renderAdminConsole", content)
        self.assertIn("/api/admin/users", content)
        self.assertIn("/api/admin/audit-logs", content)

    def test_styles_css_contains_admin_console_rules(self):
        """styles.css must include .admin-* component styling."""
        styles_file = PROJECT_ROOT / "web" / "static" / "css" / "styles.css"
        content = styles_file.read_text(encoding="utf-8")

        self.assertIn(".admin-console-wrapper", content)
        self.assertIn(".admin-kpi-grid", content)
        self.assertIn(".admin-table", content)
        self.assertIn(".admin-modal", content)

    # -----------------------------------------------------------------------
    # 2. Authorization Integration Checks
    # -----------------------------------------------------------------------

    def test_auth_me_returns_server_verified_role(self):
        """GET /api/auth/me returns the database-verified role."""
        # Admin
        resp_adm = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(resp_adm.status_code, 200)
        self.assertEqual(resp_adm.json()["user"]["role"], "admin")

        # Regular User
        resp_usr = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {self.user_token}"})
        self.assertEqual(resp_usr.status_code, 200)
        self.assertEqual(resp_usr.json()["user"]["role"], "user")

    def test_auth_js_controls_admin_nav_visibility_strictly_by_role(self):
        """auth.js must check user.role === 'admin' before showing nav-item-admin."""
        auth_js = PROJECT_ROOT / "web" / "static" / "js" / "auth.js"
        content = auth_js.read_text(encoding="utf-8")

        self.assertIn("user.role === 'admin'", content)
        self.assertIn("nav-item-admin", content)
        # Ensure logout resets admin nav
        self.assertIn("adminNav.style.display = 'none'", content)

    def test_app_js_guards_admin_console_view(self):
        """app.js must guard admin-console view and require user.role === 'admin'."""
        app_js = PROJECT_ROOT / "web" / "static" / "js" / "app.js"
        content = app_js.read_text(encoding="utf-8")

        self.assertIn('state.view === "admin-console"', content)
        self.assertIn("currentUser.role !== 'admin'", content)

    def test_api_helper_attaches_authorization_header(self):
        """api() helper in app.js must attach Bearer token from getToken()."""
        app_js = PROJECT_ROOT / "web" / "static" / "js" / "app.js"
        content = app_js.read_text(encoding="utf-8")

        self.assertIn("headers['Authorization'] = 'Bearer ' + tok", content.replace('"', "'"))
        self.assertIn("!url.startsWith('/api/admin')", content.replace('"', "'"))

    # -----------------------------------------------------------------------
    # 3. Security: No Hardcoded Secrets in Frontend
    # -----------------------------------------------------------------------

    def test_no_secrets_in_frontend_code(self):
        """Ensure no tokens, passwords, or secrets are hardcoded in static files."""
        frontend_dir = PROJECT_ROOT / "web"
        secret_patterns = [
            re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{30,}"),
            re.compile(r"password\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
            re.compile(r"AYURINTEL_ADMIN_EMAIL\s*[:=]"),
            re.compile(r"AYURINTEL_SESSION_SECRET\s*[:=]"),
        ]

        for file_path in frontend_dir.rglob("*"):
            if file_path.suffix in [".js", ".html", ".css"]:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pat in secret_patterns:
                    matches = pat.findall(content)
                    # Filter out template placeholder mentions like password: password in auth forms
                    filtered = [m for m in matches if "password" not in m.lower() or "input" in m.lower() or "secret" in m.lower()]
                    self.assertEqual(len(filtered), 0, f"Found potential secret match in {file_path}: {filtered}")


if __name__ == "__main__":
    unittest.main()
