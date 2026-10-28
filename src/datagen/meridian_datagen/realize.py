"""Realize the calibrated plan into individual executions.

Every plan row (sub-flow × month × side) becomes n executions whose contracts / notional sum EXACTLY to the
plan, spread over the market's business days with the day-weight profile (September volatility spike), with
trade sizes kept inside the fee floor / cap band so per-trade minimums and caps never bind on planted slices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import market as MK
from . import refdata as R

SETTLEMENT_LOCATION = {"HK": "PRC-CCASS", "CN": "PRC-NORTHBOUND", "SG": "MRC-CDP", "AU": "SXC-CHESS", "IN": "ICC-DEPOSITORY",
                       "KR": "HRX-KSD", "TW": "FMX-TDCC", "MY": "STX-DEPOSITORY"}
MARKET_HOURS = {"HK": (9.5, 16.0), "CN": (9.5, 15.0), "SG": (9.0, 17.0), "AU": (10.0, 16.0), "IN": (9.25, 15.5),
                "KR": (9.0, 15.5), "TW": (9.0, 13.5), "MY": (9.0, 17.0)}
VENUE_MARKET = {"PRX": "HK", "CNX": "CN", "MRX": "SG", "SXA": "AU", "TAM": "AU", "IGX": "IN", "DCX": "IN", "HRX": "KR",
                "FMX": "TW", "STX": "MY"}


def trade_market(venue: str, legal_entity: str) -> str:
    return VENUE_MARKET.get(venue) or R.ENTITY_MARKET[legal_entity]


def alloc_contracts(total: int, n: int, median: float, rng) -> np.ndarray:
    w = rng.lognormal(np.log(max(median, 1.0)), 0.9, n)
    extra = rng.multinomial(total - n, w / w.sum())
    return 1 + extra


def alloc_notional(total: float, n: int, lo: float, hi: float, rng) -> np.ndarray:
    mean = total / n
    if not lo <= mean <= hi:
        raise ValueError(f"mean trade size {mean:,.0f} outside fee band [{lo:,.0f}, {hi:,.0f}]: floors/caps would bind")
    x = rng.lognormal(0.0, 0.85, n)
    x = np.clip(x / x.sum() * total, lo, hi)
    gap = total - x.sum()
    room = (hi - x) if gap > 0 else (x - lo)
    x = x + gap * room / room.sum()
    x = np.round(x, 2)
    resid = round(total - x.sum(), 2)
    j = int(np.argmax(hi - x if resid > 0 else x - lo))
    x[j] = round(x[j] + resid, 2)
    return x


def realize(plan: pd.DataFrame, seed: int = 99) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    clients = R.COUNTERPARTIES[R.COUNTERPARTIES.is_client]
    street = R.COUNTERPARTIES[~R.COUNTERPARTIES.is_client]
    parts = []
    for r in plan.itertuples():
        mkt = trade_market(r.venue, r.legal_entity)
        days = R.business_days(r.period, mkt)
        kind = "deriv" if r.unit == "CONTRACTS" else ("cash" if r.settles else "otc")
        w = MK.day_weights(days, r.period, kind, rng)
        n = int(r.n_trades)
        day_idx = np.repeat(np.arange(len(days)), rng.multinomial(n, w))
        if r.unit == "CONTRACTS":
            contracts = alloc_contracts(int(r.contracts), n, r.median_contracts, rng)
            level = R.INSTRUMENTS[r.product_family][0][2]
            price = np.round(level * rng.lognormal(0, 0.012, n), 2)
            notional = np.round(contracts * R.CONTRACT_MULTIPLIER[r.product_family] * price, 2)
            qty = contracts.astype(float)
            instruments = np.array([R.INSTRUMENTS[r.product_family][0][0]] * n)
            names = np.array([R.INSTRUMENTS[r.product_family][0][1]] * n)
        else:
            notional = alloc_notional(float(r.notional), n, r.band_min or 1.0, r.band_max or 1e12, rng)
            contracts = np.zeros(n, dtype=int)
            ins = R.INSTRUMENTS[r.product_family]
            pick = rng.integers(0, len(ins), n)
            levels = np.array([ins[i][2] for i in pick])
            instruments = np.array([ins[i][0] for i in pick])
            names = np.array([ins[i][1] for i in pick])
            if r.settles:
                px = levels * rng.lognormal(0, 0.03, n)
                qty = np.maximum(1, np.round(notional / px))
                price = np.round(notional / qty, 4)
            else:
                qty = notional.copy()
                price = np.round(levels * rng.lognormal(0, 0.002, n), 6) if r.product_family in ("USD_CREDIT_BOND", "MYR_GOVT_BOND") \
                    else np.ones(n)
        if r.capacity == "CLIENT":
            dom = clients[clients.domicile.eq(mkt)]
            pool = pd.concat([dom, dom, clients]) if not dom.empty else clients
        else:
            dom = street[street.domicile.eq(mkt)]
            pool = dom if not dom.empty else street
        cpty = pool.counterparty_id.to_numpy()[rng.integers(0, len(pool), n)]
        books = R.BOOKS[r.desk]
        if r.desk == "HKED":
            book = np.where(r.capacity == "MM", "HKED-MM-01", np.array(books[:2])[rng.integers(0, 2, n)])
        elif r.desk == "HKCE":
            book = np.where(r.capacity == "HOUSE", "HKCE-FAC-01", np.array(books[:2])[rng.integers(0, 2, n)])
        elif r.desk == "D1PR":
            book = np.array([{"HK": "D1PR-SWAP-HK", "AU": "D1PR-SWAP-AU", "SG": "D1PR-SWAP-SG"}[mkt]] * n)
        elif r.desk == "KTEQ":
            book = np.array([("KTEQ-TW-01" if mkt == "TW" else books[rng.integers(0, 2)]) for _ in range(n)])
        else:
            book = np.array(books)[rng.integers(0, len(books), n)]
        h0, h1 = MARKET_HOURS.get(mkt, (9.0, 17.0))
        secs = (h0 * 3600 + rng.random(n) * (h1 - h0) * 3600).astype(int)
        parts.append(pd.DataFrame({
            "trade_date": np.array(days, dtype=object)[day_idx], "exec_seconds": secs, "desk_code": r.desk, "book": book,
            "legal_entity": r.legal_entity, "product_family": r.product_family, "instrument_id": instruments,
            "product": names, "venue": r.venue, "market": mkt, "execution_type": r.execution_type,
            "exec_broker": r.exec_broker, "ccp": r.ccp, "settle_vendor": r.settle_vendor, "capacity": r.capacity,
            "side": r.side, "qty": qty, "price": price, "contracts": contracts, "notional": notional,
            "currency": r.currency, "counterparty_id": cpty, "settles": bool(r.settles), "subflow_id": r.subflow_id,
        }))
    t = pd.concat(parts, ignore_index=True)
    t = t.sort_values(["trade_date", "exec_seconds", "desk_code"], kind="stable").reset_index(drop=True)
    seq = t.groupby("trade_date").cumcount() + 1
    t["trade_id"] = "MT" + pd.to_datetime(t.trade_date).dt.strftime("%y%m%d") + "-" + seq.astype(str).str.zfill(6)
    t["exec_time_local"] = pd.to_datetime(t.exec_seconds, unit="s").dt.strftime("%H:%M:%S")
    t["period"] = pd.to_datetime(t.trade_date).dt.strftime("%Y-%m")
    t["clearing_broker"] = np.where(t.execution_type.isin(["DMA_ALL_IN"]), t.exec_broker,
                                    np.where(t.execution_type.eq("VOICE_IDB"), "BILATERAL", "MERIDIAN"))
    t["settlement_location"] = np.where(t.settles, t.market.map(SETTLEMENT_LOCATION), "CUSTODIAN")
    t["is_affiliate"] = t.exec_broker.eq("B08")
    t["give_up_flag"] = t.execution_type.eq("GIVE_UP")
    return t.drop(columns=["exec_seconds"])


def engine_rows(trades: pd.DataFrame, fx_month: dict) -> pd.DataFrame:
    """Shape executions for the expected-cost engine (one row per trade)."""
    return pd.DataFrame({
        "row_id": trades.trade_id, "period": trades.period, "trade_date": trades.trade_date, "desk": trades.desk_code,
        "product_family": trades.product_family, "venue": trades.venue, "execution_type": trades.execution_type,
        "exec_broker": trades.exec_broker, "ccp": trades.ccp, "settle_vendor": trades.settle_vendor,
        "legal_entity": trades.legal_entity, "currency": trades.currency, "capacity": trades.capacity, "side": trades.side,
        "contracts": trades.contracts.astype(float), "notional": trades.notional, "n_trades": 1.0,
        "n_instructions": trades.settles.astype(float), "notional_usd": trades.notional * trades.currency.map(fx_month),
        "book": trades.book,
    })
