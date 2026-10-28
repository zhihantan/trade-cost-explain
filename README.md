# Trade Cost Explain — FP&A driver analytics on Databricks (APAC Global Markets edition)

A deployable demo of a **driver-based "cost explain"** for trade costs: APAC Global Markets trade costs rose
**US$5.0M → US$6.2M (+24%)** in September 2026, and the platform explains why in a bridge that adds up to the dollar
— volume +900, mix +190, rate +100, fails +150, timing −50, FX −100, unexplained +10 (US$K) — from the GL line down to
individual executions, with agent-drafted, analyst-approved commentary and Unity Catalog lineage as control evidence.

Synthetic entity **Meridian Group** (US GAAP, April–March fiscal year). **All numbers are illustrative**; venues,
brokers and planted fee changes are fictional (modelled on public HKEX / SGX / ASX / NSE-BSE fee structures).

## Six layers, one journey

| Layer | What it does here | Where |
|---|---|---|
| Lakeflow | SDP pipeline `ce_medallion`: Auto Loader bronze → silver with expectations → Gold materialized views; job `ce_build` ends with a 56-check tie-out gate | `src/pipeline/`, `resources/ce_medallion.pipeline.yml`, `resources/ce_build.job.yml` |
| Unity Catalog | Desk row filters on Gold, grants, metric views, recorded lineage | `src/governance/`, `src/metric_views/` |
| Lakebase | Review and approval store (drafts, versions, four-eyes approvals, audit), replicated back to Unity Catalog | `resources/cost_explain_db.postgres_project.yml`, `cost-explain-app/backend/db_lakebase.py`, `src/review_sync/` |
| Gen AI | Commentary agent (MLflow ResponsesAgent on Model Serving, UC function tools, figure chips); PDF fee extraction (`ai_parse_document` → `ai_extract`) | `src/agent/`, `src/extraction/` |
| Genie Agent | Space over the metric views and Gold, 11/11 benchmarks | `src/genie/`, `resources/cost_explain.genie_space.yml` |
| Databricks App | React + FastAPI review and approval app; reads with the signed-in user's token | `cost-explain-app/` |

## Proof it runs

Committed, text-readable evidence is in [`evidence/`](evidence/README.md): tie-out gate 56/56, 59 dashboard queries
re-run with 0 failures, the row filter tested as a desk-head persona (12 desks → 1), agent drafts with every figure chip
resolved, Genie 11/11, approve → Unity Catalog in 35 s, and on 2026-10-28 a local re-run (17 tests passed, independent
verifier PASS) plus a live re-check (tie-out 56/56 queried from Gold, agent eval PASSED 5/5). Decisions, trade-offs and where AI helped: [`BUILD.md`](BUILD.md).

| Document | What it covers |
|---|---|
| `BUILD_PLAN.md` | Architecture, decisions, data design, work breakdown, risks, deviation log |
| `docs/CONTRACTS.md` | Gold tables, figure registry, agent and app contracts |
| `docs/TALK_TRACK.md` | 30-minute run of show with the exact figures, clicks and Genie questions |
| `docs/EXTRACTION.md` | Rate-card PDF extraction accuracy (English, Traditional Chinese, Korean) |
| `docs/APP.md` | Review & approval app (React + Vite + FastAPI + Lakebase): design, findings, runbook |
| `docs/DESIGN.md` | App design system and the five themes to vet (`?theme=marunouchi \| otemachi \| washi \| kon \| sumi`), with screenshots |
| `docs/DASHBOARD.md`, `docs/GENIE.md` | Dashboard pages and datasets; Genie sources, instructions and benchmark results |
| `docs/GOVERNANCE.md`, `docs/RUNBOOK.md` | Row security evidence, lineage, controls; pre-demo checklist and fallbacks |

## Live assets (workspace `fe-vm-zh-serverless`)

| Asset | Link / name |
|---|---|
| AI/BI dashboard | https://fe-vm-zh-serverless-ws.cloud.databricks.com/sql/dashboardsv3/01f1cdaa355f19f88f21661e96bbf0a6/published |
| Genie space | https://fe-vm-zh-serverless-ws.cloud.databricks.com/genie/rooms/01f1cda9f4a9153882ea4c4ecda34bc3 |
| Review & approval app | https://cost-explain-app-2515635694809473.aws.databricksapps.com |
| Commentary agent | Model Serving endpoint `ce-commentary-agent` (model `cost_explain.gold.commentary_agent`, alias `champion`) |
| Control evidence | `cost_explain.gold.tie_out_results` (56 checks) |

## What gets deployed (one Asset Bundle)

| Asset | Name |
|---|---|
| Catalog / schemas / volumes | `cost_explain` · `landing` (volumes `raw`, `rate_cards`), `bronze`, `silver`, `gold`, `review` |
| SQL warehouse | `cost-explain-wh` (serverless) |
| Fee-schedule extraction job | `ce_fee_extraction` — `ai_parse_document` → `ai_extract` → analyst review → `silver.fee_schedule` |
| Lakeflow SDP pipeline | `ce_medallion` — bronze (Auto Loader) → silver (expectations) → gold (expected cost, bridge, recon, fails, KPIs) |
| Metric views | `gold.trade_cost_flux_metrics`, `trade_cost_metrics`, `desk_cost_kpi_metrics`, `invoice_recon_metrics`, `settlement_fail_metrics` |
| Build job | `ce_build` — [regenerate] → extraction → pipeline (full refresh) → metric views → **tie-out gate** |
| Commentary agent | `ce_agent_deploy` → UC tool functions + `cost_explain.gold.commentary_agent` → endpoint `ce-commentary-agent` |
| Lakebase | project `cost-explain-db` (review & approval store) |
| Databricks App | `cost-explain-app` (React + Vite UI, FastAPI API) |
| Review sync job | `ce_review_sync` — Lakebase → `cost_explain.review` (Lakehouse Sync fallback) |
| AI/BI dashboard, Genie space | `Trade Cost Explain` |

## Deploy to a new workspace

```bash
PROFILE=<profile>
# 0. one-time: catalog (Default-Storage accounts need SQL/UI for this)
databricks bundle deploy -t dev --profile $PROFILE            # creates the warehouse first
scripts/bootstrap_catalog.sh $PROFILE <warehouse_id>
databricks bundle deploy -t dev --profile $PROFILE            # schemas, volumes, jobs, pipeline, app, ...
# 1. rate-card PDFs (rendered from src/datagen/config/rate_cards.yaml)
src/rate_cards/publish.sh $PROFILE
# 2. data + Gold + tie-out (regenerates the synthetic data into the landing Volume)
databricks bundle run ce_build --params regenerate_data=true -t dev --profile $PROFILE
# 3. agent (≈15 min)
databricks bundle run ce_agent_deploy -t dev --profile $PROFILE
# 4. app
databricks bundle run cost_explain_app -t dev --profile $PROFILE
```

Local generation and verification (no Databricks needed): `cd src/datagen && uv run python -m meridian_datagen.main
--out ../../.local_out/raw` — it rebuilds the bridge from the landed files with an independent implementation and
fails unless every planted cell ties.

## Repository layout

```
databricks.yml, resources/        bundle definition (one YAML per resource)
src/datagen/                      calibrated synthetic-data generator + canonical rate cards (single source of truth)
src/rate_cards/, src/extraction/  rate-card PDFs and the AI extraction job
src/pipeline/{bronze,silver,gold} Lakeflow SDP SQL
src/metric_views/, src/tests/     semantic layer and the tie-out gate
src/agent/                        commentary agent (MLflow ResponsesAgent) and its UC tool functions
src/governance/                   desk-level row security (row filters; ABAC policy version for customer workspaces)
src/review_sync/                  Lakebase → Unity Catalog replication
cost-explain-app/                 Databricks App (React + Vite + FastAPI + Lakebase)
docs/                             contracts, talk track, extraction report, app notes
```
