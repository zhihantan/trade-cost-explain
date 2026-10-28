"""Settlements and settlement fails, costed with the market-specific fail_cost_rule (spec §5 "Fails").

Fail cost accrues daily from fail ageing: per business day the shortfall persists (min / max per day), a one-off
default fee where the market has one, a buy-in once the fail exceeds the market threshold, and an auction
close-out in India. Client-caused fails on client capacity are recharged; the rest is borne.

Planted: in September a cluster of Australia cash-equity fails with Kestrel Asset Management, root cause a Meridian
SSI static-data mismatch after Kestrel changed custodian. Absorber fails make August fails exactly US$60K and
September exactly US$210K at August FX (fails effect +US$150K).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import ratecards as RC
from . import refdata as R

FAIL_RATE = {"HK": 0.0022, "CN": 0.0008, "SG": 0.003, "AU": 0.002, "IN": 0.0012, "KR": 0.0002, "TW": 0.0002, "MY": 0.002}
ROOT_CAUSES = [
    ("Counterparty late delivery", "client", 0.30), ("Counterparty SSI incorrect", "client", 0.12),
    ("Client securities not available", "client", 0.10), ("Late allocation or booking (internal)", "internal", 0.15),
    ("House inventory shortfall", "internal", 0.10), ("Meridian SSI static-data error", "internal", 0.08),
    ("Custodian processing delay", "agent", 0.10), ("Cash funding shortfall", "internal", 0.05),
]
KESTREL_CAUSE = "Meridian SSI static-data mismatch after counterparty custodian change"
DEFAULT_FEE = {"HK": 1000.0, "SG": 200.0}
FUNDING_RATE, BORROW_RATE = 0.045, 0.015


def _rules() -> dict:
    return {r["market"]: r for r in RC.fail_rules().to_dict("records")}


def fail_days_list(due: dt.date, n: int, market: str) -> list[dt.date]:
    out, d = [due], due
    while len(out) < n:
        d = R.add_business_days(d, 1, market)
        out.append(d)
    return out


def cost_fail(market: str, value: float, days: int, rule: dict, buy_in_pct: float = 0.0) -> list[tuple]:
    """Daily cost components for one fail: [(day_index, component, amount_lcy)]."""
    comps = []
    if rule["rule_type"] == "CLOSE_OUT_PCT":
        comps.append((0, "CLOSE_OUT", max(rule["pct_per_day"] * value, rule["min_per_day"] or 0.0)))
        return comps
    lo, hi = rule["min_per_day"] or 0.0, rule["max_per_day"] if rule["max_per_day"] is not None else np.inf
    per_day = float(np.clip(rule["pct_per_day"] * value, lo, hi))
    for i in range(days):
        comps.append((i, "PER_DAY_FEE", per_day))
    if market in DEFAULT_FEE:
        comps.append((0, "DEFAULT_FEE", DEFAULT_FEE[market]))
    if buy_in_pct > 0:
        comps.append((days - 1, "BUY_IN", buy_in_pct * value))
    return comps


class FailBook:
    def __init__(self, trades: pd.DataFrame, fxl: dict, seed: int = 404):
        self.t = trades
        self.fxl = fxl
        self.rng = np.random.default_rng(seed)
        self.rules = _rules()
        self.fails: list[dict] = []

    def _new_fail(self, tr, days: int, pct: float, cause: str, kind: str, buy_in: bool, tag: str = "background",
                  value: float | None = None) -> dict:
        mkt = tr.market
        rule = self.rules[mkt]
        due = R.add_business_days(tr.trade_date, R.SETTLE_CYCLE[mkt], mkt)
        val = round(tr.notional * pct if value is None else value, 2)
        bpct = float(self.rng.uniform(0.008, 0.025)) if buy_in else 0.0
        comps = cost_fail(mkt, val, days, rule, bpct)
        dates = fail_days_list(due, max(days, 1), mkt)
        recharge = kind == "client" and tr.capacity == "CLIENT"
        f = {"trade_id": tr.trade_id, "desk_code": tr.desk_code, "legal_entity": tr.legal_entity, "market": mkt,
             "capacity": tr.capacity, "counterparty_id": tr.counterparty_id, "currency": tr.currency,
             "rule_vendor_id": rule["vendor_id"], "settle_due_date": due, "fail_days": days,
             "shortfall_qty": round(tr.qty * (val / tr.notional)), "shortfall_value": val, "root_cause": cause,
             "root_cause_class": kind, "resolution": "BUY_IN" if buy_in else ("CLOSE_OUT" if rule["rule_type"] == "CLOSE_OUT_PCT" else "SETTLED_LATE"),
             "buy_in_pct": bpct, "recharge": recharge, "tag": tag,
             "components": [(dates[min(i, len(dates) - 1)], c, a) for i, c, a in comps]}
        f["settled_date"] = R.add_business_days(dates[-1], 1, mkt)
        return f

    def background(self):
        cash = self.t[self.t.settles & self.t.execution_type.ne("DMA_ALL_IN")]
        p = cash.market.map(FAIL_RATE).to_numpy()
        pick = cash[self.rng.random(len(cash)) < p]
        causes, kinds, w = zip(*ROOT_CAUSES)
        w = np.array(w) / sum(w)
        for tr in pick.itertuples():
            rule = self.rules[tr.market]
            days = int(min(1 + self.rng.geometric(0.45) - 1, 9))
            days = max(days, 1)
            buy_in = rule["rule_type"] != "CLOSE_OUT_PCT" and days > rule["buy_in_after_days"]
            if buy_in:
                days = rule["buy_in_after_days"] + 1
            ci = self.rng.choice(len(causes), p=w)
            self.fails.append(self._new_fail(tr, days, float(self.rng.uniform(0.25, 1.0)), causes[ci], kinds[ci], buy_in))

    # ── monthly cost (net, LCY → USD at a given FX month) ──
    def monthly_net_usd(self, period: str, fx_period: str) -> float:
        tot = 0.0
        for f in self.fails:
            for d, _, a in f["components"]:
                if d.strftime("%Y-%m") == period and not f["recharge"]:
                    tot += a * self.fxl[(f["currency"], fx_period)]
        return tot

    def _absorber(self, gap_usd: float, period: str, fx_period: str, cpty: str | None, cause: str, tag: str,
                  date_lo: dt.date, date_hi: dt.date, desk: str = "AUCE"):
        """Add AU fails (0.10%/day, A$100–5,000 per day, no buy-in) that close a positive gap exactly."""
        fx = self.fxl[("AUD", fx_period)]
        used = {f["trade_id"] for f in self.fails}
        pool = self.t[(self.t.desk_code == desk) & (self.t.market == "AU") & self.t.settles
                      & (self.t.trade_date >= date_lo) & (self.t.trade_date <= date_hi)
                      & (self.t.notional >= 1_000_000) & ~self.t.trade_id.isin(used)]
        pool = pool.sample(frac=1.0, random_state=int(self.rng.integers(1e9)))
        gap_aud = gap_usd / fx
        assert gap_aud >= 100, f"absorber gap too small: A${gap_aud:,.2f}"
        caps = 4 * np.minimum(0.001 * pool.notional.to_numpy(), 5000.0)
        n = int(np.searchsorted(np.cumsum(caps), gap_aud) + 1)
        shares = gap_aud * caps[:n] / caps[:n].sum()
        for tr_row, share in zip(pool.iloc[:n].itertuples(), shares):
            days = 4 if share >= 400 else 1
            value = share / (0.001 * days)
            if cpty:
                self.t.loc[self.t.trade_id == tr_row.trade_id, "counterparty_id"] = cpty
            tr = self.t[self.t.trade_id == tr_row.trade_id].iloc[0]
            f = self._new_fail(tr, days, 1.0, cause, "internal", False, tag=tag, value=value)
            assert all(c[0].strftime("%Y-%m") == period for c in f["components"]), "absorber spills over month end"
            self.fails.append(f)

    def _cost_usd(self, f: dict, fx_period: str) -> float:
        return 0.0 if f["recharge"] else sum(a for _, _, a in f["components"]) * self.fxl[(f["currency"], fx_period)]

    def plant(self, fails_aug_usd: float, fails_sep_cc_usd: float):
        aug, sep = "2026-08", "2026-09"
        # August: trim background if it overshoots, then fill exactly
        while self.monthly_net_usd(aug, aug) > fails_aug_usd * 0.85:
            only_aug = [f for f in self.fails if f["tag"] == "background" and not f["recharge"]
                        and all(c[0].strftime("%Y-%m") == aug for c in f["components"])]
            self.fails.remove(max(only_aug, key=lambda f: self._cost_usd(f, aug)))
        self._absorber(fails_aug_usd - self.monthly_net_usd(aug, aug), aug, aug, None,
                       "Late allocation or booking (internal)", "absorber", dt.date(2026, 8, 3), dt.date(2026, 8, 20))
        # September background held at August's level (at August FX) so the increase is the Kestrel cluster
        while self.monthly_net_usd(sep, aug) > fails_aug_usd * 1.03:
            only_sep = [f for f in self.fails if f["tag"] == "background" and not f["recharge"]
                        and all(c[0].strftime("%Y-%m") == sep for c in f["components"])]
            self.fails.remove(max(only_sep, key=lambda f: self._cost_usd(f, aug)))
        # September: Kestrel cluster on large AU client trades 9–21 Sep, sized until ~US$15K remains for the absorber
        cand = self.t[(self.t.desk_code == "AUCE") & (self.t.capacity == "CLIENT") & self.t.settles
                      & (self.t.trade_date >= dt.date(2026, 9, 9)) & (self.t.trade_date <= dt.date(2026, 9, 21))
                      & (self.t.notional >= 2_500_000)]
        used = {f["trade_id"] for f in self.fails}
        cand = cand[~cand.trade_id.isin(used)].sample(frac=1.0, random_state=7)
        gap = fails_sep_cc_usd - self.monthly_net_usd(sep, aug)
        assert gap > 40_000, f"September background fails leave too little room: {gap:,.0f}"
        n_added = 0
        for tr in cand.itertuples():
            buy_in = n_added in (3, 8)
            days = 6 if buy_in else int(self.rng.integers(3, 6))
            trial = self._new_fail(tr, days, 1.0, KESTREL_CAUSE, "internal", buy_in, tag="kestrel")
            if buy_in:  # keep buy-in premia modest so the cluster stays a fail-fee story
                trial = self._new_fail(tr, days, 1.0, KESTREL_CAUSE, "internal", False, tag="kestrel")
                trial["components"].append((trial["components"][-1][0], "BUY_IN", 0.006 * trial["shortfall_value"]))
                trial["resolution"] = "BUY_IN"
            if any(c[0].strftime("%Y-%m") != sep for c in trial["components"]):
                continue
            cost = self._cost_usd(trial, aug)
            if gap - cost < 15_000:
                break
            self.t.loc[self.t.trade_id == tr.trade_id, "counterparty_id"] = "C001"
            trial["counterparty_id"] = "C001"
            self.fails.append(trial)
            gap -= cost
            n_added += 1
        self._absorber(gap, sep, aug, "C001", KESTREL_CAUSE, "kestrel", dt.date(2026, 9, 9), dt.date(2026, 9, 21))

    # ── outputs ──
    def settlements(self) -> pd.DataFrame:
        cash = self.t[self.t.settles]
        due_map = {}
        for (m, d) in set(zip(cash.market, cash.trade_date)):
            due_map[(m, d)] = R.add_business_days(d, R.SETTLE_CYCLE[m], m)
        due = [due_map[(m, d)] for m, d in zip(cash.market, cash.trade_date)]
        s = pd.DataFrame({"settlement_id": "ST-" + cash.trade_id.str[2:], "trade_id": cash.trade_id.to_numpy(),
                          "market": cash.market.to_numpy(), "settlement_location": cash.settlement_location.to_numpy(),
                          "settle_due_date": due, "settled_date": due, "settle_status": "SETTLED", "fail_days": 0,
                          "shortfall_qty": 0.0, "shortfall_value": 0.0, "fail_fee": 0.0, "default_fee": 0.0,
                          "buy_in_cost": 0.0, "close_out_cost": 0.0, "recharged_to_client": 0.0, "root_cause": None,
                          "root_cause_class": None, "resolution": None, "currency": cash.currency.to_numpy(),
                          "counterparty_id": cash.counterparty_id.to_numpy()}).set_index("trade_id")
        rows = []
        for f in self.fails:
            comp = {"PER_DAY_FEE": 0.0, "DEFAULT_FEE": 0.0, "BUY_IN": 0.0, "CLOSE_OUT": 0.0}
            for _, c, a in f["components"]:
                comp[c] += a
            total = sum(comp.values())
            rows.append({"trade_id": f["trade_id"],
                         "settle_status": "FAILED_SETTLED_LATE" if f["resolution"] == "SETTLED_LATE" else f"FAILED_{f['resolution']}",
                         "fail_days": f["fail_days"], "shortfall_qty": float(f["shortfall_qty"]),
                         "shortfall_value": f["shortfall_value"], "fail_fee": round(comp["PER_DAY_FEE"], 2),
                         "default_fee": round(comp["DEFAULT_FEE"], 2), "buy_in_cost": round(comp["BUY_IN"], 2),
                         "close_out_cost": round(comp["CLOSE_OUT"], 2),
                         "recharged_to_client": round(total, 2) if f["recharge"] else 0.0, "root_cause": f["root_cause"],
                         "root_cause_class": f["root_cause_class"], "resolution": f["resolution"],
                         "settled_date": f["settled_date"], "counterparty_id": f["counterparty_id"]})
        fd = pd.DataFrame(rows).set_index("trade_id")
        cols = [c for c in fd.columns]
        s = s.astype({"fail_days": "int64", "root_cause": "object", "root_cause_class": "object", "resolution": "object"})
        s.loc[fd.index, cols] = fd[cols].to_numpy()
        return s.reset_index()

    def daily_costs(self) -> pd.DataFrame:
        rows = []
        for f in self.fails:
            for d, c, a in f["components"]:
                rows.append({"trade_id": f["trade_id"], "fail_date": d, "period": d.strftime("%Y-%m"), "desk_code": f["desk_code"],
                             "capacity": f["capacity"], "legal_entity": f["legal_entity"], "market": f["market"],
                             "currency": f["currency"], "rule_vendor_id": f["rule_vendor_id"],
                             "counterparty_id": f["counterparty_id"], "root_cause": f["root_cause"], "component": c,
                             "amount_lcy": a, "recharged_lcy": a if f["recharge"] else 0.0, "tag": f["tag"]})
        return pd.DataFrame(rows)
