# 06 — Databricks App: deployed and smoke-tested

App `cost-explain-app` (React + Vite frontend, FastAPI backend; `cost-explain-app/app.yaml`,
`resources/cost_explain_app.app.yml`). Reads Gold with the **signed-in user's** token (row filters apply), writes reviews
to Lakebase as the app service principal, records `actor_email` on every write, and fails closed.

Smoke-test findings, verified in workspace `fe-vm-zh-serverless` on 2026-10-22; copied from `docs/APP.md` §1.

| Check | Result |
|---|---|
| Build sequence | uv installs from `uv.lock` ("Dependencies installed successfully with uv"), then `npm install`, then `npm run build` (Vite builds `frontend/dist` on the platform), then the `command` from `app.yaml`. 14 s end to end |
| Start command | `["uvicorn","backend.main:app"]` works with no host/port flags: runtime sets `UVICORN_HOST=0.0.0.0`, `UVICORN_PORT=8000` (= `DATABRICKS_APP_PORT`) |
| Proxy / H2C | Proxy serves HTTP/2 to clients; uvicorn behind it needs no changes. `/api/health` 200 |
| Forwarded headers | `x-forwarded-email`, `x-forwarded-access-token`, `x-forwarded-user`, `x-forwarded-preferred-username`, `x-forwarded-host`, `x-forwarded-proto`, `x-real-ip`, `x-request-id` |
| User-token SQL | Works (`current_user()` = the signed-in user, named parameters bind). `databricks-sql-connector` 4.x does **not** ship pyarrow: use `fetchall()`, not `fetchall_arrow().to_pylist()` (the spec snippet fails) |
| Lakebase | OAuth via `w.postgres.generate_database_credential(endpoint=...)`, PG 17.11, ~10 ms round trip (details in `03`) |
| Scopes | `iam.current-user:read` cannot be requested explicitly ("not a valid scope"); it is added automatically as a default. Valid names: `sql`, `model-serving`, `genie` |
| Package registries | Laptops resolve through Databricks-internal proxies; lock files must point at public registries for the Apps runtime. `scripts/normalize_locks.py` rewrites hosts (same artefacts, same hashes) |

Screens (Flux overview, Commentary review, Approvals with four-eyes, Audit trail) are captured in `docs/design/*.png`.
