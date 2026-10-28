"""Lakebase data access for commentary, figure snapshots, approval events and draft jobs.

Every write runs as the app service principal and records the human actor (X-Forwarded-Email) and request id.
State transitions lock the row (SELECT ... FOR UPDATE) and use optimistic concurrency on `version`.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from fastapi import HTTPException

from . import db_lakebase
from .config import get_settings

_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def S() -> str:
    schema = get_settings().lakebase_schema
    if not _SCHEMA_RE.match(schema):
        raise RuntimeError("invalid LAKEBASE_SCHEMA")
    return schema


@dataclass
class Actor:
    email: str
    request_id: str


class Conflict(HTTPException):
    def __init__(self, current_version: int, status: str):
        super().__init__(status_code=409, detail={"message": "Version conflict: this commentary changed since you "
                                                             "loaded it.", "current_version": current_version,
                                                  "status": status})


# ---------------------------------------------------------------- helpers
async def _fetchone(conn, sql: str, params: Any = None) -> Optional[dict]:
    cur = await conn.execute(sql, params)
    return await cur.fetchone()


async def _fetchall(conn, sql: str, params: Any = None) -> list[dict]:
    cur = await conn.execute(sql, params)
    return list(await cur.fetchall())


async def _event(conn, cid, version: int, action: str, actor: Actor, from_status=None, to_status=None, note=None,
                 created_at=None) -> None:
    await conn.execute(
        f"""INSERT INTO {S()}.approval_event
            (commentary_id, version, action, from_status, to_status, actor_email, request_id, note, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s, COALESCE(%s, now()))""",
        (cid, version, action, from_status, to_status, actor.email, actor.request_id, note, created_at),
    )


async def _version_row(conn, cid, version: int, text: Optional[str], change_type: str, actor: Actor,
                       created_at=None) -> None:
    await conn.execute(
        f"""INSERT INTO {S()}.commentary_version (commentary_id, version, text, change_type, actor_email, request_id,
            created_at) VALUES (%s,%s,%s,%s,%s,%s, COALESCE(%s, now()))""",
        (cid, version, text, change_type, actor.email, actor.request_id, created_at),
    )


async def _figures(conn, cid, version: int, figures: Iterable[dict], created_at=None) -> None:
    rows = [(cid, version, f["figure_key"], f.get("label"), f.get("value"), f.get("unit"), f.get("source_table"),
             f.get("filter"), f.get("delta_version"), f.get("as_of_ts"), f.get("snapshot_ref"), created_at)
            for f in figures]
    if not rows:
        return
    async with conn.cursor() as cur:  # executemany pipelines the inserts (one round trip per batch)
        await cur.executemany(
            f"""INSERT INTO {S()}.commentary_figure
                (commentary_id, version, figure_key, label, value, unit, source_table, filter, delta_version,
                 as_of_ts, snapshot_ref, captured_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, COALESCE(%s, now()))
                ON CONFLICT DO NOTHING""", rows)


async def _lock(conn, cid) -> dict:
    row = await _fetchone(conn, f"SELECT * FROM {S()}.commentary WHERE id = %s FOR UPDATE", (cid,))
    if not row:
        raise HTTPException(status_code=404, detail="Commentary not found")
    return row


# ---------------------------------------------------------------- commentary
async def create(period: str, slice_key: str, title: str, actor: Actor) -> dict:
    cid = uuid.uuid4()
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        await conn.execute(
            f"""INSERT INTO {S()}.commentary (id, period, slice_key, title, version, status, author_email,
                last_edited_by) VALUES (%s,%s,%s,%s,1,'draft',%s,%s)""",
            (cid, period, slice_key, title, actor.email, actor.email),
        )
        await _version_row(conn, cid, 1, None, "created", actor)
        await _event(conn, cid, 1, "created", actor, None, "draft")
        return await _fetchone(conn, f"SELECT * FROM {S()}.commentary WHERE id = %s", (cid,))


async def get(cid) -> dict:
    async with db_lakebase.pool().connection() as conn:
        row = await _fetchone(conn, f"SELECT * FROM {S()}.commentary WHERE id = %s", (cid,))
    if not row:
        raise HTTPException(status_code=404, detail="Commentary not found")
    return row


async def list_(status: Optional[str] = None, limit: int = 100) -> list[dict]:
    async with db_lakebase.pool().connection() as conn:
        if status:
            return await _fetchall(conn, f"""SELECT * FROM {S()}.commentary WHERE status = %s
                                            ORDER BY updated_at DESC LIMIT %s""", (status, limit))
        return await _fetchall(conn, f"SELECT * FROM {S()}.commentary ORDER BY updated_at DESC LIMIT %s", (limit,))


async def figures(cid, version: Optional[int] = None) -> list[dict]:
    async with db_lakebase.pool().connection() as conn:
        if version is None:
            return await _fetchall(conn, f"""SELECT * FROM {S()}.commentary_figure WHERE commentary_id = %s
                                            ORDER BY version, figure_key""", (cid,))
        return await _fetchall(conn, f"""SELECT * FROM {S()}.commentary_figure WHERE commentary_id = %s
                                        AND version = %s ORDER BY figure_key""", (cid, version))


async def save_edit(cid, expected_version: int, text: str, title: Optional[str], figs: list[dict],
                    actor: Actor) -> dict:
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        row = await _lock(conn, cid)
        if row["version"] != expected_version:
            raise Conflict(row["version"], row["status"])
        if row["status"] not in ("draft", "rejected"):
            raise HTTPException(status_code=409, detail=f"Cannot edit a commentary that is {row['status']}")
        new_v = row["version"] + 1
        await conn.execute(
            f"""UPDATE {S()}.commentary SET edited_text = %s, title = COALESCE(%s, title), version = %s,
                status = 'draft', last_edited_by = %s, updated_at = now() WHERE id = %s""",
            (text, title, new_v, actor.email, cid),
        )
        await _version_row(conn, cid, new_v, text, "edited", actor)
        await _figures(conn, cid, new_v, figs)
        await _event(conn, cid, new_v, "edited", actor, row["status"], "draft")
        return await _fetchone(conn, f"SELECT * FROM {S()}.commentary WHERE id = %s", (cid,))


async def apply_draft(cid, text: str, figs: list[dict], model: str, trace_id: Optional[str], actor: Actor) -> dict:
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        row = await _lock(conn, cid)
        if row["status"] not in ("draft", "rejected"):
            raise HTTPException(status_code=409, detail=f"Cannot redraft a commentary that is {row['status']}")
        new_v = row["version"] + 1
        await conn.execute(
            f"""UPDATE {S()}.commentary SET draft_text = %s, edited_text = %s, version = %s, status = 'draft',
                drafted_by_model = %s, agent_trace_id = %s, last_edited_by = %s, updated_at = now() WHERE id = %s""",
            (text, text, new_v, model, trace_id, actor.email, cid),
        )
        await _version_row(conn, cid, new_v, text, f"drafted:{model}", actor)
        await _figures(conn, cid, new_v, figs)
        await _event(conn, cid, new_v, "drafted", actor, row["status"], "draft", note=f"model={model}")
        return await _fetchone(conn, f"SELECT * FROM {S()}.commentary WHERE id = %s", (cid,))


async def submit(cid, expected_version: int, note: Optional[str], actor: Actor) -> dict:
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        row = await _lock(conn, cid)
        if row["version"] != expected_version:
            raise Conflict(row["version"], row["status"])
        if row["status"] != "draft":
            raise HTTPException(status_code=409, detail=f"Only drafts can be submitted (status is {row['status']})")
        if not (row["edited_text"] or "").strip():
            raise HTTPException(status_code=422, detail="Commentary text is empty")
        await conn.execute(
            f"""UPDATE {S()}.commentary SET status = 'in_review', submitted_by = %s, submitted_at = now(),
                updated_at = now() WHERE id = %s""", (actor.email, cid))
        await _event(conn, cid, row["version"], "submitted", actor, "draft", "in_review", note)
        return await _fetchone(conn, f"SELECT * FROM {S()}.commentary WHERE id = %s", (cid,))


def four_eyes_blocker(row: dict, email: str) -> Optional[str]:
    if row["author_email"] == email:
        return "Four-eyes control: you authored this commentary"
    if (row.get("last_edited_by") or "") == email:
        return "Four-eyes control: you edited the current version"
    return None


async def decide(cid, expected_version: int, approve: bool, note: Optional[str], actor: Actor) -> dict:
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        row = await _lock(conn, cid)
        if row["version"] != expected_version:
            raise Conflict(row["version"], row["status"])
        if row["status"] != "in_review":
            raise HTTPException(status_code=409, detail=f"Commentary is {row['status']}, not in review")
        blocker = four_eyes_blocker(row, actor.email)
        if blocker:
            raise HTTPException(status_code=403, detail=blocker)
        to_status = "approved" if approve else "rejected"
        await conn.execute(
            f"""UPDATE {S()}.commentary SET status = %s, decided_by = %s, decision_note = %s, decided_at = now(),
                updated_at = now() WHERE id = %s AND author_email <> %s""",
            (to_status, actor.email, note, cid, actor.email),
        )
        await _event(conn, cid, row["version"], "approved" if approve else "rejected", actor, "in_review",
                     to_status, note)
        return await _fetchone(conn, f"SELECT * FROM {S()}.commentary WHERE id = %s", (cid,))


# ---------------------------------------------------------------- audit
async def audit(cid=None, limit: int = 500) -> tuple[list[dict], list[dict]]:
    async with db_lakebase.pool().connection() as conn:
        if cid:
            events = await _fetchall(conn, f"""SELECT * FROM {S()}.approval_event WHERE commentary_id = %s
                                              ORDER BY event_id""", (cid,))
            versions = await _fetchall(conn, f"""SELECT version, text, change_type, actor_email, created_at
                                                FROM {S()}.commentary_version WHERE commentary_id = %s
                                                ORDER BY version""", (cid,))
        else:
            events = await _fetchall(conn, f"SELECT * FROM {S()}.approval_event ORDER BY event_id DESC LIMIT %s",
                                     (limit,))
            versions = []
    return events, versions


# ---------------------------------------------------------------- draft jobs (state lives in the database)
async def create_job(cid, actor: Actor) -> dict:
    jid = uuid.uuid4()
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        row = await _lock(conn, cid)
        if row["status"] not in ("draft", "rejected"):
            raise HTTPException(status_code=409, detail=f"Cannot draft a commentary that is {row['status']}")
        active = await _fetchone(conn, f"""SELECT job_id FROM {S()}.draft_job WHERE commentary_id = %s
                                          AND status IN ('queued','running')
                                          AND updated_at > now() - interval '5 minutes'""", (cid,))
        if active:
            raise HTTPException(status_code=409, detail={"message": "A draft is already in progress",
                                                         "job_id": str(active["job_id"])})
        await conn.execute(
            f"""INSERT INTO {S()}.draft_job (job_id, commentary_id, status, requested_by, request_id)
                VALUES (%s,%s,'queued',%s,%s)""", (jid, cid, actor.email, actor.request_id))
        return await _fetchone(conn, f"SELECT * FROM {S()}.draft_job WHERE job_id = %s", (jid,))


async def get_job(jid) -> dict:
    async with db_lakebase.pool().connection() as conn:
        row = await _fetchone(conn, f"SELECT * FROM {S()}.draft_job WHERE job_id = %s", (jid,))
        if row and row["status"] in ("queued", "running"):
            # An instance restart orphans in-flight work: surface it instead of spinning forever.
            stale = await _fetchone(conn, f"""UPDATE {S()}.draft_job SET status = 'failed',
                     error = 'Interrupted (app restarted); please retry', finished_at = now(), updated_at = now()
                     WHERE job_id = %s AND updated_at < now() - interval '4 minutes' RETURNING *""", (jid,))
            row = stale or row
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row


async def job_update(jid, status: str, error: Optional[str] = None, result: Optional[dict] = None) -> None:
    async with db_lakebase.pool().connection() as conn:
        await conn.execute(
            f"""UPDATE {S()}.draft_job SET status = %s, error = %s, result = COALESCE(%s::jsonb, result),
                started_at = CASE WHEN %s = 'running' THEN now() ELSE started_at END,
                finished_at = CASE WHEN %s IN ('succeeded','failed') THEN now() ELSE finished_at END,
                updated_at = now() WHERE job_id = %s""",
            (status, error, json.dumps(result) if result is not None else None, status, status, jid),
        )


async def job_heartbeat(jid) -> None:
    async with db_lakebase.pool().connection() as conn:
        await conn.execute(f"UPDATE {S()}.draft_job SET updated_at = now() WHERE job_id = %s", (jid,))


# ---------------------------------------------------------------- demo seeding / reset
async def count() -> int:
    async with db_lakebase.pool().connection() as conn:
        row = await _fetchone(conn, f"SELECT count(*) AS n FROM {S()}.commentary")
    return int(row["n"])


async def truncate_all() -> None:
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        await conn.execute(f"""TRUNCATE {S()}.draft_job, {S()}.approval_event, {S()}.commentary_figure,
                               {S()}.commentary_version, {S()}.commentary""")


async def insert_seed(item: dict) -> None:
    """Insert a fully formed historical item (used only by the demo seeder)."""
    c = item["commentary"]
    async with db_lakebase.pool().connection() as conn, conn.transaction():
        await conn.execute(
            f"""INSERT INTO {S()}.commentary (id, period, slice_key, title, version, status, draft_text, edited_text,
                author_email, last_edited_by, submitted_by, decided_by, decision_note, drafted_by_model,
                created_at, updated_at, submitted_at, decided_at)
                VALUES (%(id)s,%(period)s,%(slice_key)s,%(title)s,%(version)s,%(status)s,%(draft_text)s,
                %(edited_text)s,%(author_email)s,%(last_edited_by)s,%(submitted_by)s,%(decided_by)s,
                %(decision_note)s,%(drafted_by_model)s,%(created_at)s,%(updated_at)s,%(submitted_at)s,
                %(decided_at)s)""", c)
        for v in item["versions"]:
            await _version_row(conn, c["id"], v["version"], v["text"], v["change_type"],
                               Actor(v["actor_email"], v.get("request_id", "seed")), v["created_at"])
        for version, figs in item["figures"].items():
            await _figures(conn, c["id"], int(version), figs, item["figures_captured_at"].get(version))
        for e in item["events"]:
            await _event(conn, c["id"], e["version"], e["action"], Actor(e["actor_email"], e.get("request_id", "seed")),
                         e.get("from_status"), e.get("to_status"), e.get("note"), e["created_at"])
