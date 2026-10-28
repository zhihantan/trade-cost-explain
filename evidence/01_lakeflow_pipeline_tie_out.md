# 01 — Lakeflow: the pipeline ran and its output ties to the dollar

**What ran.** Lakeflow Spark Declarative Pipeline `ce_medallion` (serverless; `resources/ce_medallion.pipeline.yml`):
bronze streaming tables via Auto Loader (`STREAM read_files` on `/Volumes/cost_explain/landing/raw/`), silver streaming
tables with expectations (`EXPECT … ON VIOLATION FAIL UPDATE / DROP ROW`), Gold materialized views carrying the desk row
filter. Job `ce_build` orchestrates it: [regenerate] → fee extraction → pipeline (full refresh) → metric views → tie-out gate.

Recorded in workspace `fe-vm-zh-serverless` (AWS us-west-2) on 2026-10-22; copied from `docs/GOVERNANCE.md` §3,
`docs/APP.md` §1b and `docs/DASHBOARD.md`.

## Tie-out gate — last run PASSED 56 / 56

> Job `ce_build` ends with `src/tests/tie_out.sql`, which writes 56 checks to `cost_explain.gold.tie_out_results` and fails
> the run if any check fails: 33 planted bridge cells (± US$50), the 75 / 28 / −3 % shares, the Broker C finding
> (US$85K ± 500), Kestrel's share of the fails increase, the identity `flux = Σ effects` on every bridge row of every
> comparison, the unexplained-residual threshold (greater of US$25K and 5 % of flux) per comparison, GL mapping
> coverage (≥ 99 %) and the approved fee-schedule line count. Last run: **PASSED 56 / 56**.

## Live Gold verification (2026-10-22)

| Check | Result |
|---|---|
| Flux `MOM_2026-09` / APAC | US$5.0M → US$6.2M; Volume +900 · Mix +190 · Rate +100 · Fails +150 · Timing −50 · FX −100 · Fixed 0 · Unexplained +10 (US$K); slice table ties to the chart |
| Flux `MOM_2026-09` / ED_EXCH_CLR | 2,170 → 2,680; +390 · +90 · +60 · 0 · −20 · −10 |
| Effect order | Follows the scene-2 narrative order (`gold.cost_flux_effects.effect_order`): VOLUME, MIX, RATE, FAILS, TIMING, FX, FIXED, UNEXPLAINED |
| Data snapshot | Gold objects are pipeline **materialized views**: `DESCRIBE HISTORY` fails (`EXPECT_TABLE_NOT_VIEW`). The app falls back to `DESCRIBE TABLE EXTENDED` → *Refresh Information* and stores `snapshot_ref = pipeline:<pipeline_id>/update:<update_id>` + `as_of_ts` = last refresh |

## Every dashboard query re-run as deployed (2026-10-22)

> `validate_dashboard.py` re-ran all 59 widget queries exactly as deployed (bare Gold names, every filter's default
> selection applied). Result: 0 failures, 0 empty results.

| Where | Figure |
|---|---|
| Flux KPIs | US$5.00M → US$6.20M, **+US$1.20M (+24.0%)** |
| Bridge (US$K) | prior 5,000 · volume +900 · mix +190 · rate +100 · fails +150 · timing / accrual −50 · FX −100 · fixed fees 0 · unexplained +10 → 6,200 |
| Comparison toggle | FY2026/27 Q2 vs Q1: +US$1.28M |
| Good vs bad | good US$900K (**75.0%**) · controllable US$340K (**28.3%**) · external, timing & residual −US$40K |
| Drill | 49,023 September executions in the two story slices (68,137 across the two volume groups) |
| Invoice | Cobalt Securities, August brokerage: expected US$425K, invoiced US$510K, **US$85K over-billed** (three legal-entity lines) · 7 lines outside tolerance · 86 awaiting the vendor invoice |
| Fails, Sep 2026 | net US$201.7K from 423 failed settlements · **Kestrel Asset Management US$144.9K** (next counterparty US$4.2K) · funding US$19.3K and borrow US$3.2K shown separately |
| Controls | tie-out **56 passed / 0 failed** · 99.76% of GL mapped to a counterparty |
