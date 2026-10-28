# Talk track — Trade Cost Explain (30-minute version)

Audience: Head of FP&A, Global Markets CFO, Business Finance (Sales & Trading), Product Control, Operations / Cost
Management. Entity: **Meridian Group, APAC Global Markets** (synthetic; built to mirror a US GAAP, April–March bank).
Say it once, early: *"Every number you'll see is synthetic and illustrative — the venues, brokers and fee changes are
fictional, modelled on public APAC fee structures."*

All figures below are what the deployed demo shows (tie-out verified by job `ce_build` → `gold.tie_out_results`).

| Asset | Where |
|---|---|
| AI/BI dashboard | https://fe-vm-zh-serverless-ws.cloud.databricks.com/sql/dashboardsv3/01f1cdaa355f19f88f21661e96bbf0a6/published |
| Review & approval app | https://cost-explain-app-2515635694809473.aws.databricksapps.com |
| Genie space | https://fe-vm-zh-serverless-ws.cloud.databricks.com/genie/rooms/01f1cda9f4a9153882ea4c4ecda34bc3 |
| Commentary agent | Model Serving endpoint `ce-commentary-agent` |

## Scene 1 — The flux (2 min) · AI/BI dashboard "Trade Cost Explain", page *Flux*
- Click: comparison filter = **Sep 2026 vs Aug 2026** (default). Point at the KPI row.
- Say: *"Half-year close. APAC Global Markets trade costs — the Commissions and floor brokerage line — went from
  **US$5.0M to US$6.2M, up US$1.2M or 24%**. Equity Derivatives is the biggest mover. This is where most month-ends
  start: a number with no explanation."*
- Toggle comparison to **FY2026/27 Q2 vs Q1** to show the fiscal calendar works, then back to Sep vs Aug.

## Scene 2 — Ask Genie (5 min) · Genie space "Trade Cost Explain"
1. Type: **"Why did APAC trade costs go up in September?"**
   Expected: volume **+US$900K**, mix **+US$190K**, rate **+US$100K**, fails **+US$150K**, timing / accrual
   **−US$50K**, FX **−US$100K**, unexplained **+US$10K** (fixed fees 0). *"The bars add up to the US$1.2M — Genie reads
   the governed bridge; it does not recompute it."*
2. Follow-up: **"And why did equity derivatives exchange and clearing fees go up?"**
   Expected: US$2.17M → US$2.68M (+US$510K): volume **+US$390K**, mix **+US$90K**, rate **+US$60K**, timing **−US$20K**,
   FX **−US$10K**, **no fails** — *"listed derivatives clear at a CCP; they don't settle through a depository."*
   (Genie returns the zero; say the CCP line yourself.)
3. Optional: *"Which brokers billed more than expected in fiscal Q2?"* → Cobalt Securities (Broker C) **+US$85K**
   (August, missed volume-tier rebate) and Dunmore Capital Markets **+US$68K** (July, duplicate line).

## Scene 3 — Good vs bad flux (3 min) · dashboard page *Good vs bad flux*
- *"**75% — US$900K — is volume-driven**, and revenue rose with it (volatility spike: the PRX Volatility Index went
  from ~20 to the low 30s in mid-September). **US$340K, 28%, is controllable** — mix plus fails. Rate, FX, timing and
  the residual net to **−US$40K**."*
- Point at the cost-vs-revenue overlay and the volatility line on the same axis of time.

## Scene 4 — Drill to the trade (4 min) · dashboard page *Drill to trade*
- From the Flux page's **mix +US$190K** bar, switch to the *Drill to trade* page (cross-page click-through is not
  available in AI/BI dashboards) — the venue / capacity / market split is already filtered to the comparison:
  - **HK Equity Derivatives, PRX 50 Index Futures: +US$90K** — ~140,600 contract-sides moved from the registered
    market-maker account (HK$5.00 concession) to the house account (HK$10.00): *"booked in the higher-fee capacity."*
  - **Australia Cash Equities: +US$100K** — the smart order router sent ~A$3.7bn from Tasman Alternative Market
    (0.20 bp) to Southern Cross Exchange (0.60 bp) from 2 September: *"routed to the higher-fee venue."*
- Open the execution table: individual trades with venue, capacity and fee paid. *"One click from a ledger line to the
  executions behind it."*

## Scene 5 — Invoice vs expected (4 min) · dashboard page *Invoice vs expected*
- *"Broker invoices arrive after month end — Cobalt Securities' (Broker C) August invoice arrived on 28 September, so
  the September close still runs on accruals."*
- Show **Cobalt Securities, August: expected US$425K, invoiced US$510K → US$85K over-billed**. Reason (inferred by the
  pipeline): *billed the standard 3.0 bp tier instead of tier 2 (2.5 bp) — August turnover of US$1.70bn qualifies:
  volume-tier rebate not applied.* *"A real savings finding — and it sits outside the September bridge: it's a billing
  correction claim on August. Accruals now re-base to expected cost automatically."*

## Scene 6 — Fails (3 min) · dashboard page *Fails*
- Fail cost by desk, legal entity, market (depository / CCP), counterparty and root cause.
- *"September fails are up US$150K, and they're concentrated: **Australia Cash Equities, Kestrel Asset Management**,
  root cause a **Meridian SSI static-data mismatch after Kestrel changed custodian** — fail fees at the Southern Cross
  rate of 0.10% a day (A$100–5,000), plus two buy-ins. Ops gets a ranked fix list, not just a cost number."*
- Funding and borrow cost are shown separately.

## Scene 7 — Commentary (5 min) · Databricks App *cost-explain-app*
1. Flux overview → open **Sep 2026 vs Aug 2026 · APAC** → *Draft commentary*. The agent (Model Serving,
   `ce-commentary-agent`, model-agnostic) drafts in the background (the UI polls).
2. Show figure chips: every number links to the Gold figure it came from (source table, filter, Delta version).
3. Edit a sentence, save (optimistic concurrency), submit for approval.
4. Approval queue: approve Ava Chen's seeded item (you cannot approve your own — four-eyes). Audit trail shows who
   drafted, edited and approved, when, with request ids.

## Scene 8 — Lineage (2 min) · Catalog Explorer
- From `cost_explain.review.v_commentary_figure_evidence` → `gold.commentary_figures` → `gold.cost_flux_bridge` →
  `gold.expected_cost_trade` / `gold.gl_monthly` / `gold.invoice_recon` → `silver.trades`, `silver.gl_actuals`,
  `silver.ap_invoice_lines`, `silver.fee_schedule` → `bronze.*_raw`, whose upstream is the `ce_medallion` pipeline
  (Auto Loader from the landing Volume — Unity Catalog records the pipeline, not each landed file).
- Then the fee-schedule branch back to the documents: `silver.fee_schedule` → `fee_schedule_review` →
  `fee_schedule_extracted` → `rate_card_parsed` → the rate-card PDFs in `/Volumes/cost_explain/landing/rate_cards/`.
- *"Audit and controllership trust: evidence for the control walkthrough, end to end."*

## If time is short
Compress scene 6; keep 1–5, 7 and 8.

## Likely questions
- **"How do you stop the bridge drifting?"** Constant currency first; FX on every GL line; volume / mix / rate inside
  groups that share a volume unit; identity checked on every row (`gold.tie_out_results`).
- **"Where do the rates come from?"** 20 PDF rate cards (English, Traditional Chinese, Korean) → `ai_parse_document` →
  `ai_extract` → analyst review → approved `silver.fee_schedule` (98.6% of fields right first time; see
  `docs/EXTRACTION.md`).
- **"Does this replace Snowflake?"** No — federate or share; Unity Catalog governs what lands here.
- **Residency:** this build is in AWS us-west-2; the bundle redeploys unchanged to Singapore / Sydney / Mumbai.
