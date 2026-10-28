"""Build the serialized Genie space for "Trade Cost Explain — APAC Global Markets".

    python src/genie/build_space.py            → writes src/genie/trade_cost_explain.geniespace.json (parsed object)

IDs are deterministic (uuid5 of a stable key) so rebuilding produces the same space definition. Every array that the
Genie API requires sorted (by id, identifier or column_name) is sorted here.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from queries import AU, BENCHMARKS, EXAMPLES, HK, MV, SG  # noqa: F401 — hub lists used in descriptions

HERE = Path(__file__).resolve().parent
NS = uuid.UUID("6d1f1c4e-2a0b-4b8e-9a51-3c1f6a7e8d20")
TITLE = "Trade Cost Explain — APAC Global Markets"
DESCRIPTION = (
    "Explains APAC Global Markets trade costs (US GAAP line 'Commissions and floor brokerage', net borne, US$) for FP&A, "
    "Product Control and Operations: the period-on-period cost bridge (volume, mix, rate, fails, timing / accrual, FX, "
    "fixed fees, unexplained), desk KPIs versus plan, invoice reconciliation against contracted rates, settlement-fail "
    "hotspots and fee-schedule events. Fiscal year April–March. Synthetic data — Meridian Group; all figures illustrative."
)


def hid(key: str) -> str:
    return uuid.uuid5(NS, key).hex


SAMPLE_QUESTIONS = [
    "Why did APAC trade costs go up in September vs August?",
    "And why did equity derivatives exchange and clearing fees go up?",
    "9月亞太區交易成本上升的主要原因是什麼？",
    "Which desks have the highest cost per trade, and how has it trended?",
    "How much of the trade cost increase is matched by revenue growth?",
    "Which brokers billed more than the expected cost in fiscal Q2 (July–September)?",
    "What are the top 5 counterparties by settlement-fail cost this month?",
    "Show trade costs as bps of revenue by desk vs. plan.",
    "Compare cost per trade in Hong Kong, Singapore and Australia.",
    "Which fee discounts, waivers or regime changes expire in the next six months, and what is the cost impact at current volumes?",
    "How much of our cost is statutory levies and taxes, and how much of that do we recharge?",
]

HUB_TEXT = ("Hubs, with the exact Desk values: Hong Kong = 'HK Cash Equities', 'HK Equity Derivatives', 'Stock Connect / China Flow', "
            "'Delta One / Prime', 'Flow Credit'; Singapore = 'Singapore FX', 'Singapore Rates', 'Singapore EM (incl. Malaysia)'; "
            "Australia = 'Australia Cash Equities', 'Australia Rates & Futures'; Mumbai = 'India Equities'; Seoul / Taipei = "
            "'Korea & Taiwan Equities'. Use these exact strings (including the parenthesis) when mapping desks to hubs.")


TEXT_INSTRUCTIONS = """## PURPOSE
- Explain APAC Global Markets trade costs (US GAAP line "Commissions and floor brokerage", net borne, US$) for FP&A, Product Control and Operations. All data are synthetic (Meridian Group).

## DISAMBIGUATION
- The fiscal year runs April to March: FY2026/27 Q1 = Apr-Jun 2026, Q2 = Jul-Sep 2026, H1 = Apr-Sep 2026. The September close is the half-year close.
- "September", "this month" or "latest month" means September 2026. If a question names no period, use September 2026 (and September vs August 2026 for changes).
- For "why did costs go up / down", answer from trade_cost_flux_metrics with prior cost, current cost, change, change % and every effect in this order: Volume, Mix, Rate, Fails, Timing / accrual, FX, Fixed fees, Unexplained. The effects add up exactly to the change; never recompute them from other sources.
- Good flux = Volume; controllable flux = Mix + Fails; external = Rate + FX + Timing + Fixed fees + Unexplained.
- "Broker C" means the vendor Cobalt Securities. Hub comparisons (Hong Kong, Singapore, Australia) group desks as described on the Desk column.

## DATA QUALITY NOTES
- Headline cost is net borne: recoverable statutory levies, taxes, GST and intra-group charges are excluded; gross is the drill.
- Vendor invoices arrive after month end: at the September close the latest reconcilable service month is 2026-08 and September invoices are pending.
- Plan figures start in April 2026 (FY2026/27 budget).

## Instructions you must follow when providing summaries
- Show amounts below US$1M in US$K (e.g. +US$900K) and US$1M or more in US$M with two decimals (e.g. US$2.17M); percentages as whole numbers.
- For a cost bridge, give the eight effects as one signed list in the bridge order above; never split them into drivers and offsets. Zero Fails on Equity Derivatives is expected: listed derivatives clear at a CCP, not through a depository.
- Say that the figures are synthetic and illustrative."""


def cc(name: str, description: str | None = None, synonyms: list[str] | None = None, match: bool = False,
       exclude: bool = False) -> dict:
    c = {"column_name": name}
    if description:
        c["description"] = [description]
    if synonyms:
        c["synonyms"] = synonyms
    if match:
        c["enable_format_assistance"] = True
        c["enable_entity_matching"] = True
    if exclude:
        c["exclude"] = True
    return c


METRIC_VIEWS = {
    f"{MV}.trade_cost_flux_metrics": [
        cc("Comparison", "Comparison id. MOM_2026-09 = September vs August 2026 (default, half-year close); MOM_YYYY-MM = that month vs the "
           "prior month; QOQ_FY2026Q2 = fiscal Q2 vs Q1 FY2026/27; QOQ_FY2026Q1 = fiscal Q1 FY2026/27 vs Q4 FY2025/26.",
           ["period comparison", "comparison id"], match=True),
        cc("Comparison Label", "Readable comparison, e.g. 'Sep 2026 vs Aug 2026'.", ["September vs August", "Q2 vs Q1"], match=True),
        cc("Comparison Type", "MoM (month on month) or QoQ (fiscal quarter on quarter).", match=True),
        cc("Prior Period", "Prior period label (P0), e.g. Aug 2026.", match=True),
        cc("Current Period", "Current period label (P1), e.g. Sep 2026.", match=True),
        cc("Business", "Business line: Cash Equities, Equity Derivatives, Prime & Delta One, Rates, Credit, FX & Emerging Markets.",
           ["business line"], match=True),
        cc("Desk", "Trading desk. " + HUB_TEXT, ["trading desk"], match=True),
        cc("Headline Slice", "'Equity Derivatives — exchange & clearing' = exchange and clearing fees of the Equity Derivatives business; "
           "everything else is 'Rest of APAC Global Markets'. Listed derivatives clear at a CCP and do not settle through a depository, "
           "so the Equity Derivatives slice has no settlement-fail cost.",
           ["equity derivatives exchange and clearing fees", "ED exchange and clearing"], match=True),
        cc("Cost Category", "Exchange & clearing, Brokerage, Settlement & custody, Levies & taxes (borne), Non-recoverable GST, "
           "Settlement fails, Fixed fees.", ["fee category", "cost type group"], match=True),
        cc("Vendor", "Billing vendor (exchange, CCP, broker, connectivity, or an unmapped AP vendor). Cobalt Securities is 'Broker C'.",
           ["broker", "exchange", "venue", "CCP", "Broker C"], match=True),
        cc("Vendor Type", "Exchange, CCP, Broker, Broker (intra-group), Connectivity, Unmapped AP vendor.", match=True),
        cc("Market", "Market code: HK, CN (Stock Connect), SG, AU, IN, KR, TW, MY.", ["country"], match=True),
        cc("Legal Entity", "Booking legal entity name.", ["entity"], match=True),
        cc("Currency", "Local currency of the cost.", ["LCY"], match=True),
        cc("Good Flux", "The part of the cost change explained by activity volume. This is the share of a cost increase that is "
           "'matched by revenue growth' (more activity earns more revenue). When asked how much of a cost change is matched or "
           "justified by revenue, report the Cost Change, Good Flux and Good Flux Share, with revenue growth from "
           "desk_cost_kpi_metrics as context. "
           "Never divide revenue growth by the cost change.",
           ["matched by revenue growth", "revenue-matched increase", "volume-driven cost increase", "good flux"]),
        cc("Good Flux Share", "Share of the cost change that is volume-driven, i.e. matched by revenue growth.",
           ["share matched by revenue", "percentage matched by revenue growth"]),
    ],
    f"{MV}.trade_cost_metrics": [
        cc("Month", "Calendar month YYYY-MM (Sep 2025 – Sep 2026).", ["period"], match=True),
        cc("Fiscal Quarter", "Fiscal quarter label, e.g. 'FY2026/27 Q2' = Jul–Sep 2026.", ["quarter"], match=True),
        cc("Fiscal Half", "Fiscal half id, e.g. FY2026H1 = Apr–Sep 2026.", ["H1", "half year"], match=True),
        cc("Business", None, None, match=True),
        cc("Desk", "Trading desk. " + HUB_TEXT, None, match=True),
        cc("Cost Category", "Cost category. 'Levies & taxes (borne)' holds statutory levies and transaction taxes (gross includes "
           "the part recharged to clients); 'Recoverable GST' is GST recovered. For levies and taxes and how much is recharged, filter "
           "this category and show Gross Trade Cost (total incurred), Recoverable Levies and Taxes (recharged to clients) and Net "
           "Borne Trade Cost (kept by Meridian).", ["statutory levies and taxes"], match=True),
        cc("Gross Trade Cost", "Cost before recharges and recoveries. In the 'Levies & taxes (borne)' category this is the total "
           "statutory levies and transaction taxes incurred.", ["total levies and taxes", "levies and taxes incurred", "gross cost"]),
        cc("Recoverable Levies and Taxes", "Statutory levies, stamp duty and transaction taxes recharged to clients (and GST "
           "recovered in the 'Recoverable GST' category).", ["recharged to clients", "how much we recharge", "recharged"]),
        cc("Net Borne Trade Cost", "Cost Meridian keeps after recharges and recoveries (GL actual). For levies and taxes this is "
           "gross minus recharged.", ["borne", "kept", "net cost"]),
        cc("Vendor", None, ["broker", "exchange"], match=True),
        cc("Legal Entity", "Legal entity code: MSHK, MSSG, MSAU, MSIN, MSKR, MSTW, MSMY.", None, match=True),
    ],
    f"{MV}.desk_cost_kpi_metrics": [
        cc("Month", "Calendar month YYYY-MM.", ["period"], match=True),
        cc("Fiscal Quarter", "Fiscal quarter id, e.g. FY2026Q2 = Jul–Sep 2026.", None, match=True),
        cc("Fiscal Half", "Fiscal half id, e.g. FY2026H1 = Apr–Sep 2026 (year to date at the September close).", ["H1", "YTD"], match=True),
        cc("Business", None, None, match=True),
        cc("Desk", "Trading desk. " + HUB_TEXT, ["trading desk"], match=True),
        cc("Cost per Trade", "Trade cost per executed trade (US$). Rank desks on the latest month (September 2026) unless a period "
           "is named; 'which desks are highest' means the top five desks, with their monthly trend when a trend is asked for.",
           ["cost per ticket", "unit cost"]),
    ],
    f"{MV}.invoice_recon_metrics": [
        cc("Service Period", "Month the invoiced service relates to (YYYY-MM). Invoices lag one month: 2026-08 is the latest "
           "reconcilable month at the September close. For a range that includes 2026-09 (e.g. fiscal Q2), answer with the months "
           "available and say that September invoices are pending; do not ask a clarifying question.",
           ["invoice month", "billing month"], match=True),
        cc("Vendor", "Vendor. Cobalt Securities is 'Broker C'.", ["broker", "Broker C"], match=True),
        cc("Vendor Type", "Exchange, CCP, Broker, Broker (intra-group), Connectivity.", match=True),
        cc("Recon Status", "MATCHED, OVERBILLED, UNDERBILLED or PENDING_INVOICE.", ["over-billed", "billed more than expected"], match=True),
        cc("Variance Reason", "Inferred reason for the variance (free text). The text can differ by legal entity for the same "
           "finding, so do not group by it when totalling per vendor: group by Vendor (and Service Period) and show the reason "
           "separately."),
        cc("Legal Entity", None, None, match=True),
        cc("Cost Type", None, None, match=True),
    ],
    f"{MV}.settlement_fail_metrics": [
        cc("Month", "Month the fail cost accrued (YYYY-MM).", ["period"], match=True),
        cc("Desk", "Desk code: HKCE HK Cash Equities, CNSC Stock Connect, KTEQ Korea & Taiwan Equities, AUCE Australia Cash Equities, "
           "INEQ India Equities, D1PR Delta One / Prime, SGEM Singapore EM.", None, match=True),
        cc("Counterparty", "Counterparty of the failed settlement.", ["client"], match=True),
        cc("Root Cause", "Fail root cause.", ["reason", "cause"], match=True),
        cc("Market", None, None, match=True),
        cc("Settlement Location", "Depository / clearing house.", ["depository"], match=True),
        cc("Legal Entity", None, None, match=True),
    ],
}
TABLES = {
    f"{MV}.dim_comparison": [
        cc("comparison_id", "Comparison id used by trade_cost_flux_metrics.Comparison.", None, match=True),
        cc("comparison_label", "Readable comparison label.", None, match=True),
        cc("sort_order", exclude=True),
    ],
    f"{MV}.fee_calendar": [
        cc("event_type", "DISCOUNT_ENDS (a discount or waiver ends with no replacement line), RATE_CHANGE (a rate, concession or "
           "waiver is replaced by a new rate, e.g. the Mini PRX 50 market-maker concession ending 31 Dec 2026), REGIME_CHANGE (the fee "
           "structure changes, e.g. slab-wise to uniform). Questions about discounts, waivers or regime changes expiring include all "
           "three event types, filtered on event_date after as_of_date.", ["fee change", "discount expiry", "regime change"], match=True),
        cc("event_date", "Date the change takes effect."),
        cc("status", "UPCOMING (after the as-of date) or IN_EFFECT.", None, match=True),
        cc("monthly_impact_usd", "Estimated monthly cost impact in US$ at current (latest month) volumes; positive = cost increase.",
           ["cost impact", "impact at current volumes"]),
        cc("vendor_name", None, ["vendor", "exchange", "broker"], match=True),
        cc("as_of_date", "As-of date of the data (September close, 2026-10-05)."),
    ],
}
SNIPPET_FILTERS = [
    ("flt_sep_vs_aug", "September vs August 2026", "trade_cost_flux_metrics.`Comparison` = 'MOM_2026-09'",
     ["September", "this month", "Sep vs Aug", "half-year close", "September close"]),
    ("flt_q2_vs_q1", "Fiscal Q2 vs Q1 FY2026/27", "trade_cost_flux_metrics.`Comparison` = 'QOQ_FY2026Q2'",
     ["Q2 vs Q1", "fiscal Q2", "quarter on quarter"]),
    ("flt_ed_exch_clr", "Equity Derivatives exchange & clearing fees",
     "trade_cost_flux_metrics.`Headline Slice` = 'Equity Derivatives — exchange & clearing'",
     ["equity derivatives exchange and clearing fees", "ED exchange and clearing", "equity derivatives exchange fees"]),
]


def build() -> dict:
    space = {
        "version": 2,
        "config": {"sample_questions": sorted(
            [{"id": hid("sample:" + q), "question": [q]} for q in SAMPLE_QUESTIONS], key=lambda x: x["id"])},
        # The Genie API stores metric views in data_sources.tables; emit the same shape so the file round-trips.
        "data_sources": {
            "tables": sorted([{"identifier": k, "column_configs": sorted(v, key=lambda c: c["column_name"])}
                              for k, v in {**METRIC_VIEWS, **TABLES}.items()], key=lambda x: x["identifier"]),
        },
        "instructions": {
            "text_instructions": [{"id": hid("text:main"), "content": [TEXT_INSTRUCTIONS]}],
            "example_question_sqls": sorted(
                [{"id": hid("example:" + k), "question": [q], "sql": [sql], "usage_guidance": [guide]}
                 for k, (q, sql, guide) in EXAMPLES.items()], key=lambda x: x["id"]),
            "sql_snippets": {"filters": sorted(
                [{"id": hid("snippet:" + k), "display_name": name, "sql": [sql], "synonyms": syn}
                 for k, name, sql, syn in SNIPPET_FILTERS], key=lambda x: x["id"])},
        },
        "benchmarks": {"questions": sorted(
            [{"id": hid("benchmark:" + k), "question": [q], "answer": [{"format": "SQL", "content": [sql]}],
              "evaluation_note": [note]} for k, (q, sql, note) in BENCHMARKS.items()], key=lambda x: x["id"])},
    }
    ids = [x["id"] for x in space["config"]["sample_questions"]] + [x["id"] for x in space["benchmarks"]["questions"]]
    assert len(ids) == len(set(ids)), "question ids must be unique"
    assert len(TEXT_INSTRUCTIONS) < 2000, len(TEXT_INSTRUCTIONS)
    return space


if __name__ == "__main__":
    s = build()
    (HERE / "trade_cost_explain.geniespace.json").write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"written: {len(s['config']['sample_questions'])} sample questions, "
          f"{len(s['data_sources']['tables'])} sources ({len(METRIC_VIEWS)} metric views), "
          f"{len(s['instructions']['example_question_sqls'])} examples, {len(s['benchmarks']['questions'])} benchmarks, "
          f"text instructions {len(TEXT_INSTRUCTIONS)} chars")
