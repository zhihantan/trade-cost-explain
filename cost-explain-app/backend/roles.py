"""Analyst / approver roles from Databricks group membership, read with the user's own identity."""
from __future__ import annotations

import logging
import threading
import time

from . import db_sql, workspace
from .auth import User
from .config import get_settings

log = logging.getLogger("cost_explain.roles")

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()
_TTL = 300


def resolve(user: User) -> dict:
    with _lock:
        hit = _cache.get(user.email)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
    settings = get_settings()
    info = {"display_name": None, "groups": set()}
    try:  # current-user API with the forwarded token (scope iam.current-user:read)
        me = workspace.user_rest(user, "GET", "/api/2.0/preview/scim/v2/Me", timeout=15)
        info["display_name"] = me.get("displayName")
        info["groups"] = {g.get("display") for g in (me.get("groups") or []) if g.get("display")}
    except Exception as exc:  # fall back to SQL group functions as the user
        log.info("current-user lookup failed (%s); using SQL group checks", type(exc).__name__)
        try:
            rows = db_sql.query_as_user(
                user, "SELECT is_account_group_member(:a) AS a, is_account_group_member(:p) AS p",
                {"a": settings.analyst_group, "p": settings.approver_group})
            if rows and rows[0]["a"]:
                info["groups"].add(settings.analyst_group)
            if rows and rows[0]["p"]:
                info["groups"].add(settings.approver_group)
        except Exception as exc2:
            log.warning("role resolution failed: %s", type(exc2).__name__)
    info["is_analyst"] = settings.analyst_group in info["groups"]
    info["is_approver"] = settings.approver_group in info["groups"]
    info["roles"] = [r for r, ok in (("analyst", info["is_analyst"]), ("approver", info["is_approver"])) if ok]
    with _lock:
        _cache[user.email] = (time.time(), info)
    return info


def require(user: User, role: str) -> dict:
    from fastapi import HTTPException

    info = resolve(user)
    if not info.get(f"is_{role}"):
        group = get_settings().analyst_group if role == "analyst" else get_settings().approver_group
        raise HTTPException(status_code=403, detail=f"Requires membership of {group}")
    return info
