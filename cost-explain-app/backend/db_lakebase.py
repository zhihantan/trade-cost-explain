"""Lakebase (Postgres) pool for the app service principal, with OAuth token rotation.

Tokens last about an hour; a fresh one is used for every new physical connection, and pooled connections are
recycled well before that. The pool opens without blocking startup and is closed in the FastAPI lifespan.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import get_settings

log = logging.getLogger("cost_explain.lakebase")

_pool: AsyncConnectionPool | None = None
_token: tuple[str, float] | None = None  # (token, expires_at_epoch)
_endpoint: str | None = None
_TOKEN_TTL_S = 40 * 60


def _workspace_client():
    from databricks.sdk import WorkspaceClient

    settings = get_settings()
    if settings.is_local:
        return WorkspaceClient(profile=settings.local_profile)
    return WorkspaceClient()  # app service principal (auto-injected credentials)


def _resolve_endpoint() -> str:
    """The postgres resource may expose an endpoint, branch or database path; normalise to an endpoint path."""
    global _endpoint
    if _endpoint:
        return _endpoint
    settings = get_settings()
    candidate = settings.lakebase_endpoint.strip()
    if "/endpoints/" in candidate:
        _endpoint = candidate
    else:
        _endpoint = settings.lakebase_endpoint_path
    return _endpoint


def _fresh_token() -> str:
    global _token
    now = time.time()
    if _token and _token[1] - now > 120:
        return _token[0]
    w = _workspace_client()
    cred = w.postgres.generate_database_credential(endpoint=_resolve_endpoint())
    _token = (cred.token, now + _TOKEN_TTL_S)
    return cred.token


def _username() -> str:
    settings = get_settings()
    if settings.is_local:
        return os.environ.get("PGUSER") or _workspace_client().current_user.me().user_name
    return os.environ["PGUSER"]


class OAuthConnection(psycopg.AsyncConnection):
    @classmethod
    async def connect(cls, conninfo: str = "", **kwargs):  # type: ignore[override]
        kwargs["password"] = await asyncio.to_thread(_fresh_token)
        return await super().connect(conninfo, **kwargs)


def _conninfo() -> str:
    host = os.environ.get("PGHOST", "")
    if not host:
        w = _workspace_client()
        ep = w.postgres.get_endpoint(name=_resolve_endpoint())
        host = ep.status.hosts.host
    return psycopg.conninfo.make_conninfo(
        host=host,
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "databricks_postgres"),
        user=_username(),
        sslmode=os.environ.get("PGSSLMODE", "require"),
        application_name=os.environ.get("PGAPPNAME", "cost-explain-app"),
        connect_timeout="10",
    )


async def _configure(conn: psycopg.AsyncConnection) -> None:
    conn.row_factory = dict_row  # type: ignore[assignment]


async def open_pool() -> None:
    """Create the pool without waiting for connections (keeps startup light)."""
    global _pool
    if _pool is not None:
        return
    info = await asyncio.to_thread(_conninfo)
    _pool = AsyncConnectionPool(
        conninfo=info,
        connection_class=OAuthConnection,
        min_size=1,
        max_size=6,
        max_lifetime=30 * 60,  # recycle well inside the token lifetime
        max_idle=10 * 60,
        timeout=20,
        configure=_configure,
        open=False,
        name="lakebase",
    )
    await _pool.open(wait=False)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close(timeout=5)  # must finish well inside the 15 s SIGTERM window
        _pool = None


def pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Lakebase pool not initialised")
    return _pool
