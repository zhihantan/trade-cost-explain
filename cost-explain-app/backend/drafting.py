"""Asynchronous commentary drafting: POST /draft returns 202 + job id; this runs the work in the background.

Steps: entitlement pre-check as the user -> fetch citable figures as the user -> call the agent endpoint on behalf
of the user (falls back to the deterministic template drafter) -> verify every cited figure against the registry
-> snapshot figures with their Delta versions -> persist the new version. Job state lives in Lakebase.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import requests
from starlette.concurrency import run_in_threadpool

from . import gold, repo, template, workspace
from .auth import User
from .config import get_settings
from .models import Figure

log = logging.getLogger("cost_explain.drafting")

_tasks: set[asyncio.Task] = set()  # keep references so tasks are not garbage-collected


class AgentUnavailable(Exception):
    pass


def _agent_call(user: User, commentary: dict, slice_label: str) -> dict[str, Any]:
    settings = get_settings()
    host = workspace.host()
    body = {
        "input": [{"role": "user", "content": (
            f"Draft the month-end variance commentary for {commentary['period']} — {slice_label}. "
            "Cite every number with a figure chip.")}],
        "custom_inputs": {"comparison_id": commentary["period"], "slice": commentary["slice_key"],
                          "audience": "CFO", "max_words": 250},
    }
    try:
        resp = requests.post(f"{host}/serving-endpoints/{settings.agent_endpoint}/invocations", json=body,
                             headers={"Authorization": f"Bearer {user.token}"},  # on behalf of the user
                             timeout=settings.agent_timeout_s)
    except requests.RequestException as exc:
        raise AgentUnavailable(type(exc).__name__) from None
    if resp.status_code >= 400:
        raise AgentUnavailable(f"HTTP {resp.status_code}")
    data = resp.json()
    co = data.get("custom_outputs") or {}
    text = co.get("commentary_markdown")
    if not text:  # fall back to the Responses output message text
        for item in data.get("output") or []:
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    text = c["text"]
    if not text:
        raise AgentUnavailable("empty response")
    return {"text": text, "figures": co.get("figures") or [], "model": co.get("model") or settings.agent_endpoint,
            "trace_id": co.get("trace_id") or data.get("id")}


def _snapshot(fig: Figure) -> dict:
    return {"figure_key": fig.figure_key, "label": fig.label, "value": fig.value, "unit": fig.unit,
            "source_table": fig.source_table, "filter": fig.filter, "delta_version": fig.delta_version,
            "as_of_ts": fig.as_of_ts, "snapshot_ref": fig.snapshot_ref}


def resolve_cited(user: User, text: str, known: dict[str, Figure]) -> tuple[list[dict], list[str]]:
    """Registry values are authoritative; unknown keys are reported (and never invented)."""
    keys = template.chip_keys(text)
    missing = [k for k in keys if k not in known]
    fetched = gold.figures_by_keys(user, missing) if missing else {}
    snaps, unknown = [], []
    for key in keys:
        fig = known.get(key) or fetched.get(key)
        if fig is None:
            unknown.append(key)
            continue
        snaps.append(_snapshot(fig))
    return snaps, unknown


async def _run(job_id, cid, user: User) -> None:
    settings = get_settings()
    actor = repo.Actor(user.email, user.request_id)
    try:
        await repo.job_update(job_id, "running")
        c = await repo.get(cid)
        comps = {x.comparison_id: x for x in await run_in_threadpool(gold.comparisons, user)}
        comp = comps.get(c["period"])
        if comp is None:
            raise ValueError("Unknown comparison")
        slice_label = gold.slice_label(c["slice_key"])
        # 1. entitlement pre-check with the user's identity (row filters apply)
        ok, hidden = await run_in_threadpool(gold.slice_access_check, user, c["period"], c["slice_key"])
        if not ok:
            raise PermissionError("Your data entitlements hide part of this slice (desks: "
                                  f"{', '.join(hidden)}); draft a slice you can see in full")
        # 2. citable figures, as the user
        figs = await run_in_threadpool(gold.figures_for, user, c["period"], c["slice_key"], comp.period_p0,
                                       comp.period_p1)
        await repo.job_heartbeat(job_id)
        # 3. agent on behalf of the user, or deterministic fallback
        text: Optional[str] = None
        model, trace_id, fallback_reason, agent_figs = "template-fallback", None, None, []
        if settings.agent_endpoint:
            try:
                res = await asyncio.to_thread(_agent_call, user, c, slice_label)
                text, model, trace_id, agent_figs = res["text"], res["model"], res["trace_id"], res["figures"]
            except AgentUnavailable as exc:
                fallback_reason = f"agent unavailable ({exc})"
                log.warning("draft job %s: %s; using template", job_id, fallback_reason)
        else:
            fallback_reason = "no agent endpoint configured"
        if not text:
            text = template.draft(comp.model_dump(), c["slice_key"], slice_label, figs)
        await repo.job_heartbeat(job_id)
        # 4. verify cited figures; 5. snapshot with Delta versions
        snaps, unknown = await run_in_threadpool(resolve_cited, user, text, figs)
        mismatches = []
        by_key = {s["figure_key"]: s for s in snaps}
        for af in agent_figs:
            reg = by_key.get(af.get("figure_key"))
            if reg and reg["value"] is not None and af.get("value") is not None and \
                    abs(float(af["value"]) - float(reg["value"])) > 0.5:
                mismatches.append(af.get("figure_key"))
        await repo.apply_draft(cid, text, snaps, model, trace_id, actor)
        await repo.job_update(job_id, "succeeded", result={
            "model": model, "figures": len(snaps), "unknown_figures": unknown, "value_mismatches": mismatches,
            "fallback_reason": fallback_reason, "data_mode": next(iter(figs.values())).mode if figs else None})
    except Exception as exc:
        msg = str(exc) if isinstance(exc, (PermissionError, ValueError)) else f"Drafting failed ({type(exc).__name__})"
        log.error("draft job %s failed: %s", job_id, type(exc).__name__)
        try:
            await repo.job_update(job_id, "failed", error=msg[:300])
        except Exception:
            log.error("could not record failure for job %s", job_id)


def start(job_id, cid, user: User) -> None:
    task = asyncio.create_task(_run(job_id, cid, user))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def cancel_all() -> None:
    for t in list(_tasks):
        t.cancel()
