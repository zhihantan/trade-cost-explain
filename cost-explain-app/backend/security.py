"""Cross-cutting HTTP hardening: request ids, CSRF/Origin checks, security headers, dev-only identity."""
from __future__ import annotations

import logging
import uuid
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

log = logging.getLogger("cost_explain.security")

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "cost-explain-app"
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid[:128]
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """Mutating /api calls need the custom header and, when an Origin is sent, a same-host Origin."""

    async def dispatch(self, request: Request, call_next):
        if request.method in MUTATING and request.url.path.startswith("/api/"):
            if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
                return JSONResponse({"detail": "Missing CSRF header"}, status_code=403)
            origin = request.headers.get("origin")
            if origin:
                host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
                if urlparse(origin).netloc.lower() != host.split(",")[0].strip().lower():
                    return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
        return await call_next(request)


class LocalIdentityMiddleware(BaseHTTPMiddleware):
    """DEV ONLY: inject X-Forwarded-* the way the Databricks Apps proxy would. Refuses to exist in prod."""

    def __init__(self, app, email: str, token_provider):
        super().__init__(app)
        self._email = email
        self._token_provider = token_provider

    async def dispatch(self, request: Request, call_next):
        headers = dict(request.scope["headers"])
        headers[b"x-forwarded-email"] = self._email.encode()
        headers[b"x-forwarded-access-token"] = self._token_provider().encode()
        headers.setdefault(b"x-forwarded-host", headers.get(b"host", b"localhost"))
        request.scope["headers"] = list(headers.items())
        return await call_next(request)


def install(app: FastAPI) -> None:
    settings = get_settings()
    app.add_middleware(CsrfMiddleware)
    if settings.is_local:
        if settings.app_env == "prod":  # belt and braces: impossible combination
            raise RuntimeError("Local identity middleware cannot run in prod")
        from .workspace import sp_config

        cfg = sp_config()

        def token() -> str:
            return cfg.authenticate()["Authorization"].split(" ", 1)[1]

        email = settings.local_user_email or "local.user@example.com"
        app.add_middleware(LocalIdentityMiddleware, email=email, token_provider=token)
        log.warning("APP_ENV=local: injecting X-Forwarded-* for %s (development only)", email)
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):  # no stack traces to clients
        rid = getattr(request.state, "request_id", "")
        log.error("unhandled error rid=%s path=%s type=%s", rid, request.url.path, type(exc).__name__)
        return JSONResponse({"detail": "Internal error", "request_id": rid}, status_code=500)
