"""Calibrated monthly plan: trade count and volume per sub-flow × month × side.

August and September 2026 are *solved* so that the Gold bridge reproduces the planted-story targets (spec §6);
other months carry seasonality, the 1-Jul annual reset and the Tech promotion (from 1-Mar-2026). Solve order
(each step is linear given the previous ones):

  1. accrual-error draws for Jul / Aug → planted accrual over-estimates absorb the timing targets
  2. γ_ED   = 1 + 390K / E_ED(Aug)                         ED volume effect
  3. Tech   non-MM Sep contracts = 60K / (HK$2.50 × fx)    ED rate effect (discount ended 31-Aug)
  4. σ_ED   scales the remaining ED flows                  E_ED(Aug) = GL_ED(Aug) − timing component
  5. S_MM   PRX 50 contracts moved MM → house in Sep       ED mix effect
  6. pins   Cobalt (Broker C) Aug turnover US$1.70bn, IGX Sep turnover from the 40K rate effect, AU base
  7. σ_R    scales the remaining REST flows                E_R(Aug) = GL_R(Aug) − fails − fixed − timing − unmapped
  8. k      scales the free September growth rates        REST volume effect
  9. S_AU   A$ moved TAM → SXA in Sep                     REST mix effect
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import bridge as BR
from . import engine as EN
from . import flows as FL
from . import market as MK
from . import ratecards as RC
from . import refdata as R

TARGETS = {
    "gl": {"ED": {"2026-08": 2_170_000.0, "2026-09": 2_680_000.0}, "REST": {"2026-08": 2_830_000.0, "2026-09": 3_520_000.0}},
    "ED": {"volume": 390_000.0, "mix": 90_000.0, "rate": 60_000.0, "fails": 0.0, "fixed": 0.0, "timing": -20_000.0,
           "fx": -10_000.0, "unexplained": 0.0},
    "REST": {"volume": 510_000.0, "mix": 100_000.0, "rate": 40_000.0, "fails": 150_000.0, "fixed": 0.0, "timing": -30_000.0,
             "fx": -90_000.0, "unexplained": 10_000.0},
    "fails_usd": {"2026-08": 60_000.0, "2026-09_cc": 210_000.0},
    "unmapped_usd": {"2026-07": 2_000.0, "2026-08": 5_000.0, "2026-09": 15_000.0},
    "broker_c_overbilling_usd": 85_000.0,
}
P0, P1 = "2026-08", "2026-09"
TECH_DISCOUNT = 2.50                   # HK$ per contract-side that disappears on 1-Sep
IGX_RATE_STEP_BPS = 0.322 - 0.250      # slab 3 → uniform
AU_VENUE_SPREAD_BPS = 0.60 - 0.20      # SXA vs TAM trade fee
AU_GST_NONREC = 0.10 * (1 - 0.75)      # non-recoverable GST share carried on AU fees
MM_SAVING = 10.00 - 5.00               # PRX 50: house vs market-maker concession (HK$)
PLANTED_TIMING_KEY = {
    "ED": ("640200", "4201", "AP-210011", "MSHK", "HKD"),
    "REST": ("640200", "4401", "AP-410031", "MSAU", "AUD"),
}
TECH_PRE_DISCOUNT_FACTOR = 0.72        # Tech volumes before the promotion launched on 1-Mar-2026


# ── GL key derivation (shared with the ledger) ───────────────────────────────────────────────────────
def gl_keys(e: pd.DataFrame) -> pd.DataFrame:
    """Map net-borne / recoverable / intra-group engine lines to GL key columns."""
    acct = e.cost_type.map(R.COST_TYPE_ACCOUNT)
    acct = np.where(e.is_affiliate, "640110", acct)
    acct = np.where(e.is_recoverable & e.cost_type.isin(["LEVY", "TAX"]), "640610", acct)
    out = e.assign(gl_account=acct)
    out = out[~(e.cost_type.eq("GST_REC"))]          # recoverable GST sits on the balance sheet
    cc = [R.cost_centre_for(d, c, le, x, p) for d, c, le, x, p in
          zip(out.desk, out.capacity, out.legal_entity, out.execution_type, out.period)]
    ap = [R.ap_vendor_for(v, le) for v, le in zip(out.billing_vendor_id, out.legal_entity)]
    return out.assign(cost_centre=cc, ap_vendor_id=ap, currency=out.cost_currency)


GL_KEY = ["gl_account", "cost_centre", "ap_vendor_id", "legal_entity", "currency"]


class Designer:
    def __init__(self, seed: int = 2026):
        self.rng = np.random.default_rng(seed)
        self.sf = FL.subflows()
        self.lines = RC.variable_lines()
        self.fx = MK.monthly_fx()
        self.fxl = MK.fx_lookup(self.fx)
        self.params: dict = {}

    # ── helpers ──
    def fx_month(self, m: str) -> dict:
        return {c: self.fxl[(c, m)] for c in R.CURRENCIES}

    def month_rows(self, vol: np.ndarray, cnt: np.ndarray, period: str, buy_share: np.ndarray | None = None) -> pd.DataFrame:
        sf, fxm = self.sf, self.fx_month(period)
        rows = []
        for i, r in enumerate(sf.itertuples()):
            v, n = float(vol[i]), int(round(cnt[i]))
            if v <= 0 or n <= 0:
                continue
            bs = 0.5 if buy_share is None else float(buy_share[i])
            nb = int(round(n * bs)); ns = n - nb
            if r.unit == "CONTRACTS":
                v = max(int(round(v)), n)
                vb = int(round(v * nb / n)) if n else 0
                vb = min(max(vb, nb), v - ns); vs = v - vb
            else:
                v = round(v, 2)
                vb = round(v * nb / n, 2); vs = round(v - vb, 2)
            for side, vv, nn in (("BUY", vb, nb), ("SELL", vs, ns)):
                if nn <= 0:
                    continue
                if r.unit == "CONTRACTS":
                    level = R.INSTRUMENTS[r.product_family][0][2]
                    notional, contracts = float(vv) * R.CONTRACT_MULTIPLIER[r.product_family] * level, int(vv)
                else:
                    notional, contracts = float(vv), 0
                rows.append({
                    "row_id": f"{r.subflow_id}|{period}|{side}", "period": period, "subflow_id": r.subflow_id,
                    "flow_id": r.flow_id, "desk": r.desk, "product_family": r.product_family, "venue": r.venue,
                    "execution_type": r.execution_type, "exec_broker": r.exec_broker, "ccp": r.ccp,
                    "settle_vendor": r.settle_vendor, "legal_entity": r.legal_entity, "currency": r.currency,
                    "capacity": r.capacity, "side": side, "unit": r.unit, "contracts": contracts, "notional": notional,
                    "n_trades": nn, "n_instructions": nn if r.settles else 0,
                    "notional_usd": notional * fxm[r.currency], "band_min": r.band_min, "band_max": r.band_max,
                    "median_contracts": r.median_contracts, "settles": r.settles,
                })
        return pd.DataFrame(rows)

    def expected(self, plan_rows: pd.DataFrame) -> pd.DataFrame:
        return EN.expected_cost(plan_rows, self.lines, per_trade=False)

    @staticmethod
    def borne(e: pd.DataFrame) -> pd.DataFrame:
        return e[e.in_net_borne]

    def ed_mask(self, e: pd.DataFrame) -> pd.Series:
        return BR.is_ed_exch_clearing(e)

    def usd(self, e: pd.DataFrame, fx: dict) -> float:
        return float((e.cost_lcy * e.cost_currency.map(fx)).sum())

    # ── vectors per sub-flow ──
    def idx(self, cond) -> np.ndarray:
        return np.asarray(cond, dtype=bool)

    def solve(self):
        sf, P, fx0 = self.sf, self.params, self.fx_month(P0)
        shape_vol = sf.aug_volume.to_numpy(float)
        shape_cnt = sf.aug_trades.to_numpy(float)
        ed_grp = self.idx(sf.scale_group.eq("ED"))
        rest_grp = self.idx(sf.scale_group.eq("REST"))
        tech = self.idx(sf.pin.eq("TECH"))
        tech_nonmm = tech & self.idx(sf.capacity.ne("MM"))

        # 1. accrual errors (USD at Aug FX) on the August GL keys; planted keys absorb the timing targets
        probe = self.month_rows(np.where(shape_vol > 0, shape_vol, 1e9), shape_cnt, P0)
        keys = gl_keys(self.borne(self.expected(probe)))
        keys = keys.assign(slice=np.where(self.ed_mask(keys), "ED", "REST"))[GL_KEY + ["slice"]].drop_duplicates()
        ae = {}
        for k in keys.itertuples(index=False):
            key = tuple(k[:5])
            ae[key] = {"slice": k.slice, "2026-07": float(self.rng.normal(0, 450)), "2026-08": float(self.rng.normal(0, 450))}
        for sl, pk in PLANTED_TIMING_KEY.items():
            ae.setdefault(pk, {"slice": sl, "2026-07": 0.0, "2026-08": 0.0})
            others = [v for k2, v in ae.items() if v["slice"] == sl and k2 != pk]
            jul = sum(v["2026-07"] for v in ae.values() if v["slice"] == sl)
            aug_others = sum(v["2026-08"] for v in others)
            # timing = Σ(−2·ae_aug + ae_jul) = target  →  planted ae_aug
            ae[pk]["2026-08"] = (jul - 2 * aug_others - TARGETS[sl]["timing"]) / 2.0
        tc_aug = {sl: sum(v["2026-08"] - v["2026-07"] for v in ae.values() if v["slice"] == sl) for sl in ("ED", "REST")}
        P["accrual_errors_usd"] = ae
        P["tc_aug_usd"] = tc_aug

        # 2–3. ED growth and the Tech pin
        e_ed_target = TARGETS["gl"]["ED"][P0] - tc_aug["ED"]
        gamma_ed = 1.0 + TARGETS["ED"]["volume"] / e_ed_target
        tech_sep_nonmm = TARGETS["ED"]["rate"] / (TECH_DISCOUNT * fx0["HKD"])
        tech_aug_nonmm = tech_sep_nonmm / gamma_ed
        tech_scale = tech_aug_nonmm / shape_vol[tech_nonmm].sum()
        P.update(gamma_ed=gamma_ed, e_ed_aug_target=e_ed_target, tech_sep_nonmm=tech_sep_nonmm, tech_scale=tech_scale)

        # 6. pins (needed before the REST solve; independent of σ)
        pin_vol = np.zeros(len(sf))
        for i, r in enumerate(sf.itertuples()):
            if r.pin and r.pin.startswith("COBALT"):
                pin_vol[i] = FL.COBALT_AUG_USD[r.pin] / fx0[r.currency]
            elif r.pin == "AU":
                pin_vol[i] = r.aug_volume
            elif r.pin == "TECH":
                pin_vol[i] = r.aug_volume * tech_scale
        gamma_in = 1.0 + FL.SEP_GROWTH["IN_CASH"]
        igx_sep = TARGETS["REST"]["rate"] / (IGX_RATE_STEP_BPS / 1e4 * fx0["INR"])
        igx = self.idx(sf.pin.eq("IGX"))
        pin_vol[igx] = igx_sep / gamma_in * sf.share[igx]
        P.update(igx_sep_turnover_inr=igx_sep, igx_aug_turnover_inr=igx_sep / gamma_in)

        def aug_vol(s_ed, s_r):
            return np.where(ed_grp, shape_vol * s_ed, np.where(rest_grp, shape_vol * s_r, pin_vol))

        # 4. σ_ED (linear; two passes for integer contracts)
        def e_ed(s_ed):
            e = self.borne(self.expected(self.month_rows(aug_vol(s_ed, 1.0), shape_cnt, P0)))
            return self.usd(e[self.ed_mask(e)], fx0)
        s_ed = 1.0
        for _ in range(3):
            a, b = e_ed(s_ed), e_ed(s_ed * 1.01)
            s_ed = s_ed + (e_ed_target - a) * (0.01 * s_ed) / (b - a)
        P["sigma_ed"] = s_ed

        # 7. σ_R
        fixed_aug = RC.fixed_fees_by_month([P0])
        fixed_aug_usd = float((fixed_aug.amount_lcy * fixed_aug.currency.map(fx0)).sum())
        e_r_target = (TARGETS["gl"]["REST"][P0] - TARGETS["fails_usd"][P0] - fixed_aug_usd - tc_aug["REST"]
                      - TARGETS["unmapped_usd"][P0])

        def e_rest(s_r):
            e = self.borne(self.expected(self.month_rows(aug_vol(s_ed, s_r), shape_cnt, P0)))
            return self.usd(e[~self.ed_mask(e)], fx0)
        s_r = 0.7
        for _ in range(4):
            a, b = e_rest(s_r), e_rest(s_r * 1.01)
            s_r = s_r + (e_r_target - a) * (0.01 * s_r) / (b - a)
        P.update(sigma_rest=s_r, e_rest_aug_target=e_r_target, fixed_aug_usd=fixed_aug_usd)
        vol_aug = aug_vol(s_ed, s_r)
        self.vol_aug, self.cnt_aug = vol_aug, shape_cnt.copy()

        # 5, 8, 9. September: growth, MM shift, AU routing shift
        mm_shift = round(TARGETS["ED"]["mix"] / (MM_SAVING * fx0["HKD"]))
        au_shift = TARGETS["REST"]["mix"] / (AU_VENUE_SPREAD_BPS / 1e4 * (1 + AU_GST_NONREC) * fx0["AUD"])
        mm_from = self.idx(sf.subflow_id.eq("HKED-PRX50-DIR-MM"))
        mm_to = self.idx(sf.subflow_id.eq("HKED-PRX50-DIR-HOUSE"))
        tam = self.idx(sf.flow_id.eq("AUCE-TAM"))
        sxa = self.idx(sf.flow_id.eq("AUCE-SXA"))

        def sep_plan(k, s_mm, s_au):
            g = np.array([gamma_ed if key == "ED" else (1 + FL.SEP_GROWTH[key]) if key in FL.FIXED_GROWTH_KEYS
                          else 1 + k * FL.SEP_GROWTH[key] for key in sf.growth_key])
            vol = vol_aug * g                     # Tech non-MM: vol_aug × γ_ED sums to tech_sep_nonmm by construction
            cnt = np.round(shape_cnt * g)
            # MM → house booking change (contracts and executions move together)
            mm_avg = vol[mm_from].sum() / cnt[mm_from].sum()
            vol[mm_from] -= s_mm; vol[mm_to] += s_mm
            cnt[mm_from] -= round(s_mm / mm_avg); cnt[mm_to] += round(s_mm / mm_avg)
            # AU smart-order-router change: TAM → SXA keeping the capacity mix
            tam_avg = vol[tam].sum() / cnt[tam].sum()
            share = sf.share[tam].to_numpy()
            vol[tam] -= s_au * share; vol[sxa] += s_au * share
            cnt[tam] -= np.round(s_au * share / tam_avg); cnt[sxa] += np.round(s_au * share / tam_avg)
            return vol, cnt

        def effects(k, s_mm, s_au):
            v1, c1 = sep_plan(k, s_mm, s_au)
            e0 = self.borne(self.expected(self.month_rows(vol_aug, shape_cnt, P0)))
            e1 = self.borne(self.expected(self.month_rows(v1, c1, P1)))
            return BR.summarize_driver_effects(BR.slice_effects(e0, e1, fx0)), (v1, c1)

        k = 1.0
        for _ in range(4):
            eff, _ = effects(k, mm_shift, au_shift)
            eff2, _ = effects(k * 1.02, mm_shift, au_shift)
            k = k + (TARGETS["REST"]["volume"] - eff["REST"]["volume_usd"]) * (0.02 * k) / (eff2["REST"]["volume_usd"] - eff["REST"]["volume_usd"])
        for _ in range(3):
            eff, _ = effects(k, mm_shift, au_shift)
            eff2, _ = effects(k, mm_shift, au_shift * 1.01)
            au_shift = au_shift + (TARGETS["REST"]["mix"] - eff["REST"]["mix_usd"]) * (0.01 * au_shift) / (eff2["REST"]["mix_usd"] - eff["REST"]["mix_usd"])
        eff, (vol_sep, cnt_sep) = effects(k, mm_shift, au_shift)
        P.update(k_growth=k, mm_shift_contracts=mm_shift, au_shift_aud=au_shift, design_effects=eff)
        self.vol_sep, self.cnt_sep = vol_sep, cnt_sep
        return P

    # ── all months ──
    def plan(self) -> pd.DataFrame:
        sf = self.sf
        frames = []
        for m in R.MONTHS:
            if m == P0:
                vol, cnt = self.vol_aug, self.cnt_aug
            elif m == P1:
                vol, cnt = self.vol_sep, self.cnt_sep
            else:
                seas = MK.SEASONAL[m]
                noise = self.rng.lognormal(0, 0.035, len(sf))
                by_flow = {f: self.rng.lognormal(0, 0.03) for f in sf.flow_id.unique()}
                fn = np.array([by_flow[f] for f in sf.flow_id])
                vol = self.vol_aug * seas * noise * fn
                cnt = np.round(self.cnt_aug * seas * fn * self.rng.lognormal(0, 0.02, len(sf)))
                if m < "2026-03":
                    t = sf.pin.eq("TECH").to_numpy()
                    vol[t] *= TECH_PRE_DISCOUNT_FACTOR
                    cnt[t] = np.round(cnt[t] * TECH_PRE_DISCOUNT_FACTOR)
            buy = np.clip(self.rng.normal(0.5, 0.025, len(sf)), 0.44, 0.56)
            if m in (P0, P1):
                buy = np.full(len(sf), 0.5)
            frames.append(self.month_rows(vol, cnt, m, buy))
        return pd.concat(frames, ignore_index=True)
