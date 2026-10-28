"""Draft job polling. State is read from Lakebase every time (multi-instance and restart safe)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from .. import migrations, repo
from ..auth import current_email
from ..models import Job

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: UUID, _: str = Depends(current_email)):
    await migrations.wait_ready()
    return await repo.get_job(job_id)
