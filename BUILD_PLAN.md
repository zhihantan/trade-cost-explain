# Trade Cost Explain — Build Plan (APAC Global Markets edition)

**Author:** Lead Solutions Architect (Databricks) · **Date:** 2026-10-22 · **Spec:** the original demo brief (the "master prompt"; customer-specific, so it is kept out of this repository — `§` references point to it)
**Status:** built and verified on `fe-vm-zh-serverless` (tie-out PASSED 56/56). This plan is the contract for every work stream; deviations are logged in §10.

---

## 1. What we are building

A deployable, reproducible demo of a **driver-based "cost explain" for FP&A**: APAC Global Markets trade costs rose **US$5.0M → US$6.2M (+24%)** in September 2026 vs August, and the platform explains *why* in a bridge that adds up to the dollar, from GL line down to individual executions. The demo covers 8 scenes (§3 of the spec): flux dashboard, Genie, good vs bad flux, drill to trade, invoice vs expected, fails, agent-drafted commentary with approval in a custom app, and Unity Catalog lineage.

Everything ships as **one Databricks Asset Bundle** so it can be redeployed to an APAC workspace (Singapore / Sydney / Mumbai) for the customer session without code changes.

## 2. Environment and key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Workspace | `fe-vm-zh-serverless` (AWS **us-west-2**), profile `fe-vm-zh-serverless` | Chosen by the user. Apps, Lakebase Autoscaling, FMAPI, `ai_parse_document`, Genie and metric views are all in-region. The APAC residency story is a talk-track item plus a redeploy target, not a build blocker |
| Catalog | `cost_explain` with schemas `landing`, `bronze`, `silver`, `gold`, `review` | Matches the spec's `GOLD_SCHEMA=cost_explain.gold`. `review` holds the commentary and approval history replicated from Lakebase |
| Packaging | DAB at the repo root, target `dev` (no name prefixing, so names match the spec). Catalog, schemas, volumes, warehouse, Lakebase project, pipeline, jobs, dashboard, Genie space and app are all bundle resources | Portability; one `bundle deploy` per workspace. Catalog and schemas use `prevent_destroy` |
| Compute | Serverless everywhere: SDP pipeline, jobs, a dedicated serverless SQL warehouse (`cost-explain-wh`) | No cluster management; fast cold start for the demo |
| LLM | `databricks-claude-sonnet-5-5` for the agent and extraction, configurable through a bundle variable (Opus / GPT / Gemini endpoints are also present) | Model-agnostic and governed through serving endpoints (spec §0, S16) |
| App | React 18 + Vite 5 + TypeScript frontend; FastAPI backend; Lakebase Autoscaling (PG 17); `uv` with `uv.lock`; build tools listed under `dependencies` | Exactly as specified in spec §4 |
| Synthetic data | **Calibrated, deterministic generator** (vectorized numpy/pandas; Faker for reference names), runnable locally and as a serverless job task. Raw files land in a UC Volume and are built up through the pipelines | The acceptance test is "the bars must add up", so the August and September aggregates are *designed*, then realized into ~3M executions. An independent verifier re-derives the bridge before anything is landed |
| Identity | User authorization (OBO) for SQL reads and agent calls; app service principal for Lakebase writes; `actor_email` recorded on every write; fail closed | Spec §4 "Who the app acts as" |

## 3. Architecture (as built)

```
 SOURCES (synthetic files in UC Volume /Volumes/cost_explain/landing/raw)      CONSUME
 ─────────────────────────────────────────────────────────────────────         ───────
 gl/            ERP GL extract (CSV)        ─┐                               ┌─ AI/BI dashboard "Trade Cost Explain"
 ap/            AP invoice lines (CSV)      ─┤  Auto Loader (bronze STs)     ├─ Genie space "Trade Cost Explain"
 trades/        OMS/EMS executions (Parquet)─┼─▶ bronze ─▶ silver ─▶ gold ───┤     (on metric views)
 settlements/   settlement + fails (Parquet)─┤   Lakeflow SDP + expectations ├─ Commentary agent (Model Serving,
 fx/ market/    FX + vol index (JSON)       ─┤        │                      │   MLflow ResponsesAgent + UC tools)
 revenue/ plan/ desk revenue, budget (CSV)  ─┤        │                      ├─ Databricks App cost-explain-app
 ref/           masters + mappings (CSV)    ─┘        │                      │   React+Vite / FastAPI / Lakebase
 rate_cards/    20 fee schedule PDFs (EN/繁中/한국어) ──▶ ai_parse_document ─▶ ai_query extraction ─▶ analyst
                                                       approval ─▶ silver.fee_schedule (feeds expected cost)
                                       Unity Catalog: lineage, metric views, governed tags + ABAC row filters,
                                       Lakebase ─▶ cost_explain.review (Lakehouse Sync, or Delta write-back fallback)
```

Gold is **precomputed and deterministic**. Genie and the agent read it; neither recomputes the bridge (spec §4, vetting #16).

## 4. Repository layout

```
trade-cost-explain/
├── databricks.yml                  # bundle root (variables: catalog, warehouse, llm_endpoint, lakebase)
├── resources/                      # one YAML per resource (<name>.<type>.yml)
├── src/
│   ├── datagen/                    # calibrated generator + canonical rate cards (single source of truth)
│   ├── rate_cards/                 # PDF renderer (EN, Traditional Chinese, Korean)
│   ├── extraction/                 # ai_parse_document → ai_query → approval
│   ├── pipeline/                   # SDP transformations: bronze / silver / gold
│   ├── metric_views/               # UC metric view YAML
│   ├── dashboards/                 # .lvdash.json
│   ├── genie/                      # space config, instructions, benchmarks
│   ├── agent/                      # commentary agent, UC tool functions, eval, deploy
│   ├── governance/                 # groups, governed tags, ABAC policies
│   └── tests/                      # tie-out test (SQL + python), run as a job task
├── cost-explain-app/               # spec §4 layout: app.yaml, package.json, pyproject.toml, uv.lock, backend/, frontend/
├── docs/                           # ARCHITECTURE, DATA_MODEL, TALK_TRACK, RUNBOOK, TIE_OUT
└── tests/                          # local unit tests for the generator / verifier
```

## 5. Data design: how the planted stories are guaranteed to tie

### 5.1 Conventions (applied identically in the generator, the verifier and the Gold SQL)

1. **Headline = net borne cost (US$).** Statutory levies, stamp duty / transaction taxes on **client** capacity are recharged (`is_recoverable`); recoverable GST goes to the balance sheet; non-recoverable GST is a cost. Gross is the drill.
2. **Intra-group eliminated.** Meridian Execution Services (an in-house agency-execution affiliate) charges are tagged `is_affiliate` and excluded from the bridge, shown as an elimination line.
3. **Constant currency first.** Every effect except FX is measured at **P0 average FX**. `FX = Σ(P1 local-currency GL) × (fx1 − fx0)` over *all* GL lines, so nothing is counted twice and fixed fees in local currency don't "move" from translation.
4. **Two layers.** `Actual flux = Δ expected trade cost (volume + mix + rate) + FX + Δ fails (one-off) + Δ fixed + Δ timing + unexplained`.
   * **Volume / mix / rate** come from `expected_cost` (trade × approved rate card) inside groups that share a volume unit: `cost_type × fee_basis × product_family`. Slice = group × desk × vendor × venue × capacity × market. Corrected SQL from spec §5 (identity `vol + mix + rate = Δc` holds per slice).
   * **Fails** are rule-based from settlements × `fail_cost_rule`, accrued daily, net of recharges.
   * **Timing** = Δ(GL − driver-based cost) on mapped GL keys (account × cost centre × vendor): accrual over or under estimates and their reversal.
   * **Unexplained** = residual, which by design equals GL booked to vendors **missing from `map_vendor_counterparty`** (the mapping-coverage expectation). Threshold: US$25K or 5% of flux.
5. **Fiscal calendar:** April–March. FY2026/27 Q1 = Apr–Jun 2026, Q2 = Jul–Sep 2026, H1 = Apr–Sep 2026. Comparisons precomputed: 12 × MoM, 3 × QoQ, plus H1 YTD actual vs plan.
6. **Invoices lag one period.** As-of date is the September close (WD3, 2026-10-05). August invoices are in (Broker C's arrived 2026-09-28); September invoices are not yet received.

### 5.2 Target bridge and the mechanism behind every cell (September vs August, US$K)

| Slice | Volume | Mix | Rate | Fails | Timing | FX | Unexpl. | Total |
|---|---|---|---|---|---|---|---|---|
| Equity Derivatives, exchange + clearing (2,170 → 2,680) | +390 | +90 | +60 | 0 | −20 | −10 | 0 | **+510** |
| Rest of APAC Global Markets (2,830 → 3,520) | +510 | +100 | +40 | +150 | −30 | −90 | +10 | **+690** |
| **APAC Global Markets (5,000 → 6,200)** | **+900** | **+190** | **+100** | **+150** | **−50** | **−100** | **+10** | **+1,200** |

| Cell | Planted mechanism (all fictional, modelled on public schedules) | Calibration lever |
|---|---|---|
| ED volume +390 | Volatility spike 8–19 Sep (PRX Volatility Index, VHSI-like, ~19 → ~33). Listed-derivative contract-sides +18.06% across all ED groups | Group growth γ = 1 + 390 / E₀ |
| ED mix +90 | Booking change: ~140.6K *PRX 50 Index Futures* contract-sides moved from the registered **market-maker account (HK$5.00 concession)** to the **house account (HK$10.00)**. Booked in the higher-fee capacity | Shift size |
| ED rate +60 | Time-limited **50% discount on PRX Tech Index Futures ended 31 Aug** (HK$2.50 → HK$5.00 per contract-side) on 187.5K September contract-sides. Modelled on HKEX's HS TECH discount; **not a real action** | September Tech volume |
| ED timing −20 | August accrual over-estimated by US$10K (HKD), reversed in September; September accrual re-based to expected cost | Accrual error |
| ED FX −10 | ED costs are mostly HKD (pegged) and USD (MRX China 50 futures). The FX comes from KRW / AUD / TWD index futures | Solved last |
| Rest volume +510 | Cash equities and Connect flow up with volatility (~+20–25%), FICC up ~+10% | Absorber group γ |
| Rest mix +100 | Smart-order-router change on 2 Sep moved ~A$3.8B of Australian cash flow from **Tasman Alternative Market (0.20 bp)** to **Southern Cross Exchange (0.60 bp)** | Shift size |
| Rest rate +40 | **Indus Exchange moved Meridian from its slab rate to a uniform transaction charge on 1 Sep** (+0.072 bp). Modelled on India's 2024 "true to label" change; **not a real action** | September IGX turnover |
| Fails +150 | Australia cash equities: **Kestrel Asset Management** SSI static-data mismatch after a custodian change → a cluster of fails at the A$5,000/day cap (ASX-style 0.10%/day, min A$100, max A$5,000) plus two buy-ins. Ops gets a ranked fix list | One absorber fail in the linear band |
| Rest timing −30 | August accrual over-estimated by US$15K (AUD / INR), reversed in September | Accrual error |
| Rest FX −90 | Local currencies weaker vs US$ in September (AUD ≈ −2.6%, KRW ≈ −3.1%, INR ≈ −1.1%, TWD ≈ −1.7%, SGD ≈ −0.8%, MYR ≈ −1.0%, CNH ≈ −0.4%, HKD ≈ flat) | 2×2 solve (two currencies) to hit both slices exactly |
| Unexplained +10 | GL from two vendors not yet mapped (US$5K August → US$15K September) | Unmapped GL lines |
| **Broker C +US$85K** (outside the bridge) | **Cobalt Securities ("Broker C")** August invoice billed the standard 3.0 bp tier on US$1.70B of turnover despite qualifying for the ≥US$1.2B tier (2.5 bp): a missed volume-tier rebate. Disputed (AP hold), so it never hits the September P&L | August Broker C turnover |
| Story 7 (optional) | Southern Cross IRF volume-discount rebate accrued monthly, trued up when credited (July, visible in Q2 vs Q1) | — |
| Story 8 (optional) | Affiliate (MES) charges tagged and eliminated | — |

Derived checks: good (volume) 900 = 75%; controllable (mix + fails) 340 = 28%; rate + timing + FX + residual = −40 = −3%.

### 5.3 Generator method (why it can't drift)

1. **Design:** compute slice-month aggregates for Aug and Sep analytically (volume, unit rate, currency) from the canonical rate cards so every target is hit; background months (Sep-2025…Jul-2026) carry realistic seasonality, the 1 July annual reset, run-rate accrual noise and occasional billing errors.
2. **Realize:** split each slice-day into executions (lognormal sizes, exact integer contract sums, exact notional sums; trade sizes kept inside fee floor/cap bands so per-trade min/max logic exists but doesn't bind on the planted slices).
3. **Book:** GL journals (accrual, reversal, invoice, fixed, fails, unmapped), AP invoices (with GST lines, received dates, the Broker C error), settlements and fails.
4. **Verify:** an independent Python implementation of the Gold logic recomputes the bridge from the *files*. Landing is blocked unless every cell rounds to target, totals are within ±US$50 and Broker C = US$85K. The same checks run again in SQL against Gold as a job task.

### 5.4 Volumes (spec §6)

12 desks (HK cash eq, HK equity derivatives, Stock Connect / China flow, Korea & Taiwan equities, Australia cash eq, India equities, flow credit, Singapore FX, Singapore rates, Singapore EM incl. Malaysia, Australia rates & futures, Delta One / Prime); 7 legal entities (HK, SG, AU, IN, KR, HK-Taiwan branch, MY); 8 brokers (one affiliate); 10 venues; 4 CCPs; ~3.0M executions over 13 months ending Sep-2026; ~20K GL lines; ~600 invoices / ~8K lines; 20 rate-card PDFs including Traditional Chinese and Korean cards.

## 6. Work breakdown, owners and acceptance

| Phase | Scope | Owner | Acceptance |
|---|---|---|---|
| **0. Foundation** | Bundle skeleton; catalog, schemas, volumes; serverless warehouse; Lakebase project; groups (`ce_fpa_analysts`, `ce_fpa_approvers`, `ce_desk_head_eqd`, `ce_cfo_office`); **hello-world FastAPI + Vite smoke-test app** (spec Appendix B) | Lead SA + app stream | `bundle validate --strict` clean; smoke app `/api/health` = 200 through the Apps proxy |
| **1. Data + rate cards** | Reference and master data with deliberate mapping gaps; canonical rate cards; calibrated generator; local verifier; land files; PDFs (EN / 繁中 / 한국어) | Lead SA (generator); PDF stream | Verifier reproduces §5.2 to the US$K; row counts per §5.4 |
| **2. Pipelines + expected cost** | Fee extraction job (`ai_parse_document` → `ai_query` → confidence → approval → `silver.fee_schedule`); SDP pipeline (bronze → silver → gold with expectations incl. mapping coverage); orchestrator job `ce_build` (generate → extract → pipeline → tie-out) | Lead SA; extraction stream | SQL tie-out task green: 24 cells + US$85K + 75% / 28% shares |
| **3. Metric views + dashboard** | `mv_cost_flux`, `mv_trade_costs`, `mv_invoice_recon`, `mv_fails` (descriptions, synonyms, window measures); AI/BI dashboard (Flux, Good vs bad, Drill to trade, Invoice vs expected, Fails, Fee calendar; market and local-currency drill) | Lead SA (MVs); dashboard stream | Waterfall shows §5.2; drill reaches executions |
| **4. Genie space** | Space on metric views + selected Gold tables; instructions (fiscal calendar, flux classes, net vs gross); sample questions and benchmarks (spec §8) | Genie stream | Both scene-2 questions exact; ≥ 8/10 benchmarks |
| **5a. Commentary agent** | UC SQL functions as tools; MLflow ResponsesAgent; output = markdown + figure references (`figure_key`, value, source table, filter, version); MLflow eval set; deployed to `ce-commentary-agent` | Lead SA | Draft for Sep vs Aug cites only figures that tie to Gold; eval pass |
| **5b. Review app** | Four screens; API surface from spec §4; OBO reads; Lakebase `commentary`, `commentary_figure`, `approval_event`, `draft_job`; async drafting (202 + poll); four-eyes; optimistic concurrency; CSRF and Origin checks; replication to `cost_explain.review` | App stream | Draft → edit → submit → approve (different user) → audit, end to end in the deployed app |
| **6. Governance, tie-out, talk track** | Governed tags + ABAC row filters by desk / market / entity; lineage walkthrough; talk track, run-of-show, pre-demo checklist, backup screenshots | Lead SA | Dry run of 8 scenes ≤ 30 min |

**Parallel streams.** The app stream starts now, contract-first against §7, with mocks until Gold lands. The PDF and extraction stream starts once the canonical rate cards are fixed in Phase 1. Dashboard and Genie streams start once metric views exist. Only the Lead SA edits `databricks.yml`; streams own their own `resources/*.yml` and `src/<area>/`.

## 7. Data contracts (shared by all streams)

**Gold tables (`cost_explain.gold`)**

| Table | Grain | Purpose / key columns |
|---|---|---|
| `dim_comparison` | comparison | `comparison_id` (`MOM_2026-09`, `QOQ_FY26Q2`, …), `comparison_type`, `period_p0`, `period_p1`, labels, `is_default` |
| `cost_flux_bridge` | comparison × business × desk × cost_type × vendor × market × legal_entity × currency | `p0_actual_usd`, `p1_actual_usd`, `p1_cc_usd`, `volume_usd`, `mix_usd`, `rate_usd`, `fx_usd`, `fails_usd`, `fixed_usd`, `timing_usd`, `unexplained_usd`, `flux_usd`, `cost_category` |
| `cost_flux_effects` | long form of the bridge (view) | `effect`, `effect_order`, `flux_class` (Good / Controllable / External, timing and residual), `amount_usd` |
| `cost_flux_slice` | comparison × driver slice | group (`cost_type`, `fee_basis`, `product_family`), desk, vendor, venue, capacity, market; `v0`, `v1`, `c0_usd`, `c1_cc_usd`, unit rates, `volume_usd`, `mix_usd`, `rate_usd` |
| `expected_cost_trade` | trade × fee line | `trade_id`, dates, desk, product, venue, vendor, `cost_type`, `fee_basis`, `volume`, `rate`, `fee_schedule_id`, `cost_lcy`, `cost_usd`, `is_recoverable`, `is_affiliate` |
| `expected_cost_daily` | day × slice | aggregated expected cost (gross, borne, recoverable) |
| `fail_cost_detail` / `fail_cost_summary` | fail / month × desk × entity × market × counterparty × root cause | per-day fees, default fees, buy-ins, recharges, net, funding and borrow (separate) |
| `invoice_recon` | vendor × entity × service period × cost type (lagged one period) | expected vs invoiced (lcy / usd), variance, reason, status, `finding_id` |
| `cost_monthly` / `cost_kpis` | month × desk (× cost type …) | actual, expected, gross, recoverable, eliminated; cost per trade, per US$M notional, bps of revenue, fail rate, plan |
| `fee_calendar` | fee change | upcoming effective-from / effective-to dates and cost impact at current volumes |
| `commentary_figures` | figure | `figure_key`, `comparison_id`, scope, metric, `value_usd`, `source_table`, `filter_expr` (resolver for app chips) |

**Lakebase (`cost_explain_app` database):** `commentary`, `commentary_figure`, `approval_event`, `draft_job`, exactly as in spec §4.
**App API:** as spec §4. `period` = `comparison_id`; `slice` = `APAC` | `business:<name>` | `desk:<code>` | `category:<name>`.
**Agent endpoint:** `ce-commentary-agent` (Responses API). Input: comparison_id, slice, tone. Output: `{commentary_markdown, figures[]}`, with figure chips written as `[[fig:<figure_key>]]` in the text.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Planted numbers drift (the demo's credibility rests on the bridge adding up) | Design-first generator, independent verifier gating the landing step, SQL tie-out task in the build job |
| `ai_parse_document` weaker on Chinese / Korean images | Headline path uses English cards; extraction accuracy is reported per language; the analyst approval step guarantees approved rates (the simulated analyst review is disclosed in docs) |
| App user-authorization scopes restricted or unsupported | Probe early in the smoke test; fallback = service principal reads plus an explicit entitlement pre-check |
| Lakehouse Sync (Beta) unavailable | Delta write-back fallback job into `cost_explain.review` |
| Proxy timeouts on drafting | Async job + polling; state in Lakebase |
| Genie answer variance | Precomputed Gold, metric views with synonyms, benchmarks, curated instructions |
| AI/BI waterfall rendering | Use a native waterfall if available; otherwise a stacked-bar bridge; the app renders the canonical Recharts waterfall |
| Cold starts during the live demo | Pre-warm the warehouse, app and agent (RUNBOOK checklist) |

## 9. Open items carried from spec Appendix B

Naming ("Meridian" synthetic entity, kept), the client's real desk list and hubs, GL system and the mapping to "Commissions and floor brokerage", fail-cost schedules outside ASX (fictional, flagged as illustrative), settlement-cycle timelines, Chinese / Korean extraction quality (measured here on synthetic cards), app scopes in the client's workspace, Git-only deploy policy, Lakehouse Sync acceptability, four-eyes control confirmation. These remain customer-discovery items. The build parameterizes each so it can change without code rewrites.

## 10. Deviation log

| # | Area | Deviation | Reason |
|---|---|---|---|
| 1 | Region | Built in AWS us-west-2, not SG / SYD / BOM | User choice; bundle is portable; residency covered in the talk track |
| 2 | Data gen | numpy calibrated generator instead of pure Spark + Faker | Exact tie-out is the acceptance test; still runs as a serverless job and lands raw files to a Volume |
| 3 | Catalog | `cost_explain` created by SQL (`scripts/bootstrap_catalog.sh`), not the bundle `catalogs` resource | The account uses Default Storage; the catalogs API rejects creation without a managed location |
| 4 | Lakebase → UC | Lakehouse Sync replaced by job `ce_review_sync` (Lakebase registered as catalog `cost_explain_lakebase`, MERGE into `cost_explain.review`) | Lakehouse Sync does not support Default Storage catalogs — the spec's documented fallback |
| 5 | ABAC | Desk security via UC row filters (`WITH ROW FILTER` on the Gold MVs) instead of a governed-tag ABAC policy; `abac.sql` kept for the customer workspace | The shared FEVM account hit its governed-tag (tag policy) limit; same entitlement logic, verified with a persona (docs/GOVERNANCE.md) |
| 6 | Groups | Role and desk-head groups are workspace-local; the row filter checks `is_member()` as well as `is_account_group_member()` | Workspace admin cannot create account groups here; on a customer workspace use account groups |
| 7 | Volumes | ~3.28M executions, 2.6M settlements, 9.3K GL lines, 640 invoices / 5.4K lines | Spec sizes are approximate ("~"); GL is itemised by book × product × fee code |
| 8 | Bridge order | Effects ordered Volume, Mix, Rate, Fails, Timing, FX, Fixed, Unexplained | Matches the scene-2 narrative |
| 9 | LLM | `databricks-claude-sonnet-5-5` called without sampling parameters | The endpoint rejects `temperature`; the agent passes sampling options only when configured |
