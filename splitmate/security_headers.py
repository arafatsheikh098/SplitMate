"""Strict security headers for every response.

Adds a content-security-policy and other defensive headers to all
HTTP responses (M7 A3).  We refuse inline scripts and remote sources
for the main app shell; the language toggle and HTMX are first-party
or self-hosted.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

#: Single source of truth for the CSP.  The ``connect-src 'self'`` line is
#: required because HTMX posts to the same origin only.
#: ``style-src 'self' 'unsafe-inline'`` is a deliberate trade-off:
#: HTMX's htmx-indicator plugin uses inline style attributes to hide
#: elements during requests, and we want to keep using the no-build
#: htmx.min.js that ships in ``splitmate/static/vendor/``.  Scripts
#: are still locked to ``'self'`` so user-controlled strings can't
#: run as JavaScript.
CONTENT_SECURITY_POLICY: str = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

#: Other defensive headers we apply to every response.
EXTRA_HEADERS: dict[str, str] = {
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply the CSP and other defensive headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        for name, value in EXTRA_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


__all__ = [
    "CONTENT_SECURITY_POLICY",
    "EXTRA_HEADERS",
    "SecurityHeadersMiddleware",
]
