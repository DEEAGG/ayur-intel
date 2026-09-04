"""AYUR-INTEL — Security Utilities (Phase 17).

Input validation, authorization helpers, and security middleware.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

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


def get_current_user(db: Session) -> User:
    """Get the current authenticated user.

    Phase 1-17: returns the demo user in demo mode.
    Phase 19: will implement full session-based auth.
    """
    from api.core.config import settings
    from api.services.product_case_service import get_or_create_demo_user

    if settings.AYURINTEL_DEMO_MODE:
        return get_or_create_demo_user(db)

    raise HTTPException(status_code=401, detail="Authentication required")


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
