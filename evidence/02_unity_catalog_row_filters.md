# 02 — Unity Catalog: desk-level row security, tested as a persona, and recorded lineage

Recorded in workspace `fe-vm-zh-serverless` on 2026-10-22; copied from `docs/GOVERNANCE.md` §1–2.

## Mechanism

The desk-grained Gold materialized views (`cost_flux_bridge`, `cost_flux_slice`, `cost_monthly`, `cost_kpis`,
`fail_cost_summary`, `expected_cost_daily`, `expected_cost_trade`) declare
`WITH ROW FILTER cost_explain.gold.ce_desk_scope ON (desk_code)` in the pipeline definition, so the metric views,
`commentary_figures`, the agent's UC tool functions, the dashboard, Genie and the app's user-authorized reads all
inherit the filter for the caller. `ce_desk_scope(row_desk)` (`src/governance/row_filters.sql`) is entitlement-driven:
desk heads see only desks granted to their group in `cost_explain.gold.desk_entitlements`; the CFO office, FP&A, the
app service principal and the agent are unaffected. The preferred ABAC policy (`src/governance/abac.sql`) is kept for a
customer workspace; this shared account had hit its governed-tag limit, so the same logic runs as row filters.

## Evidence (2026-10-22, persona service principal `ce-persona-eqd-desk-head`, member of `ce_desk_head_eqd`)

| Query | CFO office (`zhihan.tan@…`) | EQD desk-head persona |
|---|---|---|
| `is_member('ce_desk_head_eqd')` / `is_account_group_member(…)` | false / false | **true** / false (workspace-local group) |
| `cost_flux_bridge`, MOM_2026-09 — desks, P1, flux (US$K) | 12 desks · 6,200.0 · +1,200.0 | **1 desk (HKED)** · 3,069.5 · +559.4 |
| `trade_cost_flux_metrics` by headline slice (change, US$K) | ED exch & clr +510.0 · Rest +690.0 | ED exch & clr +510.0 · Rest **+49.4** (HKED's own brokerage, levies, GST, fixed) |
| `commentary_figures` `MOM_2026-09\|APAC\|FLUX` (US$K) | 1,200.0 | **559.4** |
| `expected_cost_trade`, September — desks, fee lines | 12 desks · 1,592,115 | **HKED** · 157,489 |

The persona's OAuth secret was created for the test and deleted immediately afterwards (never written to disk).

## Lineage captured by Unity Catalog (`system.access.table_lineage`)

- `commentary_figures ← cost_flux_bridge ← {cost_flux_slice, gl_monthly, fail_cost_daily, fixed_fee_monthly, comparison_fx}`
- `cost_flux_slice ← expected_cost_monthly ← expected_cost_trade ← {silver.trades, silver.fee_schedule, silver.fx_monthly}`
- `gl_monthly ← silver.gl_actuals ← {bronze.gl_journal_lines_raw, map_gl_cost_type, map_vendor_counterparty, map_costcentre_desk}`
- `silver.trades ← bronze.trades_raw ← pipeline ce_medallion` (Auto Loader streams from `/Volumes/cost_explain/landing/raw/trades/`)
- `silver.fee_schedule ← silver.fee_schedule_review ← silver.fee_schedule_extracted ← silver.rate_card_parsed ← /Volumes/cost_explain/landing/rate_cards/`
- The review app's approvals land in `cost_explain.review.*` via job `ce_review_sync`, and
  `review.v_commentary_figure_evidence` joins every cited figure back to Gold (82/82 `TIES`, see `03`).
