"""Who is calling: the signed-in user, as forwarded by the Databricks Apps proxy."""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class User:
    email: str
    token: str = field(repr=False)  # forwarded user token: short-lived, per request. Never log it.
    request_id: str = ""


def current_user(request: Request) -> User:
    email = request.headers.get("x-forwarded-email")
    token = request.headers.get("x-forwarded-access-token")
    if not email or not token:
        raise HTTPException(status_code=401, detail="User authorization required")  # fail closed
    return User(email=email.strip().lower(), token=token, request_id=getattr(request.state, "request_id", ""))


def current_email(request: Request) -> str:
    """Identity only (no token needed), for SP-side writes that record the human actor."""
    email = request.headers.get("x-forwarded-email")
    if not email:
        raise HTTPException(status_code=401, detail="User identity required")
    return email.strip().lower()
