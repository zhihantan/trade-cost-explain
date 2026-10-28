"""Idempotent Lakebase schema for the review app. Runs at startup as the app service principal, which therefore
creates and owns the schema. An advisory lock serialises concurrent app instances."""
from __future__ import annotations

import asyncio
import logging

from . import db_lakebase
from .config import get_settings

log = logging.getLogger("cost_explain.migrations")

_ready = asyncio.Event()
_error: str | None = None


def ddl(schema: str) -> list[str]:
    s = schema
    return [
        f"CREATE SCHEMA IF NOT EXISTS {s}",
        f"""CREATE TABLE IF NOT EXISTS {s}.commentary (
            id uuid PRIMARY KEY,
            period text NOT NULL,
            slice_key text NOT NULL,
            title text NOT NULL,
            version integer NOT NULL DEFAULT 1,
            status text NOT NULL CHECK (status IN ('draft','in_review','approved','rejected')),
            draft_text text,
            edited_text text,
            author_email text NOT NULL,
            last_edited_by text,
            submitted_by text,
            decided_by text,
            decision_note text,
            drafted_by_model text,
            agent_trace_id text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            submitted_at timestamptz,
            decided_at timestamptz)""",
        f"CREATE INDEX IF NOT EXISTS commentary_status_idx ON {s}.commentary (status, updated_at DESC)",
        f"CREATE INDEX IF NOT EXISTS commentary_period_idx ON {s}.commentary (period, slice_key)",
        f"""CREATE TABLE IF NOT EXISTS {s}.commentary_version (
            commentary_id uuid NOT NULL REFERENCES {s}.commentary(id),
            version integer NOT NULL,
            text text,
            change_type text NOT NULL,
            actor_email text NOT NULL,
            request_id text,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (commentary_id, version))""",
        f"""CREATE TABLE IF NOT EXISTS {s}.commentary_figure (
            commentary_id uuid NOT NULL REFERENCES {s}.commentary(id),
            version integer NOT NULL,
            figure_key text NOT NULL,
            label text,
            value double precision,
            unit text,
            source_table text,
            filter text,
            delta_version bigint,
            as_of_ts timestamptz,
            captured_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (commentary_id, version, figure_key))""",
        # Materialized views have no Delta history: the snapshot is the pipeline update id (+ refresh timestamp).
        f"ALTER TABLE {s}.commentary_figure ADD COLUMN IF NOT EXISTS snapshot_ref text",
        f"""CREATE TABLE IF NOT EXISTS {s}.approval_event (
            event_id bigserial PRIMARY KEY,
            commentary_id uuid NOT NULL REFERENCES {s}.commentary(id),
            version integer NOT NULL,
            action text NOT NULL,
            from_status text,
            to_status text,
            actor_email text NOT NULL,
            request_id text,
            note text,
            created_at timestamptz NOT NULL DEFAULT now())""",
        f"CREATE INDEX IF NOT EXISTS approval_event_c_idx ON {s}.approval_event (commentary_id, event_id)",
        f"""CREATE TABLE IF NOT EXISTS {s}.draft_job (
            job_id uuid PRIMARY KEY,
            commentary_id uuid NOT NULL REFERENCES {s}.commentary(id),
            status text NOT NULL CHECK (status IN ('queued','running','succeeded','failed')),
            error text,
            requested_by text NOT NULL,
            request_id text,
            result jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            finished_at timestamptz,
            updated_at timestamptz NOT NULL DEFAULT now())""",
        # Controls enforced in the database as well as the API.
        f"""CREATE OR REPLACE FUNCTION {s}.forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END $$""",
        f"""CREATE OR REPLACE FUNCTION {s}.protect_approved() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF OLD.status = 'approved' THEN
                RAISE EXCEPTION 'approved commentary % is immutable', OLD.id;
              END IF;
              IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
              RETURN NEW;
            END $$""",
        f"DROP TRIGGER IF EXISTS approval_event_append_only ON {s}.approval_event",
        f"""CREATE TRIGGER approval_event_append_only BEFORE UPDATE OR DELETE ON {s}.approval_event
            FOR EACH ROW EXECUTE FUNCTION {s}.forbid_mutation()""",
        f"DROP TRIGGER IF EXISTS commentary_version_append_only ON {s}.commentary_version",
        f"""CREATE TRIGGER commentary_version_append_only BEFORE UPDATE OR DELETE ON {s}.commentary_version
            FOR EACH ROW EXECUTE FUNCTION {s}.forbid_mutation()""",
        f"DROP TRIGGER IF EXISTS commentary_figure_append_only ON {s}.commentary_figure",
        f"""CREATE TRIGGER commentary_figure_append_only BEFORE UPDATE OR DELETE ON {s}.commentary_figure
            FOR EACH ROW EXECUTE FUNCTION {s}.forbid_mutation()""",
        f"DROP TRIGGER IF EXISTS commentary_protect_approved ON {s}.commentary",
        f"""CREATE TRIGGER commentary_protect_approved BEFORE UPDATE OR DELETE ON {s}.commentary
            FOR EACH ROW EXECUTE FUNCTION {s}.protect_approved()""",
        # Ready for Lakehouse Sync (CDC) should it become available for this catalog.
        *[f"ALTER TABLE {s}.{t} REPLICA IDENTITY FULL"
          for t in ("commentary", "commentary_version", "commentary_figure", "approval_event", "draft_job")],
    ]


async def run(after=None) -> None:
    """Apply DDL, then the optional `after` hook (demo seed), then open the gate for requests."""
    global _error
    settings = get_settings()
    for attempt in range(1, 6):
        try:
            async with db_lakebase.pool().connection(timeout=30) as conn:
                async with conn.transaction():
                    await conn.execute("SELECT pg_advisory_xact_lock(hashtext('cost_explain_app_migrations'))")
                    for stmt in ddl(settings.lakebase_schema):
                        await conn.execute(stmt)
            log.info("Lakebase schema %s ready", settings.lakebase_schema)
            if after is not None:
                try:
                    await after()
                except Exception as exc:
                    log.warning("post-migration hook failed: %s", type(exc).__name__)
            _error = None
            _ready.set()
            return
        except Exception as exc:  # keep the app up; mutating endpoints report not-ready
            _error = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.warning("migration attempt %s failed: %s", attempt, _error)
            await asyncio.sleep(min(2 ** attempt, 20))


async def wait_ready(timeout: float = 25) -> None:
    from fastapi import HTTPException

    try:
        await asyncio.wait_for(_ready.wait(), timeout)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail=f"Review store not ready ({_error or 'starting'})") from None
