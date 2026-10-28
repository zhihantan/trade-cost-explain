"""Approve / reject with a reason. Four-eyes: the author (or last editor) cannot decide their own item."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from .. import migrations, repo, review_sync, roles
from ..auth import User, current_user
from ..models import Commentary, RejectAction, VersionedAction

router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=list[Commentary])
async def queue(user: User = Depends(current_user)):
    await migrations.wait_ready()
    return await repo.list_("in_review")


@router.post("/commentary/{cid}/approve", response_model=Commentary)
async def approve(cid: UUID, body: VersionedAction, user: User = Depends(current_user)):
    await run_in_threadpool(roles.require, user, "approver")
    await migrations.wait_ready()
    row = await repo.decide(cid, body.version, True, body.note, repo.Actor(user.email, user.request_id))
    review_sync.trigger()
    return row


@router.post("/commentary/{cid}/reject", response_model=Commentary)
async def reject(cid: UUID, body: RejectAction, user: User = Depends(current_user)):
    await run_in_threadpool(roles.require, user, "approver")
    await migrations.wait_ready()
    row = await repo.decide(cid, body.version, False, body.note, repo.Actor(user.email, user.request_id))
    review_sync.trigger()
    return row
