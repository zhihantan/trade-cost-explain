"""Fixture Gold data for local development and for `DATA_MODE=auto` before Gold exists.

Mirrors docs/CONTRACTS.md §2: the planted September-vs-August bridge ties exactly (APAC 5.0M -> 6.2M; Equity
Derivatives exchange & clearing 2.17M -> 2.68M). Other comparisons are scaled from the same row structure.
Every number here is synthetic and illustrative.
"""
from __future__ import annotations

from functools import lru_cache

EFFECTS = ["volume", "mix", "rate", "fx", "fails", "fixed", "timing", "unexplained"]
GOLD = "cost_explain.gold"

COMPARISONS = [  # same shape as gold.dim_comparison (sort_order YYYYMM for MoM, 9000xx for QoQ)
    dict(comparison_id="MOM_2026-09", comparison_type="MoM", period_p0="2026-08", period_p1="2026-09",
         p0_label="Aug 2026", p1_label="Sep 2026", sort_order=202609, is_default=True,
         comparison_label="Sep 2026 vs Aug 2026"),
    dict(comparison_id="QOQ_FY2026Q2", comparison_type="QoQ", period_p0="FY2026Q1", period_p1="FY2026Q2",
         p0_label="FY2026/27 Q1", p1_label="FY2026/27 Q2", sort_order=900004, is_default=False,
         comparison_label="FY2026/27 Q2 vs FY2026/27 Q1"),
    dict(comparison_id="MOM_2026-08", comparison_type="MoM", period_p0="2026-07", period_p1="2026-08",
         p0_label="Jul 2026", p1_label="Aug 2026", sort_order=202608, is_default=False,
         comparison_label="Aug 2026 vs Jul 2026"),
    dict(comparison_id="MOM_2026-07", comparison_type="MoM", period_p0="2026-06", period_p1="2026-07",
         p0_label="Jun 2026", p1_label="Jul 2026", sort_order=202607, is_default=False,
         comparison_label="Jul 2026 vs Jun 2026"),
]

BUSINESS = {"CEQ": "Cash Equities", "EQD": "Equity Derivatives", "PDO": "Prime & Delta One", "RTS": "Rates",
            "CRD": "Credit", "FXE": "FX & Emerging Markets"}
DESK = {"HKCE": "HK Cash Equities", "CNSC": "Stock Connect / China Flow", "KTEQ": "Korea & Taiwan Equities",
        "AUCE": "Australia Cash Equities", "INEQ": "India Equities", "HKED": "HK Equity Derivatives",
        "D1PR": "Delta One / Prime", "SGRT": "Singapore Rates", "AURF": "Australia Rates & Futures",
        "FLCR": "Flow Credit", "SGFX": "Singapore FX", "SGEM": "Singapore EM (incl. Malaysia)"}
DESK_BUS = {"HKCE": "CEQ", "CNSC": "CEQ", "KTEQ": "CEQ", "AUCE": "CEQ", "INEQ": "CEQ", "HKED": "EQD",
            "D1PR": "PDO", "SGRT": "RTS", "AURF": "RTS", "FLCR": "CRD", "SGFX": "FXE", "SGEM": "FXE"}
ENTITY = {"HK": ("MSHK", "Meridian Securities (Hong Kong) Ltd"), "CN": ("MSHK", "Meridian Securities (Hong Kong) Ltd"),
          "SG": ("MSSG", "Meridian Securities Singapore Pte Ltd"), "AU": ("MSAU", "Meridian Australia Securities Ltd"),
          "IN": ("MSIN", "Meridian Financial Services India Pvt Ltd"), "KR": ("MSKR", "Meridian Securities Korea Co Ltd"),
          "TW": ("MSTW", "Meridian Securities (HK) Ltd — Taiwan Branch"),
          "MY": ("MSMY", "Meridian Securities Malaysia Sdn Bhd")}
VENDOR = {"PRX": ("Pearl River Exchange", "Exchange"), "PRC": ("Pearl River Clearing", "CCP"),
          "MRX": ("Merlion Exchange", "Exchange"), "HRX": ("Han River Exchange", "Exchange"),
          "SXA": ("Southern Cross Exchange", "Exchange"), "TAM": ("Tasman Alternative Market", "Exchange"),
          "SXC": ("Southern Cross Clear", "CCP"), "CNX": ("Connect Northbound", "Exchange"),
          "FMX": ("Formosa Exchange", "Exchange"), "IGX": ("Indus Exchange", "Exchange"),
          "B01": ("Aurora Pacific Securities", "Broker"), "B02": ("Bluewater Brokerage", "Broker"),
          "B03": ("Cobalt Securities", "Broker"), "B05": ("Emberly Securities", "Broker"),
          "B06": ("Foxglove Brokerage", "Broker"), "V901": ("Unmapped vendor (2)", "Unmapped")}
CATEGORY = {"EXCHANGE": "Exchange & clearing", "CLEARING": "Exchange & clearing", "BROKERAGE": "Brokerage",
            "SETTLEMENT": "Settlement & custody", "FAILS": "Settlement fails", "FIXED": "Fixed fees",
            "UNMAPPED": "Unmapped"}

# desk, cost_type, vendor, market, currency, p0, volume, mix, rate, fx, fails, fixed, timing, unexplained  (US$)
_SEP_ROWS = [
    ("HKED", "EXCHANGE", "PRX", "HK", "HKD", 1_480_000, 268_000, 90_000, 60_000, -1_000, 0, 0, -14_000, 0),
    ("HKED", "CLEARING", "PRC", "HK", "HKD", 420_000, 76_000, 0, 0, -500, 0, 0, -6_000, 0),
    ("HKED", "EXCHANGE", "MRX", "SG", "USD", 160_000, 28_900, 0, 0, 0, 0, 0, 0, 0),
    ("HKED", "EXCHANGE", "HRX", "KR", "KRW", 70_000, 10_500, 0, 0, -5_000, 0, 0, 0, 0),
    ("HKED", "EXCHANGE", "SXA", "AU", "AUD", 40_000, 6_600, 0, 0, -3_500, 0, 0, 0, 0),
    ("HKCE", "EXCHANGE", "PRX", "HK", "HKD", 615_000, 129_000, 0, 0, -300, 0, 0, 0, 0),
    ("HKCE", "SETTLEMENT", "PRC", "HK", "HKD", 150_000, 30_000, 0, 0, -100, 0, 0, 0, 0),
    ("HKCE", "FIXED", "PRX", "HK", "HKD", 160_000, 0, 0, 0, -100, 0, 0, 0, 0),
    ("CNSC", "EXCHANGE", "CNX", "CN", "CNH", 210_000, 42_000, 0, 0, -1_200, 0, 0, 0, 0),
    ("KTEQ", "BROKERAGE", "B03", "KR", "USD", 300_000, 63_000, 0, 0, 0, 0, 0, 0, 0),
    ("KTEQ", "EXCHANGE", "HRX", "KR", "KRW", 160_000, 32_000, 0, 0, -20_000, 0, 0, 0, 0),
    ("KTEQ", "EXCHANGE", "FMX", "TW", "TWD", 140_000, 28_000, 0, 0, -8_000, 0, 0, 0, 0),
    ("AUCE", "EXCHANGE", "SXA", "AU", "AUD", 260_000, 60_000, 160_000, 0, -30_000, 0, 0, -15_000, 0),
    ("AUCE", "EXCHANGE", "TAM", "AU", "AUD", 90_000, 21_000, -60_000, 0, -1_200, 0, 0, 0, 0),
    ("AUCE", "FAILS", "SXC", "AU", "AUD", 15_000, 0, 0, 0, -8_900, 150_000, 0, 0, 0),
    ("AUCE", "UNMAPPED", "V901", "AU", "USD", 5_000, 0, 0, 0, 0, 0, 0, 0, 10_000),
    ("INEQ", "EXCHANGE", "IGX", "IN", "INR", 230_000, 48_000, 0, 40_000, -12_000, 0, 0, -15_000, 0),
    ("SGRT", "BROKERAGE", "B02", "SG", "SGD", 120_000, 14_000, 0, 0, -1_000, 0, 0, 0, 0),
    ("AURF", "EXCHANGE", "SXA", "AU", "AUD", 95_000, 11_000, 0, 0, -6_600, 0, 0, 0, 0),
    ("FLCR", "BROKERAGE", "B05", "HK", "USD", 85_000, 9_000, 0, 0, 0, 0, 0, 0, 0),
    ("SGFX", "BROKERAGE", "B02", "SG", "USD", 70_000, 7_000, 0, 0, 0, 0, 0, 0, 0),
    ("SGEM", "BROKERAGE", "B06", "MY", "MYR", 45_000, 4_000, 0, 0, -500, 0, 0, 0, 0),
    ("D1PR", "BROKERAGE", "B01", "HK", "HKD", 80_000, 12_000, 0, 0, -100, 0, 0, 0, 0),
]

# APAC totals per comparison: p0 and each effect (US$). MOM_2026-09 equals the planted targets exactly.
_TOTALS = {
    "MOM_2026-08": dict(p0=5_180_000, volume=-220_000, mix=15_000, rate=5_000, fx=12_000, fails=-8_000, fixed=0,
                        timing=25_000, unexplained=-9_000),
    "MOM_2026-07": dict(p0=4_900_000, volume=190_000, mix=10_000, rate=45_000, fx=-8_000, fails=12_000, fixed=0,
                        timing=20_000, unexplained=11_000),
    "QOQ_FY2026Q2": dict(p0=14_600_000, volume=1_350_000, mix=210_000, rate=190_000, fx=-120_000, fails=130_000,
                         fixed=0, timing=-5_000, unexplained=25_000),
}


def _row(cid: str, desk, cost_type, vendor, market, ccy, p0, *effects) -> dict:
    bus = DESK_BUS[desk]
    le, le_name = ENTITY[market]
    category = CATEGORY[cost_type]
    eff = dict(zip(EFFECTS, effects))
    row = dict(comparison_id=cid, division="APAC Global Markets", business_code=bus, business=BUSINESS[bus],
               desk_code=desk, desk_name=DESK[desk], legal_entity=le, legal_entity_name=le_name,
               cost_type=cost_type, cost_category=category,
               headline_slice=("Equity Derivatives — exchange & clearing" if bus == "EQD" and
                               category == "Exchange & clearing" else "Rest of APAC Global Markets"),
               vendor_id=vendor, vendor_name=VENDOR[vendor][0], vendor_type=VENDOR[vendor][1], market=market,
               currency=ccy, p0_actual_usd=float(p0))
    for k, v in eff.items():
        row[f"{k}_usd"] = float(v)
    row["flux_usd"] = float(sum(eff.values()))
    row["p1_actual_usd"] = row["p0_actual_usd"] + row["flux_usd"]
    row["p1_cc_usd"] = row["p1_actual_usd"] - row["fx_usd"]
    return row


@lru_cache
def bridge_rows() -> tuple[dict, ...]:
    rows = [_row("MOM_2026-09", *r) for r in _SEP_ROWS]
    base_p0 = sum(r[5] for r in _SEP_ROWS)
    for cid, t in _TOTALS.items():
        scale = t["p0"] / base_p0
        scaled = []
        for r in _SEP_ROWS:
            share = r[5] / base_p0
            scaled.append((*r[:5], round(r[5] * scale), *[round(t[e] * share) for e in EFFECTS]))
        # absorb rounding into the largest row so APAC totals tie exactly
        diff_p0 = t["p0"] - sum(s[5] for s in scaled)
        diffs = [t[e] - sum(s[6 + i] for s in scaled) for i, e in enumerate(EFFECTS)]
        big = scaled[0]
        scaled[0] = (*big[:5], big[5] + diff_p0, *[big[6 + i] + diffs[i] for i in range(len(EFFECTS))])
        rows.extend(_row(cid, *s) for s in scaled)
    return tuple(rows)


def comparisons() -> list[dict]:
    return [dict(c) for c in COMPARISONS]


# ------------------------------------------------------------------ figure registry (mirrors gold.commentary_figures)
METRIC_LABELS = {
    "P0": "Prior period cost", "P1": "Current period cost", "FLUX": "Total flux", "FLUX_PCT": "Flux %",
    "VOLUME": "Volume effect", "MIX": "Mix effect", "RATE": "Rate effect", "FX": "FX effect",
    "FAILS": "Settlement fails", "FIXED": "Fixed fees", "TIMING": "Timing / accrual", "UNEXPLAINED": "Unexplained",
    "GOOD": "Good flux (volume-driven)", "CONTROLLABLE": "Controllable flux (mix + fails)",
    "EXTERNAL": "External, timing & residual", "GOOD_PCT": "Good flux share", "CONTROLLABLE_PCT": "Controllable share",
    "UNEXPLAINED_THRESHOLD": "Unexplained threshold (greater of US$25K and 5% of the change)",
}
SCOPE_LABELS = {"APAC": "APAC Global Markets", "ED_EXCH_CLR": "Equity Derivatives — exchange & clearing",
                "REST": "Rest of APAC Global Markets"}


def scope_filter(scope_key: str) -> tuple[str, callable]:
    if scope_key == "APAC":
        return "TRUE", lambda r: True
    if scope_key == "ED_EXCH_CLR":
        return ("business_code = 'EQD' AND cost_category = 'Exchange & clearing'",
                lambda r: r["business_code"] == "EQD" and r["cost_category"] == "Exchange & clearing")
    if scope_key == "REST":
        return ("NOT (business_code = 'EQD' AND cost_category = 'Exchange & clearing')",
                lambda r: not (r["business_code"] == "EQD" and r["cost_category"] == "Exchange & clearing"))
    kind, code = scope_key.split(":", 1)
    col = "business_code" if kind == "BUS" else "desk_code"
    return f"{col} = '{code}'", lambda r: r[col] == code


def scope_label(scope_key: str) -> str:
    if scope_key in SCOPE_LABELS:
        return SCOPE_LABELS[scope_key]
    kind, code = scope_key.split(":", 1)
    return BUSINESS.get(code, code) if kind == "BUS" else DESK.get(code, code)


@lru_cache
def figure_registry() -> dict[str, dict]:
    reg: dict[str, dict] = {}
    scopes = ["APAC", "ED_EXCH_CLR", "REST", *[f"BUS:{b}" for b in BUSINESS], *[f"DESK:{d}" for d in DESK]]
    for comp in COMPARISONS:
        cid = comp["comparison_id"]
        rows = [r for r in bridge_rows() if r["comparison_id"] == cid]
        for sk in scopes:
            where, pred = scope_filter(sk)
            sel = [r for r in rows if pred(r)]
            if not sel:
                continue
            agg = {k: sum(r[f"{k}_usd"] for r in sel) for k in EFFECTS}
            p0 = sum(r["p0_actual_usd"] for r in sel)
            p1 = sum(r["p1_actual_usd"] for r in sel)
            flux = p1 - p0
            good = agg["volume"]
            ctrl = agg["mix"] + agg["fails"]
            ext = agg["rate"] + agg["fx"] + agg["timing"] + agg["unexplained"] + agg["fixed"]
            values = {"P0": p0, "P1": p1, "FLUX": flux, "FLUX_PCT": (flux / p0) if p0 else None,
                      **{k.upper(): v for k, v in agg.items()}, "GOOD": good, "CONTROLLABLE": ctrl, "EXTERNAL": ext,
                      "GOOD_PCT": (good / flux) if flux else None, "CONTROLLABLE_PCT": (ctrl / flux) if flux else None,
                      "UNEXPLAINED_THRESHOLD": max(25_000.0, 0.05 * abs(flux))}
            for metric, value in values.items():
                key = f"{cid}|{sk}|{metric}"
                reg[key] = dict(figure_key=key, comparison_id=cid, scope_key=sk, scope_label=scope_label(sk),
                                metric=metric, metric_label=METRIC_LABELS[metric], value=value,
                                unit="PCT" if metric.endswith("_PCT") else "USD",
                                source_table=f"{GOLD}.cost_flux_bridge",
                                filter_expr=f"comparison_id = '{cid}'" + ("" if where == "TRUE" else f" AND {where}"),
                                description=f"{METRIC_LABELS[metric]} — {scope_label(sk)}, "
                                            f"{comp['p1_label']} vs {comp['p0_label']}")
    reg["INV|2026-08|B03|VARIANCE"] = dict(
        figure_key="INV|2026-08|B03|VARIANCE", comparison_id=None, scope_key="VENDOR:B03",
        scope_label="Cobalt Securities", metric="VARIANCE", metric_label="Invoiced minus expected",
        value=85_000.0, unit="USD", source_table=f"{GOLD}.invoice_recon",
        filter_expr="service_period = '2026-08' AND vendor_id = 'B03'",
        description="Invoice variance — Cobalt Securities, service period 2026-08: volume-tier rebate not applied")
    reg["FAILS|2026-09|AUCE|C001|NET"] = dict(
        figure_key="FAILS|2026-09|AUCE|C001|NET", comparison_id="MOM_2026-09", scope_key="DESK:AUCE",
        scope_label="Kestrel Asset Management", metric="NET",
        metric_label="Net settlement-fail cost", value=143_311.58, unit="USD",
        source_table=f"{GOLD}.fail_cost_summary",
        filter_expr="period = '2026-09' AND desk_code = 'AUCE' AND counterparty_id = 'C001'",
        description="Net fail cost — Kestrel Asset Management, AUCE, 2026-09 (Meridian SSI static-data mismatch after "
                    "counterparty custodian change)")
    return reg
