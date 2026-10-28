# Fee schedules: from PDF to approved rates

How the demo turns 20 broker, exchange and clearing-house rate cards (English, Traditional Chinese, Korean) into the
`cost_explain.silver.fee_schedule` table that drives expected cost, and how accurate the AI extraction was.
All issuers are **fictional**. Rates are modelled on public HKEX, SGX, ASX and NSE/BSE fee structures and are illustrative.

## Flow

```
src/datagen/config/rate_cards.yaml      canonical rate cards (single source of truth, owned by the Lead SA)
        │  src/rate_cards/render.py     HTML → PDF (plutoprint), CJK/Hangul font embedded, layouts vary by issuer
        ▼
/Volumes/cost_explain/landing/rate_cards/*.pdf        20 PDFs (17 EN, 2 繁中, 1 한국어)
        │  job ce_fee_extraction (serverless, resources/ce_fee_extraction.job.yml)
        ├─ parse_documents      ai_parse_document v2.0                → silver.rate_card_parsed
        ├─ extract_fee_lines    ai_extract v2.1, JSON schema, per-field confidence scores
        │                                                             → silver.fee_schedule_extracted
        ├─ analyst_review       answer key + field-level comparison   → silver.rate_card_answer_key
        │                                                               silver.fee_schedule_review
        │                                                               silver.fee_schedule_extraction_summary
        ├─ publish_fee_schedule approved rates (canonical values)     → silver.fee_schedule, silver.fail_cost_rule
        └─ guard_fee_schedule   fails the run on row-count / integrity drift
```

Also landed for the pipeline: `/Volumes/cost_explain/landing/raw/ref/vendor_contracts.csv` (fixed connectivity contracts,
which come from the Procurement contract register rather than a PDF) and `/Volumes/cost_explain/landing/raw/ref/fail_cost_rule.csv`.

## The rate cards

| Card | Issuer (fictional) | Language | Lines | What makes it hard |
|---|---|---|---|---|
| RC01 | Pearl River Exchanges & Clearing — securities | EN | 8 | Two vendors on one card (exchange vs clearing house), % of consideration, settlement fee with min/max, statutory levies and stamp duty |
| RC02 | Pearl River — derivatives | EN | 22 | Per contract per side, market-maker concessions, a time-limited 50% discount (ends 31 Aug 2026), a concession expiring 31 Dec 2026 and a replacement rate from 1 Jan 2027 |
| RC03 | Pearl River — derivatives (繁體中文) | zh-Hant | 22 | Traditional Chinese edition of RC02 ("港幣10.00元", "每張合約每邊", "登記莊家賬戶"); cross-language check, not a second source of rates |
| RC04 | Pearl River Connect — northbound | EN | 5 | Seller-only stamp duty, a clearing-house line on an exchange card |
| RC05 | Merlion Exchange & Clearing | EN | 8 | Clearing fee capped at S$600, GST 9%, US$-denominated futures on an SGD card |
| RC06 | Southern Cross Exchange Group | EN | 14 | 1 July annual reset (two effective periods per fee), bps vs % notation, IRF volume rebate tier, fail-fee rule in the notes (not a fee line), GST 10% |
| RC07 | Tasman Alternative Market | EN | 2 | Low-fee alternative venue (the routing-mix story) |
| RC08 | Indus Exchange & Clearing | EN | 11 | Rates in "₹ per crore", slab tiers on monthly turnover in ₹ crore, a uniform charge from 1 Sep 2026 |
| RC09 | Deccan Exchange | EN | 5 | Buyer-only stamp duty |
| RC10 | Han River Exchange (한국어) | ko | 6 | Korean only: "1,800원", "계약당·편도", seller-only transaction tax |
| RC11 | Formosa Exchange (繁體中文) | zh-Hant | 5 | Traditional Chinese only: "新台幣30元", "每口每邊" |
| RC12 | Straits Exchange | EN | 4 | Caps on clearing fee and stamp duty |
| RC13 | Cobalt Securities ("Broker C") | EN | 9 | Tiered commission on aggregate US$ monthly turnover, rebate mechanics, invoiced in local currency of each market |
| RC14–RC20 | Brokers (Aurora, Bluewater, Dunmore, Emberly, Foxglove, Goldcrest, Meridian Execution Services) | EN | 1–5 | Letter format; per-contract, per-million and bps commissions; intra-group affiliate schedule |

Answer key: 139 lines across 20 documents. Approved schedule: 119 lines (117 from cards excluding the RC03 copy, plus 2 vendor contracts).

## The analyst review (and why the pipeline stays deterministic)

The approval step is the control. Each extracted line is matched to the line the analyst expects to see in that document
(`silver.rate_card_answer_key`), field by field, and gets a status:

| Status | Meaning | What the analyst does |
|---|---|---|
| `MATCHED` | Every compared field equals the document | Approves as extracted |
| `CORRECTED` | Line found, at least one field wrong | Corrects the field(s); reason logged (e.g. "rate 0.00565 → 0.565 (unit conversion)") |
| `MISSED` | Line in the document but not extracted | Adds it manually |
| `SPURIOUS` | Extracted line with no fee behind it | Rejects it |

`silver.fee_schedule` therefore always carries the canonical values, with `extraction_confidence`, `extraction_status`,
`approved_by` and `approved_at` from the review. **Disclosure for the demo:** the reviewer (`ava.chen@meridian-demo.example`,
fictional) is simulated by comparing against the canonical cards that generated the PDFs, standing in for the analyst's
knowledge of the documents. In production the same table is an approval queue worked by a person.

Compared fields: vendor, product family, cost type, fee basis, capacity, side, rate, currency, tier basis / bounds / type,
floor and cap, pass-through flag, discount flag, GST rate, effective from / to, legal entity (fixed charges only).
`gst_recoverable_pct` is Meridian's own tax position (not on any vendor document) and is set by the analyst from tax policy.

<!-- RESULTS -->

## Results (latest run)

Tables: `rate_card_parsed` 20 docs · `fee_schedule_extracted` 139 lines · `rate_card_answer_key` 139 · `fee_schedule_review` 139 · `fee_schedule` **119** approved lines · `fail_cost_rule` 8 rules.

### By language

| Language | Cards | Lines expected | Extracted | Matched first time | Corrected | Missed | Spurious | First-time accuracy | Mean confidence |
|---|---|---|---|---|---|---|---|---|---|
| en | 17 | 106 | 106 | 77 | 29 | 0 | 0 | 72.6% | 0.903 |
| ko | 1 | 6 | 6 | 3 | 3 | 0 | 0 | 50.0% | 0.95 |
| zh-Hant | 2 | 27 | 27 | 22 | 5 | 0 | 0 | 81.5% | 0.965 |
| all | 20 | 139 | 139 | 102 | 37 | 0 | 0 | 73.4% | 0.912 |

Field-level accuracy (each line has 20 compared fields):

| Language | Fields compared | Correct first time | Field accuracy |
|---|---|---|---|
| en | 2120 | 2090 | 98.6% |
| ko | 120 | 117 | 97.5% |
| zh-Hant | 540 | 535 | 99.1% |
| all | 2780 | 2742 | 98.6% |

### By card

| Card | Lang | Expected | Extracted | Matched | Corrected | Missed | Spurious | First-time | Mean conf. |
|---|---|---|---|---|---|---|---|---|---|
| RC01 | en | 8 | 8 | 5 | 3 | 0 | 0 | 62.5% | 0.9764 |
| RC02 | en | 22 | 22 | 17 | 5 | 0 | 0 | 77.3% | 1.0 |
| RC03 | zh-Hant | 22 | 22 | 17 | 5 | 0 | 0 | 77.3% | 0.9725 |
| RC04 | en | 5 | 5 | 3 | 2 | 0 | 0 | 60.0% | 0.98 |
| RC05 | en | 8 | 8 | 5 | 3 | 0 | 0 | 62.5% | 0.9375 |
| RC06 | en | 14 | 14 | 10 | 4 | 0 | 0 | 71.4% | 0.989 |
| RC07 | en | 2 | 2 | 2 | 0 | 0 | 0 | 100.0% | 0.8833 |
| RC08 | en | 11 | 11 | 7 | 4 | 0 | 0 | 63.6% | 0.9488 |
| RC09 | en | 5 | 5 | 4 | 1 | 0 | 0 | 80.0% | 0.98 |
| RC10 | ko | 6 | 6 | 3 | 3 | 0 | 0 | 50.0% | 0.95 |
| RC11 | zh-Hant | 5 | 5 | 5 | 0 | 0 | 0 | 100.0% | 0.9578 |
| RC12 | en | 4 | 4 | 4 | 0 | 0 | 0 | 100.0% | 0.9764 |
| RC13 | en | 9 | 9 | 8 | 1 | 0 | 0 | 88.9% | 0.6333 |
| RC14 | en | 5 | 5 | 0 | 5 | 0 | 0 | 0.0% | 0.9722 |
| RC15 | en | 3 | 3 | 3 | 0 | 0 | 0 | 100.0% | 1.0 |
| RC16 | en | 3 | 3 | 3 | 0 | 0 | 0 | 100.0% | 0.85 |
| RC17 | en | 1 | 1 | 1 | 0 | 0 | 0 | 100.0% | 0.9333 |
| RC18 | en | 2 | 2 | 1 | 1 | 0 | 0 | 50.0% | 0.7333 |
| RC19 | en | 1 | 1 | 1 | 0 | 0 | 0 | 100.0% | 0.7556 |
| RC20 | en | 3 | 3 | 3 | 0 | 0 | 0 | 100.0% | 0.8056 |

### Cross-language check (RC03 繁中 vs RC02 EN)

The Traditional Chinese edition of the derivatives card produced 17 lines identical to the English edition, 5 needing a correction, 0 missed and 0 spurious.

### Fields the analyst had to correct

| Language | Field | Corrections | Mean field confidence |
|---|---|---|---|
| en | rate | 9 | 0.172 |
| en | product_family | 6 | 0.95 |
| en | cost_type | 6 | 0.85 |
| en | fee_basis | 5 | 0.83 |
| en | vendor_id | 2 | 0.995 |
| en | tier_max | 1 |  |
| en | is_pass_through | 1 | 0.2 |
| ko | product_family | 3 | 0.1 |
| zh-Hant | cost_type | 5 | 1.0 |

### Does the confidence score help triage?

| Status | Lines | Mean confidence | Mean lowest-field confidence |
|---|---|---|---|
| CORRECTED | 37 | 0.937 | 0.627 |
| MATCHED | 102 | 0.941 | 0.736 |

### Correction log

| Card | Fee | Item | Status | Conf. | Reason |
|---|---|---|---|---|---|
| RC01 | PRX-SEC-TRF | 1.2 | CORRECTED | 0.986 | fee_basis: 'PER_CONTRACT_SIDE' → 'PER_TRADE' |
| RC01 | PRX-SEC-STD | 3.1 | CORRECTED | 0.886 | rate 100 → 10 (decimal-place error) |
| RC01 | PRC-SEC-FIX | A.2 | CORRECTED | 0.99 | vendor_id: 'PRX' → 'PRC' |
| RC02 | PRX-DV-M50-EX | 1.3 | CORRECTED | 1.0 | product_family: 'PRX50_FUT' → 'PRX50_MINI_FUT' |
| RC02 | PRX-DV-M50-MM | 1.4 | CORRECTED | 1.0 | product_family: 'PRX50_FUT' → 'PRX50_MINI_FUT' |
| RC02 | PRX-DV-M50-MM2 | 1.5 | CORRECTED | 1.0 | product_family: 'PRX50_FUT' → 'PRX50_MINI_FUT' |
| RC02 | PRX-DV-M50-LV | 2.2 | CORRECTED | 1.0 | product_family: 'PRX50_FUT' → 'PRX50_MINI_FUT' |
| RC02 | PRC-DV-M50-CL | 3.2 | CORRECTED | 1.0 | product_family: 'PRX50_FUT' → 'PRX50_MINI_FUT' |
| RC03 | PRC-DV-50-CL | 3.1 | CORRECTED | 1.0 | cost_type: 'SETTLEMENT' → 'CLEARING' |
| RC03 | PRC-DV-M50-CL | 3.2 | CORRECTED | 1.0 | cost_type: 'SETTLEMENT' → 'CLEARING' |
| RC03 | PRC-DV-TCH-CL | 3.3 | CORRECTED | 1.0 | cost_type: 'SETTLEMENT' → 'CLEARING' |
| RC03 | PRC-DV-CEI-CL | 3.4 | CORRECTED | 1.0 | cost_type: 'SETTLEMENT' → 'CLEARING' |
| RC03 | PRC-DV-SOP-CL | 3.5 | CORRECTED | 1.0 | cost_type: 'SETTLEMENT' → 'CLEARING' |
| RC04 | CNX-STD | 3.1 | CORRECTED | 1.0 | rate 0.5 → 5 (decimal-place error) |
| RC04 | PRC-CNX-TRF | 4.1 | CORRECTED | 1.0 | is_pass_through: True → False |
| RC05 | MRC-SEC-CLR | 1.1 | CORRECTED | 0.7 | cost_type: 'EXCHANGE' → 'CLEARING'; rate 0.0325 → 3.25 (unit conversion) |
| RC05 | MRX-SEC-ACC | 3.1 | CORRECTED | 0.8 | rate 0.0075 → 0.75 (unit conversion) |
| RC05 | MRC-FIX | A.2 | CORRECTED | 1.0 | vendor_id: 'MRX' → 'MRC' |
| RC06 | SXA-FUT-200-EX | 1.3 | CORRECTED | 0.978 | fee_basis: 'FIXED_MONTHLY' → 'PER_CONTRACT_SIDE' |
| RC06 | SXA-FUT-IRF-EX | 1.4 | CORRECTED | 0.978 | fee_basis: 'FIXED_MONTHLY' → 'PER_CONTRACT_SIDE' |
| RC06 | SXC-FUT-200-CL | 2.3 | CORRECTED | 0.961 | fee_basis: 'FIXED_MONTHLY' → 'PER_CONTRACT_SIDE' |
| RC06 | SXC-FUT-IRF-CL | 2.4 | CORRECTED | 0.961 | fee_basis: 'FIXED_MONTHLY' → 'PER_CONTRACT_SIDE' |
| RC08 | IGX-TXN-S1 | 1.1 | CORRECTED | 0.905 | rate 34.5 → 0.345 (unit conversion) |
| RC08 | IGX-TXN-S2 | 1.2 | CORRECTED | 0.905 | rate 30 → 0.3 (unit conversion) |
| RC08 | IGX-TXN-S3 | 1.3 | CORRECTED | 0.905 | rate 25 → 0.25 (unit conversion) |
| RC08 | IGX-TXN-U | 1.4 | CORRECTED | 0.894 | rate 32.2 → 0.322 (unit conversion) |
| RC09 | DCX-STAMP | 3.2 | CORRECTED | 0.9 | rate 1.5 → 0.15 (decimal-place error) |
| RC10 | HRX-CSH-TRD | 1.1 | CORRECTED | 0.9 | product_family: 'HK_CASH_EQ' → 'KR_CASH_EQ' |
| RC10 | HRX-CSH-SET | 3.1 | CORRECTED | 0.9 | product_family: 'HK_CASH_EQ' → 'KR_CASH_EQ' |
| RC10 | HRX-CSH-STT | 4.1 | CORRECTED | 0.9 | product_family: 'HK_CASH_EQ' → 'KR_CASH_EQ' |
| RC13 | COB-STD-KR | 1.1 | CORRECTED | 0.633 | tier_max: None → 1200000000.0 |
| RC14 | AUR-50 | 1.1 | CORRECTED | 0.972 | cost_type: 'EXCHANGE' → 'BROKERAGE' |
| RC14 | AUR-M50 | 1.2 | CORRECTED | 0.972 | cost_type: 'EXCHANGE' → 'BROKERAGE' |
| RC14 | AUR-TCH | 1.3 | CORRECTED | 0.972 | cost_type: 'EXCHANGE' → 'BROKERAGE' |
| RC14 | AUR-CEI | 1.4 | CORRECTED | 0.972 | cost_type: 'EXCHANGE' → 'BROKERAGE' |
| RC14 | AUR-SOP | 1.5 | CORRECTED | 0.972 | cost_type: 'EXCHANGE' → 'BROKERAGE' |
| RC18 | FOX-NDF | 1.1 | CORRECTED | 0.733 | product_family: 'FX_SPOT_NDF' → 'EM_NDF' |

<!-- /RESULTS -->

## Run history

| Run | Prompt | Lines found | Lines fully right first time | Notes |
|---|---|---|---|---|
| 1 | v1 | 139 / 139 | 69 / 139 (49.6%): en 48.1%, zh-Hant 66.7%, ko 0% | Schema misuse (rate copied into `floor_per_trade`), % typed as "per million", broker commission typed as exchange fee |
| 2 | v2 | 139 / 139 | **102 / 139 (73.4%)**: en 72.6%, zh-Hant 81.5%, ko 50%; **98.6% of fields** | v2 added generic field semantics, unit-conversion examples and a bilingual glossary; nothing card-specific |

Runtime: about 12 minutes end to end (parse about 75 s; `ai_extract` on 20 documents about 10 minutes; review, publish and guard about 1.5 minutes).

## Failure modes in the latest run (and why the approval step exists)

| Failure mode | Example | Cards | Field confidence | Caught by |
|---|---|---|---|---|
| Unit conversion: % vs bps vs ₹ per crore | "₹345 per crore (0.00345%)" read as 34.5 bps instead of 0.345; "0.0325%" left as 0.0325 | RC08, RC05 | 0.17 average on wrong rates | Rate compare: "unit conversion" |
| Decimal-place slips on taxes | 0.10% stamp duty read as 100 bps; 0.05% as 0.5 bps; 0.015% as 1.5 bps | RC01, RC04, RC09 | Low | Rate compare: "decimal-place error" |
| Clearing vs settlement terminology | 結算費 (clearing in Hong Kong usage; 交收 = settlement) typed as SETTLEMENT despite the glossary; the Taiwan card got it right | RC03 (zh-Hant) | **1.0 (confidently wrong)** | `cost_type` compare |
| Product mapping in Korean | 유가증권시장 주식 (Korean equities) mapped to Hong Kong equities | RC10 (ko) | 0.1 | Low confidence → top of the queue |
| Similar products | Mini PRX 50 vs PRX 50 futures; FX-desk vs EM-desk NDF | RC02, RC18 | 0.95–1.0 | `product_family` compare |
| Charge category on broker schedules | Give-up commission typed as an exchange fee | RC14 | 0.97 | `cost_type` compare |
| Vendor attribution on multi-entity cards | Clearing-house fixed fees attributed to the exchange (PRC → PRX, MRC → MRX) | RC01, RC05 | 0.99 | `vendor_id` compare |
| Basis on futures | Per-contract futures fees typed as FIXED_MONTHLY | RC06 | 0.96 | `fee_basis` compare |
| Korean parser character errors | 계약당·**편**도 ("per side") parsed as 계약당·**펀**도 by `ai_parse_document`. Run 1 turned it into per-trade; run 2 recovered the basis from context | RC10 (ko) | — | `fee_basis` compare (run 1) |

Takeaways for the customer conversation:

- **Recall is the easy part.** Every fee line was found in every language, with no hallucinated lines. The value is in
  structure: 98.6% of the 2,780 extracted fields were right first time.
- **Precision is about units and terminology.** These are exactly the fields that drive invoice reconciliation, which
  is why the analyst approves before rates go live.
- **Non-Latin documents need the review step.** The Korean card had the lowest line accuracy and the Chinese edition
  produced confident terminology errors, consistent with the `ai_parse_document` documentation (weaker on non-Latin
  text, Korean named explicitly). Use English cards for the headline path; show RC10 and RC03 as the
  "human in the loop" example.
- **Confidence orders the queue; it doesn't replace review.** Low confidence flagged most of the rate and Korean mapping
  errors, but terminology mistakes came back at 1.0. The control is the field-level comparison.

## Talk track — "fee schedules live in PDFs" (scene 5 lead-in)

> "Today the rate cards sit in PDFs and circulars — twenty of them here, in English, Traditional Chinese and Korean. We point
> `ai_parse_document` and `ai_extract` at the folder, and every fee comes back as a structured row with a confidence score:
> per contract or basis points, house or client, tier thresholds, discounts and when they expire. It found all 139 fee lines,
> and 98.6% of the fields were right first time. The analyst only works the exceptions: a '₹ per crore' rate that needed
> converting, the Hong Kong Chinese term for clearing, a Korean product the model wasn't sure about. Once she approves, the
> rates go live in one governed table. That table is what we multiply every trade by to get expected cost, and it's how we
> can see that Broker C billed August at the standard tier when we'd qualified for the rebate."

Numbers to quote are regenerated by `src/extraction/make_report.py` from `silver.fee_schedule_extraction_summary` and
`silver.fee_schedule_review` after each run (LLM output varies slightly run to run; approved rates do not).

## How to run

```bash
src/rate_cards/publish.sh fe-vm-zh-serverless          # render 20 PDFs + upload PDFs and ref CSVs
databricks bundle deploy && databricks bundle run ce_fee_extraction   # Lead SA owns deploys
src/rate_cards/.venv/bin/python src/extraction/make_report.py --profile fe-vm-zh-serverless --warehouse 5f36ded0f9befdd1
src/rate_cards/.venv/bin/python src/extraction/test_review_logic.py   # local tests for the review matcher
```
