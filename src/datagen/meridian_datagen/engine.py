"""Expected-cost engine: volume rows × approved fee schedule → fee lines.

The same function runs on design aggregates (one row per sub-flow-month-side) and on individual executions, so
the calibration and the verifier can never disagree. The Gold SQL in the pipeline implements the same rules:

  venue lines      EXCHANGE / LEVY / TAX of the venue      member routes (DIRECT, AGENCY_ALGO, GIVE_UP);
                                                            LEVY / TAX also on DMA_ALL_IN (passed through by the broker)
  CCP lines        CLEARING of the CCP                     member routes
  settlement       SETTLEMENT of the settlement vendor     DIRECT, AGENCY_ALGO
  broker lines     BROKERAGE of the executing broker       any route with a broker
  then             product family, capacity, side, effective dates, monthly tiers; per-trade floor / cap;
                   GST split into non-recoverable (borne) and recoverable parts; statutory pass-through on CLIENT
                   capacity is recoverable; intra-group (MES) lines are eliminated.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MEMBER_ROUTES = ("DIRECT", "AGENCY_ALGO", "GIVE_UP")
SETTLE_ROUTES = ("DIRECT", "AGENCY_ALGO")
AFFILIATE_VENDORS = ("B08",)

VOLUME_UNIT = {"PER_CONTRACT_SIDE": "contract-sides", "BPS_NOTIONAL": "notional", "PER_TRADE": "trades",
               "PER_INSTRUCTION": "instructions", "PER_MILLION_NOTIONAL": "notional (millions)"}

ROW_COLS = ["row_id", "period", "desk", "product_family", "venue", "execution_type", "exec_broker", "ccp",
            "settle_vendor", "legal_entity", "currency", "capacity", "side", "contracts", "notional", "n_trades",
            "n_instructions", "notional_usd"]


def _capacity_ok(line_cap: pd.Series, row_cap: pd.Series) -> pd.Series:
    return (line_cap.eq("ALL") | line_cap.eq(row_cap)
            | (line_cap.eq("NON_MM") & row_cap.isin(["HOUSE", "CLIENT"]))
            | (line_cap.eq("PRINCIPAL") & row_cap.isin(["HOUSE", "MM"])))


def monthly_tier_measures(rows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Aggregates that drive tiered rates: broker turnover (US$), member venue turnover (LCY), member contracts."""
    broker = (rows[rows.exec_broker.ne("DIRECT")].groupby(["period", "exec_broker"], as_index=False)
              .notional_usd.sum().rename(columns={"exec_broker": "vendor_id", "notional_usd": "tier_measure"}))
    member = rows[rows.execution_type.isin(MEMBER_ROUTES)]
    venue_lcy = (member.groupby(["period", "venue"], as_index=False).notional.sum()
                 .rename(columns={"venue": "vendor_id", "notional": "tier_measure"}))
    venue_contracts = (member.groupby(["period", "venue", "product_family"], as_index=False).contracts.sum()
                       .rename(columns={"venue": "vendor_id", "contracts": "tier_measure"}))
    return {"VENDOR_MONTHLY_TURNOVER_USD": broker, "MEMBER_MONTHLY_TURNOVER_LCY": venue_lcy,
            "MEMBER_MONTHLY_CONTRACTS": venue_contracts}


def expected_cost(rows: pd.DataFrame, lines: pd.DataFrame, per_trade: bool, tiers: dict | None = None) -> pd.DataFrame:
    """Return one row per (volume row × applicable fee line), plus GST split lines."""
    passthrough = [c for c in ("trade_date", "book") if c in rows.columns]
    cols = ROW_COLS + passthrough
    rows = rows[cols].copy()
    # effective dating on the trade date (executions) or the first of the month (design aggregates)
    rows["period_start"] = (pd.to_datetime(rows.trade_date).dt.date if "trade_date" in rows.columns
                            else pd.to_datetime(rows.period + "-01").dt.date)
    var = lines[lines.fee_basis.ne("FIXED_MONTHLY")]
    parts = []

    def join(row_key: str, cost_types: tuple, route_ok: pd.Series):
        sub = rows[route_ok & rows[row_key].notna()]
        ln = var[var.cost_type.isin(cost_types)]
        m = sub.merge(ln, left_on=[row_key, "product_family"], right_on=["vendor_id", "product_family"],
                      suffixes=("", "_line"))
        return m

    parts.append(join("venue", ("EXCHANGE",), rows.execution_type.isin(MEMBER_ROUTES)))
    parts.append(join("venue", ("LEVY", "TAX"), rows.execution_type.isin(MEMBER_ROUTES + ("DMA_ALL_IN",))))
    parts.append(join("ccp", ("CLEARING",), rows.execution_type.isin(MEMBER_ROUTES)))
    parts.append(join("settle_vendor", ("SETTLEMENT",), rows.execution_type.isin(SETTLE_ROUTES)))
    parts.append(join("exec_broker", ("BROKERAGE",), rows.exec_broker.ne("DIRECT")))
    m = pd.concat(parts, ignore_index=True)

    # capacity / side / effective dating
    m = m[_capacity_ok(m.capacity_line, m.capacity)]
    m = m[m.side_line.eq("ALL") | m.side_line.eq(m.side)]
    m = m[(m.effective_from <= m.period_start) & (m.effective_to.isna() | (m.effective_to >= m.period_start))]

    # monthly tiers
    tiers = tiers or monthly_tier_measures(rows)
    tiered = m.tier_basis.ne("NONE")
    if tiered.any():
        t = m[tiered].copy()
        out = []
        for basis, meas in tiers.items():
            tb = t[t.tier_basis.eq(basis)]
            if tb.empty:
                continue
            keys = ["period", "vendor_id"] + (["product_family"] if basis == "MEMBER_MONTHLY_CONTRACTS" else [])
            tb = tb.merge(meas, on=keys, how="left")
            tb["tier_measure"] = tb.tier_measure.fillna(0.0)
            lo = tb.tier_min.astype(float).fillna(0.0)
            hi = tb.tier_max.astype(float).fillna(np.inf)
            out.append(tb[(tb.tier_measure >= lo) & (tb.tier_measure < hi)].drop(columns="tier_measure"))
        m = pd.concat([m[~tiered]] + out, ignore_index=True)

    basis = m.fee_basis
    vol = np.select(
        [basis.eq("PER_CONTRACT_SIDE"), basis.eq("BPS_NOTIONAL"), basis.eq("PER_TRADE"), basis.eq("PER_INSTRUCTION"),
         basis.eq("PER_MILLION_NOTIONAL")],
        [m.contracts, m.notional, m.n_trades, m.n_instructions, m.notional / 1e6], default=0.0)
    unit_rate = np.where(basis.eq("BPS_NOTIONAL"), m.rate / 1e4, m.rate)
    cost = vol * unit_rate
    if per_trade:
        floor = m.floor_per_trade.astype(float)
        cap = m.cap_per_trade.astype(float)
        cost = np.where(floor.notna() & (cost < floor), floor, cost)
        cost = np.where(cap.notna() & (cost > cap), cap, cost)
    m = m.assign(volume=vol, unit_rate=unit_rate, cost_lcy=cost, cost_currency=m.currency_line)

    is_dma_passthrough = m.execution_type.eq("DMA_ALL_IN") & m.cost_type.isin(["LEVY", "TAX"])
    m["billing_vendor_id"] = np.where(is_dma_passthrough, m.exec_broker, m.vendor_id)
    m["is_recoverable"] = m.is_pass_through & m.capacity.eq("CLIENT")

    base_cols = ["row_id", "period", "desk", "product_family", "venue", "execution_type", "exec_broker", "legal_entity",
                 "capacity", "side", "fee_id", "card_id", "vendor_id", "billing_vendor_id", "cost_type", "fee_basis",
                 "volume", "unit_rate", "cost_lcy", "cost_currency", "is_recoverable", "is_pass_through",
                 "is_discount_or_waiver", "gst_rate", "gst_recoverable_pct"]
    base_cols = base_cols + passthrough
    fees = m[base_cols].sort_values(["row_id", "cost_type", "fee_basis", "is_discount_or_waiver", "fee_id"])
    # Only the primary line of a (row, cost type, fee basis) carries the driver volume; discount, rebate and
    # concession overlays add cost but not volume (else volume would be double counted in the bridge).
    fees["is_volume_line"] = ~fees.duplicated(["row_id", "cost_type", "fee_basis"])
    g = fees[fees.gst_rate > 0]
    gst_nonrec = g.assign(cost_type="GST_NONREC", unit_rate=g.unit_rate * g.gst_rate * (1 - g.gst_recoverable_pct),
                          cost_lcy=g.cost_lcy * g.gst_rate * (1 - g.gst_recoverable_pct), is_recoverable=False,
                          is_pass_through=False, is_discount_or_waiver=False)
    gst_rec = g.assign(cost_type="GST_REC", unit_rate=g.unit_rate * g.gst_rate * g.gst_recoverable_pct,
                       cost_lcy=g.cost_lcy * g.gst_rate * g.gst_recoverable_pct, is_recoverable=True,
                       is_pass_through=False, is_discount_or_waiver=False)
    out = pd.concat([fees, gst_nonrec, gst_rec], ignore_index=True)
    out["driver_volume"] = np.where(out.is_volume_line, out.volume, 0.0)
    out["is_affiliate"] = out.billing_vendor_id.isin(AFFILIATE_VENDORS)
    out["in_net_borne"] = ~out.is_recoverable & ~out.is_affiliate
    out["volume_unit"] = out.fee_basis.map(VOLUME_UNIT)
    out.loc[out.fee_basis.eq("BPS_NOTIONAL"), "volume_unit"] = out.cost_currency + " notional"
    out.loc[out.fee_basis.eq("PER_MILLION_NOTIONAL"), "volume_unit"] = out.cost_currency + " notional (mn)"
    return out.drop(columns=["gst_rate", "gst_recoverable_pct"]).reset_index(drop=True)
