"""Optional "Ask Genie about this figure" panel (feature-flagged by GENIE_SPACE_ID). Runs as the user (`genie` scope),
so Genie respects the user's permissions. Start, then poll — no long-held requests through the proxy."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException

from .. import workspace
from ..auth import User, current_user
from ..config import get_settings
from ..models import GenieAsk

router = APIRouter(tags=["genie"])
_ID = re.compile(r"^[A-Za-z0-9_\-]{6,80}$")


def _space() -> str:
    space = get_settings().genie_space_id
    if not space:
        raise HTTPException(status_code=404, detail="Genie panel is not enabled")
    return space


@router.post("/genie/ask")
def ask(body: GenieAsk, user: User = Depends(current_user)):
    space = _space()
    question = body.question if not body.figure_key else f"{body.question} (figure {body.figure_key})"
    msg = workspace.user_rest(user, "POST", f"/api/2.0/genie/spaces/{space}/start-conversation",
                              {"content": question})
    return {"conversation_id": msg.get("conversation_id"), "message_id": msg.get("message_id") or msg.get("id")}


@router.get("/genie/{conversation_id}/{message_id}")
def poll(conversation_id: str, message_id: str, user: User = Depends(current_user)):
    space = _space()
    if not (_ID.match(conversation_id) and _ID.match(message_id)):
        raise HTTPException(status_code=422, detail="invalid id")
    base = f"/api/2.0/genie/spaces/{space}/conversations/{conversation_id}/messages/{message_id}"
    msg = workspace.user_rest(user, "GET", base)
    out = {"status": msg.get("status"), "text": None, "sql": None, "columns": [], "rows": []}
    for att in msg.get("attachments") or []:
        if att.get("text"):
            out["text"] = att["text"].get("content")
        if att.get("query"):
            out["sql"] = att["query"].get("query")
            out["text"] = out["text"] or att["query"].get("description")
            if msg.get("status") == "COMPLETED" and att.get("attachment_id"):
                res = workspace.user_rest(user, "GET", f"{base}/attachments/{att['attachment_id']}/query-result")
                sr = res.get("statement_response") or {}
                cols = [c.get("name") for c in (sr.get("manifest") or {}).get("schema", {}).get("columns", [])]
                out["columns"] = cols
                out["rows"] = ((sr.get("result") or {}).get("data_array") or [])[:20]
    return out
