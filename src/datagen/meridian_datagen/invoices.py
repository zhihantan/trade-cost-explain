"""AP invoices (headers + lines) from the vendors' point of view, received after month end.

Invoices reproduce expected cost line by line (fee code × product), with GST as tax, except planted billing errors:
  * Cobalt Securities ("Broker C") August 2026: billed the standard 3.0 bp tier although Meridian's aggregate turnover
    qualified for tier 2 (2.5 bp) → US$85K over-billed (received 28-Sep-2026; disputed, never hits the P&L)
  * smaller historical errors (discount not applied, GST charged twice, superseded rate, duplicate line)
Only invoices received on or before the as-of date (September close, 5-Oct-2026) are in the extract.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import ledger as L
from . import refdata as R

BROKER_C = "B03"
LAG_DAYS = {"Exchange": (9, 16), "CCP": (9, 16), "Broker": (24, 50), "Broker (intra-group)": (4, 6), "Connectivity": (5, 8)}
PLANTED_RECEIVED = {("2026-08", "B03"): dt.date(2026, 9, 28)}
BACKGROUND_ERRORS = [
    # (service period, vendor, entity, kind, note)
    ("2026-03", "PRX", "MSHK", "DISCOUNT_NOT_APPLIED", "PRX Tech promotional discount not applied on 2–3 Mar"),
    ("2026-05", "SXC", "MSAU", "GST_DOUBLE", "GST charged twice on settlement instruction fees"),
    ("2026-06", "B02", "MSSG", "SUPERSEDED_RATE", "FX brokerage billed at superseded US$2.40/mn rate"),
    ("2026-07", "B04", "MSKR", "DUPLICATE_LINE", "Duplicate HRX 200 commission line"),
]


def received_date(period: str, vendor_id: str, rng) -> dt.date:
    if (period, vendor_id) in PLANTED_RECEIVED:
        return PLANTED_RECEIVED[(period, vendor_id)]
    lo, hi = LAG_DAYS.get(R.VENDOR_TYPE[vendor_id], (10, 20))
    if vendor_id in ("B05",):          # Emberly bills ~45 days in arrears
        lo, hi = 42, 48
    return L.month_end(period) + dt.timedelta(days=int(rng.integers(lo, hi + 1)))


INV_KEYS = ["period", "billing_vendor_id", "legal_entity", "cost_currency", "fee_id", "week_start"]
INVOICE_TYPE = {"EXCHANGE": "TRADING", "LEVY": "TRADING", "TAX": "TRADING", "CLEARING": "CLEARING_SETTLEMENT",
                "SETTLEMENT": "CLEARING_SETTLEMENT", "FAILS": "CLEARING_SETTLEMENT", "BROKERAGE": "BROKERAGE",
                "FIXED": "MEMBERSHIP_CONNECTIVITY"}


def invoice_aggregate(e: pd.DataFrame) -> pd.DataFrame:
    """One month of engine output → invoice-line grain (fee code × product × trade week), GST as tax."""
    td = pd.to_datetime(e.trade_date)
    ws = td - pd.to_timedelta(td.dt.weekday, unit="D")
    ms = pd.Timestamp(e.period.iloc[0] + "-01")
    e = e.assign(week_start=ws.where(ws >= ms, ms).dt.date)
    fees = e[~e.cost_type.isin(["GST_NONREC", "GST_REC"])]
    fl = fees.groupby(INV_KEYS + ["cost_type", "product_family"], as_index=False).agg(
        qty=("volume", "sum"), net_amount=("cost_lcy", "sum"))
    gst = e[e.cost_type.isin(["GST_NONREC", "GST_REC"])].assign(
        rec=lambda x: np.where(x.cost_type.eq("GST_REC"), x.cost_lcy, 0.0))
    gl = gst.groupby(INV_KEYS, as_index=False).agg(tax_amount=("cost_lcy", "sum"), tax_recoverable=("rec", "sum"))
    return fl.merge(gl, on=INV_KEYS, how="left")


def build(fl: pd.DataFrame, fail_daily: pd.DataFrame, fixed_by_month: pd.DataFrame, as_of: dt.date, seed: int = 909):
    """fl: invoice_aggregate() output for all months."""
    rng = np.random.default_rng(seed)
    fl = fl.copy()
    fl[["tax_amount", "tax_recoverable"]] = fl[["tax_amount", "tax_recoverable"]].fillna(0.0)
    fl["unit_rate"] = np.where(fl.qty > 0, fl.net_amount / fl.qty, 0.0)
    fl["line_type"] = "VARIABLE"
    fx = fixed_by_month.rename(columns={"vendor_id": "billing_vendor_id", "currency": "cost_currency", "amount_lcy": "net_amount"})
    fx = fx.assign(cost_type="FIXED", product_family="ALL", qty=1.0, unit_rate=fx.net_amount, tax_amount=0.0,
                   tax_recoverable=0.0, line_type="FIXED", week_start=pd.to_datetime(fx.period + "-01").dt.date)
    fd = fail_daily.copy()
    fd = (fd.groupby(["period", "rule_vendor_id", "legal_entity", "currency", "component"], as_index=False)
            .agg(net_amount=("amount_lcy", "sum"), qty=("trade_id", "nunique")))
    fd = fd.rename(columns={"rule_vendor_id": "billing_vendor_id", "currency": "cost_currency"})
    fd = fd.assign(fee_id="FAIL-" + fd.component, cost_type="FAILS", product_family="ALL",
                   unit_rate=fd.net_amount / fd.qty, tax_amount=0.0, tax_recoverable=0.0, line_type="FAILS",
                   week_start=pd.to_datetime(fd.period + "-01").dt.date).drop(columns="component")
    lines = pd.concat([fl, fx[fl.columns.intersection(fx.columns).tolist() + ["description"]], fd], ignore_index=True)

    # planted Broker C error: August commission billed at the standard 3.0 bp tier
    bc = lines.period.eq("2026-08") & lines.billing_vendor_id.eq(BROKER_C) & lines.cost_type.eq("BROKERAGE")
    lines.loc[bc, "net_amount"] = lines.loc[bc, "net_amount"] * (3.0 / 2.5)
    lines.loc[bc, "unit_rate"] = lines.loc[bc, "unit_rate"] * (3.0 / 2.5)
    lines.loc[bc, "fee_id"] = lines.loc[bc, "fee_id"].str.replace("COB-T2", "COB-STD")
    # background errors
    for period, vend, ent, kind, _ in BACKGROUND_ERRORS:
        m = lines.period.eq(period) & lines.billing_vendor_id.eq(vend) & lines.legal_entity.eq(ent)
        if kind == "DISCOUNT_NOT_APPLIED":
            mm = m & lines.fee_id.eq("PRX-DV-TCH-DSC")
            lines.loc[mm, "net_amount"] *= 0.90
        elif kind == "GST_DOUBLE":
            mm = m & lines.cost_type.eq("SETTLEMENT")
            lines.loc[mm, "tax_amount"] *= 2.0
        elif kind == "SUPERSEDED_RATE":
            mm = m & lines.fee_id.str.startswith("BLU-FX")
            lines.loc[mm, "net_amount"] *= 2.40 / 2.50
            lines.loc[mm, "unit_rate"] *= 2.40 / 2.50
        elif kind == "DUPLICATE_LINE":
            mm = m & lines.fee_id.eq("DUN-HRX200")
            lines = pd.concat([lines, lines[mm]], ignore_index=True)

    lines["ap_vendor_id"] = [R.ap_vendor_for(v, le) for v, le in zip(lines.billing_vendor_id, lines.legal_entity)]
    lines["invoice_type"] = lines.cost_type.map(INVOICE_TYPE)
    hdr = lines.groupby(["period", "ap_vendor_id", "billing_vendor_id", "legal_entity", "cost_currency", "invoice_type"], as_index=False).agg(
        total_net=("net_amount", "sum"), total_tax=("tax_amount", "sum"), line_count=("net_amount", "size"))
    lag_by_vendor = {}
    for p, v in zip(hdr.period, hdr.billing_vendor_id):   # one received date per vendor-month across its invoices
        lag_by_vendor.setdefault((p, v), received_date(p, v, rng))
    hdr["invoice_received_date"] = [lag_by_vendor[(p, v)] for p, v in zip(hdr.period, hdr.billing_vendor_id)]
    hdr["invoice_date"] = [L.month_end(p) + dt.timedelta(days=int(rng.integers(2, 6))) for p in hdr.period]
    hdr["invoice_date"] = [min(a, b) for a, b in zip(hdr.invoice_date, hdr.invoice_received_date)]
    hdr["invoice_id"] = ("INV-" + hdr.billing_vendor_id + "-" + hdr.legal_entity + "-" + hdr.cost_currency + "-"
                         + hdr.invoice_type.str[:3] + "-" + hdr.period.str.replace("-", ""))
    hdr["vendor_invoice_number"] = [f"{v}/{p.replace('-', '')}/{int(rng.integers(1000, 9999))}"
                                    for v, p in zip(hdr.billing_vendor_id, hdr.period)]
    hdr["total_gross"] = hdr.total_net + hdr.total_tax
    hdr["status"] = np.where(hdr.period.eq("2026-08") & hdr.billing_vendor_id.eq(BROKER_C), "ON_HOLD_PENDING_REVIEW", "POSTED")
    hdr = hdr[hdr.invoice_received_date <= as_of].reset_index(drop=True)
    lines = lines.merge(hdr[["period", "ap_vendor_id", "cost_currency", "invoice_type", "invoice_id", "invoice_received_date"]],
                        on=["period", "ap_vendor_id", "cost_currency", "invoice_type"], how="inner")
    lines["line_no"] = lines.groupby("invoice_id").cumcount() + 1
    lines["description"] = lines.get("description")
    lines = lines.rename(columns={"period": "service_period", "cost_currency": "currency"})
    hdr = hdr.rename(columns={"period": "service_period", "cost_currency": "currency"})
    for c in ("net_amount", "tax_amount", "tax_recoverable", "qty", "unit_rate"):
        lines[c] = lines[c].astype(float).round(6 if c in ("unit_rate", "qty") else 2)
    return hdr, lines


def received_dates(hdr: pd.DataFrame) -> dict:
    """(service_period, ap_vendor_id) → (received date, status): dates the ledger's true-up journals."""
    return {(r.service_period, r.ap_vendor_id): (r.invoice_received_date, r.status) for r in hdr.itertuples()}
