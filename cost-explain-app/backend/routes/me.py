"""Current user, roles and feature flags."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from .. import roles, workspace
from ..auth import User, current_user
from ..config import get_settings
from ..models import Me

router = APIRouter(tags=["me"])


@router.get("/me", response_model=Me)
async def me(user: User = Depends(current_user)):
    settings = get_settings()
    info = await run_in_threadpool(roles.resolve, user)
    host = workspace.host()
    return Me(email=user.email, display_name=info.get("display_name"), roles=info["roles"],
              is_analyst=info["is_analyst"], is_approver=info["is_approver"], workspace_host=host,
              features={"genie": bool(settings.genie_space_id), "agent": bool(settings.agent_endpoint),
                        "demo_reset": settings.demo_mode},
              data_mode=settings.data_mode, default_comparison=settings.default_comparison)
