# 03 — Lakebase: the review and approval loop, end to end

**What runs.** Lakebase Autoscaling project `cost-explain-db` (PG 17; `resources/cost_explain_db.postgres_project.yml`)
is the transactional store behind the review app. Schema `cost_explain_app` (created and owned by the app service
principal at startup): `commentary` (state, version, author / editor / submitter / decider) · `commentary_version` ·
`commentary_figure` (figure snapshot per version) · `approval_event` (append-only, `request_id`) · `draft_job`.
Approved history is replicated to Unity Catalog (`cost_explain.review.*`) by job `ce_review_sync`.

Recorded in workspace `fe-vm-zh-serverless` on 2026-10-22; copied from `docs/APP.md` §1 and §1b.

| Check | Result |
|---|---|
| Lakebase connection | `valueFrom: postgres` injects the **endpoint path** (`projects/cost-explain-db/branches/production/endpoints/primary`); `PGHOST`/`PGDATABASE`/`PGUSER` (= SP client id)/`PGPORT`/`PGSSLMODE`/`PGAPPNAME` also injected. OAuth via `w.postgres.generate_database_credential(endpoint=...)`, PG 17.11, ~10 ms round trip |
| UC review history | `01_merge_review.sql` + `02_figure_evidence_view.sql` run on live Gold; `review.v_commentary_figure_evidence` = 82/82 figures `TIES` after the final demo reset |
| Event-driven sync | Re-tested 2026-10-22 on the current build: approve in the app → `ce_review_sync` run started 3 s later (app service principal) → UC shows the approval 35 s after the click. The evidence view lists current items only, so figures of items removed by a demo reset stay in the append-only history but do not appear as blank rows |

**The loop this proves:** Gold (Lakeflow) → agent draft with figure chips → analyst edits in the app → submit →
a different approver decides (four-eyes enforced; self-approval blocked) → every write lands in Lakebase with an
audit event → `ce_review_sync` MERGEs it into Unity Catalog → `v_commentary_figure_evidence` re-checks every cited
figure against Gold (82/82 tie).
