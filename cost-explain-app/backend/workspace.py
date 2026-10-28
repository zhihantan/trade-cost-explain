"""Workspace host resolution and REST calls made with the *user's* forwarded token.

Calls on behalf of the user go straight to the REST API with a Bearer token, so the SDK's credential discovery
(app service principal env vars, local CLI profiles) can never be mixed in by accident.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

import requests
from databricks.sdk.core import Config

from .config import get_settings


@lru_cache
def sp_config() -> Config:
    """Service-principal config in Databricks Apps; the chosen CLI profile when running locally."""
    settings = get_settings()
    return Config(profile=settings.local_profile) if settings.is_local else Config()


def host() -> str:
    h = sp_config().host or ""
    return h.rstrip("/") if h.startswith("http") else f"https://{h}".rstrip("/")


def hostname() -> str:
    return host().replace("https://", "")


def user_rest(user, method: str, path: str, body: Optional[dict] = None, timeout: float = 30) -> Any:
    resp = requests.request(method, f"{host()}{path}", json=body, timeout=timeout,
                            headers={"Authorization": f"Bearer {user.token}"})
    if resp.status_code >= 400:
        from fastapi import HTTPException

        detail = "Upstream request failed"
        try:
            detail = resp.json().get("message") or detail
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code if resp.status_code in (401, 403, 404) else 502,
                            detail=detail[:300])
    return resp.json() if resp.content else {}
