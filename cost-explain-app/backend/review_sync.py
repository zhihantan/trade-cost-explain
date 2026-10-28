"""Event-driven replication to Unity Catalog: after a submit / approve / reject, ask the `ce_review_sync` job to run
(as the app service principal, which holds CAN_MANAGE_RUN through the app's job resource). A daily schedule on the
job is the backstop. Missing job or permission = silently skipped (the operational write already succeeded)."""
from __future__ import annotations

import asyncio
import logging
import os
import time

from .workspace import sp_config

log = logging.getLogger("cost_explain.review_sync")

JOB_NAME = os.environ.get("REVIEW_SYNC_JOB_NAME", "ce_review_sync")
_state = {"job_id": None, "looked_up": 0.0, "last_run": 0.0}


def _run_now() -> None:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(config=sp_config())
    now = time.time()
    if _state["job_id"] is None and now - _state["looked_up"] > 300:
        _state["looked_up"] = now
        job = next(iter(w.jobs.list(name=JOB_NAME, limit=1)), None)
        _state["job_id"] = job.job_id if job else None
    if _state["job_id"] is None:
        return
    if now - _state["last_run"] < 20:  # debounce bursts; the job queues and is idempotent anyway
        return
    _state["last_run"] = now
    w.jobs.run_now(job_id=_state["job_id"])
    log.info("triggered %s (job %s)", JOB_NAME, _state["job_id"])


def trigger() -> None:
    async def _go():
        try:
            await asyncio.to_thread(_run_now)
        except Exception as exc:
            log.info("review sync trigger skipped: %s", type(exc).__name__)

    asyncio.get_running_loop().create_task(_go())
