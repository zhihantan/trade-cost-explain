"""SQL warehouse access with the *user's* identity, so Unity Catalog row filters and column masks apply."""
from __future__ import annotations

import logging
import re
from typing import Any

from databricks import sql

from . import workspace
from .config import get_settings

log = logging.getLogger("cost_explain.sql")

_IDENT = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+){2}$")


class TableMissing(Exception):
    """A Gold table/view does not exist (yet). Distinct from permission errors, which must surface."""


def safe_table(name: str) -> str:
    """Allow-list a fully qualified table name before it is interpolated into SQL (identifiers can't be bound)."""
    name = name.strip().lower()
    if not _IDENT.match(name) or not name.startswith("cost_explain."):
        raise ValueError("table name not allowed")
    return name


def query_as_user(user, statement: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Runs on the SQL warehouse with the user's token. Always parameterized (named :params)."""
    settings = get_settings()
    try:
        with sql.connect(
            server_hostname=workspace.hostname(),
            http_path=f"/sql/1.0/warehouses/{settings.warehouse_id}",
            access_token=user.token,
            user_agent_entry="cost-explain-app",
        ) as conn, conn.cursor() as cur:
            cur.execute(statement, params or {})
            return [row.asDict() for row in cur.fetchall()]  # no pyarrow needed (optional in connector 4.x)
    except Exception as exc:  # classify without leaking details
        text = str(exc)
        if "TABLE_OR_VIEW_NOT_FOUND" in text or "SCHEMA_NOT_FOUND" in text:
            raise TableMissing(text.split("\n", 1)[0][:300]) from None
        raise
