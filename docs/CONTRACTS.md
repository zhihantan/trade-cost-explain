# Data & interface contracts (shared by all work streams)

Workspace profile `fe-vm-zh-serverless` · catalog `cost_explain` · warehouse `cost-explain-wh` (`5f36ded0f9befdd1`)
Lakebase project `cost-explain-db` · branch `projects/cost-explain-db/branches/production` · database resource
`projects/cost-explain-db/branches/production/databases/databricks-postgres` (Postgres db `databricks_postgres`) ·
endpoint `projects/cost-explain-db/branches/production/endpoints/primary`.

Change control: the Lead SA owns this file. Streams propose changes, they don't edit silently.

## 1. Hierarchy and codes

Division `APAC Global Markets`. Businesses (`business_code` → `business`):

| business_code | business | desks (`desk_code` → `desk_name`) |
|---|---|---|
| CEQ | Cash Equities | HKCE HK Cash Equities · CNSC Stock Connect / China Flow · KTEQ Korea & Taiwan Equities · AUCE Australia Cash Equities · INEQ India Equities |
| EQD | Equity Derivatives | HKED HK Equity Derivatives |
| PDO | Prime & Delta One | D1PR Delta One / Prime |
| RTS | Rates | SGRT Singapore Rates · AURF Australia Rates & Futures |
| CRD | Credit | FLCR Flow Credit |
| FXE | FX & Emerging Markets | SGFX Singapore FX · SGEM Singapore EM (incl. Malaysia) |

`cost_category` values: `Exchange & clearing`, `Brokerage`, `Settlement & custody`, `Levies & taxes (borne)`,
`Non-recoverable GST`, `Settlement fails`, `Fixed fees`, `Unmapped`.
`headline_slice` values: `Equity Derivatives — exchange & clearing` (business EQD AND category `Exchange & clearing`), `Rest of APAC Global Markets`.

## 2. Gold tables the app reads (`cost_explain.gold`, regular Delta tables, so they are versioned)

### `dim_comparison`
`comparison_id` STRING (e.g. `MOM_2026-09`, `QOQ_FY2026Q2`), `comparison_type` (`MoM`/`QoQ`), `period_p0`, `period_p1`
(`2026-08` / `2026-09`, or `FY2026Q1` / `FY2026Q2`), `p0_label` (`Aug 2026`), `p1_label` (`Sep 2026`), `sort_order` INT, `is_default` BOOLEAN
(true for `MOM_2026-09`).

### `cost_flux_bridge` — one row per comparison × business × desk × cost_type × vendor × market × legal_entity × currency
Dimensions: `comparison_id`, `division`, `business_code`, `business`, `desk_code`, `desk_name`, `legal_entity`, `legal_entity_name`,
`cost_type`, `cost_category`, `headline_slice`, `vendor_id`, `vendor_name`, `vendor_type`, `market`, `currency`.
Measures (DOUBLE, US$): `p0_actual_usd`, `p1_actual_usd`, `p1_cc_usd`, `volume_usd`, `mix_usd`, `rate_usd`, `fx_usd`, `fails_usd`,
`fixed_usd`, `timing_usd`, `unexplained_usd`, `flux_usd`.
Identity per row: `flux_usd = p1_actual_usd − p0_actual_usd = volume + mix + rate + fx + fails + fixed + timing + unexplained`.

### `cost_flux_effects` (view) — long form for waterfalls
All bridge dimensions + `effect`, `effect_label`, `effect_order` INT in the scene-2 narrative order:
1 `VOLUME`, 2 `MIX`, 3 `RATE`, 4 `FAILS`, 5 `TIMING`, 6 `FX`, 7 `FIXED`, 8 `UNEXPLAINED`;
`flux_class` (`Good (volume-driven)` for VOLUME; `Controllable` for MIX, FAILS; `External, timing & residual` otherwise), `amount_usd`.
The bridge also carries `is_vendor_mapped`, `p0_expected_usd`, `p1_expected_cc_usd`; `dim_comparison` also has `comparison_label`.

### `commentary_figures` (view) — the figure registry behind commentary chips
`figure_key` STRING, `comparison_id`, `scope_key`, `scope_label`, `metric`, `metric_label`, `value` DOUBLE, `unit` (`USD`,`PCT`,`COUNT`),
`source_table` (fully qualified), `filter_expr` (SQL predicate against `source_table`), `description`.
- Bridge figures: `figure_key = {comparison_id}|{scope_key}|{metric}`
  - `scope_key`: `APAC`, `ED_EXCH_CLR`, `REST`, `BUS:<business_code>`, `DESK:<desk_code>`, `CAT:<cost_category>`,
    `VENDOR:<vendor_id>`, `MKT:<market>`, and `PF:<desk_code>:<product_family>` (VOLUME / MIX / RATE only, source `cost_flux_slice`)
  - `metric`: `P0`, `P1`, `FLUX`, `FLUX_PCT`, `VOLUME`, `MIX`, `RATE`, `FX`, `FAILS`, `FIXED`, `TIMING`, `UNEXPLAINED`, `GOOD`, `CONTROLLABLE`,
    `EXTERNAL`, `GOOD_PCT`, `CONTROLLABLE_PCT`
- Findings: `INV|{service_period}|{vendor_id}|VARIANCE` (e.g. `INV|2026-08|B03|VARIANCE` = Broker C US$85K),
  `FAILS|{period}|{desk_code}|{counterparty_id}|NET` (top fail hotspot).

Expected planted values for `MOM_2026-09` (US$): APAC P0 5,000,000 · P1 6,200,000 · VOLUME 900,000 · MIX 190,000 · RATE 100,000 · FAILS 150,000 ·
TIMING −50,000 · FX −100,000 · UNEXPLAINED 10,000 · FIXED 0. ED_EXCH_CLR: P0 2,170,000 · P1 2,680,000 · VOLUME 390,000 · MIX 90,000 ·
RATE 60,000 · TIMING −20,000 · FX −10,000.

Control evidence: `gold.tie_out_results` (check_name, check_type, expected, actual, passed, checked_at), written by the
`tie_out` task of job `ce_build`. Agent tools (UC SQL functions): `gold.get_cost_bridge`, `gold.get_top_contributors`,
`gold.get_invoice_findings`, `gold.get_fail_hotspots`, `gold.get_fee_events`.
Metric views: `gold.trade_cost_flux_metrics`, `gold.trade_cost_metrics`, `gold.desk_cost_kpi_metrics` (incl. `Hub`),
`gold.invoice_recon_metrics`, `gold.settlement_fail_metrics` (`Desk` = code, `Desk Name` = name). In `trade_cost_metrics` the
cost category `Levies & taxes` is gross (use the net borne / recoverable measures to split); the bridge's
`Levies & taxes (borne)` is net borne only.

Other Gold tables (dashboard / Genie / agent; the app may link to them): `cost_flux_slice`, `expected_cost_trade`, `expected_cost_daily`,
`invoice_recon`, `fail_cost_detail`, `fail_cost_summary`, `cost_monthly`, `cost_kpis`, `fee_calendar`.

## 3. Commentary agent endpoint `ce-commentary-agent` (MLflow ResponsesAgent on Model Serving)

Request (`POST /serving-endpoints/ce-commentary-agent/invocations`):
```json
{"input": [{"role": "user", "content": "Draft the month-end variance commentary."}],
 "custom_inputs": {"comparison_id": "MOM_2026-09", "slice": "APAC", "audience": "CFO", "max_words": 250}}
```
Response: standard ResponsesAgent `output[]` (message text = the commentary) **plus**
```json
"custom_outputs": {"commentary_markdown": "… US$900K [[fig:MOM_2026-09|APAC|VOLUME]] …",
  "figures": [{"figure_key": "MOM_2026-09|APAC|VOLUME", "label": "Volume effect", "value": 900000.0, "unit": "USD",
               "source_table": "cost_explain.gold.cost_flux_bridge", "filter": "comparison_id = 'MOM_2026-09'"}],
  "model": "databricks-claude-sonnet-5-5", "trace_id": "…"}
```
Chips are written inline as `[[fig:<figure_key>]]`. The app resolves `delta_version` and `as_of_ts` itself at draft time
(`DESCRIBE HISTORY <source_table> LIMIT 1`) and stores them in `commentary_figure`.
Until the endpoint exists, the app uses a deterministic template drafter built from `commentary_figures` (also the fallback when the endpoint fails).

## 4. App slice parameter
`slice` = `APAC` | `ED_EXCH_CLR` | `REST` | `BUS:<business_code>` | `DESK:<desk_code>` (same keys as `scope_key`).

## 5. Roles (workspace groups)
`ce_fpa_analysts` (draft, edit, submit), `ce_fpa_approvers` (approve / reject; never their own item), `ce_cfo_office` (sees all desks),
`ce_desk_head_eqd` (ABAC: Equity Derivatives only).

## 6. Review history in Unity Catalog
Lakehouse Sync is **not available** (it doesn't support Default Storage catalogs). Fallback: the Lakebase database is registered in UC as catalog
`cost_explain_lakebase`, and job `ce_review_sync` MERGEs `commentary`, `commentary_figure`, `approval_event` into `cost_explain.review.*`
and builds `review.v_commentary_figure_evidence` (figures joined to Gold for lineage and tie-checks).
