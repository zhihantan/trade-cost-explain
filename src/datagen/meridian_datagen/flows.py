"""Trade flows: each desk's routes to market, with August-2026 base shapes.

A *flow* is desk × product family × venue × execution route × legal entity × currency. Each flow splits by
capacity into *sub-flows*; a sub-flow-month is the unit the calibration designs (trade count + volume) and the
unit the realizer turns into executions. Base volumes are shapes: the solver rescales them (scale group ED or
REST) except where a planted story pins them.

execution_type
  DIRECT       Meridian is the exchange / clearing member: venue, CCP and settlement fees apply
  AGENCY_ALGO  routed through the intra-group agency platform (MES): MES commission + member fees
  GIVE_UP      executed by an external broker and given up to Meridian for clearing: commission + member fees
  DMA_ALL_IN   broker DMA at an all-in commission (exchange / clearing included); statutory taxes passed through
  VOICE_IDB    OTC via an inter-dealer broker: commission only
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class Flow:
    flow_id: str
    desk: str
    product_family: str
    venue: str                     # venue vendor id, or OTC
    execution_type: str
    exec_broker: str               # DIRECT or broker vendor id
    ccp: str | None
    settle_vendor: str | None
    legal_entity: str
    currency: str
    unit: str                      # CONTRACTS | NOTIONAL
    capacity_split: dict = field(default_factory=dict)
    aug_volume: float = 0.0        # contract-sides or notional (trade currency), shape before scaling
    aug_trades: int = 0
    band: tuple | None = None      # per-trade notional band (keeps fee floors / caps non-binding on planted slices)
    growth_key: str = ""
    pin: str | None = None         # TECH | IGX | COBALT_KR | COBALT_TW | COBALT_IN | AU
    scale_group: str = "REST"      # ED | REST | PINNED
    median_contracts: int = 20
    settles: bool = False


ED_GROWTH_KEY = "ED"

FLOWS: list[Flow] = [
    # ── HK Equity Derivatives (all exchange + clearing costs land in the planted ED slice) ──
    Flow("HKED-PRX50-DIR", "HKED", "PRX50_FUT", "PRX", "DIRECT", "DIRECT", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"HOUSE": 0.25, "CLIENT": 0.25, "MM": 0.50}, 720_000, 9_000, growth_key="ED", scale_group="ED", median_contracts=40),
    Flow("HKED-PRX50-GU", "HKED", "PRX50_FUT", "PRX", "GIVE_UP", "B01", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"CLIENT": 1.0}, 180_000, 2_500, growth_key="ED", scale_group="ED", median_contracts=40),
    Flow("HKED-MINI-DIR", "HKED", "PRX50_MINI_FUT", "PRX", "DIRECT", "DIRECT", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"HOUSE": 0.25, "CLIENT": 0.35, "MM": 0.40}, 330_000, 6_000, growth_key="ED", scale_group="ED", median_contracts=25),
    Flow("HKED-MINI-GU", "HKED", "PRX50_MINI_FUT", "PRX", "GIVE_UP", "B01", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"CLIENT": 1.0}, 70_000, 1_500, growth_key="ED", scale_group="ED", median_contracts=25),
    Flow("HKED-TECH-DIR", "HKED", "PRXTECH_FUT", "PRX", "DIRECT", "DIRECT", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"HOUSE": 0.25, "CLIENT": 0.35, "MM": 0.40}, 190_000, 3_000, growth_key="ED", pin="TECH", scale_group="PINNED",
         median_contracts=30),
    Flow("HKED-TECH-GU", "HKED", "PRXTECH_FUT", "PRX", "GIVE_UP", "B01", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"CLIENT": 1.0}, 40_000, 700, growth_key="ED", pin="TECH", scale_group="PINNED", median_contracts=30),
    Flow("HKED-CEI-DIR", "HKED", "PRXCEI_FUT", "PRX", "DIRECT", "DIRECT", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"HOUSE": 0.25, "CLIENT": 0.35, "MM": 0.40}, 250_000, 3_500, growth_key="ED", scale_group="ED", median_contracts=35),
    Flow("HKED-CEI-GU", "HKED", "PRXCEI_FUT", "PRX", "GIVE_UP", "B01", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"CLIENT": 1.0}, 50_000, 800, growth_key="ED", scale_group="ED", median_contracts=35),
    Flow("HKED-SOP-DIR", "HKED", "PRX_STOCK_OPT", "PRX", "DIRECT", "DIRECT", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"HOUSE": 0.40, "CLIENT": 0.30, "MM": 0.30}, 400_000, 5_000, growth_key="ED", scale_group="ED", median_contracts=45),
    Flow("HKED-SOP-GU", "HKED", "PRX_STOCK_OPT", "PRX", "GIVE_UP", "B01", "PRC", None, "MSHK", "HKD", "CONTRACTS",
         {"CLIENT": 1.0}, 100_000, 1_200, growth_key="ED", scale_group="ED", median_contracts=45),
    Flow("HKED-CN50", "HKED", "MRX_CN50_FUT", "MRX", "DIRECT", "DIRECT", "MRC", None, "MSSG", "USD", "CONTRACTS",
         {"HOUSE": 0.30, "CLIENT": 0.70}, 200_000, 2_500, growth_key="ED", scale_group="ED", median_contracts=50),
    Flow("HKED-HRX200-DIR", "HKED", "HRX200_FUT", "HRX", "DIRECT", "DIRECT", "HRX", None, "MSKR", "KRW", "CONTRACTS",
         {"HOUSE": 1.0}, 50_000, 700, growth_key="ED", scale_group="ED", median_contracts=40),
    Flow("HKED-HRX200-GU", "HKED", "HRX200_FUT", "HRX", "GIVE_UP", "B04", "HRX", None, "MSKR", "KRW", "CONTRACTS",
         {"CLIENT": 1.0}, 75_000, 1_000, growth_key="ED", scale_group="ED", median_contracts=40),
    Flow("HKED-SXA200-DIR", "HKED", "SXA200_FUT", "SXA", "DIRECT", "DIRECT", "SXC", None, "MSAU", "AUD", "CONTRACTS",
         {"HOUSE": 1.0}, 14_000, 400, growth_key="ED", scale_group="ED", median_contracts=20),
    Flow("HKED-SXA200-GU", "HKED", "SXA200_FUT", "SXA", "GIVE_UP", "B04", "SXC", None, "MSAU", "AUD", "CONTRACTS",
         {"CLIENT": 1.0}, 20_000, 500, growth_key="ED", scale_group="ED", median_contracts=20),
    Flow("HKED-FMX-DIR", "HKED", "FMX_IDX_FUT", "FMX", "DIRECT", "DIRECT", "FMX", None, "MSTW", "TWD", "CONTRACTS",
         {"HOUSE": 1.0}, 8_000, 300, growth_key="ED", scale_group="ED", median_contracts=15),
    Flow("HKED-FMX-GU", "HKED", "FMX_IDX_FUT", "FMX", "GIVE_UP", "B04", "FMX", None, "MSTW", "TWD", "CONTRACTS",
         {"CLIENT": 1.0}, 12_000, 400, growth_key="ED", scale_group="ED", median_contracts=15),

    # ── HK Cash Equities ──
    Flow("HKCE-DIR", "HKCE", "HK_CASH_EQ", "PRX", "DIRECT", "DIRECT", "PRC", "PRC", "MSHK", "HKD", "NOTIONAL",
         {"CLIENT": 0.97, "HOUSE": 0.03}, 32e9, 52_000, band=(100_000, 4_900_000), growth_key="HK_CASH", settles=True),
    Flow("HKCE-MES", "HKCE", "HK_CASH_EQ", "PRX", "AGENCY_ALGO", "B08", "PRC", "PRC", "MSHK", "HKD", "NOTIONAL",
         {"CLIENT": 1.0}, 6e9, 8_000, band=(100_000, 4_900_000), growth_key="HK_CASH", settles=True),
    # ── Stock Connect / China flow ──
    Flow("CNSC-DIR", "CNSC", "CN_CONNECT_EQ", "CNX", "DIRECT", "DIRECT", "PRC", None, "MSHK", "CNH", "NOTIONAL",
         {"CLIENT": 0.95, "HOUSE": 0.05}, 11e9, 24_000, band=(50_000, 4_000_000), growth_key="CN_CONNECT", settles=True),
    # ── Korea & Taiwan Equities ──
    Flow("KTEQ-KR-COB", "KTEQ", "KR_CASH_EQ", "HRX", "DMA_ALL_IN", "B03", None, None, "MSKR", "KRW", "NOTIONAL",
         {"CLIENT": 1.0}, 0.0, 14_000, band=(20e6, 5e9), growth_key="COBALT", pin="COBALT_KR", scale_group="PINNED", settles=True),
    Flow("KTEQ-KR-DIR", "KTEQ", "KR_CASH_EQ", "HRX", "DIRECT", "DIRECT", None, "HRX", "MSKR", "KRW", "NOTIONAL",
         {"CLIENT": 0.95, "HOUSE": 0.05}, 400e9, 4_000, band=(20e6, 5e9), growth_key="KR_CASH", settles=True),
    Flow("KTEQ-TW-COB", "KTEQ", "TW_CASH_EQ", "FMX", "DMA_ALL_IN", "B03", None, None, "MSTW", "TWD", "NOTIONAL",
         {"CLIENT": 1.0}, 0.0, 6_000, band=(500_000, 150e6), growth_key="COBALT", pin="COBALT_TW", scale_group="PINNED", settles=True),
    Flow("KTEQ-TW-DIR", "KTEQ", "TW_CASH_EQ", "FMX", "DIRECT", "DIRECT", None, None, "MSTW", "TWD", "NOTIONAL",
         {"CLIENT": 1.0}, 6e9, 4_000, band=(500_000, 150e6), growth_key="TW_CASH", settles=True),
    # ── Australia Cash Equities (base pinned: the routing story is sized in A$) ──
    Flow("AUCE-SXA", "AUCE", "AU_CASH_EQ", "SXA", "DIRECT", "DIRECT", "SXC", "SXC", "MSAU", "AUD", "NOTIONAL",
         {"CLIENT": 0.80, "HOUSE": 0.20}, 6.6e9, 22_000, band=(20_000, 5_000_000), growth_key="AU_CASH", pin="AU",
         scale_group="PINNED", settles=True),
    Flow("AUCE-TAM", "AUCE", "AU_CASH_EQ", "TAM", "DIRECT", "DIRECT", "SXC", "SXC", "MSAU", "AUD", "NOTIONAL",
         {"CLIENT": 0.80, "HOUSE": 0.20}, 5.4e9, 18_000, band=(20_000, 5_000_000), growth_key="AU_CASH", pin="AU",
         scale_group="PINNED", settles=True),
    Flow("AUCE-MES", "AUCE", "AU_CASH_EQ", "SXA", "AGENCY_ALGO", "B08", "SXC", "SXC", "MSAU", "AUD", "NOTIONAL",
         {"CLIENT": 1.0}, 1.2e9, 4_000, band=(20_000, 5_000_000), growth_key="AU_CASH", pin="AU", scale_group="PINNED",
         settles=True),
    # ── India Equities ──
    Flow("INEQ-IGX", "INEQ", "IN_CASH_EQ", "IGX", "DIRECT", "DIRECT", "ICC", "ICC", "MSIN", "INR", "NOTIONAL",
         {"CLIENT": 1.0}, 0.0, 18_000, band=(1e6, 200e6), growth_key="IN_CASH", pin="IGX", scale_group="PINNED", settles=True),
    Flow("INEQ-DCX", "INEQ", "IN_CASH_EQ", "DCX", "DIRECT", "DIRECT", "ICC", "ICC", "MSIN", "INR", "NOTIONAL",
         {"CLIENT": 1.0}, 60e9, 3_000, band=(1e6, 200e6), growth_key="IN_CASH", settles=True),
    Flow("INEQ-COB", "INEQ", "IN_CASH_EQ", "IGX", "DMA_ALL_IN", "B03", None, None, "MSIN", "INR", "NOTIONAL",
         {"CLIENT": 1.0}, 0.0, 5_000, band=(1e6, 200e6), growth_key="COBALT", pin="COBALT_IN", scale_group="PINNED", settles=True),
    # ── Delta One / Prime (house hedges: statutory levies and stamp duty are borne) ──
    Flow("D1PR-HK", "D1PR", "HK_CASH_EQ", "PRX", "AGENCY_ALGO", "B08", "PRC", "PRC", "MSHK", "HKD", "NOTIONAL",
         {"HOUSE": 1.0}, 0.7e9, 2_000, band=(100_000, 4_900_000), growth_key="HK_CASH", settles=True),
    Flow("D1PR-AU", "D1PR", "AU_CASH_EQ", "SXA", "DIRECT", "DIRECT", "SXC", "SXC", "MSAU", "AUD", "NOTIONAL",
         {"HOUSE": 1.0}, 0.8e9, 4_000, band=(20_000, 5_000_000), growth_key="AU_CASH", settles=True),
    Flow("D1PR-SG", "D1PR", "SG_CASH_EQ", "MRX", "DIRECT", "DIRECT", "MRC", "MRC", "MSSG", "SGD", "NOTIONAL",
         {"HOUSE": 1.0}, 0.3e9, 3_000, band=(20_000, 1_800_000), growth_key="SG_CASH", settles=True),
    # ── FICC ──
    Flow("FLCR-BOND", "FLCR", "USD_CREDIT_BOND", "OTC", "VOICE_IDB", "B05", None, None, "MSHK", "USD", "NOTIONAL",
         {"HOUSE": 1.0}, 3e9, 2_000, band=(250_000, 25_000_000), growth_key="CREDIT"),
    Flow("SGFX-FX", "SGFX", "FX_SPOT_NDF", "OTC", "VOICE_IDB", "B02", None, None, "MSSG", "USD", "NOTIONAL",
         {"HOUSE": 1.0}, 45e9, 3_500, band=(1e6, 100e6), growth_key="FX"),
    Flow("SGRT-IRS", "SGRT", "SG_IRS", "OTC", "VOICE_IDB", "B02", None, None, "MSSG", "SGD", "NOTIONAL",
         {"HOUSE": 1.0}, 25e9, 1_500, band=(5e6, 100e6), growth_key="SG_IRS"),
    Flow("SGEM-NDF", "SGEM", "EM_NDF", "OTC", "VOICE_IDB", "B06", None, None, "MSSG", "USD", "NOTIONAL",
         {"HOUSE": 1.0}, 12e9, 2_000, band=(1e6, 50e6), growth_key="EM"),
    Flow("SGEM-MGS", "SGEM", "MYR_GOVT_BOND", "OTC", "VOICE_IDB", "B06", None, None, "MSMY", "MYR", "NOTIONAL",
         {"HOUSE": 1.0}, 6e9, 800, band=(1e6, 50e6), growth_key="MYR_BOND"),
    Flow("SGEM-MYEQ", "SGEM", "MY_CASH_EQ", "STX", "DIRECT", "DIRECT", "STX", None, "MSMY", "MYR", "NOTIONAL",
         {"CLIENT": 1.0}, 1.2e9, 3_000, band=(10_000, 3_300_000), growth_key="MY_CASH", settles=True),
    Flow("AURF-DIR", "AURF", "AU_BOND_FUT", "SXA", "DIRECT", "DIRECT", "SXC", None, "MSAU", "AUD", "CONTRACTS",
         {"HOUSE": 1.0}, 96_000, 1_800, growth_key="AU_BOND_FUT", median_contracts=50),
    Flow("AURF-GU", "AURF", "AU_BOND_FUT", "SXA", "GIVE_UP", "B07", "SXC", None, "MSAU", "AUD", "CONTRACTS",
         {"HOUSE": 1.0}, 64_000, 1_200, growth_key="AU_BOND_FUT", median_contracts=50),
]

# Natural September growth by growth key (before the solver rescales the free keys to hit the volume target).
SEP_GROWTH = {
    "HK_CASH": 0.22, "CN_CONNECT": 0.18, "KR_CASH": 0.20, "TW_CASH": 0.20, "COBALT": 0.20, "SG_CASH": 0.20,
    "MY_CASH": 0.10, "AU_BOND_FUT": 0.12, "FX": 0.12, "SG_IRS": 0.08, "CREDIT": 0.06, "EM": 0.10, "MYR_BOND": 0.08,
    "AU_CASH": 0.24, "IN_CASH": 0.15,   # fixed (planted mix / rate stories are sized on these)
}
FIXED_GROWTH_KEYS = {"AU_CASH", "IN_CASH", "ED"}

# Broker C (Cobalt) August turnover by market, US$ at August average FX: 1.70bn in total (tier 2 ≥ US$1.2bn)
COBALT_AUG_USD = {"COBALT_KR": 0.80e9, "COBALT_TW": 0.45e9, "COBALT_IN": 0.45e9}


def subflows() -> pd.DataFrame:
    rows = []
    for f in FLOWS:
        for cap, share in f.capacity_split.items():
            rows.append({
                "subflow_id": f"{f.flow_id}-{cap}", "flow_id": f.flow_id, "desk": f.desk, "product_family": f.product_family,
                "venue": f.venue, "execution_type": f.execution_type, "exec_broker": f.exec_broker, "ccp": f.ccp,
                "settle_vendor": f.settle_vendor, "legal_entity": f.legal_entity, "currency": f.currency, "unit": f.unit,
                "capacity": cap, "share": share, "aug_volume": f.aug_volume * share, "aug_trades": f.aug_trades * share,
                "band_min": f.band[0] if f.band else None, "band_max": f.band[1] if f.band else None,
                "growth_key": f.growth_key, "pin": f.pin or "", "scale_group": f.scale_group,
                "median_contracts": f.median_contracts, "settles": f.settles,
            })
    return pd.DataFrame(rows)
