"""Load the canonical rate cards (config/rate_cards.yaml) into fee-line, fixed-fee and fail-rule tables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "rate_cards.yaml"

FEE_COLUMNS = [
    "fee_id", "card_id", "vendor_id", "cost_type", "fee_basis", "product_family", "capacity", "side", "rate", "currency",
    "tier_basis", "tier_min", "tier_max", "tier_type", "floor_per_trade", "cap_per_trade", "is_pass_through",
    "is_discount_or_waiver", "gst_rate", "gst_recoverable_pct", "effective_from", "effective_to", "legal_entity",
    "description", "source_doc", "source_language",
]


@lru_cache(maxsize=1)
def load_yaml(path: str = str(CONFIG)) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fee_lines() -> pd.DataFrame:
    """Every canonical line (RC03 is a translated edition of RC02, so it adds no lines)."""
    doc = load_yaml()
    d = doc["defaults"]
    rows = []
    for card in doc["cards"]:
        for ln in card.get("lines", []):
            r = {**d, **ln}
            rows.append({
                "fee_id": r["fee_id"], "card_id": card["card_id"], "vendor_id": r["vendor_id"],
                "cost_type": r["cost_type"], "fee_basis": r["fee_basis"], "product_family": r["product_family"],
                "capacity": r.get("capacity", "ALL"), "side": r.get("side", "ALL"), "rate": float(r["rate"]),
                "currency": r.get("currency", card["currency"]), "tier_basis": r.get("tier_basis", "NONE"),
                "tier_min": r.get("tier_min"), "tier_max": r.get("tier_max"), "tier_type": r.get("tier_type"),
                "floor_per_trade": r.get("floor_per_trade"), "cap_per_trade": r.get("cap_per_trade"),
                "is_pass_through": bool(r.get("pass_through", False)),
                "is_discount_or_waiver": bool(r.get("is_discount_or_waiver", False)),
                "gst_rate": float(r.get("gst_rate", 0.0)), "gst_recoverable_pct": float(r.get("gst_recoverable_pct", 0.0)),
                "effective_from": r.get("effective_from") or "2025-01-01", "effective_to": r.get("effective_to"),
                "legal_entity": r.get("legal_entity"), "description": r.get("description"),
                "source_doc": card["doc_file"], "source_language": card["language"],
            })
    for ln in doc.get("vendor_contracts", []):
        r = {**d, **ln}
        rows.append({
            "fee_id": r["fee_id"], "card_id": "CONTRACT", "vendor_id": r["vendor_id"], "cost_type": r["cost_type"],
            "fee_basis": r["fee_basis"], "product_family": "ALL", "capacity": "ALL", "side": "ALL", "rate": float(r["rate"]),
            "currency": r["currency"], "tier_basis": "NONE", "tier_min": None, "tier_max": None, "tier_type": None,
            "floor_per_trade": None, "cap_per_trade": None, "is_pass_through": False, "is_discount_or_waiver": False,
            "gst_rate": 0.0, "gst_recoverable_pct": 0.0, "effective_from": r.get("effective_from") or "2025-01-01",
            "effective_to": r.get("effective_to"), "legal_entity": r.get("legal_entity"), "description": r.get("description"),
            "source_doc": "Procurement contract register", "source_language": "en",
        })
    df = pd.DataFrame(rows, columns=FEE_COLUMNS)
    df["effective_from"] = pd.to_datetime(df.effective_from).dt.date
    df["effective_to"] = pd.to_datetime(df.effective_to).dt.date
    return df


def variable_lines() -> pd.DataFrame:
    f = fee_lines()
    return f[f.fee_basis != "FIXED_MONTHLY"].reset_index(drop=True)


def fixed_lines() -> pd.DataFrame:
    f = fee_lines()
    return f[f.fee_basis == "FIXED_MONTHLY"].reset_index(drop=True)


def fail_rules() -> pd.DataFrame:
    return pd.DataFrame(load_yaml()["fail_cost_rules"])


def fixed_fees_by_month(months: list[str]) -> pd.DataFrame:
    """Contracted fixed fee per vendor × legal entity × month (effective-dated)."""
    fl = fixed_lines()
    out = []
    for m in months:
        d = pd.Timestamp(m + "-01").date()
        live = fl[(fl.effective_from <= d) & (fl.effective_to.isna() | (fl.effective_to >= d))]
        for r in live.itertuples():
            out.append({"period": m, "fee_id": r.fee_id, "vendor_id": r.vendor_id, "legal_entity": r.legal_entity,
                        "currency": r.currency, "amount_lcy": r.rate, "description": r.description})
    return pd.DataFrame(out)
