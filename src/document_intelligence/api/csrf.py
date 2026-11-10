"""CSRF Protection middleware and token utilities for cookie-authenticated sessions."""

from __future__ import annotations

import hmac
import secrets
from typing import Final

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from document_intelligence.api.error_handlers import make_error_response
from document_intelligence.core.config import settings

SAFE_METHODS: Final = {"GET", "HEAD", "OPTIONS", "TRACE"}
CSRF_EXEMPT_PATHS: Final = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/csrf-token",
}


def generate_csrf_token() -> str:
    """Generate a high-entropy cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set readable CSRF double-submit cookie."""
    response.set_cookie(
        key="csrf_token",
        value=token,
        max_age=int(settings.refresh_token_expire_days * 86400),
        httponly=False,  # JavaScript must read this to attach X-CSRF-Token header
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def verify_csrf_request(request: Request) -> JSONResponse | None:
    """Validate CSRF token for state-changing requests authenticated via cookies.

    Requests authenticated via Authorization: Bearer <token> headers are immune to CSRF
    and are therefore exempt. Requests authenticated via ambient cookies must provide
    an X-CSRF-Token header matching the csrf_token cookie.
    """
    if request.method in SAFE_METHODS:
        return None

    path = request.url.path.rstrip("/")
    if path in CSRF_EXEMPT_PATHS or any(path.startswith(exempt) for exempt in CSRF_EXEMPT_PATHS):
        return None

    # Check whether the request is authenticating via ambient browser cookies
    has_auth_cookie = "access_token" in request.cookies or "refresh_token" in request.cookies
    has_bearer_header = bool(
        request.headers.get("authorization", "").strip().lower().startswith("bearer ")
    )

    # If caller authenticated with a Bearer header, CSRF protection is not needed
    if has_bearer_header:
        return None

    # If caller is authenticating via ambient cookies, CSRF header is mandatory
    if has_auth_cookie:
        cookie_csrf = request.cookies.get("csrf_token")
        header_csrf = request.headers.get("x-csrf-token") or request.headers.get("x-xsrf-token")

        if not cookie_csrf or not header_csrf:
            return make_error_response(
                status_code=403,
                code="CSRF_VERIFICATION_FAILED",
                message="CSRF verification failed: missing CSRF token in header or cookie.",
                details={"reason": "Missing CSRF token"},
            )

        if not hmac.compare_digest(cookie_csrf.strip(), header_csrf.strip()):
            return make_error_response(
                status_code=403,
                code="CSRF_VERIFICATION_FAILED",
                message="CSRF verification failed: token mismatch.",
                details={"reason": "CSRF token mismatch"},
            )

    return None
