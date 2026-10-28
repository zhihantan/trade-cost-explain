"""Canonical fee lines from src/datagen/config/rate_cards.yaml (pure Python, no Spark).

Shared by the PDF renderer (src/rate_cards/render.py) and the extraction job (fee_extraction.py) so the PDFs,
the analyst answer key and the approved fee schedule can never disagree.
"""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import yaml

# Column order of cost_explain.silver.fee_schedule (contract with the pipeline).
FEE_SCHEDULE_COLUMNS = [
    "fee_id", "card_id", "vendor_id", "cost_type", "fee_basis", "product_family", "capacity", "side",
    "rate", "currency", "tier_basis", "tier_min", "tier_max", "tier_type", "floor_per_trade", "cap_per_trade",
    "is_pass_through", "is_discount_or_waiver", "gst_rate", "gst_recoverable_pct", "effective_from",
    "effective_to", "legal_entity", "description", "source_doc", "source_language",
    "extraction_confidence", "extraction_status", "approved_by", "approved_at",
]

# Fields the extractor is expected to read from the document (compared in the analyst review).
EXTRACTED_FIELDS = [
    "vendor_id", "product_family", "cost_type", "fee_basis", "capacity", "side", "rate", "currency",
    "tier_basis", "tier_min", "tier_max", "tier_type", "floor_per_trade", "cap_per_trade",
    "is_pass_through", "is_discount_or_waiver", "gst_rate", "effective_from", "effective_to", "legal_entity",
]
# Fields that come from Meridian's own policies, not from the vendor's document (set by the analyst).
ENRICHED_FIELDS = ["gst_recoverable_pct"]

CONTRACT_REGISTER_DOC = "Procurement contract register"

ENUMS = {
    "cost_type": ["EXCHANGE", "CLEARING", "SETTLEMENT", "LEVY", "TAX", "BROKERAGE", "FIXED"],
    "fee_basis": ["PER_CONTRACT_SIDE", "BPS_NOTIONAL", "PER_TRADE", "PER_INSTRUCTION", "PER_MILLION_NOTIONAL", "FIXED_MONTHLY"],
    "capacity": ["ALL", "HOUSE", "CLIENT", "MM", "NON_MM", "PRINCIPAL"],
    "side": ["ALL", "BUY", "SELL"],
    "tier_basis": ["NONE", "VENDOR_MONTHLY_TURNOVER_USD", "MEMBER_MONTHLY_TURNOVER_LCY", "MEMBER_MONTHLY_CONTRACTS"],
    "tier_type": ["NONE", "UPFRONT", "REBATE"],
    "currency": ["HKD", "CNH", "SGD", "AUD", "INR", "KRW", "TWD", "MYR", "USD"],
    "legal_entity": ["MSHK", "MSSG", "MSAU", "MSIN", "MSKR", "MSTW", "MSMY", "NONE"],
}

# Fictional vendors (venues, CCPs, brokers, connectivity) — display names used in PDFs and the extractor prompt.
VENDORS = {
    "PRX": "Pearl River Exchange", "PRC": "Pearl River Clearing", "CNX": "Pearl River Connect — Northbound",
    "MRX": "Merlion Exchange", "MRC": "Merlion Clearing", "SXA": "Southern Cross Exchange",
    "SXC": "Southern Cross Clear & Settlement", "TAM": "Tasman Alternative Market", "IGX": "Indus Exchange",
    "ICC": "Indus Clearing Corporation", "DCX": "Deccan Exchange", "HRX": "Han River Exchange",
    "FMX": "Formosa Exchange", "STX": "Straits Exchange",
    "B01": "Aurora Pacific Securities", "B02": "Bluewater Brokerage", "B03": "Cobalt Securities",
    "B04": "Dunmore Capital Markets", "B05": "Emberly Securities", "B06": "Foxglove Brokerage",
    "B07": "Goldcrest Execution", "B08": "Meridian Execution Services",
    "V21": "Pacific Data Links", "V22": "Straits Connectivity",
}

LEGAL_ENTITIES = {
    "MSHK": "Meridian Securities (Hong Kong) Limited",
    "MSSG": "Meridian Securities Singapore Pte. Ltd.",
    "MSAU": "Meridian Australia Securities Limited",
    "MSIN": "Meridian Financial Services India Private Limited",
    "MSKR": "Meridian Securities Korea Co., Ltd.",
    "MSTW": "Meridian Securities (Hong Kong) Limited, Taiwan Branch",
    "MSMY": "Meridian Securities Malaysia Sdn. Bhd.",
}

PRODUCT_FAMILIES = {
    "HK_CASH_EQ": "Hong Kong listed equities (on-exchange cash trades)",
    "CN_CONNECT_EQ": "Mainland China A-shares traded northbound via Connect",
    "SG_CASH_EQ": "Singapore listed securities (cash)",
    "AU_CASH_EQ": "Australian cash equities",
    "IN_CASH_EQ": "Indian equities, cash (delivery) segment",
    "KR_CASH_EQ": "Korean listed equities (cash)",
    "TW_CASH_EQ": "Taiwan listed equities (cash)",
    "MY_CASH_EQ": "Malaysian listed equities (cash)",
    "PRX50_FUT": "PRX 50 Index Futures (Hong Kong)",
    "PRX50_MINI_FUT": "Mini PRX 50 Index Futures (Hong Kong)",
    "PRXTECH_FUT": "PRX Tech Index Futures (Hong Kong)",
    "PRXCEI_FUT": "PRX China Enterprises Index Futures (Hong Kong)",
    "PRX_STOCK_OPT": "Stock options listed on Pearl River Exchange",
    "MRX_CN50_FUT": "Merlion China 50 Index Futures (US$-denominated, Singapore)",
    "HRX200_FUT": "HRX 200 Index Futures (Korea)",
    "SXA200_FUT": "SXA 200 Index Futures (Australia)",
    "FMX_IDX_FUT": "Formosa Index Futures (Taiwan)",
    "AU_BOND_FUT": "Australian 3-year and 10-year Treasury bond futures",
    "FX_SPOT_NDF": "FX spot and non-deliverable forwards brokered inter-dealer",
    "SG_IRS": "SGD interest rate swaps",
    "USD_CREDIT_BOND": "US$ Asian credit bonds",
    "EM_NDF": "Asian non-deliverable forwards (emerging markets desk)",
    "MYR_GOVT_BOND": "Malaysia government securities",
    "ALL": "Not product-specific (membership, connectivity and other fixed monthly charges)",
}


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _norm_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _norm_float(v):
    return None if v is None else float(v)


def _normalise(line: dict, defaults: dict, currency: str) -> dict:
    row = {**copy.deepcopy(defaults), **copy.deepcopy(line)}
    out = {
        "fee_id": row["fee_id"],
        "vendor_id": row["vendor_id"],
        "cost_type": row["cost_type"],
        "fee_basis": row["fee_basis"],
        "product_family": row["product_family"],
        "capacity": row.get("capacity", "ALL"),
        "side": row.get("side", "ALL"),
        "rate": float(row["rate"]),
        "currency": row.get("currency") or currency,
        "tier_basis": row.get("tier_basis", "NONE") or "NONE",
        "tier_min": _norm_float(row.get("tier_min")),
        "tier_max": _norm_float(row.get("tier_max")),
        "tier_type": row.get("tier_type") or ("NONE" if (row.get("tier_basis", "NONE") or "NONE") == "NONE" else None),
        "floor_per_trade": _norm_float(row.get("floor_per_trade")),
        "cap_per_trade": _norm_float(row.get("cap_per_trade")),
        "is_pass_through": bool(row.get("pass_through", False)),
        "is_discount_or_waiver": bool(row.get("is_discount_or_waiver", False)),
        "gst_rate": float(row.get("gst_rate", 0.0) or 0.0),
        "gst_recoverable_pct": float(row.get("gst_recoverable_pct", 0.0) or 0.0),
        "effective_from": _norm_date(row.get("effective_from")),
        "effective_to": _norm_date(row.get("effective_to")),
        "legal_entity": row.get("legal_entity"),
        "description": row.get("description"),
        "desc_zh": row.get("desc_zh"),
        "desc_ko": row.get("desc_ko"),
    }
    if out["tier_type"] is None:
        out["tier_type"] = "UPFRONT"
    return out


def cards(doc: dict) -> list[dict]:
    """Cards with fully normalised lines; `same_as` cards get a copy of the source card's lines."""
    defaults = doc.get("defaults", {})
    by_id = {c["card_id"]: c for c in doc["cards"]}
    result = []
    for card in doc["cards"]:
        src = by_id[card["same_as"]] if card.get("same_as") else card
        currency = card.get("currency") or src.get("currency")
        lines = [_normalise(ln, defaults, src.get("currency") or currency) for ln in src.get("lines", [])]
        c = {k: v for k, v in card.items() if k != "lines"}
        c["lines"] = lines
        c["is_cross_language_copy"] = bool(card.get("same_as"))
        result.append(c)
    return result


def answer_key(doc: dict) -> list[dict]:
    """One row per card × line as the analyst expects to see it in that document (RC03 included)."""
    rows = []
    for c in cards(doc):
        for ln in c["lines"]:
            r = {k: v for k, v in ln.items() if k not in ("desc_zh", "desc_ko")}
            r.update(card_id=c["card_id"], source_doc=c["doc_file"], source_language=c["language"],
                     is_cross_language_copy=c["is_cross_language_copy"], same_as=c.get("same_as"),
                     description_local=ln.get("desc_zh") if c["language"].startswith("zh") else (ln.get("desc_ko") if c["language"] == "ko" else None))
            rows.append(r)
    return rows


def approved_lines(doc: dict) -> list[dict]:
    """Lines that go live in silver.fee_schedule: every card except cross-language copies, plus vendor contracts."""
    defaults = doc.get("defaults", {})
    rows = []
    for c in cards(doc):
        if c["is_cross_language_copy"]:
            continue
        for ln in c["lines"]:
            r = {k: v for k, v in ln.items() if k not in ("desc_zh", "desc_ko")}
            r.update(card_id=c["card_id"], source_doc=c["doc_file"], source_language=c["language"])
            rows.append(r)
    for vc in doc.get("vendor_contracts", []) or []:
        r = _normalise(vc, defaults, vc.get("currency", "USD"))
        r = {k: v for k, v in r.items() if k not in ("desc_zh", "desc_ko")}
        r.update(card_id=None, source_doc=CONTRACT_REGISTER_DOC, source_language="en")
        rows.append(r)
    ids = [r["fee_id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"Duplicate fee_id in approved lines: {dupes}")
    return rows


def fail_cost_rules(doc: dict) -> list[dict]:
    out = []
    for r in doc.get("fail_cost_rules", []) or []:
        out.append({
            "market": r["market"], "vendor_id": r["vendor_id"], "rule_type": r["rule_type"],
            "pct_per_day": _norm_float(r.get("pct_per_day")), "min_per_day": _norm_float(r.get("min_per_day")),
            "max_per_day": _norm_float(r.get("max_per_day")), "currency": r["currency"],
            "buy_in_after_days": int(r["buy_in_after_days"]) if r.get("buy_in_after_days") is not None else None,
            "invoiced": r.get("invoiced"), "source_doc": str(r.get("source_doc")), "confirmed": bool(r.get("confirmed", False)),
        })
    return out


if __name__ == "__main__":  # quick self-check: python canonical.py <yaml>
    import sys
    d = load_yaml(sys.argv[1])
    ak, ap = answer_key(d), approved_lines(d)
    print(f"cards={len(d['cards'])} answer_key_lines={len(ak)} approved_lines={len(ap)} fail_rules={len(fail_cost_rules(d))}")
