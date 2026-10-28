# Review & approval app — `cost-explain-app`

React 18 + Vite 5 (TypeScript) frontend and FastAPI backend, deployed as one Databricks App, with Lakebase
Autoscaling as the transactional store. Spec: master prompt §4. Contracts: `docs/CONTRACTS.md`.

| | |
|---|---|
| URL | https://cost-explain-app-2515635694809473.aws.databricksapps.com |
| App service principal | `app-1nohrb cost-explain-app` · client id `70edd126-8c11-4302-b0d4-8c7d644c3425` (also its Postgres role) |
| Resources | `sql-warehouse` → `cost-explain-wh` (CAN_USE) · `postgres` → `cost-explain-db/production/databricks-postgres` (CAN_CONNECT_AND_CREATE) · `serving-endpoint` → `ce-commentary-agent` (CAN_QUERY) |
| Mode | `DATA_MODE=live` (Gold only, no fixture fallback) · `AGENT_ENDPOINT` via `valueFrom: serving-endpoint` · `AGENT_TIMEOUT_S=180` |
| User API scopes | requested `sql`, `model-serving`, `genie` · effective adds `iam.current-user:read`, `iam.access-control:read` |
| Source in workspace | `/Workspace/Users/zhihan.tan@databricks.com/apps/cost-explain-app` (CLI deploys until bound into the bundle) |

## 1. Smoke-test findings (spec Appendix B), verified in `fe-vm-zh-serverless` on 2026-10-22

| Check | Result |
|---|---|
| Build sequence | uv installs from `uv.lock` ("Dependencies installed successfully with uv"), then `npm install`, then `npm run build` (Vite builds `frontend/dist` on the platform), then the `command` from `app.yaml`. 14 s end to end |
| Start command | `["uvicorn","backend.main:app"]` works with no host/port flags: runtime sets `UVICORN_HOST=0.0.0.0`, `UVICORN_PORT=8000` (= `DATABRICKS_APP_PORT`) |
| Proxy / H2C | Proxy serves HTTP/2 to clients; uvicorn behind it needs no changes. `/api/health` 200 |
| Forwarded headers | `x-forwarded-email`, `x-forwarded-access-token`, `x-forwarded-user`, `x-forwarded-preferred-username`, `x-forwarded-host`, `x-forwarded-proto`, `x-real-ip`, `x-request-id` |
| User-token SQL | Works (`current_user()` = the signed-in user, named parameters bind). `databricks-sql-connector` 4.x does **not** ship pyarrow: use `fetchall()`, not `fetchall_arrow().to_pylist()` (the spec snippet fails) |
| Lakebase | `valueFrom: postgres` injects the **endpoint path** (`projects/cost-explain-db/branches/production/endpoints/primary`); `PGHOST`/`PGDATABASE`/`PGUSER` (= SP client id)/`PGPORT`/`PGSSLMODE`/`PGAPPNAME` also injected. OAuth via `w.postgres.generate_database_credential(endpoint=...)`, PG 17.11, ~10 ms round trip |
| Scopes | `iam.current-user:read` cannot be requested explicitly ("not a valid scope"); it is added automatically as a default. Valid names: `sql`, `model-serving`, `genie` (older names `serving.serving-endpoints` / `dashboards.genie` are superseded) |
| Package registries | Laptops resolve through Databricks-internal proxies (`pypi-proxy` / `npm-proxy.cloud.databricks.com`); lock files must point at public registries for the Apps runtime. `scripts/normalize_locks.py` rewrites hosts (same artefacts, same hashes) — run after every `uv lock` / `npm install` |
| CLI gotcha | `databricks apps deploy` **without** an app name inside a bundle tree runs the whole bundle pipeline. Always pass the app name (or run from outside the repo) |

## 1b. Live-Gold verification (2026-10-22)

| Check | Result |
|---|---|
| Flux `MOM_2026-09` / APAC | US$5.0M → US$6.2M; Volume +900 · Mix +190 · Rate +100 · Fails +150 · Timing −50 · FX −100 · Fixed 0 · Unexplained +10 (US$K); slice table ties to the chart |
| Flux `MOM_2026-09` / ED_EXCH_CLR | 2,170 → 2,680; +390 · +90 · +60 · 0 · −20 · −10 |
| Effect order | Follows the scene-2 narrative order (`gold.cost_flux_effects.effect_order`): VOLUME, MIX, RATE, FAILS, TIMING, FX, FIXED, UNEXPLAINED |
| Data snapshot | Gold objects are pipeline **materialized views**: `DESCRIBE HISTORY` fails (`EXPECT_TABLE_NOT_VIEW`). The app falls back to `DESCRIBE TABLE EXTENDED` → *Refresh Information* and stores `snapshot_ref = pipeline:<pipeline_id>/update:<update_id>` + `as_of_ts` = last refresh (`delta_version` stays null). Column `commentary_figure.snapshot_ref` added (Lakebase + UC replica) |
| Figure keys | `CAT:<cost_category>` keys (spaces, `&`, `()`) resolve in chips and `/api/figures`; Kestrel hotspot `FAILS|2026-09|AUCE|C001|NET` = US$143K; `UNEXPLAINED_THRESHOLD` cited (APAC US$60K = 5% of the change, ED US$25.5K) |
| Entitlements | Row filter `gold.ce_desk_scope` on `desk_code`. The pre-check now requires **full** visibility of the slice: it calls `ce_desk_scope(d)` as the user for every desk in the slice (static hierarchy), falling back to visible-desk comparison. A desk head (HKED only) can draft `ED_EXCH_CLR` / `DESK:HKED` but not `APAC` (unit-tested; the agent may read Gold under its own principal) |
| Agent draft end to end | `ce-commentary-agent` (model v2, `databricks-claude-sonnet-5-5`): 41–52 s per draft, 14–16 chips, all resolved, no value mismatches; edit → v3 → submit → four-eyes block on self-approval → audit. Early probes returned an empty message / `EXECUTE on get_cost_bridge` error; the template fallback covered them transparently |
| UC review history | `01_merge_review.sql` + `02_figure_evidence_view.sql` run on live Gold; `review.v_commentary_figure_evidence` = 82/82 figures `TIES` after the final demo reset |
| Event-driven sync | Re-tested 2026-10-22 on the current build: approve in the app → `ce_review_sync` run started 3 s later (app service principal) → UC shows the approval 35 s after the click. The evidence view lists current items only, so figures of items removed by a demo reset stay in the append-only history but do not appear as blank rows |

## 2. Identity model (as built)

| Action | Identity | How |
|---|---|---|
| Flux, figures, Delta versions, entitlement pre-check (SQL warehouse) | **User** (OBO token, `sql` scope) | `db_sql.query_as_user`; UC row filters / masks apply |
| Roles (analyst / approver) | **User** | SCIM `Me` with the forwarded token (default `iam.current-user:read`); fallback `is_account_group_member()` in SQL |
| Draft commentary (agent endpoint) | **User** (`model-serving` scope) | Direct REST call with the user's token; falls back to the deterministic template drafter on 404/error |
| Ask Genie (feature flag) | **User** (`genie` scope) | Start-conversation, then poll |
| Commentary, figures, approvals, draft jobs (Lakebase) | **App SP** | psycopg async pool, OAuth token per connection, `actor_email` from `X-Forwarded-Email` + `request_id` on every write |
| Trigger UC replication after submit / decision | **App SP** | `jobs.run_now` on `ce_review_sync` (job resource grants CAN_MANAGE_RUN); skipped silently if absent |

Fail closed: no forwarded token → 401; never falls back to the SP for user reads. `DATA_MODE=auto` substitutes fixture
data only when a Gold object **does not exist** — never on permission errors.

## 3. Controls

- **Four-eyes:** approve/reject requires `ce_fpa_approvers` and actor ≠ author **and** actor ≠ last editor (maker ≠ checker), enforced in the API and repeated in the UPDATE predicate.
- **Immutability:** approved commentary cannot change (API 409 + Postgres trigger). `approval_event`, `commentary_version`, `commentary_figure` are append-only (triggers reject UPDATE/DELETE).
- **Optimistic concurrency:** every save/submit/decision carries `version`; mismatch → 409 with `current_version` (UI conflict banner, edits kept).
- **Reproducible figures:** each version snapshots every cited figure (`figure_key`, value, unit, source table, filter, Delta version, as-of) — unknown figure keys are rejected on save and reported by the drafter; agent values are checked against the Gold registry.
- **HTTP hardening:** CSRF header (`X-Requested-With: cost-explain-app`) + same-host `Origin` check on mutating calls, parameterized SQL, allow-listed identifiers, Pydantic validation, global handler without stack traces, request id echoed, tokens never logged, pool closed within the 15 s SIGTERM window.
- **Async drafting:** `POST /draft` → 202 + job id; UI polls `GET /api/jobs/{id}` every 2 s; state in Lakebase (multi-instance and restart safe; orphaned jobs fail after 4 min of no heartbeat).
- **Demo reset** (`APP_DEMO_MODE=true`, approvers only): truncates the operational store and reseeds the storyline from the **live** figure registry (texts for July/August are re-drafted from live figures, so text and chips always agree). UC replicas are append-only, so history survives a reset — drop and rebuild them (`01_merge_review.sql`) if you want a clean rehearsal state. Set `APP_DEMO_MODE=false` outside demos.
- **Template drafter scope:** invoice findings (vendors span desks) are cited only in APAC / Rest-of-APAC commentary; the fail hotspot only where the desk is in scope.

## 4. Lakebase schema `cost_explain_app` (created and owned by the app SP at startup)

`commentary` (state, version, texts, author/editor/submitter/decider) · `commentary_version` (text per version) ·
`commentary_figure` (figure snapshot per version, incl. `delta_version`, `as_of_ts`) · `approval_event` (append-only,
`request_id`) · `draft_job` (job state). `REPLICA IDENTITY FULL` on all tables (ready for Lakehouse Sync if it becomes
available for this catalog). Migrations take an advisory lock; requests wait until migrations **and** the demo seed finish.

**Seed:** July and August APAC commentary (approved by `priya.raman@meridian-demo.example`) and the September APAC commentary
by `ava.chen@meridian-demo.example`, `in_review`, so the presenter can approve it without breaching four-eyes.

## 5. Review history in Unity Catalog (Lakehouse Sync fallback)

- Lakebase database registered in UC as **`cost_explain_lakebase`** (`databricks postgres create-catalog`).
- Job **`ce_review_sync`** (`resources/ce_review_sync.job.yml`, SQL file task on `cost-explain-wh`) MERGEs into
  `cost_explain.review.commentary` (current state) and append-only `commentary_version`, `commentary_figure`,
  `approval_event`. Triggered by the app after each submit/decision; daily 02:00 SGT backstop.
- **After Gold is live**, run `src/review_sync/02_figure_evidence_view.sql` once: `review.v_commentary_figure_evidence`
  joins every cited figure to `gold.commentary_figures` (`TIES` / `CHANGED` / `NOT_IN_REGISTRY`) and gives the
  scene-8 lineage path commentary figure → Gold → Silver → Bronze.

## 6. Screens

1. **Flux overview** — comparison + slice selectors, KPI tiles, Recharts waterfall and slice table from one payload (`/api/flux`), breakdown by business / desk / cost category / vendor / market / entity / currency, data source + Delta version footnote, "Draft commentary".
2. **Commentary review** — rendered commentary with figure chips, edit mode, "Draft with agent" (async), save / submit, approve / reject for approvers, cited-figure panel (source table, filter, Delta version, UC + lineage links, optional Ask Genie), history; version-conflict banner and unsaved-changes guard.
3. **Approval queue** — in-review items, approve / reject with reason, four-eyes blockers explained inline.
4. **Audit trail** — event log (actor, version, status transition, request id, note), version texts, per-version figure snapshots.

### Design and themes (2026-10-23)
- Full redesign — sidebar shell, sticky page headers, Explain-the-change panel, tabbed review rail, approval cards —
  with **five themes** to vet (Marunouchi, Otemachi Night, Washi, Kon, Sumi). Pick one in the sidebar or with
  `?theme=<key>`. Design rationale, palettes, validation results and screenshots: [`docs/DESIGN.md`](DESIGN.md).
- No synthetic-data banner or disclaimers in the app, the Genie instructions, the agent prompt or the dashboard.

### Responsiveness (2026-10-23)
- The first screen loads in parallel: `/api/me` carries `default_comparison` (`DEFAULT_COMPARISON`, default
  `MOM_2026-09`), so the bridge no longer waits for the comparison list. After 4 s the page says the SQL warehouse
  is starting; switching slices keeps the previous view, dimmed, instead of flashing skeletons.
- Gold reads are cached per signed-in user (row filters make them identity-specific): comparisons and slices
  10 min, bridge and figures 2 min; concurrent requests share one load. Figures load a comparison (or a findings
  period) at a time because every query on the `commentary_figures` view costs ~4 s however narrow the filter.
  Snapshot labels skip `DESCRIBE HISTORY` on materialized views and run alongside the bridge query.
- Measured: bridge 2.4–4.6 s → 0.9 s repeat (most of it network); figure details 7.7 s → 0.9 s after the first
  in a comparison; cold first paint ~31 s → about 15 s (estimated from API timings: one warehouse start instead of
  two queries in sequence).

## 7. Local development

```bash
cd cost-explain-app
uv venv .venv --python 3.11 && uv export --frozen --no-hashes --no-emit-project --all-groups > /tmp/req.txt \
  && uv pip install -r /tmp/req.txt --python .venv/bin/python        # installs the locked versions via the local proxy
npm install && npm run build                                          # or `npm run dev:frontend` (Vite :5173 proxies /api)
APP_ENV=local DATA_MODE=fixtures LAKEBASE_SCHEMA=cost_explain_app_local LOCAL_USER_EMAIL=<you> \
  WAREHOUSE_ID=5f36ded0f9befdd1 .venv/bin/uvicorn backend.main:app --reload --port 8000
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_unit.py         # fast unit checks
PYTHONPATH=. LAKEBASE_SCHEMA=cost_explain_app_local .venv/bin/python tests/local_e2e.py   # full API exercise
```
The dev-only middleware injects `X-Forwarded-*` from the `fe-vm-zh-serverless` CLI profile when `APP_ENV=local` and cannot
run when `APP_ENV=prod`. Use a separate Lakebase schema locally so the app SP keeps ownership of `cost_explain_app`.

## 8. Deploy

Until the app is bound into the bundle:
```bash
cd cost-explain-app && python3 scripts/normalize_locks.py && rm -rf frontend/dist
databricks sync . /Workspace/Users/zhihan.tan@databricks.com/apps/cost-explain-app --profile fe-vm-zh-serverless
cd /tmp && databricks apps deploy cost-explain-app \
  --source-code-path /Workspace/Users/zhihan.tan@databricks.com/apps/cost-explain-app --profile fe-vm-zh-serverless
```
Bundle integration (Lead SA): rename `resources/cost_explain_app.app.yml.pending` → `.yml`, then
`databricks bundle deployment bind cost_explain_app cost-explain-app --auto-approve`, then deploy and
`databricks bundle run cost_explain_app` (a bare `bundle deploy` leaves app compute stopped). When the agent endpoint and the
Genie space exist, uncomment their resources in the app YAML, switch `AGENT_ENDPOINT` / `GENIE_SPACE_ID` in `app.yaml` to
`valueFrom`, and set `DATA_MODE=live` once Gold is published (no silent fixture fallback during the demo).

## 9. Known limits / follow-ups

- `npm audit` reports 5 advisories in the pinned Vite 5 / esbuild toolchain (dev-server issues; not shipped at runtime). Revisit pins after the demo.
- Recharts 2.x is flagged deprecated upstream (spec pins `^2`); fine for the demo.
- The SQL connector opens a connection per request (~0.7 s on a warm warehouse); add a per-user connection cache if the demo feels slow.
- Pre-warm before the session: open the app (wakes compute and Lakebase), run one flux query (warms the warehouse).
