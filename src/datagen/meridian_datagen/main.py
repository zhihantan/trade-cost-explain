"""Generate the Meridian Group synthetic dataset and land it as source-system extracts.

    python -m meridian_datagen.main --out /Volumes/cost_explain/landing/raw      (Databricks job)
    python -m meridian_datagen.main --out ../../.local_out/raw                   (local)

Layout (one folder per source feed, picked up by Auto Loader):
    trades/        OMS/EMS executions, Parquet, one file per trade date
    settlements/   settlement status and fails, Parquet, one file per settlement due date
    gl/            ERP GL journal lines, CSV, one file per fiscal period
    ap/            AP invoice headers and lines, CSV, one file per received month
    fx/            FX rates (monthly average + daily spot), JSON lines
    market/        volatility index and index levels, JSON lines
    revenue/       desk revenue, CSV;  plan/  FY2026/27 budget, CSV
    ref/           masters and mappings, CSV (fee schedules come from the rate-card PDFs, not from here)
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import design as D
from . import engine as EN
from . import fails as FA
from . import invoices as INV
from . import ledger as LG
from . import market as MK
from . import ratecards as RC
from . import realize as RZ
from . import refdata as R

GL_AGG_DIMS = ["period", "desk", "capacity", "legal_entity", "execution_type", "billing_vendor_id", "cost_type",
               "is_recoverable", "is_affiliate", "in_net_borne", "cost_currency", "product_family", "fee_id", "book"]
TRADE_COLS = ["trade_id", "trade_date", "exec_time_local", "book", "desk_code", "legal_entity", "product_family",
              "instrument_id", "product", "venue", "market", "execution_type", "exec_broker", "clearing_broker", "ccp",
              "settle_vendor", "settlement_location", "capacity", "side", "qty", "price", "contracts", "notional",
              "currency", "counterparty_id", "is_affiliate", "give_up_flag"]


def log(msg: str, t0: float):
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


def generate(seed: int = 2026) -> dict:
    t0 = time.time()
    d = D.Designer(seed)
    P = d.solve()
    plan = d.plan()
    log(f"plan solved: {len(plan):,} sub-flow-month-side rows", t0)
    trades = RZ.realize(plan)
    log(f"realized {len(trades):,} executions", t0)

    fb = FA.FailBook(trades, MK.fx_lookup(d.fx))
    fb.background()
    fb.plant(D.TARGETS["fails_usd"]["2026-08"], D.TARGETS["fails_usd"]["2026-09_cc"])
    trades = fb.t                                      # counterparties re-pointed for the Kestrel cluster
    settlements, fail_daily = fb.settlements(), fb.daily_costs()
    log(f"settlements {len(settlements):,}, fails {settlements.settle_status.ne('SETTLED').sum():,}", t0)

    fxl = MK.fx_lookup(d.fx)
    lines = RC.variable_lines()
    gl_aggs, inv_aggs = [], []
    for m in R.MONTHS:
        t = trades[trades.period == m]
        fxm = {c: fxl[(c, m)] for c in R.CURRENCIES}
        e = EN.expected_cost(RZ.engine_rows(t, fxm), lines, per_trade=True)
        gl_aggs.append(e.groupby(GL_AGG_DIMS, as_index=False).cost_lcy.sum())
        inv_aggs.append(INV.invoice_aggregate(e))
    e_gl = pd.concat(gl_aggs, ignore_index=True)
    log("expected cost computed for every execution", t0)

    fixed = RC.fixed_fees_by_month(R.MONTHS)
    hdr, inv_lines = INV.build(pd.concat(inv_aggs, ignore_index=True), fail_daily, fixed, R.AS_OF_DATE)
    led = LG.Ledger(P, d.fx)
    led.variable(D.gl_keys(e_gl), INV.received_dates(hdr))
    led.fixed(fixed)
    led.fails(fail_daily)
    led.unmapped()
    fx_solution = led.solve_fx(D.TARGETS)
    gl = led.with_usd()
    fx_m = led.fx
    log(f"GL {len(gl):,} lines; FX solve AUD {fx_solution['AUD']:+.3%} KRW {fx_solution['KRW']:+.3%}", t0)

    # Broker C must stay in tier 2 in September at the final FX
    fxs = MK.fx_lookup(fx_m)
    sep_c = trades[(trades.period == "2026-09") & (trades.exec_broker == "B03")]
    sep_c_usd = float((sep_c.notional * sep_c.currency.map({c: fxs[(c, "2026-09")] for c in R.CURRENCIES})).sum())
    aug_c = trades[(trades.period == "2026-08") & (trades.exec_broker == "B03")]
    aug_c_usd = float((aug_c.notional * aug_c.currency.map({c: fxs[(c, "2026-08")] for c in R.CURRENCIES})).sum())
    assert 1.2e9 <= sep_c_usd < 2.5e9 and 1.2e9 <= aug_c_usd < 2.5e9, (aug_c_usd, sep_c_usd)

    P.update(fx_solution=fx_solution, broker_c_turnover_usd={"2026-08": aug_c_usd, "2026-09": sep_c_usd})
    return {"params": P, "trades": trades, "settlements": settlements, "fail_daily": fail_daily, "gl": gl,
            "ap_headers": hdr, "ap_lines": inv_lines, "fx_monthly": fx_m, "fixed": fixed}


def _csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write(out: Path, data: dict, seed: int):
    t0 = time.time()
    # Replace the generator's own feeds; leave ref/ files owned by the extraction job (fail_cost_rule, vendor_contracts).
    for feed in ("trades", "settlements", "gl", "ap", "fx", "market", "revenue", "plan"):
        if (out / feed).exists():
            shutil.rmtree(out / feed)
    out.mkdir(parents=True, exist_ok=True)
    tr = data["trades"]
    (out / "trades").mkdir(parents=True, exist_ok=True)
    for d_, g in tr.groupby("trade_date"):
        g = g[TRADE_COLS].assign(source_system="OMS-EMS")
        g.to_parquet(out / "trades" / f"trades_{d_:%Y%m%d}.parquet", index=False)
    st = data["settlements"]
    (out / "settlements").mkdir(parents=True, exist_ok=True)
    for d_, g in st.groupby("settle_due_date"):
        g.assign(source_system="SETTLEMENTS").to_parquet(out / "settlements" / f"settlements_{d_:%Y%m%d}.parquet", index=False)
    gl = data["gl"]
    for p, g in gl.groupby("fiscal_period"):
        _csv(g, out / "gl" / f"gl_journal_lines_{p.replace('-', '')}.csv")
    hdr, lines = data["ap_headers"], data["ap_lines"]
    hdr = hdr.assign(received_month=pd.to_datetime(hdr.invoice_received_date).dt.strftime("%Y%m"))
    lines = lines.merge(hdr[["invoice_id", "received_month"]], on="invoice_id")
    lines = lines.rename(columns={"week_start": "service_week_start"})
    keep = ["invoice_id", "line_no", "ap_vendor_id", "legal_entity", "service_period", "service_week_start",
            "invoice_received_date", "cost_type", "fee_id", "product_family", "qty", "unit_rate", "net_amount", "tax_amount",
            "tax_recoverable", "currency", "line_type", "description"]
    for mth, g in hdr.groupby("received_month"):
        _csv(g.drop(columns=["received_month", "billing_vendor_id"]).rename(columns={"ap_vendor_id": "vendor_id"}),
             out / "ap" / f"ap_invoice_headers_{mth}.csv")
    for mth, g in lines.groupby("received_month"):
        _csv(g[keep].rename(columns={"ap_vendor_id": "vendor_id"}), out / "ap" / f"ap_invoice_lines_{mth}.csv")
    fxm = data["fx_monthly"].assign(rate_type="MONTHLY_AVERAGE")
    fxd = MK.daily_fx(fxm)
    (out / "fx").mkdir(parents=True, exist_ok=True)
    for p in R.MONTHS:
        recs = [{"currency": r.currency, "period": p, "rate_date": f"{p}-01", "rate_type": "MONTHLY_AVERAGE",
                 "rate_to_usd": r.rate_to_usd, "source": "Group Treasury"} for r in fxm[fxm.period == p].itertuples()]
        dd = fxd[pd.to_datetime(fxd.rate_date).dt.strftime("%Y-%m") == p]
        recs += [{"currency": r.currency, "period": p, "rate_date": str(r.rate_date), "rate_type": r.rate_type,
                  "rate_to_usd": r.rate_to_usd, "source": "Market data vendor"} for r in dd.itertuples()]
        with open(out / "fx" / f"fx_rates_{p.replace('-', '')}.json", "w") as f:
            f.write("\n".join(json.dumps(x) for x in recs))
    vi = MK.vol_index()
    (out / "market").mkdir(parents=True, exist_ok=True)
    for p, g in vi.groupby(pd.to_datetime(vi.trade_date).dt.strftime("%Y%m")):
        with open(out / "market" / f"market_data_{p}.json", "w") as f:
            f.write("\n".join(json.dumps({**r, "trade_date": str(r["trade_date"])}) for r in g.to_dict("records")))
    rev = MK.revenue_daily()
    for p, g in rev.groupby("period"):
        _csv(g, out / "revenue" / f"desk_revenue_{p.replace('-', '')}.csv")
    gl_aug = gl[(gl.fiscal_period == "2026-08") & gl.gl_account.isin(LG.NET_BORNE_ACCOUNTS)]
    cc_desk = dict(zip(R.COST_CENTRES.cost_centre, R.COST_CENTRES.desk_code))
    cost_aug = gl_aug.assign(desk=gl_aug.cost_centre.map(cc_desk)).groupby("desk").amount_usd.sum().to_dict()
    _csv(MK.plan_monthly(cost_aug), out / "plan" / "fy2026_27_trade_cost_plan.csv")
    ref = out / "ref"
    _csv(R.LEGAL_ENTITIES, ref / "legal_entities.csv")
    books = pd.DataFrame([{"book": b, "desk_code": dk} for dk, bs in R.BOOKS.items() for b in bs])
    hier = books.merge(R.DESKS, on="desk_code").assign(valid_from="2025-01-01", valid_to=None, is_current=True)
    d1 = hier[hier.desk_code.eq("D1PR")]
    hier = pd.concat([hier[~hier.desk_code.eq("D1PR")],
                      d1.assign(business_code="CEQ", business="Cash Equities", valid_from="2025-01-01", valid_to="2026-03-31", is_current=False),
                      d1.assign(valid_from="2026-04-01")], ignore_index=True)
    _csv(hier, ref / "dim_desk_hierarchy.csv")
    _csv(R.COST_CENTRES, ref / "map_costcentre_desk.csv")
    _csv(pd.DataFrame([{"fee_id": k, "cost_centre": v, "allocation_basis": "host desk (primary user of the membership / line)"}
                       for k, v in LG.FIXED_COST_CENTRE.items()]), ref / "map_fixed_fee_costcentre.csv")
    _csv(R.VENDORS, ref / "vendors.csv")
    _csv(R.AP_VENDORS, ref / "ap_vendors.csv")
    _csv(R.map_vendor_counterparty(), ref / "map_vendor_counterparty.csv")
    _csv(R.COUNTERPARTIES, ref / "counterparties.csv")
    _csv(R.GL_ACCOUNTS, ref / "map_gl_cost_type.csv")
    _csv(R.fiscal_calendar(), ref / "dim_fiscal_calendar.csv")
    cal = []
    for mk in ["HK", "CN", "SG", "AU", "IN", "KR", "TW", "MY"]:
        for d_ in pd.date_range("2025-08-01", "2026-12-31").date:
            hol = set(R.HOLIDAYS["ALL"]) | set(R.HOLIDAYS.get(mk, []))
            cal.append({"market": mk, "calendar_date": d_, "is_business_day": d_.weekday() < 5 and d_.isoformat() not in hol})
    _csv(pd.DataFrame(cal), ref / "business_calendar.csv")
    ins = pd.DataFrame([{"product_family": pf, "instrument_id": i, "instrument_name": n, "reference_price": px,
                         "contract_multiplier": R.CONTRACT_MULTIPLIER.get(pf)} for pf, lst in R.INSTRUMENTS.items() for i, n, px in lst])
    _csv(ins, ref / "instruments.csv")
    P = data["params"]
    manifest = {
        "generated_by": "meridian_datagen", "seed": seed, "as_of_date": str(R.AS_OF_DATE), "months": R.MONTHS,
        "row_counts": {"trades": int(len(tr)), "settlements": int(len(st)), "fails": int(st.settle_status.ne("SETTLED").sum()),
                       "gl_lines": int(len(gl)), "ap_invoices": int(len(data["ap_headers"])), "ap_invoice_lines": int(len(data["ap_lines"]))},
        "targets": D.TARGETS,
        "design": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in P.items()
                   if k in ("gamma_ed", "sigma_ed", "sigma_rest", "k_growth", "mm_shift_contracts", "au_shift_aud",
                            "tech_sep_nonmm", "igx_sep_turnover_inr", "igx_aug_turnover_inr", "tc_aug_usd",
                            "broker_c_turnover_usd", "fixed_aug_usd")},
        "fx_solution": {k: v for k, v in P["fx_solution"].items() if k in ("AUD", "KRW")},
    }
    with open(out / "_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    log(f"landed files under {out}", t0)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--skip-verify", action="store_true")
    a = ap.parse_args()
    data = generate(a.seed)
    out = Path(a.out)
    manifest = write(out, data, a.seed)
    print(json.dumps(manifest["row_counts"], indent=2))
    if not a.skip_verify:
        from . import verify
        report = verify.verify(out)
        verify.print_report(report)
        if not report["passed"]:
            raise SystemExit("tie-out FAILED — files landed but do not reproduce the planted targets")


if __name__ == "__main__":
    main()
