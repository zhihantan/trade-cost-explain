# Execution evidence

Text-readable proof that the build ran, in two kinds:

- **Re-run on 2026-10-28, locally** (no workspace needed): unit tests and the independent tie-out verifier — `00`.
- **Recorded live on 2026-10-22** in workspace `fe-vm-zh-serverless` (AWS us-west-2) by the build's own jobs and
  scripts (`ce_build` tie-out gate, `validate_dashboard.py`, the Genie benchmark eval API, the extraction report, app
  smoke tests, a persona service principal) — `01`–`06`, copied from `docs/` with the source section named in each file.

| Layer | Evidence | Headline result |
|---|---|---|
| Lakeflow — ingest and transform | [`01_lakeflow_pipeline_tie_out.md`](01_lakeflow_pipeline_tie_out.md) | SDP pipeline `ce_medallion` (Auto Loader → expectations → Gold MVs); tie-out gate **56/56 passed**; 59 dashboard queries re-run, **0 failures** |
| Unity Catalog — govern | [`02_unity_catalog_row_filters.md`](02_unity_catalog_row_filters.md) | Row filter tested as a desk-head persona: **12 desks → 1 desk (HKED)**, flux 1,200.0 → 559.4; lineage recorded Bronze → Gold → commentary |
| Lakebase — operational serving | [`03_lakebase_review_loop.md`](03_lakebase_review_loop.md) | Review store on PG 17 (~10 ms OAuth round trip); approve → sync job **3 s** → Unity Catalog **35 s**; **82/82** cited figures tie to Gold |
| Gen AI — make it intelligent | [`04_genai_agent_and_extraction.md`](04_genai_agent_and_extraction.md) | Agent on Model Serving: **14–16 chips per draft, all resolved, no value mismatches**; PDF fee extraction **98.6%** field accuracy (prompt v1 → v2: 49.6% → 73.4% lines fully right) |
| Genie Agent — ask in plain language | [`05_genie_benchmarks.md`](05_genie_benchmarks.md) | **11/11** benchmarks after 10 eval runs (5/10 → 10/10, one lever per run) |
| Databricks App — put it in front of the business | [`06_app_smoke_test.md`](06_app_smoke_test.md) | Deployed; `/api/health` 200; user-token SQL; Lakebase OAuth; four-eyes approvals |
| All layers, offline | [`00_local_checks.md`](00_local_checks.md) | **17 tests passed**; regenerated 3,280,842 executions; independent verifier **RESULT: PASS** |

## Reproduce

```bash
# local (no workspace)
cd src/datagen && python -m meridian_datagen.main --out ../../.local_out/raw     # generator + independent verifier
python -m pytest tests/test_design.py src/extraction/test_review_logic.py -q      # from the repo root
cd cost-explain-app && .venv/bin/python -m pytest tests/test_unit.py -q

# live (any workspace with the bundle deployed; see README "Deploy to a new workspace")
databricks bundle run ce_build -t dev --profile <profile>        # ends with the 56-check tie-out gate
python src/dashboards/validate_dashboard.py --profile <profile>  # re-runs every widget query
python src/genie/ask.py "Why did APAC trade costs go up in September vs August?"   # space id + profile set in the script
python src/agent/eval_agent.py --endpoint ce-commentary-agent --warehouse-id <id> --profile <profile>
```
