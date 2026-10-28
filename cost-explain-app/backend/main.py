# backend/main.py — FastAPI app: REST API under /api, compiled React bundle for every other path.
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db_lakebase, drafting, migrations, security, seed
from .routes import admin, approvals, audit, commentary, flux, genie, health, jobs, me

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cost_explain")

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


async def _bootstrap() -> None:
    """Schema migrations and demo seed run in the background so startup stays light; requests that need the
    review store wait until both are done."""
    await migrations.run(after=seed.seed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_lakebase.open_pool()      # fresh OAuth token per connection (tokens last about an hour)
    boot = asyncio.create_task(_bootstrap())
    yield
    boot.cancel()
    await drafting.cancel_all()
    await db_lakebase.close_pool()     # must finish well inside the 15 s SIGTERM window


app = FastAPI(title="Trade Cost Explain — review & approval", lifespan=lifespan)
security.install(app)
for r in (health, me, flux, commentary, approvals, jobs, audit, genie, admin):
    app.include_router(r.router, prefix="/api")

if DIST.exists():                      # absent during local backend-only work
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(DIST / "index.html")
