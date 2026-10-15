"""AYUR-INTEL — Security Utilities (Phase 17).

Input validation, authorization helpers, and security middleware.
"""

from __future__ import annotations

import html
import ipaddress
import logging
import re
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.models import ProductCase, User

logger = logging.getLogger("ayur_intel.security")

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

# Maximum lengths
MAX_NAME_LENGTH = 300
MAX_TEXT_LENGTH = 10000
MAX_URL_LENGTH = 500
MAX_SEARCH_LENGTH = 500
MAX_ID_LENGTH = 100

# Allowed characters patterns
_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
_SAFE_JURISDICTION_PATTERN = re.compile(r"^[A-Z]{2}$")
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def validate_string_input(
    value: str,
    *,
    field_name: str = "input",
    max_length: int = MAX_TEXT_LENGTH,
    allow_html: bool = False,
    required: bool = True,
) -> str:
    """Validate and sanitize a string input.

    - Strips whitespace
    - Enforces max length
    - Escapes HTML unless allow_html=True
    """
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return ""

    value = value.strip()

    if not value and required:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")

    if len(value) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name} exceeds maximum length of {max_length}")

    if not allow_html:
        value = html.escape(value)

    return value


def validate_id(value: str, field_name: str = "ID") -> str:
    """Validate an ID parameter (public_id format)."""
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")

    value = value.strip()

    if len(value) > MAX_ID_LENGTH:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")

    if not _SAFE_ID_PATTERN.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")

    return value


def validate_jurisdiction(value: str) -> str:
    """Validate a jurisdiction code (2-letter uppercase)."""
    if not value:
        raise HTTPException(status_code=400, detail="Jurisdiction code is required")

    value = value.strip().upper()

    if not _SAFE_JURISDICTION_PATTERN.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid jurisdiction code: {value}")

    return value


def validate_search_query(value: str) -> str:
    """Validate a search query string."""
    return validate_string_input(
        value, field_name="search query", max_length=MAX_SEARCH_LENGTH, required=True
    )


# ---------------------------------------------------------------------------
# Authorization helpers
# ---------------------------------------------------------------------------


def get_authenticated_user(
    request: Request = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Strictly authenticate user from Authorization: Bearer <token>.

    Enforces token validation in all environments. No demo fallback.
    """
    from api.services.auth_service import get_user_from_token

    authToken = None
    if authorization and authorization.startswith("Bearer "):
        authToken = authorization[7:].strip()

    if not authToken:
        raise HTTPException(
            status_code=401,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_bg = False
    if request:
        try:
            if request.headers.get("X-Background-Request", "").lower() in ("true", "1"):
                is_bg = True
            elif request.url.path.endswith("/api/auth/me"):
                is_bg = True
        except Exception:
            pass

    return get_user_from_token(db, authToken, request=request, is_background_request=is_bg)


def require_admin(
    user: User = Depends(get_authenticated_user),
) -> User:
    """Strict authorization dependency for administrative endpoints.

    Security Policies:
    - Strictly relies on get_authenticated_user (requires valid Bearer token, no demo fallback).
    - Checks the authenticated user's current database role (user.role == 'admin').
    - Returns 401 if unauthenticated (handled by get_authenticated_user).
    - Returns 403 Forbidden if authenticated user is not an admin.
    - Never trusts client-supplied headers, request bodies, or JWT claims alone.
    """
    if getattr(user, "role", "user") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )
    return user


def get_current_user(
    request: Request = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user for protected API routes.

    Security Policy:
    - In production (settings.is_production is True):
        Strictly requires valid Authorization: Bearer <token>.
        Demo mode fallback is strictly prohibited to prevent authentication bypass.
    - In local development (settings.is_production is False):
        If an Authorization header is provided, it is strictly validated.
        If no Authorization header is provided and settings.AYURINTEL_DEMO_MODE is True,
        falls back to the local demo user for developer convenience.

    Raises:
        HTTPException(401): If token is missing (in prod), malformed, expired,
                            or user account is inactive/not found.
    """
    from api.core.config import settings
    from api.services.auth_service import get_user_from_token
    from api.services.product_case_service import get_or_create_demo_user

    authToken = None
    if authorization and authorization.startswith("Bearer "):
        authToken = authorization[7:].strip()

    if authToken:
        is_bg = False
        if request:
            try:
                if request.headers.get("X-Background-Request", "").lower() in ("true", "1"):
                    is_bg = True
                elif request.url.path.endswith("/api/auth/me"):
                    is_bg = True
            except Exception:
                pass
        return get_user_from_token(db, authToken, request=request, is_background_request=is_bg)

    # In production, demo mode is strictly disallowed as an authentication bypass.
    if settings.is_production:
        raise HTTPException(
            status_code=401,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In local development only, permit demo mode fallback if explicitly enabled
    if getattr(settings, "AYURINTEL_DEMO_MODE", False):
        return get_or_create_demo_user(db)

    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_case_access(
    db: Session,
    user: User,
    case_public_id: str,
) -> ProductCase:
    """Verify that a user has access to a Product Case.

    Returns the case if authorized, raises 403/404 otherwise.
    Uses 404 (not found) to avoid leaking existence of cases.
    """
    case = (
        db.query(ProductCase)
        .filter(
            ProductCase.public_id == case_public_id,
            ProductCase.owner_id == user.id,
        )
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Product Case not found")
    return case


def verify_resource_access(
    db: Session,
    user: User,
    resource,
    resource_type: str = "Resource",
):
    """Verify that a resource belongs to the authenticated user's case.

    Generic authorization check for any resource linked to a ProductCase.
    Returns the resource if authorized, raises 404 otherwise.
    """
    if resource is None:
        raise HTTPException(status_code=404, detail=f"{resource_type} not found")

    # Check if the resource's product_case belongs to the user
    if hasattr(resource, "product_case_id") and resource.product_case_id:
        case = db.query(ProductCase).filter(
            ProductCase.id == resource.product_case_id,
            ProductCase.owner_id == user.id,
        ).first()
        if case is None:
            raise HTTPException(status_code=404, detail=f"{resource_type} not found")

    return resource


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------


async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Clickjacking protection
    response.headers["X-Frame-Options"] = "DENY"

    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # XSS protection (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Content Security Policy - restrictive but functional
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://d3js.org",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
        "img-src 'self' data: blob:",
        "font-src 'self' https://fonts.gstatic.com",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    return response


# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory)
# ---------------------------------------------------------------------------

_rate_limit_store: dict = {}


def check_rate_limit(key: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
    """Simple in-memory rate limiter.

    Returns True if request is allowed, False if rate limited.
    """
    import time

    now = time.time()
    window_start = now - window_seconds

    if key not in _rate_limit_store:
        _rate_limit_store[key] = []

    # Clean old entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if t > window_start]

    if len(_rate_limit_store[key]) >= max_requests:
        return False

    _rate_limit_store[key].append(now)
    return True


# ---------------------------------------------------------------------------
# Authentication Rate Limiting (Thread-Safe, Bounded Storage)
# ---------------------------------------------------------------------------

import hashlib
import threading
import time

_auth_rate_limit_lock = threading.Lock()
_auth_rate_limit_store: dict = {}
MAX_AUTH_RATE_LIMIT_KEYS = 5000

# Default thresholds (sliding window)
AUTH_LOGIN_IP_LIMIT = 15      # max 15 login attempts per 60s per IP
AUTH_LOGIN_ACC_LIMIT = 5      # max 5 login attempts per 60s per account identifier
AUTH_SIGNUP_IP_LIMIT = 10     # max 10 signups per 60s per IP
AUTH_WINDOW_SECONDS = 60      # 60s window duration


def _cleanup_auth_rate_limit_store(now: float, window_seconds: int = 60) -> None:
    """Purge stale timestamps and evict excess keys if storage exceeds capacity."""
    global _auth_rate_limit_store
    cutoff = now - window_seconds
    expired_keys = []
    for k, timestamps in _auth_rate_limit_store.items():
        active = [t for t in timestamps if t > cutoff]
        if not active:
            expired_keys.append(k)
        else:
            _auth_rate_limit_store[k] = active

    for k in expired_keys:
        _auth_rate_limit_store.pop(k, None)

    # If still over capacity, evict oldest 20% to bound memory consumption
    if len(_auth_rate_limit_store) > MAX_AUTH_RATE_LIMIT_KEYS:
        sorted_keys = sorted(
            _auth_rate_limit_store.keys(),
            key=lambda k: max(_auth_rate_limit_store[k]) if _auth_rate_limit_store[k] else 0,
        )
        num_to_drop = int(len(_auth_rate_limit_store) * 0.2)
        for k in sorted_keys[:num_to_drop]:
            _auth_rate_limit_store.pop(k, None)


def check_auth_rate_limit(
    ip: str,
    identifier: Optional[str] = None,
    action: str = "login",
) -> None:
    """Enforce authentication rate limits per IP and per account identifier.

    Architecture & Concurrency Scope:
    This rate limiter uses a thread-safe in-memory sliding window that is strictly
    PROCESS-LOCAL. It does NOT provide distributed rate limiting and will not synchronize
    counters across multiple worker processes (e.g. Uvicorn --workers > 1) or separate
    container instances. Each worker process enforces its own independent limits.
    For horizontal multi-process/cluster deployments, a centralized cache (such as Redis)
    must be deployed.

    Raises:
        HTTPException(status_code=429): If the rate limit is exceeded.
    """
    now = time.time()
    cutoff = now - AUTH_WINDOW_SECONDS
    clean_ip = (ip or "127.0.0.1").strip()

    with _auth_rate_limit_lock:
        if len(_auth_rate_limit_store) > MAX_AUTH_RATE_LIMIT_KEYS // 2:
            _cleanup_auth_rate_limit_store(now, AUTH_WINDOW_SECONDS)

        # 1. IP Check
        ip_limit = AUTH_SIGNUP_IP_LIMIT if action == "signup" else AUTH_LOGIN_IP_LIMIT
        ip_key = f"{action}:ip:{clean_ip}"
        ip_timestamps = [t for t in _auth_rate_limit_store.get(ip_key, []) if t > cutoff]

        if len(ip_timestamps) >= ip_limit:
            _auth_rate_limit_store[ip_key] = ip_timestamps
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(AUTH_WINDOW_SECONDS)},
            )

        # 2. Account Check (for login only)
        acc_key = None
        if action == "login" and identifier and identifier.strip():
            # Hash identifier to prevent unbounded string storage or memory bloat
            clean_id = identifier.strip().lower()
            id_hash = hashlib.sha256(clean_id.encode("utf-8")).hexdigest()[:16]
            acc_key = f"login:acc:{id_hash}"
            acc_timestamps = [t for t in _auth_rate_limit_store.get(acc_key, []) if t > cutoff]

            if len(acc_timestamps) >= AUTH_LOGIN_ACC_LIMIT:
                _auth_rate_limit_store[acc_key] = acc_timestamps
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(AUTH_WINDOW_SECONDS)},
                )
        else:
            acc_timestamps = None

        # Record this attempt
        ip_timestamps.append(now)
        _auth_rate_limit_store[ip_key] = ip_timestamps
        if acc_key is not None:
            acc_timestamps.append(now)
            _auth_rate_limit_store[acc_key] = acc_timestamps


def reset_auth_rate_limits() -> None:
    """Reset the auth rate limit store (used in test suites)."""
    with _auth_rate_limit_lock:
        _auth_rate_limit_store.clear()


def _is_valid_ip(address: str) -> bool:
    """Validate whether an address string is a syntactically valid IPv4 or IPv6 address."""
    if not address or not isinstance(address, str):
        return False
    try:
        ipaddress.ip_address(address.strip())
        return True
    except ValueError:
        return False


def _is_trusted_proxy_ip(ip_str: str, trusted_hosts: set[str]) -> bool:
    """Check if an IP string matches the trusted proxies configuration."""
    if not ip_str or not trusted_hosts:
        return False
    if ip_str in trusted_hosts:
        return True
    try:
        cand_ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for entry in trusted_hosts:
        if entry == "*":
            continue
        try:
            if "/" in entry:
                if cand_ip in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if cand_ip == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


def get_client_ip(request: Request) -> str:
    """Extract client IP address safely according to proxy trust policy.

    Trust Policy:
    1. By default, proxy headers (X-Forwarded-For, X-Real-IP) are NOT trusted.
       Direct socket IP (request.client.host) is used to prevent header spoofing
       when the application is directly exposed to the internet.
    2. Proxy headers are ONLY evaluated if settings.should_trust_proxy_headers
       is True (configured via AYURINTEL_TRUST_PROXY_HEADERS or AYURINTEL_BEHIND_PROXY).
    3. Even when proxy headers are enabled, if AYURINTEL_TRUSTED_PROXIES is configured
       (and not '*'), the immediate socket connection (request.client.host) must originate
       from an authorized proxy IP before forwarded headers are accepted.
    4. When traversing X-Forwarded-For, right-to-left traversal is used:
       We inspect from right to left, skipping trusted intermediate proxies. The first
       untrusted IP encountered from the right is the actual client IP. Any IPs prepended
       to the left by an attacker are discarded.
    5. Forwarded candidate IPs are validated with ipaddress.ip_address() to reject malformed
       or injection values. If validation fails or no valid IP is found, falls back safely
       to request.client.host (or '127.0.0.1').
    """
    from api.core.config import settings

    direct_host = ""
    if request.client and request.client.host:
        direct_host = request.client.host.strip()

    # Determine whether proxy headers should be evaluated
    trust_headers = getattr(settings, "should_trust_proxy_headers", False)

    if trust_headers:
        trusted_proxies = getattr(settings, "trusted_proxy_hosts", set())
        # If trusted proxies list is not wildcard '*' and direct host is known,
        # verify direct host is in the trusted proxy set
        is_trusted_origin = (
            ("*" in trusted_proxies)
            or (not direct_host)
            or _is_trusted_proxy_ip(direct_host, trusted_proxies)
        )

        if is_trusted_origin:
            # Check X-Forwarded-For using right-to-left traversal
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ips = [p.strip() for p in forwarded.split(",") if p.strip()]
                # Traverse right-to-left: skip trusted intermediate proxies.
                # The first untrusted IP from the right is the genuine client IP.
                for candidate in reversed(ips):
                    if not _is_valid_ip(candidate):
                        continue
                    if _is_trusted_proxy_ip(candidate, trusted_proxies):
                        continue
                    return candidate

                # If all valid IPs in the chain were trusted proxies, return leftmost valid IP
                for candidate in ips:
                    if _is_valid_ip(candidate):
                        return candidate

            # Check X-Real-IP
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                candidate = real_ip.strip()
                if _is_valid_ip(candidate):
                    return candidate

    # Fallback to direct client host or loopback default
    if direct_host and _is_valid_ip(direct_host):
        return direct_host
    return direct_host or "127.0.0.1"


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


def safe_error_response(status_code: int, detail: str) -> JSONResponse:
    """Create a safe error response that doesn't leak internal details."""
    safe_messages = {
        400: "Invalid request. Please check your input.",
        401: "Authentication required.",
        403: "Access denied.",
        404: "Resource not found.",
        429: "Too many requests. Please try again later.",
        500: "An internal error occurred. Please try again.",
    }

    message = safe_messages.get(status_code, "An error occurred.")

    return JSONResponse(
        status_code=status_code,
        content={"error": message, "status_code": status_code},
    )
