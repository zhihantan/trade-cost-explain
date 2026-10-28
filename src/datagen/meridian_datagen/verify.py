"""Independent tie-out: rebuild the September-vs-August bridge from the LANDED FILES and compare with the targets.

Nothing here reuses generator state: trades, GL, settlements, invoices and FX are read back from disk, expected cost is
recomputed from the canonical rate cards, fail costs are recomputed from fail_cost_rule, and the bridge follows the
same rules as the Gold SQL. Pass = every cell rounds to its US$K target and is within US$50, totals tie, and the
Broker C finding is US$85K.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import bridge as BR
from . import design as D
from . import engine as EN
from . import fails as FA
from . import ratecards as RC
from . import realize as RZ
from . import refdata as R

TOL_USD = 50.0
EFFECTS = ["volume", "mix", "rate", "fails", "fixed", "timing", "fx", "unexplained"]


def _fx(raw: Path) -> dict:
    recs = []
    for f in sorted((raw / "fx").glob("*.json")):
        recs += [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    fx = pd.DataFrame(recs)
    fx = fx[fx.rate_type == "MONTHLY_AVERAGE"]
    return {(r.currency, r.period): r.rate_to_usd for r in fx.itertuples()}


def _trades(raw: Path, period: str) -> pd.DataFrame:
    files = sorted((raw / "trades").glob(f"trades_{period.replace('-', '')}*.parquet"))
    t = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    t["period"] = period
    t["settles"] = t.settle_vendor.notna() | t.settlement_location.ne("CUSTODIAN")
    t["settles"] = t.settlement_location.ne("CUSTODIAN")
    return t


def _fail_costs(raw: Path, fxl: dict, fx_period_for: dict) -> dict:
    """Net fail cost per (period) in USD, recomputed from settlements × fail_cost_rule."""
    st = pd.concat([pd.read_parquet(f) for f in sorted((raw / "settlements").glob("*.parquet"))], ignore_index=True)
    st = st[st.settle_status.ne("SETTLED")]
    rules = {r["market"]: r for r in RC.fail_rules().to_dict("records")}
    out: dict = {}
    for r in st.itertuples():
        rule = rules[r.market]
        due = pd.Timestamp(r.settle_due_date).date()
        days = FA.fail_days_list(due, max(int(r.fail_days), 1), r.market)
        comps = FA.cost_fail(r.market, float(r.shortfall_value), int(r.fail_days), rule, 0.0)
        recharged = float(r.recharged_to_client) > 0
        items = [(days[min(i, len(days) - 1)], a) for i, _, a in comps]
        if r.buy_in_cost:
            items.append((days[-1], float(r.buy_in_cost)))
        for d, a in items:
            p = d.strftime("%Y-%m")
            if recharged or p not in fx_period_for:
                continue
            out[p] = out.get(p, 0.0) + a * fxl[(r.currency, fx_period_for[p])]
    return out


def verify(raw: Path, p0: str = "2026-08", p1: str = "2026-09") -> dict:
    raw = Path(raw)
    fxl = _fx(raw)
    fx0 = {c: fxl[(c, p0)] for c in R.CURRENCIES}
    lines = RC.variable_lines()
    e = {}
    for p in (p0, p1):
        t = _trades(raw, p)
        e[p] = EN.expected_cost(RZ.engine_rows(t, {c: fxl[(c, p)] for c in R.CURRENCIES}), lines, per_trade=True)
    s = BR.slice_effects(e[p0][e[p0].in_net_borne], e[p1][e[p1].in_net_borne], fx0)
    drv = BR.summarize_driver_effects(s)

    gl = pd.concat([pd.read_csv(raw / "gl" / f"gl_journal_lines_{p.replace('-', '')}.csv", dtype={"gl_account": str, "cost_centre": str})
                    for p in (p0, p1)], ignore_index=True)
    acc = pd.read_csv(raw / "ref" / "map_gl_cost_type.csv", dtype={"gl_account": str})
    nb = set(acc[acc.in_net_borne].gl_account)
    mapped = set(pd.read_csv(raw / "ref" / "map_vendor_counterparty.csv").ap_vendor_id)
    gl = gl[gl.gl_account.isin(nb)].copy()
    gl["slice"] = np.where(gl.gl_account.isin(["640200", "640300"]) & gl.cost_centre.isin(["4201", "4202"]), "ED", "REST")
    gl["cc_usd"] = gl.amount_lcy * gl.currency.map(fx0)
    gl["mapped"] = gl.vendor_id.isin(mapped)

    F = _fail_costs(raw, fxl, {p0: p0, p1: p0})
    fixed = RC.fixed_fees_by_month([p0, p1])
    fixed["usd0"] = fixed.amount_lcy * fixed.currency.map(fx0)

    rep = {"cells": {}, "totals": {}, "passed": True}
    for sl in ("ED", "REST"):
        g0 = gl[(gl.fiscal_period == p0) & (gl.slice == sl)]
        g1 = gl[(gl.fiscal_period == p1) & (gl.slice == sl)]
        GL0, GL1, GL1cc = g0.amount_usd.sum(), g1.amount_usd.sum(), g1.cc_usd.sum()
        e0 = e[p0][e[p0].in_net_borne & (BR.is_ed_exch_clearing(e[p0]) == (sl == "ED"))]
        e1 = e[p1][e[p1].in_net_borne & (BR.is_ed_exch_clearing(e[p1]) == (sl == "ED"))]
        E0 = float((e0.cost_lcy * e0.cost_currency.map(fx0)).sum())
        E1 = float((e1.cost_lcy * e1.cost_currency.map(fx0)).sum())
        F0, F1 = (F.get(p0, 0.0), F.get(p1, 0.0)) if sl == "REST" else (0.0, 0.0)
        X0 = fixed[fixed.period == p0].usd0.sum() if sl == "REST" else 0.0
        X1 = fixed[fixed.period == p1].usd0.sum() if sl == "REST" else 0.0
        U0, U1 = g0[~g0.mapped].cc_usd.sum(), g1[~g1.mapped].cc_usd.sum()
        timing = (GL1cc - E1 - F1 - X1 - U1) - (GL0 - E0 - F0 - X0 - U0)
        fx_eff = GL1 - GL1cc
        cells = {"volume": drv[sl]["volume_usd"], "mix": drv[sl]["mix_usd"], "rate": drv[sl]["rate_usd"],
                 "fails": F1 - F0, "fixed": X1 - X0, "timing": timing, "fx": fx_eff}
        cells["unexplained"] = (GL1 - GL0) - sum(cells.values())
        rep["cells"][sl] = cells
        rep["totals"][sl] = {"p0": GL0, "p1": GL1, "flux": GL1 - GL0}
        for k in EFFECTS:
            tgt = D.TARGETS[sl][k]
            ok = abs(cells[k] - tgt) <= TOL_USD and round(cells[k] / 1000) == round(tgt / 1000)
            rep["passed"] &= ok
        for p, tgt in D.TARGETS["gl"][sl].items():
            got = GL0 if p == p0 else GL1
            rep["passed"] &= abs(got - tgt) <= TOL_USD
    # Broker C: August invoice vs expected brokerage
    inv = pd.concat([pd.read_csv(f) for f in sorted((raw / "ap").glob("ap_invoice_lines_*.csv"))], ignore_index=True)
    bc_ap = set(R.AP_VENDORS[R.AP_VENDORS.vendor_id.eq("B03")].ap_vendor_id)
    bi = inv[inv.vendor_id.isin(bc_ap) & inv.service_period.eq(p0) & inv.cost_type.eq("BROKERAGE")]
    invoiced = float((bi.net_amount * bi.currency.map(fx0)).sum())
    be = e[p0][e[p0].billing_vendor_id.eq("B03") & e[p0].cost_type.eq("BROKERAGE")]
    expected = float((be.cost_lcy * be.cost_currency.map(fx0)).sum())
    rep["broker_c"] = {"expected_usd": expected, "invoiced_usd": invoiced, "overbilled_usd": invoiced - expected}
    rep["passed"] &= abs(invoiced - expected - D.TARGETS["broker_c_overbilling_usd"]) <= 500.0
    apac = {k: rep["cells"]["ED"][k] + rep["cells"]["REST"][k] for k in EFFECTS}
    rep["cells"]["APAC"] = apac
    rep["totals"]["APAC"] = {k: rep["totals"]["ED"][k] + rep["totals"]["REST"][k] for k in ("p0", "p1", "flux")}
    flux = rep["totals"]["APAC"]["flux"]
    rep["shares"] = {"good_volume": apac["volume"] / flux, "controllable_mix_fails": (apac["mix"] + apac["fails"]) / flux,
                     "external_timing_residual": (apac["rate"] + apac["timing"] + apac["fx"] + apac["unexplained"]) / flux}
    return rep


def print_report(rep: dict):
    print("\nTIE-OUT  September 2026 vs August 2026 (US$K; volume / mix / rate at constant currency)")
    hdr = f"{'slice':<6}{'P0':>9}{'P1':>9}" + "".join(f"{k:>12}" for k in EFFECTS) + f"{'flux':>10}"
    print(hdr)
    for sl in ("ED", "REST", "APAC"):
        c, t = rep["cells"][sl], rep["totals"][sl]
        print(f"{sl:<6}{t['p0'] / 1e3:9.1f}{t['p1'] / 1e3:9.1f}" + "".join(f"{c[k] / 1e3:12.3f}" for k in EFFECTS)
              + f"{t['flux'] / 1e3:10.1f}")
    s = rep["shares"]
    print(f"good (volume) {s['good_volume']:.1%} · controllable (mix + fails) {s['controllable_mix_fails']:.1%} · "
          f"external / timing / residual {s['external_timing_residual']:.1%}")
    b = rep["broker_c"]
    print(f"Broker C August: expected {b['expected_usd'] / 1e3:,.1f}K, invoiced {b['invoiced_usd'] / 1e3:,.1f}K, "
          f"over-billed {b['overbilled_usd'] / 1e3:,.2f}K")
    print("RESULT:", "PASS" if rep["passed"] else "FAIL")
