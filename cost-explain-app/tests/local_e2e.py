"""Local end-to-end exercise of the API (APP_ENV=local, fixtures, real Lakebase in a dev schema)."""
import os, time, json
os.environ.update(APP_ENV="local", DATA_MODE="fixtures", LAKEBASE_SCHEMA=os.environ.get("LAKEBASE_SCHEMA", "cost_explain_app_local"),
                  LOCAL_USER_EMAIL="zhihan.tan@databricks.com", WAREHOUSE_ID="5f36ded0f9befdd1")
from fastapi.testclient import TestClient
from backend.main import app

H = {"X-Requested-With": "cost-explain-app"}
with TestClient(app) as c:
    for _ in range(60):
        r = c.get("/api/commentary")
        if r.status_code == 200: break
        time.sleep(1)
    print("list", r.status_code, [(x["period"], x["status"], x["author_email"]) for x in r.json()])
    print("me", c.get("/api/me").json())
    print("comparisons", [x["comparison_id"] for x in c.get("/api/comparisons").json()])
    fx = c.get("/api/flux", params={"period": "MOM_2026-09", "slice": "APAC"}).json()
    print("flux totals", fx["totals"], "effects", [(e["effect"], e["amount"]) for e in fx["effects"]], "source", fx["source"])
    print("flux ED rows", [(r["key"], r["flux"]) for r in c.get("/api/flux", params={"period": "MOM_2026-09", "slice": "ED_EXCH_CLR"}).json()["rows"]])
    print("figure", c.get("/api/figures/MOM_2026-09|APAC|VOLUME").json()["value"], c.get("/api/figures/nope|x|y").status_code)
    print("csrf-missing", c.post("/api/commentary", json={"period": "MOM_2026-09", "slice_key": "ED_EXCH_CLR"}).status_code)
    cr = c.post("/api/commentary", json={"period": "MOM_2026-09", "slice_key": "ED_EXCH_CLR"}, headers=H)
    print("create", cr.status_code); cm = cr.json(); cid = cm["id"]
    d = c.post(f"/api/commentary/{cid}/draft", headers=H); print("draft", d.status_code, d.json())
    jid = d.json()["job_id"]
    for _ in range(30):
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("succeeded", "failed"): break
        time.sleep(1)
    print("job", j["status"], j.get("error"), j.get("result"))
    det = c.get(f"/api/commentary/{cid}").json()
    print("detail v", det["version"], det["status"], "figs", len(det["figures"]), det["permissions"], det["blockers"])
    print(det["edited_text"][:600])
    stale = c.put(f"/api/commentary/{cid}", json={"version": 1, "edited_text": "x"}, headers=H); print("stale put", stale.status_code, stale.json())
    txt = det["edited_text"] + "\n\nAnalyst note: confirmed with the HK derivatives desk."
    up = c.put(f"/api/commentary/{cid}", json={"version": det["version"], "edited_text": txt}, headers=H); print("put", up.status_code, up.json()["version"])
    bad = c.put(f"/api/commentary/{cid}", json={"version": up.json()["version"], "edited_text": txt + " [[fig:MOM_2026-09|APAC|NOPE]]"}, headers=H); print("bad fig", bad.status_code, bad.json())
    sb = c.post(f"/api/commentary/{cid}/submit", json={"version": up.json()["version"]}, headers=H); print("submit", sb.status_code, sb.json()["status"])
    ap = c.post(f"/api/commentary/{cid}/approve", json={"version": up.json()["version"]}, headers=H); print("self-approve", ap.status_code, ap.json())
    q = c.get("/api/approvals").json(); print("queue", [(x["period"], x["slice_key"], x["author_email"]) for x in q])
    seeded = [x for x in q if x["author_email"].startswith("ava")][0]
    ok = c.post(f"/api/commentary/{seeded['id']}/approve", json={"version": seeded["version"], "note": "Approved for CFO pack"}, headers=H); print("approve seeded", ok.status_code, ok.json()["status"])
    imm = c.put(f"/api/commentary/{seeded['id']}", json={"version": seeded["version"], "edited_text": "tamper"}, headers=H); print("edit approved", imm.status_code, imm.json())
    rj = c.post(f"/api/commentary/{seeded['id']}/reject", json={"version": seeded["version"], "note": "x"}, headers=H); print("reject short note", rj.status_code)
    au = c.get("/api/audit", params={"commentary_id": seeded["id"]}).json()
    print("audit", [(e["action"], e["actor_email"], e["version"]) for e in au["events"]], "versions", [v["version"] for v in au["versions"]], "fig versions", list(au["figures_by_version"].keys()))
    rs = c.post("/api/admin/demo-reset", headers=H); print("reset", rs.status_code, rs.json())
    print("after reset", [(x["period"], x["status"]) for x in c.get("/api/commentary").json()])
