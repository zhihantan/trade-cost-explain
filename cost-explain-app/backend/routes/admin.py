"""Demo affordance: reset the review store to the seeded storyline (APP_DEMO_MODE only, approvers only).
Truncating the append-only audit log is never acceptable outside a demo environment."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from .. import migrations, repo, roles, seed
from ..auth import User, current_user
from ..config import get_settings

router = APIRouter(tags=["admin"])
log = logging.getLogger("cost_explain.admin")


@router.post("/admin/demo-reset")
async def demo_reset(user: User = Depends(current_user)):
    if not get_settings().demo_mode:
        raise HTTPException(status_code=404, detail="Not found")
    await run_in_threadpool(roles.require, user, "approver")
    await migrations.wait_ready()
    await repo.truncate_all()
    n = await seed.seed(user=user, force=True)
    log.warning("DEMO RESET by %s request_id=%s (seeded %s items)", user.email, user.request_id, n)
    return {"seeded": n}
