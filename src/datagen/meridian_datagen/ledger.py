"""General ledger journals (ERP extract) and the September FX solve.

Per mapped variable-cost GL key (account × cost centre × AP vendor × entity × currency) and month P:
  ACCRUAL   E(P) + ae(P)            month-end accrual (until August: run-rate estimate with error ae; from
                                    September the accrual is re-based to expected cost, so ae(Sep) = 0)
  REVERSAL  −(E(P−1) + ae(P−1))     auto-reversal of last month's accrual on day 1
  TRUE-UP   +E(P−1)                 last month's actual (invoice, or expected cost if the invoice is disputed / pending)
Net = E(P) + ae(P) − ae(P−1)  →  timing effect = Δ(ae(P) − ae(P−1)).
Fails accrue daily from fail ageing (net of recharges); fixed fees post when billed; recharged statutory levies post
gross and recovered; intra-group MES charges post to an eliminated account; two new AP vendors are not yet mapped.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import design as D
from . import market as MK
from . import refdata as R

NET_BORNE_ACCOUNTS = {"640100", "640200", "640300", "640400", "640500", "640600", "640650", "640700", "640800"}
VARIABLE_ACCOUNTS = {"640100", "640200", "640300", "640400", "640600", "640650", "640800"}
FIXED_COST_CENTRE = {"PRX-SEC-FIX": "4101", "PRC-SEC-FIX": "4101", "PRX-DV-FIX": "4201", "CNX-FIX": "4102", "MRX-FIX": "4201",
                     "MRC-FIX": "4201", "SXA-FIX": "4401", "SXA-FIX-27": "4401", "SXC-FIX": "4401", "TAM-FIX": "4401",
                     "IGX-FIX": "4501", "ICC-FIX": "4501", "DCX-FIX": "4501", "HRX-FIX": "4301", "FMX-FIX": "4302",
                     "STX-FIX": "5402", "PDL-FIX": "4101", "STC-FIX": "5201"}
UNMAPPED = [  # ap vendor, entity, account, cost centre, description, {period: USD}
    ("AP-440301", "MSAU", "640700", "4401", "Lotus Market Services — market data and order-routing services",
     {"2026-07": 1_200.0, "2026-08": 3_000.0, "2026-09": 9_000.0}),
    ("AP-540302", "MSIN", "640400", "4501", "Harbour Settlement Agents — local settlement agency fees",
     {"2026-07": 800.0, "2026-08": 2_000.0, "2026-09": 6_000.0}),
]


def month_end(period: str) -> dt.date:
    y, m = map(int, period.split("-"))
    return (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))


def next_period(period: str) -> str:
    y, m = map(int, period.split("-"))
    return f"{y + (m == 12):04d}-{m % 12 + 1:02d}"


def prev_period(period: str) -> str:
    y, m = map(int, period.split("-"))
    return f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"


def close_date(period: str) -> dt.date:
    """Working day 2 after month end (the accrual posting date)."""
    return R.add_business_days(month_end(period), 2, "HK")


def slice_of(account: pd.Series, cost_centre: pd.Series) -> np.ndarray:
    return np.where(account.isin(["640200", "640300"]) & cost_centre.isin(["4201", "4202"]), "ED", "REST")


class Ledger:
    def __init__(self, params: dict, fx_monthly: pd.DataFrame, seed: int = 808):
        self.P = params
        self.fx = fx_monthly.copy()
        self.rng = np.random.default_rng(seed)
        self.lines: list[dict] = []
        self.jseq = 0

    def _je(self, period: str, jtype: str) -> str:
        self.jseq += 1
        return f"JE{period.replace('-', '')}-{jtype[:3]}-{self.jseq:06d}"

    def _post(self, jid, period, posting_date, key, amount, is_accrual, jtype, desc, service_period, line_no=1):
        acct, cc, ap, le, ccy = key
        self.lines.append({"journal_id": jid, "journal_line": line_no, "posting_date": posting_date, "fiscal_period": period,
                           "gl_account": acct, "cost_centre": cc, "vendor_id": ap, "legal_entity": le, "currency": ccy,
                           "amount_lcy": round(float(amount), 2), "is_accrual": bool(is_accrual), "journal_type": jtype,
                           "description": desc, "service_period": service_period, "source_system": "ERP-GL"})

    # ── variable costs ─────────────────────────────────────────────────────────────────────────────
    def variable(self, e_keys: pd.DataFrame, invoice_dates: dict):
        """e_keys: GL-keyed expected cost (gl_keys output aggregated) with columns period, GL_KEY, product_family, cost_lcy."""
        part_cols = [c for c in ("book", "product_family", "fee_id") if c in e_keys.columns]
        agg = e_keys.groupby(["period"] + D.GL_KEY + part_cols, as_index=False).cost_lcy.sum()
        tot = agg.groupby(["period"] + D.GL_KEY, as_index=False).cost_lcy.sum()
        ae_design = self.P["accrual_errors_usd"]
        fx_aug = {c: v for (c, p), v in MK.fx_lookup(self.fx).items() if p == "2026-08"}
        months = R.MONTHS
        E = {(r.period, (r.gl_account, r.cost_centre, r.ap_vendor_id, r.legal_entity, r.currency)): r.cost_lcy
             for r in tot.itertuples()}
        keys = sorted({k for _, k in E})
        ae = {}
        for k in keys:
            if k[0] not in VARIABLE_ACCOUNTS:
                continue
            for p in months:
                e = E.get((p, k), 0.0)
                if p == "2026-09":
                    a = 0.0
                elif p in ("2026-07", "2026-08"):
                    a = ae_design.get(k, {}).get(p, 0.0) / fx_aug[k[4]]
                else:
                    a = e * (self.rng.normal(0, 0.016) + (self.rng.choice([-1, 1]) * 0.05 if self.rng.random() < 0.05 else 0.0))
                ae[(p, k)] = a
        self.ae = ae
        # itemised accrual lines: one per product family × fee code
        parts: dict = {}
        for r in agg.itertuples():
            k = (r.gl_account, r.cost_centre, r.ap_vendor_id, r.legal_entity, r.currency)
            label = " / ".join(str(getattr(r, c)) for c in part_cols)
            parts.setdefault((r.period, k), []).append((label, r.cost_lcy))

        def accrual_lines(p, k, e, a):
            pl = parts.get((p, k)) or [("ALL", e)]
            return [(lab, c + a * (c / e if e else 1.0 / len(pl))) for lab, c in pl]

        for k in keys:
            acct = k[0]
            for i, p in enumerate(months):
                e = E.get((p, k), 0.0)
                if acct in ("640610",):          # recharged statutory levies / taxes: gross and recovery
                    if e:
                        jid = self._je(p, "RCH")
                        self._post(jid, p, close_date(p), k, e, False, "RECHARGE_GROSS", f"Statutory levies and taxes charged {p}", p, 1)
                        self._post(jid, p, close_date(p), ("640619",) + k[1:], -e, False, "RECHARGE_RECOVERY",
                                   f"Recovered from clients on contract notes {p}", p, 2)
                    continue
                if acct == "640110":             # intra-group (eliminated)
                    if e:
                        self._post(self._je(p, "ICO"), p, close_date(p), k, e, False, "INTRAGROUP",
                                   f"Intra-group agency execution charges {p} (eliminated on consolidation)", p)
                    continue
                a = ae.get((p, k), 0.0)
                if e or a:
                    jid = self._je(p, "ACR")
                    for j, (lab, amt) in enumerate(accrual_lines(p, k, e, a), start=1):
                        self._post(jid, p, close_date(p), k, amt, True, "ACCRUAL", f"Month-end accrual {p} — {lab}", p, j)
                pp = prev_period(p)
                if i > 0:
                    e_prev, a_prev = E.get((pp, k), 0.0), ae.get((pp, k), 0.0)
                    prev_lines = accrual_lines(pp, k, e_prev, a_prev) if (e_prev or a_prev) else []
                    prev_parts = parts.get((pp, k)) or ([("ALL", e_prev)] if e_prev else [])
                else:                            # opening month: reverse / true-up an estimated prior accrual
                    prev_lines = [(lab, c * 0.97) for lab, c in (parts.get((p, k)) or [])]
                    prev_parts = prev_lines
                if prev_lines:
                    jid = self._je(p, "REV")
                    for j, (lab, amt) in enumerate(prev_lines, start=1):
                        self._post(jid, p, dt.date.fromisoformat(p + "-01"), k, -amt, True, "ACCRUAL_REVERSAL",
                                   f"Reverse {pp} accrual — {lab}", pp, j)
                if prev_parts:
                    inv_date, inv_status = invoice_dates.get((pp, k[2]), (None, None))
                    if inv_date and inv_status and inv_status.startswith("ON_HOLD"):
                        desc, post = f"{pp} actual at expected cost — invoice on hold, variance under review", inv_date
                    elif inv_date and inv_date.strftime("%Y-%m") == p:
                        desc, post = f"{pp} actual per invoice", inv_date
                    else:
                        desc, post = f"{pp} actual at expected cost (invoice pending or disputed)", close_date(p)
                    jid = self._je(p, "TRU")
                    for j, (lab, amt) in enumerate(prev_parts, start=1):
                        self._post(jid, p, post, k, amt, False, "TRUE_UP", f"{desc} — {lab}", pp, j)

    def fixed(self, fixed_by_month: pd.DataFrame):
        for r in fixed_by_month.itertuples():
            k = ("640700", FIXED_COST_CENTRE[r.fee_id], R.ap_vendor_for(r.vendor_id, r.legal_entity), r.legal_entity, r.currency)
            self._post(self._je(r.period, "FIX"), r.period, dt.date.fromisoformat(r.period + "-05"), k, r.amount_lcy, False,
                       "INVOICE", r.description, r.period)

    def fails(self, fail_daily: pd.DataFrame):
        if fail_daily.empty:
            return
        f = fail_daily.assign(net=fail_daily.amount_lcy - fail_daily.recharged_lcy)
        f["cost_centre"] = [R.cost_centre_for(d, c, le, "DIRECT", p) for d, c, le, p in
                            zip(f.desk_code, f.capacity, f.legal_entity, f.period)]
        f["ap"] = [R.ap_vendor_for(v, le) for v, le in zip(f.rule_vendor_id, f.legal_entity)]
        g = f.groupby(["period", "cost_centre", "ap", "legal_entity", "currency"], as_index=False).net.sum()
        F = {(r.period, ("640500", r.cost_centre, r.ap, r.legal_entity, r.currency)): r.net for r in g.itertuples()}
        keys = sorted({k for _, k in F})
        for k in keys:
            for i, p in enumerate(R.MONTHS):
                v = F.get((p, k), 0.0)
                if v:
                    self._post(self._je(p, "FLA"), p, close_date(p), k, v, True, "ACCRUAL",
                               f"Settlement fail costs accrued from fail ageing {p}", p)
                pp = prev_period(p)
                vp = F.get((pp, k), 0.0) if i > 0 else 0.0
                if vp:
                    self._post(self._je(p, "FLR"), p, dt.date.fromisoformat(p + "-01"), k, -vp, True, "ACCRUAL_REVERSAL",
                               f"Reverse {pp} fail accrual", pp)
                    self._post(self._je(p, "FLT"), p, close_date(p), k, vp, False, "TRUE_UP", f"{pp} fail fees per CCP invoice", pp)

    def unmapped(self):
        for ap, le, acct, cc, desc, amounts in UNMAPPED:
            for p, usd in amounts.items():
                self._post(self._je(p, "INV"), p, dt.date.fromisoformat(p + "-20"), (acct, cc, ap, le, "USD"), usd, False,
                           "INVOICE", desc, p)

    # ── FX solve ───────────────────────────────────────────────────────────────────────────────────
    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.lines)

    def solve_fx(self, targets: dict) -> dict:
        """Choose September AUD and KRW moves so the ED and REST FX effects land exactly on target."""
        g = self.frame()
        g = g[g.fiscal_period.eq("2026-09") & g.gl_account.isin(NET_BORNE_ACCOUNTS)]
        g = g.assign(slice=slice_of(g.gl_account, g.cost_centre))
        L = g.groupby(["slice", "currency"]).amount_lcy.sum()
        fxl = MK.fx_lookup(self.fx)
        fx0 = {c: fxl[(c, "2026-08")] for c in R.CURRENCIES}
        move = {c: fxl[(c, "2026-09")] / fx0[c] - 1 for c in R.CURRENCIES}

        def fx_effect(sl, mv):
            return sum(L.get((sl, c), 0.0) * fx0[c] * mv[c] for c in R.CURRENCIES)
        base = {sl: fx_effect(sl, {**move, "AUD": 0.0, "KRW": 0.0}) for sl in ("ED", "REST")}
        A = np.array([[L.get((sl, c), 0.0) * fx0[c] for c in ("AUD", "KRW")] for sl in ("ED", "REST")])
        b = np.array([targets["ED"]["fx"] - base["ED"], targets["REST"]["fx"] - base["REST"]])
        m_aud, m_krw = np.linalg.solve(A, b)
        for c, mv in (("AUD", m_aud), ("KRW", m_krw)):
            self.fx.loc[(self.fx.currency == c) & (self.fx.period == "2026-09"), "rate_to_usd"] = fx0[c] * (1 + mv)
        return {"AUD": float(m_aud), "KRW": float(m_krw), "exposure_usd": {f"{a}|{c}": float(v * fx0[c]) for (a, c), v in L.items()}}

    def with_usd(self) -> pd.DataFrame:
        g = self.frame()
        fxl = MK.fx_lookup(self.fx)
        g["amount_usd"] = [round(a * fxl[(c, p)], 2) for a, c, p in zip(g.amount_lcy, g.currency, g.fiscal_period)]
        return g
