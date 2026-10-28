# Governance and control evidence

## 1. Desk-level row security (spec §4 "Desk heads see only their desks")

**Mechanism in this build.** The desk-grained Gold materialized views — `cost_flux_bridge`, `cost_flux_slice`,
`cost_monthly`, `cost_kpis`, `fail_cost_summary`, `expected_cost_daily`, `expected_cost_trade` — declare
`WITH ROW FILTER cost_explain.gold.ce_desk_scope ON (desk_code)` in the pipeline definition. Everything built on them
(metric views, `commentary_figures`, the agent's UC tool functions, the dashboard, Genie, the app's user-authorized
reads) inherits the filter for the caller.

`ce_desk_scope(row_desk)` (`src/governance/row_filters.sql`) is entitlement-driven:
callers in **no** desk-head group see every row; desk heads see only rows whose desk is granted to their group in
`cost_explain.gold.desk_entitlements` (`ce_desk_head_eqd → HKED`). Group checks use both `is_member()` (workspace-local
groups — what this FEVM workspace has) and `is_account_group_member()` (account groups — the norm on a customer
workspace). The CFO office, FP&A analysts, the app's service principal and the commentary agent are unaffected.

**Why not the ABAC policy here.** The preferred design is the ABAC row-filter policy in `src/governance/abac.sql`
(governed tag `ce_rls_scope = desk` on the desk columns, `CREATE POLICY … ROW FILTER … TO ce_desk_head_eqd FOR TABLES
MATCH COLUMNS has_tag_value('ce_rls_scope','desk')`). Creating the governed tag failed in this shared FEVM account:
*"The maximum number of tag policies allowed is reached for the account."* The entitlement logic is identical, so on
the customer workspace run `abac.sql` instead of attaching row filters in the pipeline.

**Evidence (2026-10-22, persona service principal `ce-persona-eqd-desk-head`, member of `ce_desk_head_eqd`).**

| Query | CFO office (`zhihan.tan@…`) | EQD desk-head persona |
|---|---|---|
| `is_member('ce_desk_head_eqd')` / `is_account_group_member(…)` | false / false | **true** / false (workspace-local group) |
| `cost_flux_bridge`, MOM_2026-09 — desks, P1, flux (US$K) | 12 desks · 6,200.0 · +1,200.0 | **1 desk (HKED)** · 3,069.5 · +559.4 |
| `trade_cost_flux_metrics` by headline slice (change, US$K) | ED exch & clr +510.0 · Rest +690.0 | ED exch & clr +510.0 · Rest **+49.4** (HKED's own brokerage, levies, GST, fixed) |
| `commentary_figures` `MOM_2026-09\|APAC\|FLUX` (US$K) | 1,200.0 | **559.4** |
| `expected_cost_trade`, September — desks, fee lines | 12 desks · 1,592,115 | **HKED** · 157,489 |

The persona's OAuth secret was created for the test and deleted immediately afterwards (never written to disk).

## 2. Lineage (scene 8)

Captured automatically by Unity Catalog (`system.access.table_lineage`), for example:
`commentary_figures ← cost_flux_bridge ← {cost_flux_slice, gl_monthly, fail_cost_daily, fixed_fee_monthly, comparison_fx}`;
`cost_flux_slice ← expected_cost_monthly ← expected_cost_trade ← {silver.trades, silver.fee_schedule, silver.fx_monthly}`;
`gl_monthly ← silver.gl_actuals ← {bronze.gl_journal_lines_raw, map_gl_cost_type, map_vendor_counterparty, map_costcentre_desk}`;
`silver.trades ← bronze.trades_raw ← pipeline ce_medallion` (Auto Loader streams from
`/Volumes/cost_explain/landing/raw/trades/`; Unity Catalog records the pipeline as the upstream entity, not the files —
batch `read_files` reference tables such as `silver.dim_vendor` do record their CSV paths);
`silver.fee_schedule ← silver.fee_schedule_review ← silver.fee_schedule_extracted ← silver.rate_card_parsed ←
/Volumes/cost_explain/landing/rate_cards/` (the review and publish steps join in SQL so these edges are recorded).
The review app's approvals land in `cost_explain.review.*` via job `ce_review_sync`, and
`review.v_commentary_figure_evidence` joins every cited figure back to Gold.

## 3. Automated tie-out (control over the numbers)

Job `ce_build` ends with `src/tests/tie_out.sql`, which writes 56 checks to `cost_explain.gold.tie_out_results` and fails
the run if any check fails: 33 planted bridge cells (± US$50), the 75 / 28 / −3 % shares, the Broker C finding
(US$85K ± 500), Kestrel's share of the fails increase, the identity `flux = Σ effects` on every bridge row of every
comparison, the unexplained-residual threshold (greater of US$25K and 5 % of flux) per comparison, GL mapping
coverage (≥ 99 %) and the approved fee-schedule line count. Last run: **PASSED 56 / 56**.

## 4. Review and approval controls (app)

Four-eyes (an author cannot approve their own commentary), immutable approved versions, optimistic concurrency,
append-only `approval_event` with request ids, every write attributed to the signed-in user (`X-Forwarded-Email`),
user-authorized reads (row filters apply), fail-closed on a missing user token, CSRF / Origin checks. Details in
`docs/APP.md`.
