"""Extraction schema + instructions for fee schedules (shared by the job and local prototyping)."""
from __future__ import annotations

import json

import canonical

FIELD_DOCS = {
    "item_ref": "Item number exactly as printed in the document (e.g. '1.3', 'A.1').",
    "vendor_id": "Code of the entity that levies the charge (use the section heading 'Charges levied by …' or the issuer).",
    "product_family": "Meridian product family code the charge applies to; ALL for fixed monthly charges that are not product specific.",
    "cost_type": "Charge category.",
    "fee_basis": "How the charge is calculated. Percentages of value, basis points and '₹ per crore' are BPS_NOTIONAL; use PER_MILLION_NOTIONAL only when the document says 'per million'.",
    "capacity": "Account capacity the rate applies to.",
    "side": "Trade side the charge applies to: ALL unless the document says buyer only or seller only.",
    "rate": "Numeric rate in the line currency. For BPS_NOTIONAL express in basis points (1% = 100 bps; 0.01% = 1 bp; '₹X per crore' = X/1000 bps). Discounts and rebates are negative numbers.",
    "currency": "ISO currency of the amount.",
    "tier_basis": "Volume measure that determines the tier, NONE if the rate is not tiered.",
    "tier_min": "Lower bound of the tier in full units of the tier basis (US$1.2bn = 1200000000; ₹10,000 crore = 100000000000; 50,000 contracts = 50000). Null if not tiered; 0 for the first tier.",
    "tier_max": "Upper bound of the tier in full units; null when open-ended or not tiered.",
    "tier_type": "UPFRONT if the tier rate is charged directly, REBATE if the difference is credited back, NONE if not tiered.",
    "floor_per_trade": "Explicit minimum charge per trade stated in the document (e.g. 'min HK$2'), in the line currency. Null unless a minimum is printed. Never copy the rate here.",
    "cap_per_trade": "Explicit maximum / cap per trade stated in the document (e.g. 'capped at S$600'), in the line currency. Null unless a cap is printed. Never copy the rate here.",
    "is_pass_through": "True for statutory levies, regulator fees, stamp duty and transaction taxes collected on behalf of a regulator or government.",
    "is_discount_or_waiver": "True for concessions, promotional discounts, rebates and waivers.",
    "gst_rate": "GST/VAT rate charged on this fee as a fraction (9% = 0.09); 0 if none.",
    "effective_from": "First date the rate applies, ISO YYYY-MM-DD.",
    "effective_to": "Last date the rate applies, ISO YYYY-MM-DD; null when 'until further notice'.",
    "legal_entity": "Meridian legal entity a fixed charge is invoiced to; NONE when not stated.",
    "evidence": "The table row text verbatim (max 200 characters).",
}


def extraction_schema() -> dict:
    e = canonical.ENUMS
    props = {
        "item_ref": {"type": "string"},
        "vendor_id": {"type": "enum", "labels": list(canonical.VENDORS.keys())},
        "product_family": {"type": "enum", "labels": list(canonical.PRODUCT_FAMILIES.keys())},
        "cost_type": {"type": "enum", "labels": e["cost_type"]},
        "fee_basis": {"type": "enum", "labels": e["fee_basis"]},
        "capacity": {"type": "enum", "labels": e["capacity"]},
        "side": {"type": "enum", "labels": e["side"]},
        "rate": {"type": "number"},
        "currency": {"type": "enum", "labels": e["currency"]},
        "tier_basis": {"type": "enum", "labels": e["tier_basis"]},
        "tier_min": {"type": "number"},
        "tier_max": {"type": "number"},
        "tier_type": {"type": "enum", "labels": e["tier_type"]},
        "floor_per_trade": {"type": "number"},
        "cap_per_trade": {"type": "number"},
        "is_pass_through": {"type": "boolean"},
        "is_discount_or_waiver": {"type": "boolean"},
        "gst_rate": {"type": "number"},
        "effective_from": {"type": "string"},
        "effective_to": {"type": "string"},
        "legal_entity": {"type": "enum", "labels": e["legal_entity"]},
        "evidence": {"type": "string"},
    }
    for k, v in props.items():
        v["description"] = FIELD_DOCS[k]
    return {
        "fee_lines": {
            "type": "array",
            "description": "One entry per distinct rate in the fee tables and annexes. Each tier, capacity, side and effective period is a separate entry.",
            "items": {"type": "object", "properties": props},
        }
    }


# Local-language aliases from Meridian's product taxonomy (helps map Chinese / Korean product names).
LOCAL_ALIASES = {
    "KR_CASH_EQ": "유가증권시장 주식", "HRX200_FUT": "HRX 200 지수선물", "TW_CASH_EQ": "集中市場股票", "FMX_IDX_FUT": "台股指數期貨",
    "PRX50_FUT": "PRX 50指數期貨", "PRX50_MINI_FUT": "小型PRX 50指數期貨", "PRXTECH_FUT": "PRX科技指數期貨",
    "PRXCEI_FUT": "PRX國企指數期貨", "PRX_STOCK_OPT": "股票期權", "ALL": "會員及連線費用, 회원 및 접속 수수료",
}


def instructions() -> str:
    vendors = "; ".join(f"{k} = {v}" for k, v in canonical.VENDORS.items())
    families = "; ".join(f"{k} = {v}" + (f" ({LOCAL_ALIASES[k]})" if k in LOCAL_ALIASES else "")
                         for k, v in canonical.PRODUCT_FAMILIES.items())
    entities = "; ".join(f"{k} = {v}" for k, v in canonical.LEGAL_ENTITIES.items())
    return (
        "The document is a fee schedule (rate card) issued by an exchange, clearing house or broker to Meridian Group. "
        "Documents may be in English, Traditional Chinese or Korean. Extract every fee, levy, tax, discount, rebate and fixed monthly "
        "charge listed in the fee tables and annexes — one entry per distinct rate. Do NOT extract late-payment interest, billing "
        "terms, settlement-fail penalties that only appear in the notes, GST as a separate entry, or document metadata.\n"
        f"Vendor codes: {vendors}.\n"
        f"Product family codes: {families}.\n"
        f"Meridian legal entities: {entities}.\n"
        "Charges on a broker's schedule (vendors B01–B08) are BROKERAGE (commission), whatever the product.\n"
        "Glossary: 結算 / 結算費 / 청산 = clearing (CLEARING); 交收 / 결제 = settlement (SETTLEMENT); 經手費 / 거래수수료 / 交易所費用 = "
        "exchange or handling fee (EXCHANGE); 徵費 = levy (LEVY); 印花稅 / 證券交易稅 / 증권거래세 = tax (TAX); 莊家 / 시장조성자 = market maker; "
        "每邊 / 편도 = per side; 每口 = per contract.\n"
        "cost_type: EXCHANGE = exchange, trading, handling, access or transaction fees, trading tariff, market-maker concessions and "
        "discounts or volume rebates on exchange fees; CLEARING = clearing or transfer fees; SETTLEMENT = settlement or depository "
        "fees; LEVY = statutory levies, regulator turnover fees, securities management fee; TAX = stamp duty and securities "
        "transaction tax; BROKERAGE = broker commission; FIXED = fixed monthly membership, participantship or connectivity charges.\n"
        "capacity: ALL; NON_MM = house and client accounts excluding registered market makers (自營及客戶賬戶（不包括登記莊家賬戶）, "
        "자기·위탁 계좌(시장조성자 계좌 제외)); MM = registered market-maker accounts (登記莊家賬戶, 시장조성자 계좌); HOUSE; CLIENT; PRINCIPAL.\n"
        "side: ALL unless the charge is buyer only (BUY; 只限買方, 매수자) or seller only (SELL; 只限賣方, 賣方負擔, 매도자).\n"
        "Rates: amounts like 'HK$10.00', '港幣10.00元', '1,800원', '新台幣30元' are 10.00 HKD, 1800 KRW, 30 TWD. Percentages of value are "
        "BPS_NOTIONAL in basis points: move the decimal point two places (0.00565% = 0.565 bps; 0.0001% = 0.01 bps; 0.015% = 0.15 bps; 0.05% = 5 bps; 0.10% = 10 bps; 0.3% = 30 bps; ₹250 per crore = 0.25 bps). Commission is invoiced in the local currency of each "
        "market when the document says so (Korean equities = KRW, Taiwan equities = TWD, Indian equities = INR).\n"
        "legal_entity: set only for FIXED monthly charges invoiced to a named Meridian entity (annex headings); NONE for all other lines. "
        "tier_min / tier_max / tier_type: null, null, NONE when the rate is not tiered.\n"
        "Dates: '1 Mar 2026', '2026年3月1日', '2026년 3월 1일' are 2026-03-01; 'Until further notice', '另行通知前有效', '별도 공지 시까지' mean "
        "effective_to is null."
    )


if __name__ == "__main__":
    print(json.dumps(extraction_schema())[:300])
    print(len(json.dumps(extraction_schema())), "schema chars;", len(instructions()), "instruction chars")
