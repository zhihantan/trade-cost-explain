"""Ask the Genie space a question via the Conversation API; print SQL, text and result rows."""
import json
import sys
import time

from databricks.sdk import WorkspaceClient

SPACE = "01f1cda9f4a9153882ea4c4ecda34bc3"
w = WorkspaceClient(profile="fe-vm-zh-serverless")


def do(method, path, body=None, query=None):
    for attempt in range(4):
        try:
            return w.api_client.do(method, path, body=body, query=query)
        except Exception as e:
            if "IP ACL" in str(e) and attempt < 3:
                time.sleep(30); continue
            raise


def ask(question: str, conversation_id: str | None = None) -> dict:
    if conversation_id:
        m = do("POST", f"/api/2.0/genie/spaces/{SPACE}/conversations/{conversation_id}/messages", {"content": question})
        cid, mid = conversation_id, m["id"] if "id" in m else m["message_id"]
    else:
        m = do("POST", f"/api/2.0/genie/spaces/{SPACE}/start-conversation", {"content": question})
        cid, mid = m["conversation_id"], m["message_id"]
    t0 = time.time()
    while True:
        msg = do("GET", f"/api/2.0/genie/spaces/{SPACE}/conversations/{cid}/messages/{mid}")
        if msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED") or time.time() - t0 > 240:
            break
        time.sleep(3)
    out = {"conversation_id": cid, "status": msg.get("status"), "error": msg.get("error"), "sql": None, "text": None, "rows": None,
           "columns": None, "seconds": round(time.time() - t0)}
    for a in msg.get("attachments") or []:
        if a.get("query"):
            out["sql"] = a["query"].get("query")
            try:
                res = do("GET", f"/api/2.0/genie/spaces/{SPACE}/conversations/{cid}/messages/{mid}/attachments/{a['attachment_id']}/query-result")
                sr = res.get("statement_response", {})
                out["columns"] = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
                out["rows"] = (sr.get("result", {}) or {}).get("data_array")
            except Exception as e:
                out["rows"] = f"result fetch failed: {e}"
        if a.get("text"):
            out["text"] = a["text"].get("content")
    return out


if __name__ == "__main__":
    r = ask(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(r, indent=1, ensure_ascii=False)[:6000])
