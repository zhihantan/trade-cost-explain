"""Local tests for the analyst-review matcher: python -m pytest src/extraction/test_review_logic.py (or run directly)."""
from __future__ import annotations

import copy
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import canonical  # noqa: E402
import review_logic as rl  # noqa: E402

YAML = HERE.parent / "datagen" / "config" / "rate_cards.yaml"
NOW = datetime(2026, 10, 22, 9, 0)


def _ext_from_canon(lines):
    out = []
    for i, c in enumerate(lines):
        e = {k: c.get(k) for k in rl.COMPARE}
        e.update(line_index=i, item_ref=f"1.{i + 1}", extraction_confidence=0.95, min_field_confidence=0.9,
                 field_confidence={k: 1.0 for k in rl.COMPARE}, evidence="row", source_language=c.get("source_language"))
        if e["tier_basis"] == "NONE":
            e["tier_min"] = 0.0  # extractor habit: 0 for non-tiered lines — must not count as an error
        if e["cost_type"] != "FIXED":
            e["legal_entity"] = "MSHK"  # extractor habit: entity on variable lines — ignored
        out.append(e)
    return out


def _by_card(card_id):
    return [r for r in canonical.answer_key(canonical.load_yaml(YAML)) if r["card_id"] == card_id]


def test_perfect_extraction_all_matched():
    for card in ("RC02", "RC08", "RC13", "RC06"):
        can = _by_card(card)
        rows = rl.review_card(card, can, _ext_from_canon(can), analyst="a", reviewed_at=NOW)
        assert {r["status"] for r in rows} == {"MATCHED"}, (card, [r for r in rows if r["status"] != "MATCHED"])
        assert len(rows) == len(can)


def test_unit_error_corrected_missing_and_spurious():
    can = _by_card("RC01")
    ext = _ext_from_canon(can)
    trd = next(e for e in ext if e["product_family"] == "HK_CASH_EQ" and e["cost_type"] == "EXCHANGE" and e["fee_basis"] == "BPS_NOTIONAL")
    trd["rate"] = trd["rate"] / 100  # percent left unconverted
    ext = [e for e in ext if not (e["cost_type"] == "LEVY" and abs(e["rate"] - 0.015) < 1e-9)]  # AFRC levy missed
    junk = copy.deepcopy(ext[0])
    junk.update(line_index=99, product_family="ALL", cost_type="FIXED", fee_basis="FIXED_MONTHLY", rate=1.5, vendor_id="PRX",
                effective_from=None, capacity="ALL", side="ALL", currency="USD")  # late-payment interest picked up
    ext.append(junk)
    rows = rl.review_card("RC01", can, ext, analyst="a", reviewed_at=NOW)
    st = {r["fee_id"]: r for r in rows if r["fee_id"]}
    assert st["PRX-SEC-TRD"]["status"] == "CORRECTED" and "unit conversion" in st["PRX-SEC-TRD"]["correction_reason"]
    assert st["PRX-SEC-AFR"]["status"] == "MISSED"
    assert sum(r["status"] == "SPURIOUS" for r in rows) == 1
    assert sum(r["status"] == "MATCHED" for r in rows) == len(can) - 2


def test_effective_periods_not_confused():
    can = _by_card("RC06")
    ext = _ext_from_canon(can)
    for e in ext:  # shuffle order: matching must use dates, not position
        e["line_index"] = 100 - e["line_index"]
    rows = rl.review_card("RC06", can, list(reversed(ext)), analyst="a", reviewed_at=NOW)
    assert {r["status"] for r in rows} == {"MATCHED"}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
