"""Render the canonical rate cards (src/datagen/config/rate_cards.yaml) into realistic fee-schedule PDFs.

Usage (from repo root):
    src/rate_cards/.venv/bin/python src/rate_cards/render.py [--yaml ...] [--out src/rate_cards/out]

Re-runnable: every run rebuilds HTML + PDF from the YAML. Fonts: Latin text uses Helvetica/Times; CJK and Hangul
fall back to a Unicode TrueType font (default /Library/Fonts/Arial Unicode.ttf, override with --cjk-font) that is
embedded (subset) in each PDF so the text stays extractable. All issuers are fictional.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src" / "extraction"))
import canonical  # noqa: E402

# ─────────────────────────────── issuer profiles (fictional) ───────────────────────────────
ISSUERS = {
    "Pearl River Exchanges & Clearing": dict(
        theme="pearl", logo="PR", legal="Pearl River Exchanges & Clearing Limited",
        address="38/F One Harbour Gate, 18 Connaught Road Central, Hong Kong", web="www.pearlriver-exchange.example",
        address_zh="香港中環干諾道中18號 港灣一號38樓", name_zh="珠江交易及結算所有限公司", ref_prefix="PRX/MO"),
    "Merlion Exchange & Merlion Clearing": dict(
        theme="merlion", logo="MX", legal="Merlion Exchange Ltd and Merlion Clearing Pte. Ltd.",
        address="2 Shenton Way, #18-00, Singapore 068804", web="www.merlion-exchange.example", ref_prefix="MRX/FEE"),
    "Southern Cross Exchange Group": dict(
        theme="southern", logo="SX", legal="Southern Cross Exchange Group Limited (ABN 00 000 000 000)",
        address="20 Bridge Street, Sydney NSW 2000, Australia", web="www.southerncross-exchange.example", ref_prefix="SXG/SOF"),
    "Tasman Alternative Market": dict(
        theme="southern", logo="TA", legal="Tasman Alternative Market Pty Ltd",
        address="Level 23, 1 Macquarie Place, Sydney NSW 2000, Australia", web="www.tasman-market.example", ref_prefix="TAM/FS"),
    "Indus Exchange & Indus Clearing Corporation": dict(
        theme="indus", logo="IX", legal="Indus Exchange Limited and Indus Clearing Corporation Limited",
        address="Exchange Plaza, Bandra Kurla Complex, Bandra (East), Mumbai 400 051", web="www.indus-exchange.example",
        ref_prefix="IGX/MSD"),
    "Deccan Exchange": dict(
        theme="indus", logo="DX", legal="Deccan Exchange Limited",
        address="Deccan Towers, Dalal Street, Fort, Mumbai 400 001", web="www.deccan-exchange.example", ref_prefix="DCX/TRD"),
    "Han River Exchange": dict(
        theme="asia", logo="HR", legal="Han River Exchange", name_ko="한강거래소",
        address="76 Yeouinaru-ro, Yeongdeungpo-gu, Seoul, Korea", address_ko="서울특별시 영등포구 여의나루로 76",
        web="www.hanriver-exchange.example", ref_prefix="HRX-FEE"),
    "Formosa Exchange": dict(
        theme="asia", logo="FM", legal="Formosa Exchange Corporation", name_zh="福爾摩沙交易所股份有限公司",
        address="No. 7, Section 5, Xinyi Road, Taipei 110, Taiwan", address_zh="台北市信義路五段7號",
        web="www.formosa-exchange.example", ref_prefix="FMX(交)"),
    "Straits Exchange": dict(
        theme="merlion", logo="ST", legal="Straits Exchange Berhad",
        address="Exchange Square, Bukit Kewangan, 50200 Kuala Lumpur, Malaysia", web="www.straits-exchange.example",
        ref_prefix="STX/PO"),
}
BROKER_ADDRESS = {
    "B01": "Level 41, Two Pacific Place, 88 Queensway, Hong Kong",
    "B02": "12 Marina Boulevard, #30-01, Singapore 018982",
    "B03": "One IFC, 10 Gukjegeumyung-ro, Seoul / 101 Songren Road, Taipei / BKC, Mumbai",
    "B04": "Level 27, 8 Chifley Square, Sydney NSW 2000",
    "B05": "Level 18, Three Garden Road, Central, Hong Kong",
    "B06": "1 Raffles Quay, #25-01, Singapore 048583",
    "B07": "Level 9, 60 Martin Place, Sydney NSW 2000",
    "B08": "Meridian Tower, 1 Harbour View Street, Central, Hong Kong",
}

SECTION_ORDER = ["EXCHANGE", "CLEARING", "SETTLEMENT", "BROKERAGE", "LEVY", "TAX", "FIXED"]

# ─────────────────────────────── localisation ───────────────────────────────
L = {
    "en": dict(
        headers=["Item", "Product / service", "Charge", "Basis", "Applies to", "Rate", "Min / max per trade", "Effective from", "Effective to", "Currency"],
        basis={"PER_CONTRACT_SIDE": "Per contract, per side", "BPS_NOTIONAL": "Value of transaction", "PER_TRADE": "Per transaction",
               "PER_INSTRUCTION": "Per settlement instruction", "PER_MILLION_NOTIONAL": "Per million notional", "FIXED_MONTHLY": "Per month"},
        capacity={"ALL": "All accounts", "NON_MM": "House and client accounts (excl. registered market-maker accounts)",
                  "MM": "Registered market-maker accounts", "HOUSE": "House (principal) accounts", "CLIENT": "Client accounts",
                  "PRINCIPAL": "House and market-maker accounts"},
        side={"ALL": "", "BUY": "Buyer only", "SELL": "Seller only"},
        cost={"EXCHANGE": "Trading / exchange fees", "CLEARING": "Clearing fees", "SETTLEMENT": "Settlement fees", "LEVY": "Statutory levies",
              "TAX": "Stamp duty and transaction taxes", "BROKERAGE": "Commission", "FIXED": "Fixed monthly charges"},
        open="Until further notice", none="—", per_month="per month", per_million="per million", gst="GST",
        min="Min", max="Max", page="Page", of="of", annex="Annex A — Monthly fixed charges invoiced to",
        passthru="Collected on behalf of the regulator / government and passed through to clients at cost.",
        discount="discount", rebate="rebate", effective_note="This schedule is effective for trades executed on or after the dates shown and supersedes previous editions.",
        footer="ILLUSTRATIVE SYNTHETIC DOCUMENT — prepared for the Meridian Group Trade Cost Explain demonstration. The issuer is fictional; rates are modelled on public fee structures and are not actual fees."),
    "zh-Hant": dict(
        headers=["項目", "產品／服務", "收費項目", "計費基準", "適用賬戶", "費率", "每宗最低／最高", "生效日期", "屆滿日期", "貨幣"],
        basis={"PER_CONTRACT_SIDE": "每張合約每邊", "BPS_NOTIONAL": "按成交金額計算", "PER_TRADE": "每宗交易",
               "PER_INSTRUCTION": "每項交收指示", "PER_MILLION_NOTIONAL": "每百萬名義金額", "FIXED_MONTHLY": "每月"},
        capacity={"ALL": "所有賬戶", "NON_MM": "自營及客戶賬戶（不包括登記莊家賬戶）", "MM": "登記莊家賬戶", "HOUSE": "自營賬戶",
                  "CLIENT": "客戶賬戶", "PRINCIPAL": "自營及莊家賬戶"},
        side={"ALL": "", "BUY": "只限買方", "SELL": "只限賣方"},
        cost={"EXCHANGE": "交易所費用", "CLEARING": "結算費", "SETTLEMENT": "交收費", "LEVY": "法定徵費", "TAX": "印花稅及交易稅",
              "BROKERAGE": "佣金", "FIXED": "每月固定費用"},
        open="另行通知前有效", none="—", per_month="每月", per_million="每百萬", gst="商品及服務稅",
        min="最低", max="最高", page="第", of="頁，共", annex="附件甲 — 向以下參與者收取之每月固定費用：",
        passthru="代監管機構／政府收取，並按成本轉嫁予客戶。", discount="優惠", rebate="回贈",
        effective_note="本收費表適用於所示生效日期或之後執行之交易，並取代以往版本。",
        footer="示例合成文件 — 為 Meridian Group 交易成本解析示範而編製。發行機構屬虛構；費率僅參考公開收費結構，並非實際收費。"),
    "ko": dict(
        headers=["항목", "상품／서비스", "수수료 구분", "부과 기준", "적용 대상", "요율", "건당 최저／최고", "적용 시작일", "적용 종료일", "통화"],
        basis={"PER_CONTRACT_SIDE": "계약당·편도", "BPS_NOTIONAL": "거래대금 기준", "PER_TRADE": "거래 건당",
               "PER_INSTRUCTION": "결제지시 건당", "PER_MILLION_NOTIONAL": "명목금액 백만 단위당", "FIXED_MONTHLY": "월정액"},
        capacity={"ALL": "전체 계좌", "NON_MM": "자기·위탁 계좌(시장조성자 계좌 제외)", "MM": "시장조성자 계좌", "HOUSE": "자기매매 계좌",
                  "CLIENT": "위탁 계좌", "PRINCIPAL": "자기·시장조성 계좌"},
        side={"ALL": "", "BUY": "매수자 부담", "SELL": "매도자 부담"},
        cost={"EXCHANGE": "거래수수료", "CLEARING": "청산수수료", "SETTLEMENT": "결제수수료", "LEVY": "법정 부담금", "TAX": "증권거래세",
              "BROKERAGE": "중개수수료", "FIXED": "월정액 수수료"},
        open="별도 공지 시까지", none="—", per_month="월", per_million="백만 단위당", gst="부가가치세",
        min="최저", max="최고", page="페이지", of="/", annex="별첨 — 다음 회원사에 청구되는 월정액 수수료:",
        passthru="정부를 대신하여 징수하며 고객에게 실비로 전가됩니다.", discount="할인", rebate="리베이트",
        effective_note="본 수수료표는 표시된 적용 시작일 이후 체결된 거래부터 적용되며 종전 수수료표를 대체합니다.",
        footer="예시용 합성 문서 — Meridian Group 거래비용 분석 데모용으로 작성되었습니다. 발행 기관은 가상이며, 요율은 공개된 수수료 구조를 참고한 것으로 실제 수수료가 아닙니다."),
}

PRODUCT_NAMES = {
    "en": {
        "HK_CASH_EQ": "Hong Kong equity securities", "CN_CONNECT_EQ": "China A-shares (Northbound Connect)",
        "SG_CASH_EQ": "Singapore securities (cash)", "AU_CASH_EQ": "Australian cash market equities",
        "IN_CASH_EQ": "Indian equities — cash (delivery)", "KR_CASH_EQ": "Korean equities", "TW_CASH_EQ": "Taiwan equities",
        "MY_CASH_EQ": "Malaysian equities", "PRX50_FUT": "PRX 50 Index Futures",
        "PRX50_MINI_FUT": "Mini PRX 50 Index Futures", "PRXTECH_FUT": "PRX Tech Index Futures",
        "PRXCEI_FUT": "PRX China Enterprises Index Futures", "PRX_STOCK_OPT": "Stock Options",
        "MRX_CN50_FUT": "Merlion China 50 Index Futures", "HRX200_FUT": "HRX 200 Index Futures", "SXA200_FUT": "SXA 200 Index Futures",
        "FMX_IDX_FUT": "Formosa Index Futures", "AU_BOND_FUT": "3-Year & 10-Year Treasury Bond Futures", "FX_SPOT_NDF": "FX spot & NDF",
        "SG_IRS": "SGD interest rate swaps", "USD_CREDIT_BOND": "US$ Asian credit bonds", "EM_NDF": "Asian NDFs",
        "MYR_GOVT_BOND": "Malaysia government securities", "ALL": "Membership & connectivity"},
    "zh-Hant": {
        "PRX50_FUT": "PRX 50指數期貨", "PRX50_MINI_FUT": "小型PRX 50指數期貨", "PRXTECH_FUT": "PRX科技指數期貨",
        "PRXCEI_FUT": "PRX國企指數期貨", "PRX_STOCK_OPT": "股票期權", "TW_CASH_EQ": "集中市場股票", "FMX_IDX_FUT": "台股指數期貨",
        "ALL": "會員及連線"},
    "ko": {"KR_CASH_EQ": "유가증권시장 주식", "HRX200_FUT": "HRX 200 지수선물", "ALL": "회원 및 접속"},
}

CCY_SYMBOL = {"HKD": "HK$", "USD": "US$", "SGD": "S$", "AUD": "A$", "INR": "₹", "KRW": "KRW ", "TWD": "NT$", "MYR": "RM", "CNH": "CNH "}
ZERO_DP = {"KRW", "TWD"}

# Per-issuer conventions for basis-point fees (vary the notation so extraction is not templated).
BPS_STYLE = {"SXC": "bps", "B03": "bps", "B05": "bps", "B06": "bps", "B08": "bps", "IGX": "crore", "ICC": "pct"}

MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_date(iso: str | None, lang: str, labels: dict) -> str:
    if not iso:
        return labels["open"]
    d = date.fromisoformat(iso)
    if lang.startswith("zh"):
        return f"{d.year}年{d.month}月{d.day}日"
    if lang == "ko":
        return f"{d.year}년 {d.month}월 {d.day}일"
    return f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}"


def _trim(x: float, min_dp: int = 2, max_dp: int = 6) -> str:
    s = f"{x:.{max_dp}f}".rstrip("0")
    if "." in s:
        whole, frac = s.split(".")
        frac = frac.ljust(min_dp, "0")
        return f"{whole}.{frac}" if frac else whole
    return s + ("." + "0" * min_dp if min_dp else "")


def fmt_money(amount: float, ccy: str, lang: str) -> str:
    neg = amount < 0
    a = abs(amount)
    dp = 0 if (ccy in ZERO_DP and float(a).is_integer()) else 2
    num = f"{a:,.{dp}f}"
    if lang == "ko" and ccy == "KRW":
        s = f"{num}원"
    elif lang.startswith("zh") and ccy == "TWD":
        s = f"新台幣{num}元"
    elif lang.startswith("zh") and ccy == "HKD":
        s = f"港幣{num}元"
    else:
        s = f"{CCY_SYMBOL.get(ccy, ccy + ' ')}{num}"
    return ("− " + s) if neg else s


def fmt_rate(line: dict, lang: str, labels: dict) -> str:
    basis, rate, ccy = line["fee_basis"], line["rate"], line["currency"]
    if basis == "BPS_NOTIONAL":
        style = BPS_STYLE.get(line["vendor_id"], "pct")
        if line["cost_type"] in ("TAX",):
            style = "pct"
        if style == "bps":
            return f"{rate:.1f} bps" if float(rate * 10).is_integer() else f"{_trim(rate, 1, 4)} bps"
        if style == "crore":
            per_crore = rate * 1000
            return f"₹{per_crore:,.0f} per crore ({_trim(rate / 100, 2, 6)}%)"
        return f"{_trim(rate / 100, 2, 6)}%"
    if basis == "PER_MILLION_NOTIONAL":
        return f"{fmt_money(rate, ccy, lang)} {labels['per_million']}"
    if basis == "FIXED_MONTHLY":
        return f"{fmt_money(rate, ccy, lang)} {labels['per_month']}"
    return fmt_money(rate, ccy, lang)


def fmt_minmax(line: dict, lang: str, labels: dict) -> str:
    parts = []
    if line.get("floor_per_trade") is not None:
        parts.append(f"{labels['min']} {fmt_money(line['floor_per_trade'], line['currency'], lang)}")
    if line.get("cap_per_trade") is not None:
        parts.append(f"{labels['max']} {fmt_money(line['cap_per_trade'], line['currency'], lang)}")
    return " / ".join(parts) if parts else labels["none"]


def _crore(x: float) -> str:
    return f"₹{x / 1e7:,.0f} crore"


def fmt_tier(line: dict, lang: str) -> str:
    tb = line.get("tier_basis", "NONE")
    if tb == "NONE":
        return ""
    lo, hi = line.get("tier_min"), line.get("tier_max")
    if tb == "VENDOR_MONTHLY_TURNOVER_USD":
        f = lambda v: f"US${v / 1e9:g}bn"  # noqa: E731
        if (lo or 0) == 0 and hi:
            rng = f"below {f(hi)}"
        elif hi:
            rng = f"{f(lo)} to below {f(hi)}"
        else:
            rng = f"{f(lo)} and above"
        return f"Aggregate monthly turnover {rng}"
    if tb == "MEMBER_MONTHLY_TURNOVER_LCY":
        if (lo or 0) == 0 and hi:
            return f"Member's total monthly turnover up to {_crore(hi)}"
        if hi:
            return f"Member's total monthly turnover above {_crore(lo)} and up to {_crore(hi)}"
        return f"Member's total monthly turnover above {_crore(lo)}"
    if tb == "MEMBER_MONTHLY_CONTRACTS":
        return f"Monthly volume above {lo:,.0f} contracts" + (f" up to {hi:,.0f}" if hi else "")
    return tb


def product_name(pf: str, lang: str) -> str:
    return PRODUCT_NAMES.get(lang, {}).get(pf) or PRODUCT_NAMES["en"].get(pf, pf)


def local_desc(line: dict, lang: str) -> str:
    if lang.startswith("zh") and line.get("desc_zh"):
        return line["desc_zh"]
    if lang == "ko" and line.get("desc_ko"):
        return line["desc_ko"]
    return line["description"]


# ─────────────────────────────── CSS themes ───────────────────────────────
BASE_CSS = """
@font-face { font-family: 'CJKFallback'; src: url('%(cjk)s'); }
@page { size: A4; margin: 20mm 15mm 20mm 15mm;
  @top-right { content: "%(docref)s"; font-family: Helvetica, 'CJKFallback'; font-size: 7.5pt; color: #777; }
  @bottom-left { content: "%(footer_short)s"; font-family: Helvetica, 'CJKFallback'; font-size: 6.5pt; color: #999; }
  @bottom-right { content: counter(page) " / " counter(pages); font-family: Helvetica; font-size: 7.5pt; color: #777; } }
body { font-family: %(font)s, 'CJKFallback', sans-serif; font-size: 9.2pt; color: #1d1d1d; line-height: 1.38; }
h1 { font-size: 16pt; margin: 4mm 0 1mm 0; } h2 { font-size: 11.5pt; margin: 6mm 0 2mm 0; } h3 { font-size: 10pt; margin: 4mm 0 1.5mm 0; }
table.fees { width: 100%%; border-collapse: collapse; margin: 2mm 0 3mm 0; font-size: 8.2pt; }
table.fees th { text-align: left; padding: 4px 5px; vertical-align: bottom; }
table.fees td { padding: 4px 5px; vertical-align: top; }
table.meta { border-collapse: collapse; font-size: 8pt; margin: 2mm 0; } table.meta td { padding: 2px 8px 2px 0; }
.small { font-size: 7.8pt; color: #555; } .note { font-size: 8.2pt; } .rate { white-space: nowrap; font-weight: bold; }
.disclaimer { margin-top: 8mm; font-size: 7pt; color: #888; border-top: 1px solid #ccc; padding-top: 2mm; }
h1, h2, h3 { page-break-after: avoid; } table.fees tr { page-break-inside: avoid; } table.fees { page-break-inside: auto; }
.tag { font-size: 7pt; padding: 1px 4px; border-radius: 3px; background: #eee; color: #444; }
"""

THEMES = {
    "pearl": """
.letterhead { border-bottom: 3px solid #12355b; padding-bottom: 3mm; display: flex; }
.logo { width: 16mm; height: 16mm; background: #12355b; color: white; font-weight: bold; font-size: 15pt; text-align: center; line-height: 16mm; margin-right: 4mm; }
.issuer { font-size: 13pt; color: #12355b; font-weight: bold; } h1 { color: #12355b; } h2 { color: #0f6f7a; border-bottom: 1px solid #b7d4d8; }
table.fees th { background: #12355b; color: white; } table.fees tr:nth-child(even) td { background: #eef4f8; }
""",
    "merlion": """
.letterhead { border-top: 8mm solid #b5121b; padding-top: 3mm; }
.logo { display: inline-block; border: 2px solid #b5121b; color: #b5121b; font-weight: bold; padding: 2mm 3mm; margin-right: 3mm; }
.issuer { font-size: 13pt; font-weight: bold; color: #b5121b; display: inline-block; } h1 { color: #333; } h2 { color: #b5121b; }
table.fees th { border-bottom: 2px solid #b5121b; background: #fbeaea; } table.fees td { border-bottom: 1px solid #e3c2c2; }
""",
    "southern": """
.letterhead { background: #0b4f3c; color: white; padding: 4mm 5mm; }
.logo { display: inline-block; background: #f2c14e; color: #0b4f3c; font-weight: bold; width: 12mm; height: 12mm; text-align: center; line-height: 12mm; margin-right: 3mm; }
.issuer { display: inline-block; font-size: 14pt; font-weight: bold; } .letterhead .small { color: #d7e9e1; } h1 { color: #0b4f3c; } h2 { color: #0b4f3c; border-left: 4px solid #f2c14e; padding-left: 2mm; }
table.fees th { border-top: 1px solid #0b4f3c; border-bottom: 1px solid #0b4f3c; } table.fees td { border-bottom: 0.5px solid #c9d8d2; }
""",
    "indus": """
.letterhead { text-align: center; border-bottom: 2px double #c25e00; padding-bottom: 2mm; }
.logo { display: inline-block; border-radius: 50%%; background: #c25e00; color: white; width: 14mm; height: 14mm; line-height: 14mm; font-weight: bold; }
.issuer { font-size: 14pt; font-weight: bold; color: #7a3b00; } h1 { text-align: center; font-size: 13pt; } h2 { color: #7a3b00; }
.circular { font-size: 9pt; margin: 3mm 0; } table.fees th { background: #fbe3cc; border: 1px solid #d9a679; } table.fees td { border: 1px solid #e8c9ab; }
""",
    "asia": """
.letterhead { border-left: 6mm solid #4b2a7b; padding-left: 4mm; }
.logo { display: inline-block; color: #4b2a7b; font-weight: bold; font-size: 12pt; border: 1.5px solid #4b2a7b; padding: 1mm 2mm; }
.issuer { font-size: 14pt; color: #4b2a7b; font-weight: bold; } .issuer-en { font-size: 9pt; color: #666; } h1 { color: #4b2a7b; } h2 { color: #4b2a7b; }
table.fees th { background: #ece6f5; border-bottom: 1.5px solid #4b2a7b; } table.fees td { border-bottom: 0.5px solid #d6cce6; }
""",
    "broker": """
body { font-size: 9.6pt; } .letterhead { border-bottom: 1px solid #555; padding-bottom: 2mm; }
.logo { display: none; } .issuer { font-size: 15pt; letter-spacing: 1px; text-transform: uppercase; color: #3a2f2a; }
h1 { font-size: 13pt; color: #3a2f2a; } h2 { font-size: 10.5pt; color: #3a2f2a; text-transform: uppercase; letter-spacing: 0.5px; }
table.fees th { border-bottom: 1px solid #3a2f2a; font-style: italic; } table.fees td { border-bottom: 0.4px dotted #999; }
""",
}


def e(s) -> str:
    return html.escape("" if s is None else str(s))


def _issuer_profile(card: dict) -> dict:
    if card["issuer"] in ISSUERS:
        return ISSUERS[card["issuer"]]
    vendor = card["lines"][0]["vendor_id"] if card.get("lines") else None
    name = re.sub(r"\s*\(.*\)$", "", card["issuer"])
    return dict(theme="broker", logo="", legal=name, address=BROKER_ADDRESS.get(vendor, ""), web="", ref_prefix="CS")


def _doc_ref(card: dict, prof: dict) -> str:
    year = card["published"][:4]
    num = int(re.sub(r"\D", "", card["card_id"])) * 37 % 900 + 100
    return f"{prof['ref_prefix']}/{year}/{num}"


def fee_table(lines: list[dict], lang: str, labels: dict, *, show_capacity=True, show_minmax=True, show_gst=False,
              item_prefix="1", vendor_col=False) -> str:
    h = labels["headers"]
    cols = [h[0], h[1], h[2], h[3]] + ([h[4]] if show_capacity else []) + [h[5], h[9]] + ([h[6]] if show_minmax else [])
    if show_gst:
        cols.append(labels["gst"])
    cols += [h[7], h[8]]
    out = ["<table class='fees'><tr>" + "".join(f"<th>{e(c)}</th>" for c in cols) + "</tr>"]
    for i, ln in enumerate(lines, 1):
        applies = labels["capacity"].get(ln["capacity"], ln["capacity"])
        side = labels["side"].get(ln["side"], "")
        tier = fmt_tier(ln, lang)
        cond = "; ".join(x for x in [applies if show_capacity else "", side, tier] if x)
        charge = local_desc(ln, lang)
        if ln["is_discount_or_waiver"]:
            word = labels["rebate"] if ln.get("tier_type") == "REBATE" else labels["discount"]
            charge += f" <span class='tag'>{e(word)}</span>"
        cells = [f"{item_prefix}.{i}", e(product_name(ln["product_family"], lang)), charge, e(labels["basis"][ln["fee_basis"]])]
        if show_capacity:
            cells.append(e(cond))
        elif cond:
            cells[2] += f"<br/><span class='small'>{e(cond)}</span>"
        cells.append(f"<span class='rate'>{e(fmt_rate(ln, lang, labels))}</span>")
        cells.append(e(ln["currency"]))
        if show_minmax:
            cells.append(e(fmt_minmax(ln, lang, labels)))
        if show_gst:
            cells.append(e(f"{ln['gst_rate'] * 100:g}%" if ln["gst_rate"] else "—"))
        cells += [e(fmt_date(ln["effective_from"], lang, labels)), e(fmt_date(ln["effective_to"], lang, labels))]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def fixed_annex(lines: list[dict], lang: str, labels: dict, show_gst: bool = False) -> str:
    if not lines:
        return ""
    by_entity: dict[str, list] = {}
    for ln in lines:
        by_entity.setdefault(ln.get("legal_entity") or "", []).append(ln)
    parts = []
    for ent, lns in by_entity.items():
        ent_name = canonical.LEGAL_ENTITIES.get(ent, ent)
        h = labels["headers"]
        parts.append(f"<h2>{e(labels['annex'])} {e(ent_name)}</h2>")
        hdr = [h[0], h[2], h[5]] + ([labels["gst"]] if show_gst else []) + [h[7], h[8]]
        parts.append("<table class='fees'><tr>" + "".join(f"<th>{e(c)}</th>" for c in hdr) + "</tr>")
        for i, ln in enumerate(lns, 1):
            gst = [e(f"{ln['gst_rate'] * 100:g}%" if ln["gst_rate"] else "Not applicable")] if show_gst else []
            parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in [
                f"A.{i}", e(local_desc(ln, lang)), f"<span class='rate'>{e(fmt_rate(ln, lang, labels))}</span>"] + gst + [
                e(fmt_date(ln["effective_from"], lang, labels)), e(fmt_date(ln["effective_to"], lang, labels))]) + "</tr>")
        parts.append("</table>")
    return "\n".join(parts)


INTRO = {
    "pearl": "This schedule sets out the charges levied by {issuer} on Exchange Participants and Clearing Participants for the products shown. Charges are calculated per side on each transaction unless stated otherwise and are billed monthly in arrears.",
    "merlion": "The following fees apply to trades executed on and cleared through the Merlion markets. Fees are calculated on contract value unless otherwise specified. Members are invoiced monthly; payment is due within 14 days of the invoice date.",
    "southern": "This Schedule of Fees applies to participants of the Southern Cross markets and the associated clearing and settlement facilities. The schedule is reviewed annually and resets on 1 July. All amounts are in Australian dollars.",
    "indus": "Members are hereby notified of the revised schedule of charges applicable to the equity cash segment. Members are requested to take note and ensure that client contract notes reflect statutory charges accurately.",
    "asia": "",
    "broker": "Dear Meridian Group trading desk,\n\nWe are pleased to confirm the commission schedule below, which applies to orders executed by us on your behalf. Commission is invoiced monthly in arrears; invoices are payable within 30 days.",
}
BILLING = {
    "pearl": "Invoices are issued by the 10th business day of the following month. Late payment interest of 1.5% per month applies to overdue amounts. Queries must be raised within 30 days of the invoice date.",
    "merlion": "Fees are subject to periodic review. Merlion may amend this schedule by giving members not less than 30 days' notice.",
    "southern": "Invoices are issued monthly in arrears. Participants must notify Southern Cross of any billing dispute within 20 business days.",
    "indus": "Charges shall be debited to the member's settlement account on the 7th working day of the following month. This circular shall come into force from the dates mentioned against each item.",
    "asia": "",
    "broker": "This schedule supersedes all prior commission agreements for the products listed. Either party may revise the schedule with 30 days' written notice.",
}
ASIA_TEXT = {
    "ko": dict(intro="본 수수료표는 한강거래소 회원에게 부과되는 거래수수료, 청산수수료 및 결제수수료를 안내합니다. 수수료는 매월 말 기준으로 산정하여 익월 10영업일 이내에 청구합니다.",
               billing="연체 시 월 1.5%의 지연이자가 부과됩니다. 이의 신청은 청구일로부터 30일 이내에 하여야 합니다."),
    "zh-Hant": dict(intro="本收費標準適用於本所會員之集中市場及期貨市場交易。各項費用按月結算，並於次月十個營業日內向會員收取。",
                    billing="逾期付款者，按月息1.5%計收遲延利息。會員如有異議，應於帳單日起三十日內提出。"),
}


PEARL_ZH = dict(
    intro="本收費表列載珠江交易及結算所就所示產品向交易所參與者及結算參與者收取之費用。除另有註明外，各項費用按每宗交易每邊計算，並按月於期後收取。",
    billing="發票於次月第十個營業日前發出。逾期款項按月息1.5%計收利息。如對發票有任何查詢，須於發票日期起計三十日內提出。")


def render_card(card: dict, cjk_font_url: str) -> tuple[str, str]:
    lang = card["language"]
    labels = L[lang]
    prof = _issuer_profile(card)
    theme = prof["theme"]
    docref = _doc_ref(card, prof)
    font = "'Times New Roman', Times, serif" if theme == "broker" else "Helvetica, Arial"
    css = BASE_CSS % dict(cjk=cjk_font_url, docref=e(f"{docref} · {card['card_id']}"), font=font,
                          footer_short=("Illustrative — fictional issuer" if lang == "en" else "示例文件 — 虛構機構" if lang.startswith("zh") else "예시 문서 — 가상 기관"))
    css += THEMES[theme]

    lines = card["lines"]
    fixed = [ln for ln in lines if ln["cost_type"] == "FIXED"]
    variable = [ln for ln in lines if ln["cost_type"] != "FIXED"]
    has_gst = any(ln["gst_rate"] for ln in lines)
    vendors = list(dict.fromkeys(ln["vendor_id"] for ln in variable))

    # ── letterhead
    if theme == "asia":
        local_name = prof.get("name_ko") if lang == "ko" else prof.get("name_zh")
        local_addr = prof.get("address_ko") if lang == "ko" else prof.get("address_zh")
        head = (f"<div class='letterhead'><span class='logo'>{e(prof['logo'])}</span> <span class='issuer'>{e(local_name)}</span>"
                f"<div class='issuer-en'>{e(prof['legal'])} · {e(local_addr)} · {e(prof['web'])}</div></div>")
    elif theme == "pearl" and lang.startswith("zh"):
        head = (f"<div class='letterhead'><div class='logo'>{e(prof['logo'])}</div><div><div class='issuer'>{e(prof['name_zh'])}</div>"
                f"<div class='small'>{e(prof['legal'])}<br/>{e(prof['address_zh'])} · {e(prof['web'])}</div></div></div>")
    else:
        head = (f"<div class='letterhead'><div class='logo'>{e(prof['logo'])}</div><div><div class='issuer'>{e(prof['legal'])}</div>"
                f"<div class='small'>{e(prof['address'])}{(' · ' + e(prof['web'])) if prof['web'] else ''}</div></div></div>")

    meta_labels = {"en": ("Document", "Published", "Currency", "Supersedes"),
                   "zh-Hant": ("文件編號", "發佈日期", "貨幣", "取代版本"),
                   "ko": ("문서번호", "발행일", "통화", "대체 문서")}[lang]
    meta = (f"<table class='meta'><tr><td><b>{meta_labels[0]}</b></td><td>{e(docref)}</td><td><b>{meta_labels[1]}</b></td>"
            f"<td>{e(fmt_date(card['published'], lang, labels))}</td><td><b>{meta_labels[2]}</b></td><td>{e(card['currency'])}</td>"
            f"<td><b>{meta_labels[3]}</b></td><td>{e(docref.rsplit('/', 1)[0])}/{int(docref.rsplit('/', 1)[1]) - 11}</td></tr></table>")

    title = e(card["title"])
    subtitle = f"<div class='small'>{e(card['title_en'])}</div>" if card.get("title_en") else ""
    body = [head, f"<h1>{title}</h1>", subtitle, meta]

    if theme == "indus":
        body.append(f"<div class='circular'><b>CIRCULAR</b> &nbsp; Ref: {e(docref)} &nbsp; Date: {e(fmt_date(card['published'], lang, labels))}<br/>"
                    f"To: All Trading Members &nbsp; Subject: {e(card['title'])}</div>")
    if theme == "broker":
        body.append(f"<p class='note'>To: Meridian Group — Procurement and Trading Operations<br/>From: {e(prof['legal'])}, {e(prof['address'])}</p>")

    if theme == "asia" or (theme == "pearl" and lang.startswith("zh")):
        intro = ASIA_TEXT[lang]["intro"] if theme == "asia" else PEARL_ZH["intro"]
    else:
        intro = INTRO[theme].format(issuer=prof["legal"])
    for para in intro.split("\n\n"):
        if para.strip():
            body.append(f"<p class='note'>{e(para)}</p>")
    body.append(f"<p class='small'>{e(labels['effective_note'])}</p>")

    # ── fee sections: by vendor, then by cost type (statutory items separated)
    sec_no = 0
    for vend in vendors:
        vlines = [ln for ln in variable if ln["vendor_id"] == vend]
        if len(vendors) > 1 or theme not in ("broker",):
            vname = canonical.VENDORS.get(vend, vend)
            if lang == "ko":
                body.append(f"<h2>{e(vname)} ({e(vend)}) 수수료</h2>")
            elif lang.startswith("zh"):
                body.append(f"<h2>{e(vname)}（{e(vend)}）收費</h2>")
            else:
                body.append(f"<h2>Charges levied by {e(vname)} ({e(vend)})</h2>")
        for ct in SECTION_ORDER:
            clines = [ln for ln in vlines if ln["cost_type"] == ct]
            if not clines:
                continue
            sec_no += 1
            body.append(f"<h3>{sec_no}. {e(labels['cost'][ct])}</h3>")
            if ct in ("LEVY", "TAX"):
                body.append(f"<p class='small'>{e(labels['passthru'])}</p>")
            show_cap = any(ln["capacity"] != "ALL" for ln in clines) or theme in ("pearl",)
            show_mm = any(ln.get("floor_per_trade") is not None or ln.get("cap_per_trade") is not None for ln in clines)
            body.append(fee_table(clines, lang, labels, show_capacity=show_cap, show_minmax=show_mm, show_gst=has_gst, item_prefix=str(sec_no)))

    # ── notes
    if card.get("notes"):
        nh = {"en": "Notes", "zh-Hant": "附註", "ko": "참고 사항"}[lang]
        body.append(f"<h2>{nh}</h2><ol class='note'>" + "".join(f"<li>{e(n)}</li>" for n in card["notes"]) + "</ol>")
    if has_gst and lang == "en":
        rate = max(ln["gst_rate"] for ln in lines)
        body.append(f"<p class='note'>All fees are quoted exclusive of GST. GST at {rate * 100:g}% is charged only on fees showing a rate in the GST column; fixed charges marked 'Not applicable' are not subject to GST.</p>")

    # ── billing / terms
    billing = (ASIA_TEXT[lang]["billing"] if theme == "asia" else PEARL_ZH["billing"] if (theme == "pearl" and lang.startswith("zh"))
               else BILLING[theme])
    if billing:
        bh = {"en": "Billing and terms", "zh-Hant": "收費及條款", "ko": "청구 및 조건"}[lang]
        body.append(f"<h2>{bh}</h2><p class='note'>{e(billing)}</p>")

    body.append(fixed_annex(fixed, lang, labels, show_gst=has_gst))
    body.append(f"<div class='disclaimer'>{e(labels['footer'])}" + (f"<br/>{e(L['en']['footer'])}" if lang != "en" else "") + "</div>")

    doc = (f"<!DOCTYPE html><html lang='{e(lang)}'><head><meta charset='utf-8'><title>{title}</title><style>{css}</style></head>"
           f"<body>{''.join(body)}</body></html>")
    return doc, docref


def verify_pdf(pdf_path: Path, card: dict) -> dict:
    import pypdf
    reader = pypdf.PdfReader(str(pdf_path))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    lang = card["language"]
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    hangul = sum(1 for ch in text if "가" <= ch <= "힣")
    ok = True
    if lang.startswith("zh") and cjk < 50:
        ok = False
    if lang == "ko" and hangul < 50:
        ok = False
    return dict(card_id=card["card_id"], pages=len(reader.pages), chars=len(text), cjk_chars=cjk, hangul_chars=hangul, text_ok=ok)


def write_eval_questions(doc: dict, out_pdf_dir: Path) -> Path:
    """One grounded question per card (skill convention: pdf_eval_questions.json next to the PDFs)."""
    qs = {}
    for card in canonical.cards(doc):
        lines = [ln for ln in card["lines"] if ln["cost_type"] != "FIXED"] or card["lines"]
        ln = max(lines, key=lambda x: (x["is_discount_or_waiver"], x.get("effective_to") is not None, abs(x["rate"])))
        prod = PRODUCT_NAMES["en"].get(ln["product_family"], ln["product_family"])
        when = f" effective from {ln['effective_from']}" + (f" to {ln['effective_to']}" if ln.get("effective_to") else "")
        qs[card["doc_file"]] = {
            "question": f"In {card['issuer']}'s schedule, what is the {L['en']['cost'][ln['cost_type']].lower()} rate for {prod}"
                        f" ({L['en']['capacity'][ln['capacity']].lower()}){when}?",
            "expected_fact": f"{fmt_rate(ln, 'en', L['en'])} {L['en']['basis'][ln['fee_basis']].lower()} ({ln['fee_id']})",
        }
    path = out_pdf_dir / "pdf_eval_questions.json"
    path.write_text(json.dumps(qs, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_ref_csvs(doc: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    vc_path, fr_path = out_dir / "vendor_contracts.csv", out_dir / "fail_cost_rule.csv"
    vcs = [ln for ln in canonical.approved_lines(doc) if ln["source_doc"] == canonical.CONTRACT_REGISTER_DOC]
    cols = ["fee_id", "vendor_id", "vendor_name", "cost_type", "fee_basis", "product_family", "rate", "currency", "legal_entity",
            "effective_from", "effective_to", "description"]
    with open(vc_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for v in vcs:
            w.writerow({**{k: v.get(k) for k in cols}, "vendor_name": canonical.VENDORS.get(v["vendor_id"])})
    rules = canonical.fail_cost_rules(doc)
    with open(fr_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rules[0].keys()))
        w.writeheader()
        w.writerows(rules)
    return [vc_path, fr_path]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaml", default=str(REPO / "src" / "datagen" / "config" / "rate_cards.yaml"))
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--cjk-font", default="/Library/Fonts/Arial Unicode.ttf")
    ap.add_argument("--only", nargs="*", help="card ids to render")
    args = ap.parse_args()

    import plutoprint

    doc = canonical.load_yaml(args.yaml)
    out = Path(args.out)
    (out / "html").mkdir(parents=True, exist_ok=True)
    (out / "pdf").mkdir(parents=True, exist_ok=True)
    font_url = Path(args.cjk_font).resolve().as_uri()
    report = []
    for card in canonical.cards(doc):
        if args.only and card["card_id"] not in args.only:
            continue
        html_doc, docref = render_card(card, font_url)
        html_path = out / "html" / card["doc_file"].replace(".pdf", ".html")
        html_path.write_text(html_doc, encoding="utf-8")
        pdf_path = out / "pdf" / card["doc_file"]
        book = plutoprint.Book(plutoprint.PAGE_SIZE_A4)
        book.load_html(html_doc, base_url=html_path.parent.resolve().as_uri() + "/")
        book.set_metadata(plutoprint.PDF_METADATA_TITLE, card["title"])
        book.set_metadata(plutoprint.PDF_METADATA_AUTHOR, card["issuer"])
        book.set_metadata(plutoprint.PDF_METADATA_SUBJECT, f"{docref} — illustrative fee schedule (fictional issuer)")
        book.set_metadata(plutoprint.PDF_METADATA_KEYWORDS, f"{card['card_id']}; fee schedule; synthetic")
        book.write_to_pdf(str(pdf_path))
        info = verify_pdf(pdf_path, card)
        info.update(doc_file=card["doc_file"], language=card["language"], lines=len(card["lines"]), bytes=pdf_path.stat().st_size)
        report.append(info)
        print(json.dumps(info, ensure_ascii=False))
    refs = write_ref_csvs(doc, out / "ref")
    write_eval_questions(doc, out / "pdf")
    (out / "render_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    bad = [r for r in report if not r["text_ok"]]
    print(f"rendered={len(report)} text_check_failures={len(bad)} refs={[str(p) for p in refs]}")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
