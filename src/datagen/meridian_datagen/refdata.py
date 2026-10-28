"""Reference and master data for Meridian Group, APAC Global Markets (synthetic).

Everything here is fictional. Structure mirrors a US GAAP, April–March fiscal-year sell-side bank with a
Singapore / Hong Kong dual-hub model (spec §0). Mapping tables carry deliberate gaps (two unmapped AP vendors)
so the pipeline's mapping-coverage expectation has something to find.
"""
from __future__ import annotations

import datetime as dt
import hashlib

import pandas as pd

DIVISION = "APAC Global Markets"
GROUP = "Meridian Group"
AS_OF_DATE = dt.date(2026, 10, 5)          # September close, working day 3
FIRST_MONTH = "2025-09"
LAST_MONTH = "2026-09"


def months() -> list[str]:
    out, y, m = [], 2025, 9
    while (y, m) <= (2026, 9):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


MONTHS = months()

# ── Legal entities ────────────────────────────────────────────────────────────────────────────────
LEGAL_ENTITIES = pd.DataFrame(
    [
        ("MSHK", "Meridian Securities (Hong Kong) Limited", "HK", "HKD"),
        ("MSSG", "Meridian Securities Singapore Pte. Ltd.", "SG", "SGD"),
        ("MSAU", "Meridian Australia Securities Limited", "AU", "AUD"),
        ("MSIN", "Meridian Financial Services India Private Limited", "IN", "INR"),
        ("MSKR", "Meridian Securities Korea Co., Ltd.", "KR", "KRW"),
        ("MSTW", "Meridian Securities (Hong Kong) Limited — Taiwan Branch", "TW", "TWD"),
        ("MSMY", "Meridian Securities Malaysia Sdn. Bhd.", "MY", "MYR"),
    ],
    columns=["legal_entity", "legal_entity_name", "country", "functional_currency"],
)
ENTITY_MARKET = dict(zip(LEGAL_ENTITIES.legal_entity, LEGAL_ENTITIES.country))

CURRENCY_MARKET = {"HKD": "HK", "CNH": "CN", "SGD": "SG", "AUD": "AU", "INR": "IN", "KRW": "KR", "TWD": "TW", "MYR": "MY"}
MARKET_NAMES = {"HK": "Hong Kong", "CN": "Mainland China (Connect)", "SG": "Singapore", "AU": "Australia",
                "IN": "India", "KR": "South Korea", "TW": "Taiwan", "MY": "Malaysia"}
CURRENCIES = ["USD", "HKD", "CNH", "SGD", "AUD", "INR", "KRW", "TWD", "MYR"]


def reporting_market(currency: str, legal_entity: str) -> str:
    """Market used on every bridge row: the currency's home market, or the booking entity's market for US$."""
    return CURRENCY_MARKET.get(currency) or ENTITY_MARKET[legal_entity]


# ── Desk hierarchy: book → desk → business → division → legal entity ───────────────────────────────
BUSINESSES = {
    "CEQ": "Cash Equities",
    "EQD": "Equity Derivatives",
    "PDO": "Prime & Delta One",
    "RTS": "Rates",
    "CRD": "Credit",
    "FXE": "FX & Emerging Markets",
}
DESKS = pd.DataFrame(
    [
        ("HKCE", "HK Cash Equities", "CEQ", "Hong Kong", "MSHK"),
        ("CNSC", "Stock Connect / China Flow", "CEQ", "Hong Kong", "MSHK"),
        ("KTEQ", "Korea & Taiwan Equities", "CEQ", "Seoul / Taipei", "MSKR"),
        ("AUCE", "Australia Cash Equities", "CEQ", "Sydney", "MSAU"),
        ("INEQ", "India Equities", "CEQ", "Mumbai", "MSIN"),
        ("HKED", "HK Equity Derivatives", "EQD", "Hong Kong", "MSHK"),
        ("D1PR", "Delta One / Prime", "PDO", "Hong Kong", "MSHK"),
        ("FLCR", "Flow Credit", "CRD", "Hong Kong", "MSHK"),
        ("SGFX", "Singapore FX", "FXE", "Singapore", "MSSG"),
        ("SGRT", "Singapore Rates", "RTS", "Singapore", "MSSG"),
        ("SGEM", "Singapore EM (incl. Malaysia)", "FXE", "Singapore", "MSSG"),
        ("AURF", "Australia Rates & Futures", "RTS", "Sydney", "MSAU"),
    ],
    columns=["desk_code", "desk_name", "business_code", "hub", "primary_legal_entity"],
)
DESKS["business"] = DESKS.business_code.map(BUSINESSES)
DESKS["division"] = DIVISION
DESK_NAME = dict(zip(DESKS.desk_code, DESKS.desk_name))
DESK_BUSINESS = dict(zip(DESKS.desk_code, DESKS.business_code))

BOOKS = {
    "HKCE": ["HKCE-AGY-01", "HKCE-AGY-02", "HKCE-FAC-01"],
    "CNSC": ["CNSC-NB-01", "CNSC-NB-02"],
    "KTEQ": ["KTEQ-KR-01", "KTEQ-KR-02", "KTEQ-TW-01"],
    "AUCE": ["AUCE-AGY-01", "AUCE-PT-01", "AUCE-FAC-01"],
    "INEQ": ["INEQ-AGY-01", "INEQ-AGY-02"],
    "HKED": ["HKED-FLOW-01", "HKED-FLOW-02", "HKED-MM-01", "HKED-REG-01"],
    "D1PR": ["D1PR-SWAP-HK", "D1PR-SWAP-AU", "D1PR-SWAP-SG"],
    "FLCR": ["FLCR-IG-01", "FLCR-HY-01"],
    "SGFX": ["SGFX-SPOT-01", "SGFX-NDF-01"],
    "SGRT": ["SGRT-IRS-01", "SGRT-IRS-02"],
    "SGEM": ["SGEM-NDF-01", "SGEM-MY-01"],
    "AURF": ["AURF-FUT-01", "AURF-FUT-02"],
}

# Cost centres (GL) with effective dating: HK equity derivatives market making was split out on 1-Apr-2026.
COST_CENTRES = pd.DataFrame(
    [
        ("4101", "HK Cash Equities — Agency", "HKCE", "2025-01-01", None),
        ("4111", "HK Cash Equities — Facilitation", "HKCE", "2025-01-01", None),
        ("4102", "Stock Connect / China Flow", "CNSC", "2025-01-01", None),
        ("4301", "Korea Equities", "KTEQ", "2025-01-01", None),
        ("4302", "Taiwan Equities", "KTEQ", "2025-01-01", None),
        ("4401", "Australia Cash Equities — Agency", "AUCE", "2025-01-01", None),
        ("4411", "Australia Cash Equities — Program Trading", "AUCE", "2025-01-01", None),
        ("4501", "India Equities", "INEQ", "2025-01-01", None),
        ("4201", "HK Equity Derivatives — Flow", "HKED", "2025-01-01", None),
        ("4202", "HK Equity Derivatives — Market Making", "HKED", "2026-04-01", None),
        ("4103", "Delta One / Prime", "D1PR", "2025-01-01", None),
        ("5101", "Flow Credit", "FLCR", "2025-01-01", None),
        ("5201", "Singapore FX", "SGFX", "2025-01-01", None),
        ("5301", "Singapore Rates", "SGRT", "2025-01-01", None),
        ("5401", "Singapore EM", "SGEM", "2025-01-01", None),
        ("5402", "Malaysia Markets", "SGEM", "2025-01-01", None),
        ("5302", "Australia Rates & Futures", "AURF", "2025-01-01", None),
    ],
    columns=["cost_centre", "cost_centre_name", "desk_code", "effective_from", "effective_to"],
)


def cost_centre_for(desk: str, capacity: str, legal_entity: str, execution_type: str, month: str) -> str:
    """GL cost centre a cost line is booked to (the inverse of map_costcentre_desk)."""
    if desk == "HKCE":
        return "4111" if capacity == "HOUSE" else "4101"
    if desk == "KTEQ":
        return "4302" if legal_entity == "MSTW" else "4301"
    if desk == "AUCE":
        return "4411" if execution_type == "AGENCY_ALGO" else "4401"
    if desk == "HKED":
        return "4202" if (capacity == "MM" and month >= "2026-04") else "4201"
    if desk == "SGEM":
        return "5402" if legal_entity == "MSMY" else "5401"
    return {"CNSC": "4102", "INEQ": "4501", "D1PR": "4103", "FLCR": "5101", "SGFX": "5201", "SGRT": "5301",
            "AURF": "5302"}[desk]


# ── Vendors: venues, CCPs, brokers, connectivity (trade-system / Procurement view) ────────────────────
VENDORS = pd.DataFrame(
    [
        ("PRX", "Pearl River Exchange", "Exchange", "HK"),
        ("PRC", "Pearl River Clearing", "CCP", "HK"),
        ("CNX", "Connect Northbound (Pearl River link)", "Exchange", "CN"),
        ("MRX", "Merlion Exchange", "Exchange", "SG"),
        ("MRC", "Merlion Clearing", "CCP", "SG"),
        ("SXA", "Southern Cross Exchange", "Exchange", "AU"),
        ("SXC", "Southern Cross Clear", "CCP", "AU"),
        ("TAM", "Tasman Alternative Market", "Exchange", "AU"),
        ("IGX", "Indus Exchange", "Exchange", "IN"),
        ("ICC", "Indus Clearing Corporation", "CCP", "IN"),
        ("DCX", "Deccan Exchange", "Exchange", "IN"),
        ("HRX", "Han River Exchange", "Exchange", "KR"),
        ("FMX", "Formosa Exchange", "Exchange", "TW"),
        ("STX", "Straits Exchange", "Exchange", "MY"),
        ("B01", "Aurora Pacific Securities", "Broker", "HK"),
        ("B02", "Bluewater Brokerage", "Broker", "SG"),
        ("B03", "Cobalt Securities", "Broker", "Regional"),
        ("B04", "Dunmore Capital Markets", "Broker", "Regional"),
        ("B05", "Emberly Securities", "Broker", "HK"),
        ("B06", "Foxglove Brokerage", "Broker", "SG"),
        ("B07", "Goldcrest Execution", "Broker", "AU"),
        ("B08", "Meridian Execution Services", "Broker (intra-group)", "Regional"),
        ("V21", "Pacific Data Links", "Connectivity", "Regional"),
        ("V22", "Straits Connectivity", "Connectivity", "SG"),
    ],
    columns=["vendor_id", "vendor_name", "vendor_type", "home_market"],
)
VENDORS["is_affiliate"] = VENDORS.vendor_id.eq("B08")
VENDOR_NAME = dict(zip(VENDORS.vendor_id, VENDORS.vendor_name))
VENDOR_TYPE = dict(zip(VENDORS.vendor_id, VENDORS.vendor_type))


def _lei(seed: str) -> str:
    """Fake but well-formed ISO 17442 LEI (4-char LOU prefix + '00' + 12 chars + 2 check digits)."""
    h = hashlib.sha1(seed.encode()).hexdigest().upper()
    body = "5493" + "00" + "".join(c if c.isalnum() else "X" for c in h[:12])
    num = "".join(str(int(c, 36)) for c in body + "00")
    check = 98 - int(num) % 97
    return f"{body}{check:02d}"


VENDORS["lei"] = VENDORS.vendor_id.map(lambda v: _lei("vendor:" + v))

# AP vendor master (ERP view). One trade-system vendor can have several AP vendors (one per billing entity).
# The ERP knows nothing about trades: map_vendor_counterparty is the missing link (spec §5).
AP_VENDORS = pd.DataFrame(
    [
        ("AP-210011", "PEARL RIVER EXCHANGE LTD", "PRX", "MSHK"),
        ("AP-210012", "PEARL RIVER CLEARING CORP LTD", "PRC", "MSHK"),
        ("AP-210013", "PEARL RIVER EXCH - CONNECT NB SVCS", "CNX", "MSHK"),
        ("AP-310021", "MERLION EXCHANGE LIMITED", "MRX", "MSSG"),
        ("AP-310022", "MERLION CLEARING & DEPOSITORY PTE", "MRC", "MSSG"),
        ("AP-410031", "SOUTHERN CROSS EXCHANGE LIMITED", "SXA", "MSAU"),
        ("AP-410032", "SOUTHERN CROSS CLEAR PTY LTD", "SXC", "MSAU"),
        ("AP-410033", "TASMAN ALTERNATIVE MARKET PTY", "TAM", "MSAU"),
        ("AP-510041", "INDUS EXCHANGE OF INDIA LTD", "IGX", "MSIN"),
        ("AP-510042", "INDUS CLEARING CORPORATION LTD", "ICC", "MSIN"),
        ("AP-510043", "DECCAN EXCHANGE LIMITED", "DCX", "MSIN"),
        ("AP-610051", "HAN RIVER EXCHANGE", "HRX", "MSKR"),
        ("AP-710061", "FORMOSA EXCHANGE CORP", "FMX", "MSTW"),
        ("AP-810071", "STRAITS EXCHANGE BHD", "STX", "MSMY"),
        ("AP-220101", "AURORA PACIFIC SECURITIES LTD", "B01", "MSHK"),
        ("AP-320102", "BLUEWATER BROKERAGE (S) PTE LTD", "B02", "MSSG"),
        ("AP-620103", "COBALT SECURITIES (KOREA) CO LTD", "B03", "MSKR"),
        ("AP-720103", "COBALT SECURITIES TAIWAN BRANCH", "B03", "MSTW"),
        ("AP-520103", "COBALT SECURITIES INDIA PVT LTD", "B03", "MSIN"),
        ("AP-220104", "DUNMORE CAPITAL MARKETS (HK) LTD", "B04", "MSHK"),
        ("AP-620104", "DUNMORE CAPITAL MARKETS KOREA", "B04", "MSKR"),
        ("AP-420104", "DUNMORE CAPITAL MARKETS AUSTRALIA", "B04", "MSAU"),
        ("AP-720104", "DUNMORE CAPITAL MKTS TAIWAN", "B04", "MSTW"),
        ("AP-220105", "EMBERLY SECURITIES ASIA LTD", "B05", "MSHK"),
        ("AP-320106", "FOXGLOVE BROKERAGE PTE LTD", "B06", "MSSG"),
        ("AP-820106", "FOXGLOVE BROKERAGE (M) SDN BHD", "B06", "MSMY"),
        ("AP-420107", "GOLDCREST EXECUTION PTY LTD", "B07", "MSAU"),
        ("AP-990108", "MERIDIAN EXECUTION SERVICES - IC", "B08", "MSHK"),
        ("AP-990109", "MERIDIAN EXECUTION SERVICES AU - IC", "B08", "MSAU"),
        ("AP-990110", "MERIDIAN EXECUTION SERVICES SG - IC", "B08", "MSSG"),
        ("AP-230201", "PACIFIC DATA LINKS LTD", "V21", "MSHK"),
        ("AP-330202", "STRAITS CONNECTIVITY PTE LTD", "V22", "MSSG"),
        # Deliberately NOT mapped (new vendors onboarded in Q2; mapping request still with Procurement)
        ("AP-440301", "LOTUS MARKET SERVICES PTY LTD", None, "MSAU"),
        ("AP-540302", "HARBOUR SETTLEMENT AGENTS PVT LTD", None, "MSIN"),
    ],
    columns=["ap_vendor_id", "ap_vendor_name", "vendor_id", "legal_entity"],
)
UNMAPPED_AP_VENDORS = ["AP-440301", "AP-540302"]


_AP_EXACT = {(v, le): a for a, v, le in zip(AP_VENDORS.ap_vendor_id, AP_VENDORS.vendor_id, AP_VENDORS.legal_entity) if v}
_AP_FIRST = {}
for _a, _v in zip(AP_VENDORS.ap_vendor_id, AP_VENDORS.vendor_id):
    if _v and _v not in _AP_FIRST:
        _AP_FIRST[_v] = _a


def ap_vendor_for(vendor_id: str, legal_entity: str) -> str:
    """AP vendor that bills this vendor's charges to this entity (falls back to the vendor's first billing entity)."""
    return _AP_EXACT.get((vendor_id, legal_entity)) or _AP_FIRST[vendor_id]


def map_vendor_counterparty() -> pd.DataFrame:
    m = AP_VENDORS.dropna(subset=["vendor_id"]).merge(VENDORS, on="vendor_id", how="left")
    ai_suggested = {"AP-720103", "AP-520103", "AP-720104", "AP-820106", "AP-990110"}
    out = pd.DataFrame({
        "ap_vendor_id": m.ap_vendor_id,
        "ap_vendor_name": m.ap_vendor_name,
        "vendor_id": m.vendor_id,
        "counterparty_name": m.vendor_name,
        "counterparty_lei": m.lei,
        "vendor_type": m.vendor_type,
        "is_affiliate": m.is_affiliate,
        "mapping_source": ["AI-suggested, analyst approved" if a in ai_suggested else "Procurement vendor master"
                           for a in m.ap_vendor_id],
        "match_confidence": [0.93 if a in ai_suggested else 1.0 for a in m.ap_vendor_id],
        "approved_by": ["ava.chen@meridian-demo.example" if a in ai_suggested else "procurement.master@meridian-demo.example"
                        for a in m.ap_vendor_id],
        "effective_from": "2025-01-01",
    })
    return out


# ── GL chart (trade-cost accounts all roll to the US GAAP line "Commissions and floor brokerage") ─────
GL_ACCOUNTS = pd.DataFrame(
    [
        ("640100", "Brokerage and commissions — external", "BROKERAGE", True, False),
        ("640110", "Brokerage — intra-group (eliminated on consolidation)", "BROKERAGE", False, True),
        ("640200", "Exchange trading fees", "EXCHANGE", True, False),
        ("640300", "Clearing fees", "CLEARING", True, False),
        ("640400", "Settlement and custody fees", "SETTLEMENT", True, False),
        ("640500", "Settlement fails, penalties and buy-ins", "FAILS", True, False),
        ("640600", "Statutory levies — borne", "LEVY", True, False),
        ("640650", "Transaction taxes and stamp duty — borne", "TAX", True, False),
        ("640610", "Statutory levies and taxes — recharged to clients (gross)", "RECHARGED", False, False),
        ("640619", "Statutory levies and taxes — recovered from clients", "RECHARGED", False, False),
        ("640700", "Exchange membership, connectivity and market access", "FIXED", True, False),
        ("640800", "Irrecoverable GST on trade fees", "GST_NONREC", True, False),
    ],
    columns=["gl_account", "gl_account_name", "cost_type", "in_net_borne", "is_intragroup"],
)
GL_ACCOUNTS["fs_line"] = "Commissions and floor brokerage"
COST_TYPE_ACCOUNT = {"BROKERAGE": "640100", "EXCHANGE": "640200", "CLEARING": "640300", "SETTLEMENT": "640400",
                     "FAILS": "640500", "LEVY": "640600", "TAX": "640650", "FIXED": "640700", "GST_NONREC": "640800"}
COST_CATEGORY = {"EXCHANGE": "Exchange & clearing", "CLEARING": "Exchange & clearing", "BROKERAGE": "Brokerage",
                 "SETTLEMENT": "Settlement & custody", "LEVY": "Levies & taxes (borne)", "TAX": "Levies & taxes (borne)",
                 "GST_NONREC": "Non-recoverable GST", "FAILS": "Settlement fails", "FIXED": "Fixed fees"}

# ── Counterparties (trade-system clients and street) ───────────────────────────────────────────────
_CPTY = [
    ("C001", "Kestrel Asset Management", "Asset manager", "AU"),
    ("C002", "Harbourview Capital Partners", "Hedge fund", "HK"),
    ("C003", "Jadeite Investment Management", "Asset manager", "HK"),
    ("C004", "Southern Ocean Super Fund", "Pension fund", "AU"),
    ("C005", "Lion Gate Global Investors", "Asset manager", "SG"),
    ("C006", "Monsoon Alpha Fund", "Hedge fund", "SG"),
    ("C007", "Ganges Growth Advisors", "Asset manager", "IN"),
    ("C008", "Bodhi Tree Capital", "Hedge fund", "IN"),
    ("C009", "Hanok Investment Trust", "Asset manager", "KR"),
    ("C010", "Seorak Quant Partners", "Hedge fund", "KR"),
    ("C011", "Jade Mountain Asset Management", "Asset manager", "TW"),
    ("C012", "Kowloon Bay Opportunities", "Hedge fund", "HK"),
    ("C013", "Pacific Rim Sovereign Investors", "Sovereign fund", "SG"),
    ("C014", "Coral Sea Capital", "Asset manager", "AU"),
    ("C015", "Banyan Ridge Partners", "Hedge fund", "SG"),
    ("C016", "Northern Star Endowment", "Endowment", "AU"),
    ("C017", "Lotus Pond Investments", "Family office", "HK"),
    ("C018", "Tidewater Global Macro", "Hedge fund", "SG"),
    ("C019", "Saffron Equity Partners", "Asset manager", "IN"),
    ("C020", "Penang Straits Fund", "Asset manager", "MY"),
    ("C021", "Golden Bauhinia Insurance", "Insurer", "HK"),
    ("C022", "Murray River Investment Trust", "Asset manager", "AU"),
    ("C023", "Victoria Peak Quant", "Hedge fund", "HK"),
    ("C024", "Yangtze Delta Fund (QFII)", "Asset manager", "CN"),
    ("S101", "Aldwych Securities Asia", "Street broker", "HK"),
    ("S102", "Brightwater Markets", "Street broker", "SG"),
    ("S103", "Coastline Capital Markets", "Street broker", "AU"),
    ("S104", "Darling Harbour Securities", "Street broker", "AU"),
    ("S105", "Elephanta Securities", "Street broker", "IN"),
    ("S106", "Gyeongbok Securities", "Street broker", "KR"),
    ("S107", "Keelung Securities", "Street broker", "TW"),
    ("S108", "Raffles Quay Securities", "Street broker", "SG"),
    ("S109", "Sha Tin Securities", "Street broker", "HK"),
    ("S110", "Huangpu River Securities", "Street broker", "CN"),
    ("S111", "Klang Valley Securities", "Street broker", "MY"),
    ("S112", "Manly Point Securities", "Street broker", "AU"),
]
COUNTERPARTIES = pd.DataFrame(_CPTY, columns=["counterparty_id", "counterparty_name", "counterparty_type", "domicile"])
COUNTERPARTIES["lei"] = COUNTERPARTIES.counterparty_id.map(lambda c: _lei("cpty:" + c))
COUNTERPARTIES["is_client"] = ~COUNTERPARTIES.counterparty_id.str.startswith("S")

# Instruments by product family (ticker, name, price level in trade currency, contract multiplier)
INSTRUMENTS = {
    "HK_CASH_EQ": [("0700.PRX", "Pearl Tech Holdings", 420.0), ("0005.PRX", "Harbour Bank Group", 72.0),
                   ("0941.PRX", "Pearl Mobile", 80.0), ("1299.PRX", "Bauhinia Life", 61.0),
                   ("3690.PRX", "Kowloon Delivery", 128.0), ("9988.PRX", "Jade Commerce", 96.0),
                   ("0388.PRX", "Pearl River Exchanges & Clearing", 330.0), ("2318.PRX", "Ping Harbour Insurance", 49.0)],
    "CN_CONNECT_EQ": [("600519.SH", "Moutai Spirits (A)", 1530.0), ("300750.SZ", "Ningde Battery (A)", 205.0),
                      ("601318.SH", "Ping Harbour Insurance (A)", 47.0), ("000858.SZ", "Wuliang Spirits (A)", 135.0),
                      ("600036.SH", "Merchants Harbour Bank (A)", 35.0)],
    "SG_CASH_EQ": [("D05.MRX", "Lion City Bank", 38.0), ("O39.MRX", "Straits Banking Corp", 15.5),
                   ("Z74.MRX", "Merlion Telecom", 3.1), ("C6L.MRX", "Merlion Airways", 6.6)],
    "AU_CASH_EQ": [("BHP.SXA", "Broken Hill Resources", 41.0), ("CBA.SXA", "Commonwealth Coastal Bank", 152.0),
                   ("CSL.SXA", "Southern Biologics", 265.0), ("NAB.SXA", "National Southern Bank", 36.0),
                   ("WES.SXA", "Westland Retail", 74.0), ("FMG.SXA", "Pilbara Iron", 19.0)],
    "IN_CASH_EQ": [("RELIANCE.IGX", "Reliant Industries", 2890.0), ("TCS.IGX", "Tata Consulting Systems", 4120.0),
                   ("HDFCBANK.IGX", "Housing Finance Bank", 1680.0), ("INFY.IGX", "Infosys Digital", 1850.0),
                   ("ICICIBANK.IGX", "Indus Credit Bank", 1240.0)],
    "KR_CASH_EQ": [("005930.HRX", "Han River Electronics", 78000.0), ("000660.HRX", "Seoul Semiconductor Works", 185000.0),
                   ("035420.HRX", "Naeil Internet", 205000.0), ("005380.HRX", "Han Motor", 245000.0)],
    "TW_CASH_EQ": [("2330.FMX", "Formosa Semiconductor", 980.0), ("2317.FMX", "Hon Precision", 182.0),
                   ("2454.FMX", "Media Tek Design", 1250.0), ("2308.FMX", "Delta Formosa Electronics", 365.0)],
    "MY_CASH_EQ": [("1155.STX", "Malayan Straits Bank", 10.4), ("1295.STX", "Penang Public Bank", 4.5),
                   ("5347.STX", "Tenaga Straits", 13.8)],
    "PRX50_FUT": [("PRX50 Z26", "PRX 50 Index Futures", 24500.0)],
    "PRX50_MINI_FUT": [("MPRX50 Z26", "Mini PRX 50 Index Futures", 24500.0)],
    "PRXTECH_FUT": [("PRXTECH Z26", "PRX Tech Index Futures", 5400.0)],
    "PRXCEI_FUT": [("PRXCEI Z26", "PRX China Enterprises Index Futures", 8700.0)],
    "PRX_STOCK_OPT": [("0700 C450", "Pearl Tech call options", 12.0), ("9988 P90", "Jade Commerce put options", 4.5)],
    "MRX_CN50_FUT": [("CN50 Z26", "Merlion China 50 Index Futures", 13600.0)],
    "HRX200_FUT": [("HRX200 Z26", "HRX 200 Index Futures", 352.0)],
    "SXA200_FUT": [("SXA200 Z26", "SXA 200 Index Futures", 8250.0)],
    "FMX_IDX_FUT": [("FMXIDX Z26", "Formosa Index Futures", 22100.0)],
    "AU_BOND_FUT": [("YM Z26", "3-year bond futures", 96.2), ("XM Z26", "10-year bond futures", 95.4)],
    "FX_SPOT_NDF": [("USD/SGD", "USD/SGD spot", 1.0), ("USD/KRW NDF", "USD/KRW 1M NDF", 1.0), ("USD/TWD NDF", "USD/TWD 1M NDF", 1.0)],
    "SG_IRS": [("SGD IRS 5Y", "SGD SORA OIS 5Y", 1.0), ("SGD IRS 10Y", "SGD SORA OIS 10Y", 1.0)],
    "USD_CREDIT_BOND": [("HARBNK 5.25 31", "Harbour Bank 5.25% 2031", 101.2), ("PEARL 4.8 29", "Pearl Tech 4.8% 2029", 99.4)],
    "EM_NDF": [("USD/INR NDF", "USD/INR 1M NDF", 1.0), ("USD/IDR NDF", "USD/IDR 1M NDF", 1.0), ("USD/PHP NDF", "USD/PHP 1M NDF", 1.0)],
    "MYR_GOVT_BOND": [("MGS 3.9 33", "Malaysia Government Securities 3.9% 2033", 101.8)],
}
CONTRACT_MULTIPLIER = {"PRX50_FUT": 50, "PRX50_MINI_FUT": 10, "PRXTECH_FUT": 50, "PRXCEI_FUT": 50, "PRX_STOCK_OPT": 100,
                       "MRX_CN50_FUT": 1, "HRX200_FUT": 250000, "SXA200_FUT": 25, "FMX_IDX_FUT": 200, "AU_BOND_FUT": 1000}

# Market holidays (simplified: major closures only)
HOLIDAYS = {
    "ALL": ["2025-12-25", "2026-01-01"],
    "HK": ["2025-10-01", "2025-10-29", "2026-02-17", "2026-02-18", "2026-02-19", "2026-04-03", "2026-04-06", "2026-05-01",
           "2026-06-19", "2026-07-01", "2025-12-26"],
    "CN": ["2025-10-01", "2025-10-02", "2025-10-03", "2025-10-06", "2025-10-07", "2026-02-16", "2026-02-17", "2026-02-18",
           "2026-02-19", "2026-02-20", "2026-05-01", "2026-06-19"],
    "SG": ["2025-10-20", "2026-02-17", "2026-02-18", "2026-04-03", "2026-05-01", "2026-08-10"],
    "AU": ["2025-12-26", "2026-01-26", "2026-04-03", "2026-04-06", "2026-04-27", "2026-06-08"],
    "IN": ["2025-10-02", "2025-10-21", "2025-11-05", "2026-01-26", "2026-03-04", "2026-04-03", "2026-05-01", "2026-08-15"],
    "KR": ["2025-10-03", "2025-10-06", "2025-10-07", "2025-10-09", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-02",
           "2026-05-05", "2026-08-17", "2026-09-24", "2026-09-25"],
    "TW": ["2025-10-06", "2025-10-10", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-04-03", "2026-06-19",
           "2026-09-25"],
    "MY": ["2025-10-20", "2026-02-17", "2026-02-18", "2026-03-20", "2026-05-01", "2026-08-31", "2026-09-16"],
}


def business_days(month: str, market: str) -> list[dt.date]:
    y, m = map(int, month.split("-"))
    d = dt.date(y, m, 1)
    hol = set(HOLIDAYS["ALL"]) | set(HOLIDAYS.get(market, []))
    out = []
    while d.month == m:
        if d.weekday() < 5 and d.isoformat() not in hol:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def add_business_days(d: dt.date, n: int, market: str) -> dt.date:
    hol = set(HOLIDAYS["ALL"]) | set(HOLIDAYS.get(market, []))
    while n > 0:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in hol:
            n -= 1
    return d


SETTLE_CYCLE = {"HK": 2, "CN": 1, "SG": 2, "AU": 2, "IN": 1, "KR": 2, "TW": 2, "MY": 2}


# ── Fiscal calendar (April–March; FY2026/27 = Apr-2026..Mar-2027) ──────────────────────────────────────
def fiscal_attrs(month: str) -> dict:
    y, m = map(int, month.split("-"))
    fy = y if m >= 4 else y - 1
    p = (m - 4) % 12 + 1
    q = (p - 1) // 3 + 1
    return {
        "period": month,
        "calendar_year": y,
        "calendar_month": m,
        "month_label": dt.date(y, m, 1).strftime("%b %Y"),
        "fiscal_year": fy,
        "fiscal_year_label": f"FY{fy}/{str(fy + 1)[-2:]}",
        "fiscal_period_num": p,
        "fiscal_quarter": f"Q{q}",
        "fiscal_quarter_id": f"FY{fy}Q{q}",
        "fiscal_quarter_label": f"FY{fy}/{str(fy + 1)[-2:]} Q{q}",
        "fiscal_half": "H1" if p <= 6 else "H2",
        "fiscal_half_id": f"FY{fy}H{1 if p <= 6 else 2}",
        "is_fiscal_year_end": m == 3,
        "is_half_year_end": m in (3, 9),
    }


def fiscal_calendar() -> pd.DataFrame:
    rows = []
    y, m = 2025, 4
    while (y, m) <= (2027, 3):
        rows.append(fiscal_attrs(f"{y:04d}-{m:02d}"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return pd.DataFrame(rows)
