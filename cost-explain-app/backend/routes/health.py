"""Liveness and a deep diagnostic (identity, scopes, warehouse, Lakebase). The deep check never returns secrets."""
from __future__ import annotations

import base64
import json
import os
import time

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from .. import db_lakebase, db_sql
from ..auth import User, current_user
from ..config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


def _token_scopes(token: str) -> list[str]:
    """Read the `scope` claim of the forwarded OAuth token (claims only; the token itself is never returned)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        scope = claims.get("scope") or claims.get("scp") or ""
        return sorted(scope.split() if isinstance(scope, str) else scope)
    except Exception:
        return ["<opaque token>"]


@router.get("/health/deep")
async def deep(request: Request, user: User = Depends(current_user)):
    settings = get_settings()
    out: dict = {
        "user": user.email,
        "request_id": user.request_id,
        "headers_present": sorted(h for h in request.headers.keys() if h.startswith("x-")),
        "token_scopes": _token_scopes(user.token),
        "env": {
            k: (os.environ.get(k) if k not in {"DATABRICKS_CLIENT_SECRET"} else "<set>")
            for k in [
                "APP_ENV", "DATA_MODE", "DATABRICKS_APP_PORT", "UVICORN_PORT", "UVICORN_HOST", "DATABRICKS_HOST",
                "WAREHOUSE_ID", "PGHOST", "PGDATABASE", "PGUSER", "PGPORT", "PGSSLMODE", "PGAPPNAME",
                "LAKEBASE_ENDPOINT", "AGENT_ENDPOINT", "GENIE_SPACE_ID", "GOLD_SCHEMA",
            ]
            if os.environ.get(k) is not None
        },
    }
    t0 = time.perf_counter()
    try:
        rows = await run_in_threadpool(
            db_sql.query_as_user, user, "SELECT current_user() AS who, current_catalog() AS cat, :p AS echo",
            {"p": "param-ok"},
        )
        out["sql"] = {"ok": True, "row": rows[0], "ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as exc:
        out["sql"] = {"ok": False, "error": type(exc).__name__, "message": str(exc)[:300]}
    t0 = time.perf_counter()
    try:
        async with db_lakebase.pool().connection(timeout=20) as conn:
            cur = await conn.execute("SELECT current_user AS role, current_database() AS db, version() AS v")
            row = await cur.fetchone()
        out["lakebase"] = {"ok": True, "row": {k: str(v)[:80] for k, v in row.items()},
                           "ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as exc:
        out["lakebase"] = {"ok": False, "error": type(exc).__name__, "message": str(exc)[:300]}
    out["settings"] = {"data_mode": settings.data_mode, "gold_schema": settings.gold_schema,
                       "lakebase_endpoint_resolved": db_lakebase._resolve_endpoint()}
    return out
