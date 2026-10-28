# AI/BI dashboard — Trade Cost Explain — APAC Global Markets

Covers talk-track scenes 1 and 3–6 (`docs/TALK_TRACK.md`) plus the close-control evidence. Published 2026-10-22, and
every widget query was verified against the live Gold layer.

| | |
|---|---|
| Dashboard | **Trade Cost Explain — APAC Global Markets** · id `01f1cdaa355f19f88f21661e96bbf0a6` |
| Open | [draft](https://fe-vm-zh-serverless-ws.cloud.databricks.com/sql/dashboardsv3/01f1cdaa355f19f88f21661e96bbf0a6) · [published](https://fe-vm-zh-serverless-ws.cloud.databricks.com/sql/dashboardsv3/01f1cdaa355f19f88f21661e96bbf0a6/published) |
| Workspace path | `/Shared/trade-cost-explain/Trade Cost Explain — APAC Global Markets.lvdash.json` |
| Warehouse | `cost-explain-wh` (`5f36ded0f9befdd1`) |
| Dataset defaults | catalog `cost_explain`, schema `gold`. SQL datasets use bare Gold names and `silver.<table>`. |
| Credentials | **Not embedded.** Viewers query as themselves, so the desk row filter `gold.ce_desk_scope` applies. |
| Source | `src/dashboards/build_dashboard.py` generates `src/dashboards/trade_cost_explain.lvdash.json`. Edit the script, never the JSON. |
| Check | `src/dashboards/validate_dashboard.py` |
| Bundle resource | `resources/trade_cost_explain.dashboard.yml.pending`, staged (see [Binding into the bundle](#binding-into-the-bundle)) |

## Layout

**Global filter: Comparison.** It sits in the Filters panel as a single select.
- Default: **Sep 2026 vs Aug 2026** (`MOM_2026-09`).
- It offers 12 month-on-month comparisons (Oct 2025 vs Sep 2025 … Sep 2026 vs Aug 2026).
- It also offers 3 fiscal quarter-on-quarter comparisons (FY2025/26 Q4 vs Q3, FY2026/27 Q1 vs FY2025/26 Q4, FY2026/27 Q2 vs Q1).
- It drives every bridge dataset: `ds_flux`, `ds_steps`, `ds_slice` and `ds_mix_groups`.
- The invoice, fails, calendar and control pages aren't comparison-based, so they have their own page filters.

Every page header carries *Synthetic data — Meridian Group; all figures illustrative.*

| Page | Scene | Widgets | Datasets |
|---|---|---|---|
| **Flux** | 1 | Headline slice and Business filters · KPI row: prior, current, change, change % · waterfall *prior period → current period* · *Change by driver* bar (same steps; adds up to the change) · ED exchange & clearing vs the rest · by business and desk · change by market and driver · local-currency drill (change and FX effect by currency) | `ds_flux`, `ds_steps` |
| **Good vs bad flux** | 3 | Good (volume-driven) and controllable (mix + fails) flux, each with its share of the change · change by driver and by flux class · trade cost vs revenue, 13 months · PRX Volatility Index vs HK Equity Derivatives exchange & clearing cost, daily, Aug–Sep 2026 · cost as bps of revenue vs plan, Sep 2026 | `ds_flux`, `ds_steps`, `ds_trend`, `ds_vol` |
| **Drill to trade** | 4 | Mix by desk × product family · mix by venue · capacity, pre-filtered to the two story groups · driver-slice table (largest mix first) · September exchange-fee executions, with Story slice (default: the two planted stories), Desk, Venue and Capacity filters | `ds_mix_groups`, `ds_slice`, `ds_trades` |
| **Invoice vs expected** | 5 | Service period filter · over-billed on August 2026 invoices · lines outside tolerance · lines awaiting the vendor invoice · variance by vendor · Broker C (Cobalt Securities) August commission by fee code · reconciliation lines needing attention | `ds_recon`, `ds_recon_line`, `ds_recon_tbl` |
| **Fails** | 6 | Month filter (default 2026-09) · net fail cost and failed settlements, with funding and borrow cost shown separately · by counterparty, by root cause, by market and desk · Kestrel · AUCE vs all other fails by month · operations fix list | `ds_fails`, `ds_fails_trend` |
| **Fee calendar & controls** | close / 8 | Fee and regime calendar with monthly impact · tie-out checks passed / failed, plus the results table · share of GL mapped to a counterparty, Sep 2026 · GL booked to unmapped AP vendors (the unexplained residual) | `ds_fee_cal`, `ds_tie`, `ds_coverage` |

Colours are fixed by meaning:

| Meaning | Colour |
|---|---|
| Good (volume) | `#17A589` |
| Controllable | `#E15F41` |
| External / timing / residual | `#8C9BA5` |
| Prior period | `#1F4E79` |

## Datasets

| Dataset | Source | Grain / notes |
|---|---|---|
| `ds_flux` | metric view `gold.trade_cost_flux_metrics` | KPIs and good / controllable shares; slice, business, desk and currency tables |
| `ds_trend` | metric view `gold.desk_cost_kpi_metrics` | Month × desk: cost, revenue, plan |
| `ds_recon` | metric view `gold.invoice_recon_metrics` | Invoice counters and vendor variance |
| `ds_fails` | metric view `gold.settlement_fail_metrics` | Fails counters, breakdowns and fix list |
| `ds_steps` | `cost_flux_bridge` (prior-period row) ∪ `cost_flux_effects`, joined to `dim_comparison` | Bridge cell × step. `step_order` 0–8 fixes the waterfall order. |
| `ds_slice` | `cost_flux_slice` + `dim_comparison` | Volume / mix / rate per desk × product × venue × capacity slice |
| `ds_mix_groups` | `cost_flux_slice` grouped by desk × product family | Groups with \|mix\| ≥ US$1K |
| `ds_trades` | `expected_cost_trade` | Sep 2026 exchange-fee lines for HKED PRX 50 futures and AUCE cash equities, each tagged with a `story_slice` |
| `ds_vol` | `silver.market_data` (PRXVI) full-joined to `expected_cost_daily` (HKED exchange + clearing) | Trading day, Aug–Sep 2026 |
| `ds_recon_tbl` | `invoice_recon` | Non-matched lines, over-billed first |
| `ds_recon_line` | `invoice_recon_line` × `silver.fx_monthly` | Broker C (B03), August brokerage, by fee code and legal entity |
| `ds_fails_trend` | `fail_cost_summary` | Month: Kestrel · AUCE vs all other fails |
| `ds_fee_cal` | `fee_calendar` | One row per event |
| `ds_tie` | `tie_out_results` | One row per check |
| `ds_coverage` | `gl_monthly` (net-borne lines) | Month: mapped share and unmapped US$ |

## Verified figures (2026-10-22)

`validate_dashboard.py` re-ran all 59 widget queries exactly as deployed:
- Bare Gold names, in the dashboard's catalog / schema context.
- Every filter's default selection applied.

Result: 0 failures, 0 empty results.

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

## Viewer access

Credentials are not embedded, so each viewer needs all of the following:
- **Dashboard:** `CAN_RUN` or higher. Today `users` inherit `CAN_MANAGE` from `/Shared`, and the bundle resource adds `CAN_RUN`.
- **Warehouse:** `CAN_USE` on `cost-explain-wh`.
- **Gold:** `USE CATALOG` on `cost_explain`, plus `USE SCHEMA` and `SELECT` on `cost_explain.gold`.
- **Two Silver tables:** `USE SCHEMA` on `cost_explain.silver`, plus `SELECT` on `silver.market_data` (volatility combo) and `silver.fx_monthly` (Broker C fee-code table). Both are reference data, not desk-scoped.

As of 2026-10-22, only these principals hold grants on `cost_explain`:
- the owner,
- admins,
- the persona service principal `ce-persona-eqd-desk-head`, which has Gold only.

The presenter therefore sees everything. A Gold-only viewer would see an error on those two widgets. The cleaner fix is to expose both tables as Gold views and repoint `ds_vol` / `ds_recon_line`. Until then, grant as follows:

```sql
GRANT USE CATALOG ON CATALOG cost_explain TO `<viewer-group>`;
GRANT USE SCHEMA, SELECT ON SCHEMA cost_explain.gold TO `<viewer-group>`;
GRANT USE SCHEMA ON SCHEMA cost_explain.silver TO `<viewer-group>`;
GRANT SELECT ON TABLE cost_explain.silver.market_data TO `<viewer-group>`;
GRANT SELECT ON TABLE cost_explain.silver.fx_monthly TO `<viewer-group>`;
```

## Binding into the bundle

The dashboard was created through the Lakeview API, so the bundle resource is staged as `.pending`. With the file
enabled, `bundle plan` shows `create dashboards.trade_cost_explain`, which would create a second copy. To adopt the
existing dashboard instead:

```bash
mv resources/trade_cost_explain.dashboard.yml.pending resources/trade_cost_explain.dashboard.yml
databricks bundle deployment bind trade_cost_explain 01f1cdaa355f19f88f21661e96bbf0a6 --profile fe-vm-zh-serverless
databricks bundle plan --profile fe-vm-zh-serverless     # dashboards.trade_cost_explain must not show "create"
databricks bundle deploy --profile fe-vm-zh-serverless
```

Things to know about this step:
- `bind` asks for confirmation.
- `bundle validate --strict` passes with the file enabled. Its single recommendation concerns `cost_explain.catalog.yml` and predates this resource.
- After binding, the bundle owns the dashboard. Make changes in `build_dashboard.py`, then deploy.
- The resource sets `dataset_catalog: ${var.catalog}`. That rewrites the SQL datasets but not the four metric-view assets, which are referenced by full name. For a catalog not named `cost_explain`, first run `CE_CATALOG=<catalog> python3 src/dashboards/build_dashboard.py`.

Iterating without the bundle (before binding):

```bash
python3 src/dashboards/build_dashboard.py
src/agent/.venv/bin/python src/dashboards/validate_dashboard.py --profile fe-vm-zh-serverless
databricks lakeview update 01f1cdaa355f19f88f21661e96bbf0a6 --profile fe-vm-zh-serverless \
  --display-name "Trade Cost Explain — APAC Global Markets" --warehouse-id 5f36ded0f9befdd1 \
  --dataset-catalog cost_explain --dataset-schema gold \
  --serialized-dashboard "$(cat src/dashboards/trade_cost_explain.lvdash.json)"
databricks lakeview publish 01f1cdaa355f19f88f21661e96bbf0a6 --profile fe-vm-zh-serverless --json '{"embed_credentials": false}'
```

## Before the demo: known limitations

1. **Rendering hasn't been checked in a browser.** Queries are verified, but no signed-in browser was available to look at the pages. Open each page once; this also warms the warehouse. Confirm two things:
   - The waterfall runs in bridge order (Prior period → Unexplained) and ends at US$6.2M. If it doesn't, the adjacent *Change by driver* bar shows the same steps in the same order, so present from that instead.
   - The two combo charts (cost vs revenue; PRXVI vs ED cost) are readable.
2. **Scene 4 click path.** Dashboard clicks don't navigate between pages, so run scene 4 on the *Drill to trade* page. No click is needed there:
   - The desk × product family bar shows the two mix groups: AUCE cash equities +US$100K and HKED PRX 50 futures +US$90K.
   - The venue · capacity bar beside it is already filtered to those groups. It shows where the mix moved: PRX · HOUSE +US$226K against PRX · MM −US$136K, and SXA +US$215K against TAM −US$115K.
3. **Large execution table.** It holds 49,023 rows by default. Rows are sorted by cost, largest first. If the table shows a truncation notice, narrow it with the Desk / Venue / Capacity filters.
4. **The over-billed counter is pinned to August 2026.** It uses a widget filter, so it shows empty if the Service period filter excludes August.
5. **The Headline slice and Business filters act on the Flux page only.** They filter that page's metric-view widgets and bridge steps.
