"""Shared fixtures for integration tests against the Gateway app."""

from __future__ import annotations

import secrets

from app.gateway.csrf_middleware import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.gateway.internal_auth import create_internal_auth_headers


def auth_headers() -> dict[str, str]:
    """Return headers that satisfy AuthMiddleware + CSRFMiddleware in tests.

    Uses the process-local internal auth token to bypass session checks
    and a self-issued CSRF token paired across the cookie and header
    (Double Submit Cookie pattern).
    """
    csrf_token = secrets.token_urlsafe(32)
    headers = {
        **create_internal_auth_headers(),
        CSRF_HEADER_NAME: csrf_token,
        "Cookie": f"{CSRF_COOKIE_NAME}={csrf_token}",
    }
    return headers
