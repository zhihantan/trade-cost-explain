"""Append-only event history plus per-version text and figure snapshots (which data each figure came from)."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from .. import migrations, repo
from ..auth import current_email
from ..models import AuditEvent, AuditResponse, Commentary, CommentaryFigure, CommentaryVersion

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditResponse)
async def audit(commentary_id: Optional[UUID] = Query(None), _: str = Depends(current_email)):
    await migrations.wait_ready()
    events, versions = await repo.audit(commentary_id)
    commentary = None
    figures_by_version: dict[int, list[CommentaryFigure]] = {}
    if commentary_id:
        commentary = Commentary(**(await repo.get(commentary_id)))
        for f in await repo.figures(commentary_id):
            figures_by_version.setdefault(int(f["version"]), []).append(CommentaryFigure(**f))
    return AuditResponse(commentary=commentary, events=[AuditEvent(**e) for e in events],
                         versions=[CommentaryVersion(**v) for v in versions], figures_by_version=figures_by_version)
