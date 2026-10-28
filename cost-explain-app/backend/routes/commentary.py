"""Commentary CRUD and drafting. Writes run as the app service principal and record the human actor."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from .. import drafting, gold, migrations, repo, review_sync, roles, template
from ..auth import User, current_user
from ..models import (Commentary, CommentaryCreate, CommentaryDetail, CommentaryFigure, CommentaryUpdate,
                      DraftAccepted, VersionedAction)

router = APIRouter(tags=["commentary"])


def _actor(user: User) -> repo.Actor:
    return repo.Actor(user.email, user.request_id)


def _permissions(row: dict, info: dict, email: str) -> tuple[dict, dict]:
    status = row["status"]
    editable = status in ("draft", "rejected")
    perms = {
        "edit": info["is_analyst"] and editable,
        "draft": info["is_analyst"] and editable,
        "submit": info["is_analyst"] and status == "draft" and bool((row.get("edited_text") or "").strip()),
        "decide": False,
    }
    blockers: dict[str, str] = {}
    if status == "in_review":
        blocker = repo.four_eyes_blocker(row, email)
        if not info["is_approver"]:
            blockers["decide"] = "Requires the approver role"
        elif blocker:
            blockers["decide"] = blocker
        else:
            perms["decide"] = True
    if not info["is_analyst"]:
        blockers["edit"] = "Requires the analyst role"
    elif not editable:
        blockers["edit"] = f"Commentary is {status.replace('_', ' ')}" + (" and immutable" if status == "approved" else "")
    return perms, blockers


@router.get("/commentary", response_model=list[Commentary])
async def list_commentary(status: Optional[str] = Query(None, pattern="^(draft|in_review|approved|rejected)$"),
                          user: User = Depends(current_user)):
    await migrations.wait_ready()
    return await repo.list_(status)


@router.post("/commentary", response_model=Commentary, status_code=201)
async def create_commentary(body: CommentaryCreate, user: User = Depends(current_user)):
    await run_in_threadpool(roles.require, user, "analyst")
    await migrations.wait_ready()
    comps = {c.comparison_id: c for c in await run_in_threadpool(gold.comparisons, user)}
    comp = comps.get(body.period)
    if comp is None:
        raise HTTPException(status_code=404, detail="Unknown comparison")
    title = body.title or f"{comp.p1_label} close — {gold.slice_label(body.slice_key)}"
    return await repo.create(body.period, body.slice_key, title, _actor(user))


@router.get("/commentary/{cid}", response_model=CommentaryDetail)
async def get_commentary(cid: UUID, user: User = Depends(current_user)):
    await migrations.wait_ready()
    row = await repo.get(cid)
    info = await run_in_threadpool(roles.resolve, user)
    figs = await repo.figures(cid, row["version"])
    perms, blockers = _permissions(row, info, user.email)
    return CommentaryDetail(**row, figures=[CommentaryFigure(**f) for f in figs], permissions=perms,
                            blockers=blockers)


@router.put("/commentary/{cid}", response_model=Commentary)
async def save_commentary(cid: UUID, body: CommentaryUpdate, user: User = Depends(current_user)):
    await run_in_threadpool(roles.require, user, "analyst")
    await migrations.wait_ready()
    current = await repo.get(cid)
    prior = {f["figure_key"]: f for f in await repo.figures(cid, current["version"])}
    keys = template.chip_keys(body.edited_text)
    new_keys = [k for k in keys if k not in prior]
    resolved: list[dict] = [prior[k] for k in keys if k in prior]  # keep the snapshot the numbers came from
    if new_keys:
        snaps, unknown = await run_in_threadpool(drafting.resolve_cited, user,
                                                 " ".join(f"[[fig:{k}]]" for k in new_keys), {})
        if unknown:
            raise HTTPException(status_code=422, detail={"message": "Unknown figure references",
                                                         "figure_keys": unknown})
        resolved += snaps
    return await repo.save_edit(cid, body.version, body.edited_text, body.title, resolved, _actor(user))


@router.post("/commentary/{cid}/draft", response_model=DraftAccepted, status_code=202)
async def draft_commentary(cid: UUID, user: User = Depends(current_user)):
    await run_in_threadpool(roles.require, user, "analyst")
    await migrations.wait_ready()
    job = await repo.create_job(cid, _actor(user))
    drafting.start(job["job_id"], cid, user)
    return DraftAccepted(job_id=job["job_id"], status=job["status"])


@router.post("/commentary/{cid}/submit", response_model=Commentary)
async def submit_commentary(cid: UUID, body: VersionedAction, user: User = Depends(current_user)):
    await run_in_threadpool(roles.require, user, "analyst")
    await migrations.wait_ready()
    row = await repo.submit(cid, body.version, body.note, _actor(user))
    review_sync.trigger()
    return row
