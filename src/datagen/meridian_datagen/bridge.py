"""Cost-flux decomposition: the reference implementation of the Gold logic (spec §5, corrected SQL).

Per slice (group × desk × vendor × venue × capacity × entity × currency), constant currency at P0 FX:
    volume = (gv1 / gv0 − 1) × c0                      group volume change applied to the slice's prior cost
    rate   = v1 × (c1 / v1 − c0 / v0)   if v0, v1 > 0   unit-rate change at current volume
    mix    = (c1 − c0) − volume − rate                  remainder (incl. new / exited slices): identity always holds
Groups share a volume unit: cost_type × fee_basis × product_family × volume_unit. A group that is new in P1
(gv0 = 0) is attributed to volume.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SLICE_DIMS = ["desk", "billing_vendor_id", "venue", "capacity", "legal_entity", "cost_currency"]
GROUP_DIMS = ["cost_type", "fee_basis", "product_family", "volume_unit"]


def cc_cost(e: pd.DataFrame, fx0: dict) -> pd.Series:
    return e.cost_lcy * e.cost_currency.map(fx0)


def slice_effects(e0: pd.DataFrame, e1: pd.DataFrame, fx0: dict) -> pd.DataFrame:
    """e0 / e1: engine output for P0 / P1 restricted to net-borne lines."""
    keys = GROUP_DIMS + SLICE_DIMS
    a0 = e0.assign(c=cc_cost(e0, fx0)).groupby(keys, as_index=False, dropna=False).agg(v0=("driver_volume", "sum"), c0=("c", "sum"))
    a1 = e1.assign(c=cc_cost(e1, fx0)).groupby(keys, as_index=False, dropna=False).agg(v1=("driver_volume", "sum"), c1=("c", "sum"))
    s = a0.merge(a1, on=keys, how="outer").fillna({"v0": 0.0, "c0": 0.0, "v1": 0.0, "c1": 0.0})
    g = s.groupby(GROUP_DIMS, as_index=False, dropna=False).agg(gv0=("v0", "sum"), gv1=("v1", "sum"))
    s = s.merge(g, on=GROUP_DIMS, how="left")
    new_group = s.gv0 <= 0
    s["volume_usd"] = np.where(new_group, s.c1, (s.gv1 / s.gv0.where(~new_group, 1.0) - 1.0) * s.c0)
    both = (s.v0 > 0) & (s.v1 > 0)
    s["rate_usd"] = np.where(both & ~new_group, s.v1 * (s.c1 / s.v1.where(both, 1.0) - s.c0 / s.v0.where(both, 1.0)), 0.0)
    s["mix_usd"] = (s.c1 - s.c0) - s.volume_usd - s.rate_usd
    s["delta_usd"] = s.c1 - s.c0
    return s


def is_ed_exch_clearing(df: pd.DataFrame) -> pd.Series:
    return df.desk.eq("HKED") & df.cost_type.isin(["EXCHANGE", "CLEARING"])


def summarize_driver_effects(s: pd.DataFrame) -> dict:
    ed = is_ed_exch_clearing(s)
    out = {}
    for name, mask in (("ED", ed), ("REST", ~ed), ("APAC", pd.Series(True, index=s.index))):
        sub = s[mask]
        out[name] = {k: float(sub[k].sum()) for k in ("volume_usd", "mix_usd", "rate_usd", "c0", "c1")}
    return out
