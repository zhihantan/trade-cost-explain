# 04 — Gen AI: grounded commentary agent and PDF fee-schedule extraction

Recorded in workspace `fe-vm-zh-serverless` on 2026-10-22; copied from `docs/APP.md` §1b and `docs/EXTRACTION.md`.

## Commentary agent `ce-commentary-agent` (MLflow ResponsesAgent on Model Serving)

Design (`src/agent/commentary_agent.py`, tools in `src/agent/tools.sql`): plan → call Unity Catalog SQL functions over
Gold (bounded tool rounds) → write commentary in which **every number is a figure chip** (`[[fig:<figure_key>]]`) →
verify that each chip is a figure the tools returned (one repair round, then unknown chips are dropped).
Model-agnostic through a serving endpoint (`databricks-claude-sonnet-5-5` in this build).

| Check | Result |
|---|---|
| Agent draft end to end | model v2: 41–52 s per draft, 14–16 chips, all resolved, no value mismatches; edit → v3 → submit → four-eyes block on self-approval → audit. Early probes returned an empty message / `EXECUTE on get_cost_bridge` error; the template fallback covered them transparently |
| Figure keys | `CAT:<cost_category>` keys (spaces, `&`, `()`) resolve in chips and `/api/figures`; Kestrel hotspot `FAILS\|2026-09\|AUCE\|C001\|NET` = US$143K; `UNEXPLAINED_THRESHOLD` cited (APAC US$60K = 5% of the change, ED US$25.5K) |
| Entitlements | A desk head (HKED only) can draft `ED_EXCH_CLR` / `DESK:HKED` but not `APAC` (unit-tested; the agent may read Gold under its own principal) |

`src/agent/eval_agent.py` evaluates the deployed endpoint per scenario (APAC, ED exchange & clearing, rest of APAC,
an AU desk, Q2 vs Q1): grounding (every chip resolves and matches the registry value) and coverage (the planted drivers
are named, e.g. Kestrel fails, the Broker C over-billing, the market-maker concession), logged as one MLflow run.

## Fee schedules from PDFs: `ai_parse_document` → `ai_extract` → analyst review → `silver.fee_schedule`

> Tables: `rate_card_parsed` 20 docs · `fee_schedule_extracted` 139 lines · `rate_card_answer_key` 139 ·
> `fee_schedule_review` 139 · `fee_schedule` **119** approved lines · `fail_cost_rule` 8 rules.

| Language | Cards | Lines expected | Extracted | Matched first time | Corrected | Missed | Spurious | First-time accuracy | Mean confidence |
|---|---|---|---|---|---|---|---|---|---|
| en | 17 | 106 | 106 | 77 | 29 | 0 | 0 | 72.6% | 0.903 |
| ko | 1 | 6 | 6 | 3 | 3 | 0 | 0 | 50.0% | 0.95 |
| zh-Hant | 2 | 27 | 27 | 22 | 5 | 0 | 0 | 81.5% | 0.965 |
| all | 20 | 139 | 139 | 102 | 37 | 0 | 0 | 73.4% | 0.912 |

Field-level accuracy (each line has 20 compared fields): en 2090/2120 (98.6%) · ko 117/120 (97.5%) ·
zh-Hant 535/540 (99.1%) · **all 2742/2780 (98.6%)**.

Run history:

| Run | Prompt | Lines found | Lines fully right first time | Notes |
|---|---|---|---|---|
| 1 | v1 | 139 / 139 | 69 / 139 (49.6%): en 48.1%, zh-Hant 66.7%, ko 0% | Schema misuse (rate copied into `floor_per_trade`), % typed as "per million", broker commission typed as exchange fee |
| 2 | v2 | 139 / 139 | **102 / 139 (73.4%)**: en 72.6%, zh-Hant 81.5%, ko 50%; **98.6% of fields** | v2 added generic field semantics, unit-conversion examples and a bilingual glossary; nothing card-specific |

Runtime: about 12 minutes end to end (parse about 75 s; `ai_extract` on 20 documents about 10 minutes; review, publish
and guard about 1.5 minutes). The analyst approval step stays because first-time line accuracy is not 100% — the
weakest card was the Korean one — and only approved lines reach `silver.fee_schedule`.
