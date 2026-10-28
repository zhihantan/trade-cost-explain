"""FX, market data (volatility index), desk revenue and FY2026/27 plan (all synthetic)."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import refdata as R

# Monthly average rates, US$ per 1 unit of local currency. August 2026 is the anchor; September moves are the
# "natural" risk-off moves (AUD and KRW are re-solved later so the FX bars land exactly on target).
AUG_FX = {"USD": 1.0, "HKD": 0.128, "CNH": 0.1395, "SGD": 0.77, "AUD": 0.66, "INR": 0.011905, "KRW": 0.000725,
          "TWD": 0.031, "MYR": 0.225}
SEP_MOVE = {"USD": 0.0, "HKD": -0.0003, "CNH": -0.004, "SGD": -0.015, "AUD": -0.045, "INR": -0.020, "KRW": -0.040,
            "TWD": -0.025, "MYR": -0.018}
# Drift of the monthly path from Sep-2025 to Aug-2026 (total move into the August anchor)
PATH_DRIFT = {"USD": 0.0, "HKD": 0.002, "CNH": 0.012, "SGD": 0.020, "AUD": 0.030, "INR": -0.025, "KRW": 0.015,
              "TWD": 0.018, "MYR": 0.030}


def monthly_fx(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    n = len(R.MONTHS)
    for ccy, aug in AUG_FX.items():
        if ccy == "USD":
            path = np.ones(n)
        else:
            k = np.arange(n - 1)  # Sep-25 .. Aug-26
            start = aug / (1 + PATH_DRIFT[ccy])
            trend = start + (aug - start) * k / (n - 2)
            noise_scale = 0.0006 if ccy == "HKD" else 0.006
            noise = rng.normal(0, noise_scale, n - 1)
            noise[-1] = 0.0
            path = np.append(trend * (1 + noise), aug * (1 + SEP_MOVE[ccy]))
        for m, v in zip(R.MONTHS, path):
            rows.append({"currency": ccy, "period": m, "rate_to_usd": float(v)})
    return pd.DataFrame(rows)


def fx_lookup(fx: pd.DataFrame) -> dict:
    return {(r.currency, r.period): r.rate_to_usd for r in fx.itertuples()}


def daily_fx(fx_monthly: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """Daily spot rates whose monthly mean equals the monthly average exactly (September drifts lower)."""
    rng = np.random.default_rng(seed)
    out = []
    for ccy in fx_monthly.currency.unique():
        for m in R.MONTHS:
            avg = fx_monthly[(fx_monthly.currency == ccy) & (fx_monthly.period == m)].rate_to_usd.iloc[0]
            days = R.business_days(m, "SG")
            if ccy == "USD":
                vals = np.ones(len(days))
            else:
                vol = 0.0002 if ccy == "HKD" else 0.003
                walk = np.cumsum(rng.normal(0, vol, len(days)))
                if m == "2026-09":
                    walk += np.linspace(0.01, -0.01, len(days)) * (SEP_MOVE[ccy] / -0.04 if SEP_MOVE[ccy] else 0)
                vals = avg * (1 + walk - walk.mean())
            for d, v in zip(days, vals):
                out.append({"currency": ccy, "rate_date": d, "rate_to_usd": float(v), "rate_type": "SPOT_CLOSE"})
    return pd.DataFrame(out)


# ── Volatility index (PRX Volatility Index, VHSI-like) and index level ──────────────────────────────
def vol_index(seed: int = 21) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows, level, idx = [], 21.0, 24_800.0
    for m in R.MONTHS:
        for d in R.business_days(m, "HK"):
            base = 20.5 + 1.5 * np.sin(d.toordinal() / 23.0)
            spike = 0.0
            if dt.date(2026, 9, 8) <= d <= dt.date(2026, 9, 19):
                spike = 13.0 * np.exp(-((d - dt.date(2026, 9, 14)).days / 4.0) ** 2)
            elif dt.date(2026, 9, 20) <= d <= dt.date(2026, 9, 30):
                spike = 4.0 * np.exp(-((d - dt.date(2026, 9, 20)).days / 6.0))
            elif dt.date(2026, 3, 9) <= d <= dt.date(2026, 3, 13):
                spike = 3.0
            level = 0.6 * level + 0.4 * (base + spike) + rng.normal(0, 0.45)
            ret = rng.normal(0.0002, 0.011 * level / 21.0)
            if dt.date(2026, 9, 8) <= d <= dt.date(2026, 9, 16):
                ret -= 0.006
            idx *= 1 + ret
            rows.append({"index_code": "PRXVI", "index_name": "PRX Volatility Index", "trade_date": d,
                         "close_value": round(float(level), 2)})
            rows.append({"index_code": "PRX50", "index_name": "PRX 50 Index", "trade_date": d,
                         "close_value": round(float(idx), 2)})
    return pd.DataFrame(rows)


def day_weights(days: list[dt.date], month: str, kind: str, rng: np.random.Generator) -> np.ndarray:
    """Relative activity per business day: weekday pattern, month-end bump, September volatility spike."""
    w = np.array([{0: 0.95, 1: 1.0, 2: 1.02, 3: 1.03, 4: 1.0}[d.weekday()] for d in days], dtype=float)
    if kind in ("cash", "deriv") and len(days) >= 2:
        w[-2:] *= 1.15
    if month == "2026-09":
        spike = np.array([np.exp(-((d - dt.date(2026, 9, 14)).days / 4.5) ** 2) for d in days])
        w *= 1 + (1.1 if kind == "deriv" else 0.45 if kind == "cash" else 0.2) * spike
    w *= rng.lognormal(0, 0.08, len(days))
    return w / w.sum()


# ── Revenue and plan ────────────────────────────────────────────────────────────────────────────────
AUG_REVENUE_USD = {"HKCE": 6.2e6, "CNSC": 2.4e6, "KTEQ": 3.1e6, "AUCE": 4.0e6, "INEQ": 2.9e6, "HKED": 9.5e6,
                   "D1PR": 3.6e6, "FLCR": 2.8e6, "SGFX": 3.3e6, "SGRT": 2.6e6, "SGEM": 1.9e6, "AURF": 1.7e6}
SEP_REVENUE_GROWTH = {"HKCE": 0.26, "CNSC": 0.22, "KTEQ": 0.24, "AUCE": 0.27, "INEQ": 0.19, "HKED": 0.31,
                      "D1PR": 0.24, "FLCR": 0.07, "SGFX": 0.15, "SGRT": 0.10, "SGEM": 0.12, "AURF": 0.14}
SEASONAL = {"2025-09": 1.03, "2025-10": 1.02, "2025-11": 1.04, "2025-12": 0.88, "2026-01": 1.06, "2026-02": 0.94,
            "2026-03": 1.10, "2026-04": 0.99, "2026-05": 1.03, "2026-06": 1.05, "2026-07": 1.04, "2026-08": 1.00}


def revenue_daily(seed: int = 31) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for desk, aug in AUG_REVENUE_USD.items():
        market = {"KTEQ": "KR", "AUCE": "AU", "INEQ": "IN", "AURF": "AU", "SGFX": "SG", "SGRT": "SG", "SGEM": "SG"}.get(desk, "HK")
        for m in R.MONTHS:
            mult = 1 + SEP_REVENUE_GROWTH[desk] if m == "2026-09" else SEASONAL[m] * rng.normal(1.0, 0.03)
            total = aug * mult
            days = R.business_days(m, market)
            w = day_weights(days, m, "deriv" if desk == "HKED" else "cash" if R.DESK_BUSINESS[desk] in ("CEQ", "PDO") else "otc", rng)
            for d, x in zip(days, total * w):
                rows.append({"desk_code": desk, "trade_date": d, "period": m, "revenue_usd": round(float(x), 2),
                             "revenue_type": "Commissions and trading revenue"})
    return pd.DataFrame(rows)


def plan_monthly(cost_aug_by_desk: dict[str, float], seed: int = 41) -> pd.DataFrame:
    """FY2026/27 budget (set in March 2026): planned net borne trade cost and revenue by desk × month."""
    rng = np.random.default_rng(seed)
    fy_months = [f"2026-{m:02d}" for m in range(4, 13)] + [f"2027-{m:02d}" for m in range(1, 4)]
    rows = []
    for desk, cost_aug in cost_aug_by_desk.items():
        bias = rng.normal(1.03, 0.02)
        for m in fy_months:
            seas = SEASONAL.get(m, SEASONAL.get("2025-" + m[5:], 1.0))
            rows.append({"desk_code": desk, "period": m, "plan_cost_usd": round(cost_aug * bias * seas, 2),
                         "plan_revenue_usd": round(AUG_REVENUE_USD[desk] * 1.04 * seas, 2), "plan_version": "FY2026/27 Budget v3"})
    return pd.DataFrame(rows)
