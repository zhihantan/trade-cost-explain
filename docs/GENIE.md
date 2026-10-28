# Genie space — Trade Cost Explain — APAC Global Markets

Covers talk-track scene 2 (`docs/TALK_TRACK.md`) and ad-hoc questions over the governed cost bridge. The space was built
and benchmarked on 2026-10-22 against the live Gold layer and metric views. The final benchmark run passed 11 of 11.

| | |
|---|---|
| Space | **Trade Cost Explain — APAC Global Markets** · id `01f1cda9f4a9153882ea4c4ecda34bc3` |
| Open | [Genie space](https://fe-vm-zh-serverless-ws.cloud.databricks.com/genie/rooms/01f1cda9f4a9153882ea4c4ecda34bc3) |
| Workspace folder | `/Shared/trade-cost-explain` |
| Warehouse | `cost-explain-wh` (`5f36ded0f9befdd1`) |
| Source | `src/genie/build_space.py` generates `src/genie/trade_cost_explain.geniespace.json`. Benchmark and example SQL live in `src/genie/queries.py`. Edit the scripts, never the JSON. |
| Tools | `push_space.py` (create / update), `ask.py` (Conversation API), `eval_report.py` (benchmark run summary) |
| Bundle resource | `resources/cost_explain.genie_space.yml.pending`, staged (see [Binding into the bundle](#binding-into-the-bundle)) |
| Access | Genie runs every query as the asking user, so the desk row filter `gold.ce_desk_scope` applies (`docs/GOVERNANCE.md`). The `/Shared` folder already gives `users` CAN_MANAGE by inheritance; the bundle adds an explicit CAN_RUN. |

## Data sources

| Source | Why it is in the space |
|---|---|
| `gold.trade_cost_flux_metrics` | The precomputed bridge: prior, current, change, change %, the eight effects, good flux and its share. Every "why did costs move" answer reads it; nothing is recomputed. |
| `gold.trade_cost_metrics` | Monthly cost by fiscal period, desk, category and vendor: gross, recoverable and net borne cost, plus expected cost. |
| `gold.desk_cost_kpi_metrics` | Desk KPIs versus plan: cost per trade, bps of revenue, revenue, trades, settlements and fails. |
| `gold.invoice_recon_metrics` | Invoices against contracted rates: over- and under-billing, variance reasons, pending invoices. |
| `gold.settlement_fail_metrics` | Fail cost by counterparty, root cause, market and depository. |
| `gold.dim_comparison` | Comparison ids and labels (`MOM_2026-09`, `QOQ_FY2026Q2`, …), so Genie can resolve "Q2 vs Q1". `sort_order` is hidden. |
| `gold.fee_calendar` | Fee events: discounts and concessions ending, rate changes and regime changes, with monthly impact at current volumes. |

`gold.cost_flux_slice` was not added. The ED exchange-and-clearing slice is the `Headline Slice` dimension of
`trade_cost_flux_metrics`, so the extra table would only offer a second path to the same numbers.

## Knowledge store

Structured levers come first. Text instructions carry only what they alone can express: rules that span tables and the
format of summaries.

**Column metadata (56 column configs).** Most configs carry a description, and most also have synonyms, format
assistance and entity matching. The configs that change answers:

| Column | What it fixes |
|---|---|
| flux `Comparison`, `Comparison Label` | Lists the comparison ids (`MOM_2026-09` is the default; `QOQ_FY2026Q2` is "Q2 vs Q1") |
| flux `Headline Slice` | Maps "equity derivatives exchange and clearing fees" to `'Equity Derivatives — exchange & clearing'`; notes that listed derivatives clear at a CCP, so the slice has no fails |
| flux `Good Flux`, `Good Flux Share` | "Matched by revenue growth" means good flux (the volume effect), never revenue growth divided by the cost change |
| `Vendor` (flux, invoices) | Synonym "Broker C" → Cobalt Securities |
| `Desk` (flux, cost, KPIs) | Exact desk names per hub (Hong Kong, Singapore, Australia, Mumbai, Seoul / Taipei), including `'Singapore EM (incl. Malaysia)'` |
| KPIs `Cost per Trade` | Rank desks on the latest month unless a period is named; "which desks are highest" means the top five |
| settlement `Desk` | Desk codes (HKCE, AUCE, …) mapped to names |
| cost `Cost Category`, `Gross Trade Cost`, `Recoverable Levies and Taxes`, `Net Borne Trade Cost` | Levies and taxes: gross incurred, recharged to clients, borne |
| invoices `Service Period`, `Variance Reason` | The one-month invoice lag: a range that includes September (fiscal Q2) is answered from the months available, without a clarifying question. The reason text differs by legal entity, so per-vendor totals don't group by it |
| fee calendar `event_type`, `monthly_impact_usd`, `as_of_date` | RATE_CHANGE also covers concessions replaced by a new rate. "Expiring" means after `as_of_date`, across all three event types |

**SQL filter snippets.** There are three:
- `Comparison = 'MOM_2026-09'`, with the synonyms September / this month / Sep vs Aug / half-year close;
- `Comparison = 'QOQ_FY2026Q2'` (Q2 vs Q1);
- the ED exchange-and-clearing `Headline Slice`.

**Example SQL (8).** Each example teaches a query shape. Their literals differ from the benchmarks (other periods and
slices), so the benchmarks still test generalisation.

| | Question | Shape |
|---|---|---|
| E01 | What drove the change in trade costs in fiscal Q2 versus Q1? | Full bridge for one comparison |
| E02 | Break down the August versus July movement in Cash Equities exchange and clearing fees. | Bridge for a slice |
| E03 | Which desks drove the mix effect in September? | Contributors to one effect (HAVING, absolute order) |
| E04 | Which vendors were over-billed for July 2026 services? | Total per vendor and month, `max_by` main reason |
| E05 | Compare the settlement fail rate of Hong Kong and Australia desks in August. | Hub mapping in a CTE, then re-aggregated from the components |
| E06 | Which fee schedule changes have taken effect since July and what do they cost per month? | Fee calendar by status and date |
| E07 | Show net borne trade cost and expected cost by fiscal quarter. | Fiscal-calendar trend |
| E08 | What share of the fiscal Q2 versus Q1 cost increase came from higher activity, and how did revenue move? | Good flux and its share, next to revenue |

**Text instructions (1,948 of 2,000 characters).** These cover:
- the fiscal year (April–March; Q2 = Jul–Sep 2026; H1 = Apr–Sep 2026);
- the default period (September 2026, and September vs August for changes);
- the answer shape for "why did costs go up": prior, current, change, change % and all eight effects in the order
  Volume, Mix, Rate, Fails, Timing / accrual, FX, Fixed fees, Unexplained, never recomputed;
- the flux classes: good flux = volume; controllable = mix + fails; external = rate + FX + timing + fixed + unexplained;
- Broker C;
- net borne as the headline and gross as the drill;
- the invoice lag (2026-08 is the latest reconcilable month);
- the plan start (April 2026);
- summary rules:
  - amounts under US$1M in US$K, and US$1M or more in US$M with two decimals;
  - the effects as one signed list in bridge order;
  - zero fails on Equity Derivatives explained by CCP clearing;
  - the synthetic-data caveat.

The full text is in `TEXT_INSTRUCTIONS` in `build_space.py`.

**Sample questions (11).** The ten questions of master prompt §8, including the Traditional Chinese one, plus the scene-2
follow-up *"And why did equity derivatives exchange and clearing fees go up?"*. The directive required the §8 questions,
so the sample questions repeat benchmark questions. The Genie guidance discourages this overlap; it is a deliberate
deviation.

## Benchmarks

There are 11 benchmarks. B01–B10 are master prompt §8, and B11 is the scene-2 follow-up asked on its own. Every
expected SQL was run read-only on the warehouse before it was added.

| | Question | Expected (September 2026 unless stated) |
|---|---|---|
| B01 | Why did APAC trade costs go up in September vs August? | US$5.00M → US$6.20M (+US$1.20M, +24%). Volume +900K, mix +190K, rate +100K, fails +150K, timing −50K, FX −100K, fixed 0, unexplained +10K |
| B02 | 9月亞太區交易成本上升的主要原因是什麼？ | Same as B01 |
| B03 | Which desks have the highest cost per trade, and how has it trended? | Top 5 desks by September cost per trade, monthly trend Sep 2025 – Sep 2026 (65 rows) |
| B04 | How much of the trade cost increase is matched by revenue growth? | US$900K (75%) of the US$1.20M is volume-driven. Revenue US$44.67M → US$53.74M (+US$9.08M) |
| B05 | Which brokers billed more than the expected cost in fiscal Q2 (July–September)? | Cobalt Securities (Broker C) +US$85K (Aug); Dunmore Capital Markets +US$68K (Jul) |
| B06 | What are the top 5 counterparties by settlement-fail cost this month? | Kestrel Asset Management US$145K, far ahead; then Raffles Quay, Lotus Pond, Darling Harbour, Harbourview (about US$4K each) |
| B07 | Show trade costs as bps of revenue by desk vs. plan. | 12 desks, actual vs plan bps |
| B08 | Compare cost per trade in Hong Kong, Singapore and Australia. | Australia US$20.5, Hong Kong US$23.1, Singapore US$24.1 |
| B09 | Which fee discounts, waivers or regime changes expire in the next six months, and what is the cost impact at current volumes? | 1 Jan 2027: Mini PRX 50 market-maker concession ends (+US$29.1K a month); MRC CN50 clearing fee rises (+US$11.5K a month) |
| B10 | How much of our cost is statutory levies and taxes, and how much of that do we recharge? | Gross US$12.73M; recharged US$12.47M; borne US$0.26M |
| B11 | Why did equity derivatives exchange and clearing fees go up in September vs August? | US$2.17M → US$2.68M (+US$510K). Volume +390K, mix +90K, rate +60K, fails 0, timing −20K, FX −10K |

**Eval history.** Every run used the Genie benchmark eval API. The optimisation passes were kept separate: two passes
repaired the benchmarks, and seven passes tuned the space, one lever at a time.

| Run | Eval run id | Change before the run | §8 (B01–B10) | B11 | Failures and cause |
|---|---|---|---|---|---|
| 1 | `01f1cdaa7efa1a17889eefc07cb64734` | Initial space | 5/10 | GOOD | B03: top 5 vs all desks. B04: revenue ÷ cost. B05: Cobalt split by reason text. B09: empty result, upcoming events are RATE_CHANGE. B10: no gross |
| 2 | `01f1cdab91fc171a81e84c91eaf7686d` | Benchmark repair: B03 is top 5 with trend | 4/10 | GOOD | B03 and B05: correct but missing expected columns. B08: `'Singapore EM'` without "(incl. Malaysia)". B04, B09, B10 as before |
| 3 | `01f1cdac729b1f3283447da6d3bede2f` | Benchmark repair: B03 and B05 expect only canonical columns | 7/10 | GOOD | B04, B09, B10 |
| 4 | `01f1cdad6b851b06a1c6188b650f14a5` | Tuning: column metadata (good flux, levies, event types, variance reason, exact hub desk names) | 9/10 | GOOD | B04: still revenue vs cost from the KPI view |
| 5 | `01f1cdae68281c1d91001501a4b9e73a` | Tuning: example E08 (good flux next to revenue) | 9/10 | GOOD | B05: grouped by `Variance Reason`, taught by example E04 |
| 6 | `01f1cdaf5b7615b8948fa5597d0f3aef` | Tuning: E04 totals per vendor | **10/10** | GOOD | — |
| 7 | `01f1cdb0077a1ac8bacb031cc66d8840` | Tuning: summary rule for bridge order and CCP | **10/10** | GOOD | — |
| 8 | `01f1cdb13d021778903dfdc761a919f3` | Tuning: summary units (US$K below US$1M) | **10/10** | GOOD | — |
| 9 | `01f1cdb28f7e131cab61a2f7b42421d7` | Tuning: no clarifying question for invoice ranges that include September | 9/10 | GOOD | B03: ranked on all months and returned only the top desk |
| 10 | `01f1cdb3998f19409c3c4be3cc6f34f7` | Tuning: `Cost per Trade` ranking note (latest month, top five) | **10/10** | GOOD | — |

Final result (run 10, the final configuration): 11 of 11. Runs 6–10 scored 11, 11, 11, 10 and 11 of 11, and §8 has met
the ≥ 8/10 bar in every run since run 4. Genie's SQL still varies from run to run (aliases, CTE shape, extra columns).
The scorer accepts correct supersets, so the expected SQL returns only the canonical columns.

## Scene 2 script (verified 2026-10-22)

Ask both questions in **one** conversation. Both answers come from `trade_cost_flux_metrics` on `MOM_2026-09`, and each
takes about 20 seconds.

1. **"Why did APAC trade costs go up in September?"**
   - Expected: US$5.00M → US$6.20M, +US$1.20M (+24%).
   - The bridge: volume **+US$900K**, mix **+US$190K**, rate **+US$100K**, fails **+US$150K**, timing / accrual
     **−US$50K**, FX **−US$100K**, fixed fees **US$0K**, unexplained **+US$10K**.
2. **"And why did equity derivatives exchange and clearing fees go up?"**
   - Expected: US$2.17M → US$2.68M, +US$510K (+24%).
   - The bridge: volume **+US$390K**, mix **+US$90K**, rate **+US$60K**, fails **US$0K**, timing / accrual **−US$20K**,
     FX **−US$10K**, fixed fees and unexplained **US$0K**.
   - Genie adds the slice filter `Headline Slice = 'Equity Derivatives — exchange & clearing'`.
   - The presenter adds: *"listed derivatives clear at a CCP; they don't settle through a depository."*
3. Optional: **"Which brokers billed more than expected in fiscal Q2?"** Expected, from the July and August service months
   (September invoices are pending):
   - Cobalt Securities (Broker C): +US$85K in August, because the volume-tier rebate was not applied;
   - Dunmore Capital Markets: +US$68K in July, a possible duplicate line.

Scene-2 conversations: `01f1cdb3b7eb170790c0a32d079dae3c` (final configuration), plus `01f1cdb0c60612fcb022ce998efa70fb`
and `01f1cdb10e481ac4b451d806288a3316` (same instructions, before the last two column notes). The optional broker question
was checked in `01f1cdb2aa6d1d5d965fb67fdf9b3563` and `01f1cdb2c277132a84f99122d3999bba`.
- **Figures:** exact in every run.
- **Wording:**
  - Every run gave the bridge as one signed list in US$K.
  - One run listed fails before rate.
  - None mentioned the CCP on its own, which is why the presenter says it.
  - The broker answers name July and August as the months in the data; one of the two also gives the reasons.
- **Fallback:** if the phrasing differs, point at the effects table in the answer (`docs/RUNBOOK.md`).

## Binding into the bundle

The space was created through the Genie API, so the bundle resource is staged as `.pending`. Enabling it as-is would
create a second space on the next deploy.

`bundle validate --strict` passes with the file enabled; this was checked in a scratch copy of the bundle. The resolved
`parent_path` is `/Workspace/Shared/trade-cost-explain`, the folder of the existing space. That field is immutable, so
keep it.

To adopt the existing space:

```bash
mv resources/cost_explain.genie_space.yml.pending resources/cost_explain.genie_space.yml
databricks bundle deployment bind trade_cost_explain_genie 01f1cda9f4a9153882ea4c4ecda34bc3 --profile fe-vm-zh-serverless
databricks bundle plan --profile fe-vm-zh-serverless     # genie_spaces.trade_cost_explain_genie must not show "create"
databricks bundle deploy --profile fe-vm-zh-serverless
```

The app's optional "Ask Genie" panel needs two changes:
- set `GENIE_SPACE_ID` to `01f1cda9f4a9153882ea4c4ecda34bc3`;
- add the commented `genie-space` resource in `resources/cost_explain_app.app.yml.pending`.

## Rebuild and iterate

Run these from the repository root. The scripts use the `fe-vm-zh-serverless` profile and retry transient IP-ACL errors.

```bash
python3 src/genie/build_space.py                                   # regenerate the .geniespace.json
uv run --with databricks-sdk python src/genie/push_space.py update 01f1cda9f4a9153882ea4c4ecda34bc3
databricks genie genie-create-eval-run 01f1cda9f4a9153882ea4c4ecda34bc3 --json '{}' --profile fe-vm-zh-serverless
uv run --with databricks-sdk python src/genie/eval_report.py <eval_run_id>
uv run --with databricks-sdk python src/genie/ask.py "<question>" [conversation_id]
```

The live definition matches the file. The API does two things differently, and neither changes the content:
- it splits the text instruction into lines;
- it returns the benchmarks in a different order.

Once the space is bound, change it through the bundle so the deployed state and the file don't drift.

## Known limitations and upstream notes

- **Hubs.** `desk_cost_kpi_metrics` has no Hub dimension, so Genie maps desks to hubs from the `Desk` description (CTE,
  then re-aggregation). A `Hub` dimension in the metric view would make hub questions sturdier.
- **Settlement desks.** `settlement_fail_metrics.Desk` holds desk codes; the other metric views use desk names.
- **Cobalt fee descriptions.** They differ by market in `rate_cards.yaml`: COB-STD-KR reads "Standard tier (< US$1.2bn) —
  3.0 bps", while TW and IN read "Standard tier — 3.0 bps". As a result, `variance_reason` differs by entity for the same
  finding. Normalising the descriptions would remove the need for the E04 pattern.
- **Levies category label.** The `Cost Category` label `'Levies & taxes (borne)'` also carries the recharged gross for
  levy and tax lines. In gross views that reads oddly; "Levies & taxes" would be clearer.
- **Data sources shape.** The Genie API stores metric views under `data_sources.tables`, so the file uses the same shape.
