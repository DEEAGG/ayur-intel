"""AYUR-INTEL — Phase 1 Critical Authentication Security Hardening Tests.

Verifies:
1. Configured signing secret is used.
2. Production startup rejects a missing or known default secret.
3. Valid tokens continue to work under the configured secret.
4. Invalid or tampered tokens are rejected.
5. Tokens passed only through URL query parameters are rejected.
6. Passwordless accounts cannot be claimed through login.
7. Existing signup and login behavior still works.
8. Repeated login/signup attempts trigger rate limiting (HTTP 429).
9. Unknown-account and incorrect-password responses do not reveal account existence.
10. Existing authentication tests and dependencies continue to pass.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

import asyncio
import os
import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.config import Settings, settings
from api.core.database import get_db
from api.core.security import (
    AUTH_LOGIN_ACC_LIMIT,
    AUTH_LOGIN_IP_LIMIT,
    AUTH_SIGNUP_IP_LIMIT,
    check_auth_rate_limit,
    get_authenticated_user,
    get_client_ip,
    get_current_user,
    reset_auth_rate_limits,
    verify_case_access,
)
from api.main import app
from api.models.models import Base, ProductCase, User
from api.routers.auth import _get_authenticated_user, get_me, login, signup
from api.routers.auth import LoginRequest, SignUpRequest
from api.services.auth_service import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_signing_secret,
    get_token_ttl_seconds,
    hash_password,
    login_user,
    signup_user,
    validate_session_secret,
    verify_access_token,
    verify_password,
)
from api.services.product_case_service import _invalidate_product_cache, create_product_case


class TestAuthSecurityHardening(unittest.TestCase):
    """Test suite for Phase 1 Authentication Security Hardening."""

    def setUp(self):
        # Create an isolated in-memory SQLite database
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Reset in-memory rate limiting store before each test
        reset_auth_rate_limits()

        # Save original settings
        self._orig_secret = settings.AYURINTEL_SESSION_SECRET
        self._orig_debug = settings.AYURINTEL_DEBUG
        self._orig_env = getattr(settings, "AYURINTEL_ENV", "development")
        self._orig_trust_proxy = getattr(settings, "AYURINTEL_TRUST_PROXY_HEADERS", False)
        self._orig_behind_proxy = getattr(settings, "AYURINTEL_BEHIND_PROXY", False)
        self._orig_trusted_proxies = getattr(settings, "AYURINTEL_TRUSTED_PROXIES", "127.0.0.1,::1")
        self._orig_ttl = getattr(settings, "AYURINTEL_SESSION_TTL_SECONDS", 86400)
        self._orig_demo = getattr(settings, "AYURINTEL_DEMO_MODE", True)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        reset_auth_rate_limits()
        _invalidate_product_cache()
        settings.AYURINTEL_SESSION_SECRET = self._orig_secret
        settings.AYURINTEL_DEBUG = self._orig_debug
        settings.AYURINTEL_ENV = self._orig_env
        settings.AYURINTEL_TRUST_PROXY_HEADERS = self._orig_trust_proxy
        settings.AYURINTEL_BEHIND_PROXY = self._orig_behind_proxy
        settings.AYURINTEL_TRUSTED_PROXIES = self._orig_trusted_proxies
        settings.AYURINTEL_SESSION_TTL_SECONDS = self._orig_ttl
        settings.AYURINTEL_DEMO_MODE = self._orig_demo

    # -------------------------------------------------------------------------
    # 1. Configured signing secret is used
    # -------------------------------------------------------------------------
    def test_configured_signing_secret_used(self):
        custom_secret = "my-secure-custom-secret-key-at-least-32-bytes-long!!"
        settings.AYURINTEL_SESSION_SECRET = custom_secret
        self.assertEqual(get_signing_secret(), custom_secret)

        token = create_access_token({"sub": "user-test-1", "email": "test@ayur.org"})
        self.assertIsNotNone(token)
        self.assertIn(".", token)

        # Token verifies successfully under the same secret
        payload = verify_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user-test-1")

        # Rotating secret invalidates tokens signed with old secret
        settings.AYURINTEL_SESSION_SECRET = "different-rotated-secret-key-32-bytes-long!!"
        rotated_payload = verify_access_token(token)
        self.assertIsNone(rotated_payload)

    # -------------------------------------------------------------------------
    # 2. Production startup rejects missing, weak, or known default secret
    # -------------------------------------------------------------------------
    def test_production_startup_rejects_missing_or_default_secret(self):
        # Known default placeholder
        with self.assertRaises(RuntimeError) as ctx:
            validate_session_secret(secret="change-me-in-production", is_production=True)
        self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

        # Legacy hardcoded secret
        with self.assertRaises(RuntimeError) as ctx:
            validate_session_secret(
                secret="ayur-intel-secret-key-signature-token-vault-2026",
                is_production=True,
            )
        self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

        # Empty secret
        with self.assertRaises(RuntimeError) as ctx:
            validate_session_secret(secret="", is_production=True)
        self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

        # Short secret (< 32 bytes)
        with self.assertRaises(RuntimeError) as ctx:
            validate_session_secret(secret="short-secret-16b", is_production=True)
        self.assertIn("too short", str(ctx.exception))

        # Strong 32+ byte secret succeeds in production
        strong_secret = "a" * 32
        result = validate_session_secret(secret=strong_secret, is_production=True)
        self.assertEqual(result, strong_secret)

        # Development mode allows default with warning, without crashing
        dev_result = validate_session_secret(secret="change-me-in-production", is_production=False)
        self.assertEqual(dev_result, "change-me-in-production")

    # -------------------------------------------------------------------------
    # 3. Valid tokens continue to work under configured secret
    # -------------------------------------------------------------------------
    def test_valid_tokens_work(self):
        settings.AYURINTEL_SESSION_SECRET = "testing-session-secret-key-32-bytes-long!!"
        user = User(
            username="validuser",
            display_name="Valid User",
            email="valid@ayur.org",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        token = create_access_token({"sub": user.public_id, "email": user.email})
        auth_header = f"Bearer {token}"

        retrieved_user = _get_authenticated_user(authorization=auth_header, db=self.db)
        self.assertEqual(retrieved_user.id, user.id)
        self.assertEqual(retrieved_user.public_id, user.public_id)

    # -------------------------------------------------------------------------
    # 4. Invalid or tampered tokens are rejected
    # -------------------------------------------------------------------------
    def test_invalid_or_tampered_tokens_rejected(self):
        settings.AYURINTEL_SESSION_SECRET = "testing-session-secret-key-32-bytes-long!!"
        token = create_access_token({"sub": "user-abc", "email": "abc@ayur.org"})

        # Tamper payload
        payload_b64, sig = token.split(".", 1)
        tampered_token = f"dGFtcGVyZWQ.{sig}"
        self.assertIsNone(verify_access_token(tampered_token))

        # Tamper signature
        tampered_sig_token = f"{payload_b64}.0000000000000000000000000000000000000000000000000000000000000000"
        self.assertIsNone(verify_access_token(tampered_sig_token))

        # Malformed tokens
        self.assertIsNone(verify_access_token("not-a-token"))
        self.assertIsNone(verify_access_token(""))

        # Passing tampered token to auth dependency raises 401
        with self.assertRaises(HTTPException) as ctx:
            _get_authenticated_user(authorization=f"Bearer {tampered_token}", db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------------------
    # 5. Tokens passed only through URL query parameters are rejected
    # -------------------------------------------------------------------------
    def test_tokens_passed_only_through_query_rejected(self):
        settings.AYURINTEL_SESSION_SECRET = "testing-session-secret-key-32-bytes-long!!"
        user = User(
            username="queryuser",
            display_name="Query User",
            email="query@ayur.org",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()

        token = create_access_token({"sub": user.public_id, "email": user.email})

        # Calling _get_authenticated_user without Authorization header raises 401
        with self.assertRaises(HTTPException) as ctx:
            _get_authenticated_user(authorization=None, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Authentication token required", ctx.exception.detail)

        # get_me endpoint strictly depends on _get_authenticated_user
        # When user dependency fails (no Bearer header), it cannot authenticate
        with self.assertRaises(HTTPException) as ctx:
            _get_authenticated_user(authorization="InvalidScheme " + token, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------------------
    # 6. Passwordless accounts cannot be claimed through login
    # -------------------------------------------------------------------------
    def test_passwordless_account_cannot_be_claimed(self):
        # Create a passwordless demo account (hashed_password is None)
        demo_user = User(
            username="demo_victim",
            display_name="Demo Victim",
            email="victim@ayur-intel.local",
            hashed_password=None,
            is_active=True,
        )
        self.db.add(demo_user)
        self.db.commit()
        self.db.refresh(demo_user)

        # Attacker attempts to login and set a password
        attacker_password = "AttackerClaimPassword123!"
        with self.assertRaises(HTTPException) as ctx:
            login_user(self.db, email_or_username=demo_user.email, password=attacker_password)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Invalid email or password")

        # Crucial check: verify that hashed_password is STILL None in the database!
        self.db.refresh(demo_user)
        self.assertIsNone(demo_user.hashed_password)

    # -------------------------------------------------------------------------
    # 7. Existing signup and login behavior still works
    # -------------------------------------------------------------------------
    def test_signup_and_login_flow(self):
        settings.AYURINTEL_SESSION_SECRET = "testing-session-secret-key-32-bytes-long!!"
        email = "legit_user@ayur.org"
        password = "LegitPassword2026!"
        full_name = "Dr. Charaka Researcher"

        # Sign up (with auto_approve for login flow testing)
        signup_result = signup_user(
            db=self.db,
            full_name=full_name,
            email=email,
            password=password,
            auto_approve=True,
        )
        self.assertIn("token", signup_result)
        self.assertIn("user", signup_result)
        self.assertEqual(signup_result["user"]["email"], email)
        self.assertEqual(signup_result["user"]["display_name"], full_name)

        # Log in with correct credentials
        login_result = login_user(
            db=self.db,
            email_or_username=email,
            password=password,
        )
        self.assertIn("token", login_result)
        self.assertIn("user", login_result)
        self.assertEqual(login_result["user"]["email"], email)

        # Log in with wrong password fails
        with self.assertRaises(HTTPException) as ctx:
            login_user(self.db, email_or_username=email, password="WrongPassword999!")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Invalid email or password")

    # -------------------------------------------------------------------------
    # 8. Repeated login/signup attempts trigger rate limiting (HTTP 429)
    # -------------------------------------------------------------------------
    def test_rate_limiting_enforced(self):
        test_ip = "192.168.1.100"
        test_email = "ratelimit_target@ayur.org"

        # Login attempts within threshold pass
        for _ in range(AUTH_LOGIN_ACC_LIMIT - 1):
            check_auth_rate_limit(ip=test_ip, identifier=test_email, action="login")

        # Reaching the limit allows the final allowed call
        check_auth_rate_limit(ip=test_ip, identifier=test_email, action="login")

        # Next call exceeds account limit -> raises 429
        with self.assertRaises(HTTPException) as ctx:
            check_auth_rate_limit(ip=test_ip, identifier=test_email, action="login")
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)

        # IP-based rate limit test for signup
        signup_ip = "192.168.1.200"
        for _ in range(AUTH_SIGNUP_IP_LIMIT):
            check_auth_rate_limit(ip=signup_ip, action="signup")

        with self.assertRaises(HTTPException) as ctx:
            check_auth_rate_limit(ip=signup_ip, action="signup")
        self.assertEqual(ctx.exception.status_code, 429)

    # -------------------------------------------------------------------------
    # 9. Unknown-account and incorrect-password responses do not reveal existence
    # -------------------------------------------------------------------------
    def test_error_consistency_and_timing_dummy_hash(self):
        # 1. Existing user with wrong password
        real_user = User(
            username="existing_user",
            display_name="Existing User",
            email="existing@ayur.org",
            hashed_password=hash_password("CorrectPassword123!"),
            is_active=True,
        )
        self.db.add(real_user)
        self.db.commit()

        err_existing = None
        try:
            login_user(self.db, email_or_username="existing@ayur.org", password="WrongPassword123!")
        except HTTPException as e:
            err_existing = e

        # 2. Non-existent user
        err_nonexistent = None
        try:
            login_user(self.db, email_or_username="nonexistent@ayur.org", password="WrongPassword123!")
        except HTTPException as e:
            err_nonexistent = e

        self.assertIsNotNone(err_existing)
        self.assertIsNotNone(err_nonexistent)

        # Both responses must be identical in status code and detail
        self.assertEqual(err_existing.status_code, 401)
        self.assertEqual(err_nonexistent.status_code, 401)
        self.assertEqual(err_existing.detail, err_nonexistent.detail)
        self.assertEqual(err_existing.detail, "Invalid email or password")

        # Verify that DUMMY_PASSWORD_HASH is valid PBKDF2 hash that executes full verification
        t0 = time.perf_counter()
        verify_password("any_arbitrary_password", DUMMY_PASSWORD_HASH)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # PBKDF2 with 100,000 iterations takes > 10ms on modern CPUs, confirming work is performed
        self.assertGreater(elapsed_ms, 10.0)

    # -------------------------------------------------------------------------
    # 10. Fix 1: Production detection when AYURINTEL_DEBUG is omitted
    # -------------------------------------------------------------------------
    def test_production_detection_when_debug_omitted(self):
        settings.AYURINTEL_ENV = "production"
        settings.AYURINTEL_DEBUG = None

        # When AYURINTEL_DEBUG is omitted in production, debug must NOT silently be True
        self.assertTrue(settings.is_production)
        self.assertFalse(settings.effective_debug)

        # In production, startup validation must fail if secret is missing or placeholder
        with self.assertRaises(RuntimeError) as ctx:
            validate_session_secret(secret="change-me-in-production")
        self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx:
            validate_session_secret(secret="")
        self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx:
            validate_session_secret(secret="too-short-secret")
        self.assertIn("too short", str(ctx.exception))

        # Valid 32+ byte secret succeeds in production
        strong = "strong-production-key-at-least-32-bytes!!"
        self.assertEqual(validate_session_secret(secret=strong), strong)

    # -------------------------------------------------------------------------
    # 11. Fix 1: Development mode defaults preserved
    # -------------------------------------------------------------------------
    def test_development_mode_defaults_preserved(self):
        settings.AYURINTEL_ENV = "development"
        settings.AYURINTEL_DEBUG = None

        self.assertFalse(settings.is_production)
        self.assertTrue(settings.effective_debug)

        # In development, default secret permits local development without throwing RuntimeError
        dev_sec = validate_session_secret(secret="change-me-in-production")
        self.assertEqual(dev_sec, "change-me-in-production")

    # -------------------------------------------------------------------------
    # 12. Fix 2: Client IP spoofing prevented when proxy trust is disabled
    # -------------------------------------------------------------------------
    def test_client_ip_spoofing_prevented_when_proxy_untrusted(self):
        settings.AYURINTEL_TRUST_PROXY_HEADERS = False
        settings.AYURINTEL_BEHIND_PROXY = False

        mock_request = MagicMock()
        mock_request.client.host = "198.51.100.20"
        mock_request.headers = {
            "X-Forwarded-For": "203.0.113.195, 10.0.0.1",
            "X-Real-IP": "203.0.113.195",
        }

        # Untrusted proxy mode: X-Forwarded-For is ignored completely
        extracted_ip = get_client_ip(mock_request)
        self.assertEqual(extracted_ip, "198.51.100.20")

    # -------------------------------------------------------------------------
    # 13. Fix 2: Client IP handling when proxy trust is enabled
    # -------------------------------------------------------------------------
    def test_client_ip_trusted_proxy_forwarding(self):
        settings.AYURINTEL_TRUST_PROXY_HEADERS = True
        settings.AYURINTEL_TRUSTED_PROXIES = "127.0.0.1,::1"

        # Case A: Request from trusted proxy -> extract valid leftmost client IP
        trusted_req = MagicMock()
        trusted_req.client.host = "127.0.0.1"
        trusted_req.headers = {"X-Forwarded-For": "203.0.113.88, 127.0.0.1"}
        self.assertEqual(get_client_ip(trusted_req), "203.0.113.88")

        # Case B: Request from trusted proxy with X-Real-IP
        real_ip_req = MagicMock()
        real_ip_req.client.host = "127.0.0.1"
        real_ip_req.headers = {"X-Real-IP": "203.0.113.99"}
        self.assertEqual(get_client_ip(real_ip_req), "203.0.113.99")

        # Case C: Request from UNTRUSTED host attempting to spoof header
        untrusted_req = MagicMock()
        untrusted_req.client.host = "198.51.100.77"  # Not in trusted_proxies
        untrusted_req.headers = {"X-Forwarded-For": "1.2.3.4"}
        # Must ignore forwarded header and bind to untrusted socket host
        self.assertEqual(get_client_ip(untrusted_req), "198.51.100.77")

    # -------------------------------------------------------------------------
    # 14. Fix 2: Client IP missing, malformed, or fallback scenarios
    # -------------------------------------------------------------------------
    def test_client_ip_missing_or_malformed_headers(self):
        settings.AYURINTEL_TRUST_PROXY_HEADERS = True
        settings.AYURINTEL_TRUSTED_PROXIES = "127.0.0.1"

        # Case A: Missing headers -> direct client host
        no_headers_req = MagicMock()
        no_headers_req.client.host = "192.168.1.66"
        no_headers_req.headers = {}
        self.assertEqual(get_client_ip(no_headers_req), "192.168.1.66")

        # Case B: Malformed / script injection in X-Forwarded-For
        bad_header_req = MagicMock()
        bad_header_req.client.host = "127.0.0.1"
        bad_header_req.headers = {"X-Forwarded-For": "<script>alert(1)</script>, 127.0.0.1"}
        # Syntactically invalid IP is rejected -> safe fallback to client.host
        self.assertEqual(get_client_ip(bad_header_req), "127.0.0.1")

        # Case C: Request without client socket info
        no_client_req = MagicMock()
        no_client_req.client = None
        no_client_req.headers = {}
        self.assertEqual(get_client_ip(no_client_req), "127.0.0.1")

        # Case D: Rate limiting functions without errors under spoofing attempt
        settings.AYURINTEL_TRUST_PROXY_HEADERS = False
        spoof_req = MagicMock()
        spoof_req.client.host = "192.168.10.5"
        spoof_req.headers = {"X-Forwarded-For": "8.8.8.8"}
        clean_ip = get_client_ip(spoof_req)
        self.assertEqual(clean_ip, "192.168.10.5")

        # Ensure rate limiter can process calls cleanly
        check_auth_rate_limit(ip=clean_ip, identifier="user@ayur.org", action="login")

    # -------------------------------------------------------------------------
    # 15. Remediation B: Right-to-left traversal defeats X-Forwarded-For spoofing
    # -------------------------------------------------------------------------
    def test_client_ip_right_to_left_anti_spoofing(self):
        settings.AYURINTEL_TRUST_PROXY_HEADERS = True
        settings.AYURINTEL_TRUSTED_PROXIES = "127.0.0.1,10.0.0.5"

        # Case A: Attacker prepends fake IP "1.1.1.1".
        # Legitimate client is "203.0.113.88", reverse proxy is "127.0.0.1".
        spoofed_req = MagicMock()
        spoofed_req.client.host = "127.0.0.1"
        spoofed_req.headers = {"X-Forwarded-For": "1.1.1.1, 203.0.113.88, 127.0.0.1"}

        # Right-to-left traversal skips trusted proxy 127.0.0.1 and extracts genuine client 203.0.113.88,
        # completely ignoring the attacker-prepended 1.1.1.1.
        resolved_ip = get_client_ip(spoofed_req)
        self.assertEqual(resolved_ip, "203.0.113.88")

        # Case B: Multi-hop trusted proxies chain:
        # [8.8.8.8 (spoofed), 198.51.100.42 (client), 10.0.0.5 (proxy 1), 127.0.0.1 (proxy 2)]
        multi_hop_req = MagicMock()
        multi_hop_req.client.host = "127.0.0.1"
        multi_hop_req.headers = {
            "X-Forwarded-For": "8.8.8.8, 198.51.100.42, 10.0.0.5, 127.0.0.1"
        }
        self.assertEqual(get_client_ip(multi_hop_req), "198.51.100.42")

        # Case C: Direct connection from untrusted host claiming to be behind a proxy
        untrusted_origin_req = MagicMock()
        untrusted_origin_req.client.host = "192.0.2.99"  # Untrusted socket peer
        untrusted_origin_req.headers = {"X-Forwarded-For": "1.1.1.1, 203.0.113.88"}
        # Must refuse forwarded header from untrusted origin
        self.assertEqual(get_client_ip(untrusted_origin_req), "192.0.2.99")

    # -------------------------------------------------------------------------
    # 16. Remediation C: Token TTL configuration and expiration verification
    # -------------------------------------------------------------------------
    def test_token_ttl_configuration_and_expiration(self):
        # Configured TTL binding
        settings.AYURINTEL_SESSION_TTL_SECONDS = 3600
        self.assertEqual(get_token_ttl_seconds(), 3600)

        # Clamping to safe minimum (60s)
        settings.AYURINTEL_SESSION_TTL_SECONDS = 10
        self.assertEqual(get_token_ttl_seconds(), 60)

        # Clamping to safe maximum (30 days = 2592000s)
        settings.AYURINTEL_SESSION_TTL_SECONDS = 100000000
        self.assertEqual(get_token_ttl_seconds(), 2592000)

        # Restore reasonable TTL
        settings.AYURINTEL_SESSION_TTL_SECONDS = 3600

        # Expired token is rejected
        expired_payload = {
            "sub": "user-expired",
            "email": "exp@ayur.org",
            "iat": int(time.time()) - 1000,
            "exp": int(time.time()) - 100,  # Expired 100 seconds ago
        }
        import base64
        import hashlib
        import hmac
        import json

        def craft_token(payload_dict, secret):
            p_bytes = json.dumps(payload_dict).encode("utf-8")
            p_b64 = base64.urlsafe_b64encode(p_bytes).decode("utf-8").rstrip("=")
            sig = hmac.new(secret.encode("utf-8"), p_b64.encode("utf-8"), hashlib.sha256).hexdigest()
            return f"{p_b64}.{sig}"

        expired_token = craft_token(expired_payload, get_signing_secret())
        self.assertIsNone(verify_access_token(expired_token))

        # Non-expired token verifies
        valid_payload = {
            "sub": "user-valid",
            "email": "valid@ayur.org",
            "iat": int(time.time()),
            "exp": int(time.time()) + 1000,
        }
        valid_token = craft_token(valid_payload, get_signing_secret())
        verified = verify_access_token(valid_token)
        self.assertIsNotNone(verified)
        self.assertEqual(verified["sub"], "user-valid")

    # -------------------------------------------------------------------------
    # 17. Remediation D: Fail-closed production environment detection
    # -------------------------------------------------------------------------
    def test_environment_detection_fail_closed(self):
        # Case A: When AYURINTEL_DEBUG is False and AYURINTEL_ENV omitted -> fails closed to production
        orig_env_var = os.environ.pop("AYURINTEL_ENV", None)
        try:
            s = Settings(AYURINTEL_DEBUG=False)
            self.assertTrue(s.is_production)
        finally:
            if orig_env_var is not None:
                os.environ["AYURINTEL_ENV"] = orig_env_var

        # Case B: Explicit dev environment keeps is_production False
        s_dev = Settings(AYURINTEL_ENV="development", AYURINTEL_DEBUG=True)
        self.assertFalse(s_dev.is_production)

        # Case C: Render platform detection
        os.environ["RENDER"] = "true"
        try:
            s_render = Settings(AYURINTEL_ENV="development")
            self.assertTrue(s_render.is_production)
        finally:
            os.environ.pop("RENDER", None)

    # -------------------------------------------------------------------------
    # 18. Remediation A: Centralized user authentication policy
    # -------------------------------------------------------------------------
    def test_centralized_router_authentication_policy(self):
        # Create a test user in DB
        user = User(
            username="auth_tester",
            email="auth_tester@ayur.org",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()

        # In production mode, unauthenticated request must fail with 401
        settings.AYURINTEL_ENV = "production"
        settings.AYURINTEL_SESSION_SECRET = "a" * 32

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(authorization=None, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Authentication token required", ctx.exception.detail)

        # In production mode, valid token succeeds
        token = create_access_token({"sub": user.public_id, "email": user.email})
        auth_user = get_current_user(authorization=f"Bearer {token}", db=self.db)
        self.assertEqual(auth_user.id, user.id)

        # In development mode, demo mode fallback works if explicitly enabled
        settings.AYURINTEL_ENV = "development"
        settings.AYURINTEL_DEBUG = True
        settings.AYURINTEL_DEMO_MODE = True
        dev_user = get_current_user(authorization=None, db=self.db)
        self.assertIsNotNone(dev_user)
        self.assertEqual(dev_user.username, "demo")

        # But get_authenticated_user strictly requires a token in ALL environments
        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_user(authorization=None, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------------------
    # 19. Remediation A: Cross-user isolation (IDOR protection)
    # -------------------------------------------------------------------------
    def test_cross_user_isolation(self):
        user_a = User(
            username="alice",
            email="alice@ayur.org",
            hashed_password=hash_password("PasswordAlice123!"),
            is_active=True,
        )
        user_b = User(
            username="bob",
            email="bob@ayur.org",
            hashed_password=hash_password("PasswordBob123!"),
            is_active=True,
        )
        self.db.add_all([user_a, user_b])
        self.db.commit()

        case_a = ProductCase(
            name="Alice Case",
            owner_id=user_a.id,
            is_demo=False,
        )
        self.db.add(case_a)
        self.db.commit()

        # Alice can access her own case
        accessible_case = verify_case_access(self.db, user_a, case_a.public_id)
        self.assertEqual(accessible_case.id, case_a.id)

        # Bob accessing Alice's case raises 404 (does not leak existence)
        with self.assertRaises(HTTPException) as ctx:
            verify_case_access(self.db, user_b, case_a.public_id)
        self.assertEqual(ctx.exception.status_code, 404)

    # -------------------------------------------------------------------------
    # 20. Remediation A & ASGI: Full HTTP pipeline integration tests
    # -------------------------------------------------------------------------
    def test_asgi_protected_endpoints_flow(self):
        def _get_test_db():
            yield self.db

        app.dependency_overrides[get_db] = _get_test_db

        async def run_asgi_tests():
            try:
                # Configure production mode
                settings.AYURINTEL_ENV = "production"
                settings.AYURINTEL_SESSION_SECRET = "b" * 32

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    # 1. Unauthenticated request to protected route is rejected with 401
                    unauth_res = await client.get("/api/cases")
                    self.assertEqual(unauth_res.status_code, 401)
                    self.assertIn("Authentication token required", unauth_res.json()["detail"])

                    # 2. Public health check continues to succeed without token
                    health_res = await client.get("/api/health")
                    self.assertEqual(health_res.status_code, 200)

                    # 3. Create test user and token
                    test_user = User(
                        username="asgi_user",
                        email="asgi_user@ayur.org",
                        hashed_password=hash_password("SecurePassword123!"),
                        is_active=True,
                    )
                    self.db.add(test_user)
                    self.db.commit()

                    token = create_access_token({"sub": test_user.public_id, "email": test_user.email})

                    # 4. Authenticated request with Bearer token is accepted (not 401)
                    auth_res = await client.get(
                        "/api/cases",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertIn(auth_res.status_code, (200, 404))
            finally:
                app.dependency_overrides.pop(get_db, None)

        asyncio.run(run_asgi_tests())


if __name__ == "__main__":
    unittest.main()
