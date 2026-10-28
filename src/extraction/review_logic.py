"""Simulated analyst review: match extracted fee lines to the document's canonical lines (pure Python, unit-testable)."""
from __future__ import annotations

import math

COMPARE = ["vendor_id", "product_family", "cost_type", "fee_basis", "capacity", "side", "rate", "currency", "tier_basis",
           "tier_min", "tier_max", "tier_type", "floor_per_trade", "cap_per_trade", "is_pass_through",
           "is_discount_or_waiver", "gst_rate", "effective_from", "effective_to", "legal_entity"]
NUMERIC = {"rate", "tier_min", "tier_max", "floor_per_trade", "cap_per_trade", "gst_rate"}
MIN_MATCH_SCORE = 8


def _missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def num_eq(a, b) -> bool:
    if _missing(a) or _missing(b):
        return _missing(a) and _missing(b)
    return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-9)


def norm_extracted(e: dict) -> dict:
    e = dict(e)
    for k in ("effective_from", "effective_to"):
        if e.get(k) is not None and not isinstance(e[k], str):
            e[k] = e[k].isoformat()
    if (e.get("tier_basis") or "NONE") == "NONE":
        e["tier_basis"], e["tier_min"], e["tier_max"], e["tier_type"] = "NONE", None, None, "NONE"
    if e.get("cost_type") != "FIXED" or e.get("legal_entity") == "NONE":
        e["legal_entity"] = None  # entity only matters for fixed monthly charges
    for k in ("floor_per_trade", "cap_per_trade"):
        if not _missing(e.get(k)) and float(e[k]) == 0.0:
            e[k] = None
    for k in ("side", "capacity"):
        if not e.get(k):
            e[k] = "ALL"
    if _missing(e.get("gst_rate")):
        e["gst_rate"] = 0.0
    for k in ("is_pass_through", "is_discount_or_waiver"):
        if e.get(k) is None:
            e[k] = False
    return e


def norm_canonical(c: dict) -> dict:
    c = dict(c)
    if (c.get("tier_basis") or "NONE") == "NONE":
        c["tier_basis"], c["tier_min"], c["tier_max"], c["tier_type"] = "NONE", None, None, "NONE"
    if c.get("cost_type") != "FIXED":
        c["legal_entity"] = None
    return c


def field_eq(f: str, a, b) -> bool:
    if f in NUMERIC:
        return num_eq(a, b)
    return (a or None) == (b or None)


def score(c: dict, e: dict) -> float:
    s = 0.0
    s += 5 if c["product_family"] == e.get("product_family") else 0
    s += 4 if c["cost_type"] == e.get("cost_type") else 0
    s += 3 if num_eq(c["rate"], e.get("rate")) else 0
    s += 2 if c["capacity"] == e.get("capacity") else 0
    s += 1 if c["fee_basis"] == e.get("fee_basis") else 0
    s += 1 if c["side"] == e.get("side") else 0
    s += 1 if c["vendor_id"] == e.get("vendor_id") else 0
    s += 1 if c.get("effective_from") == e.get("effective_from") else 0
    s += 1 if c.get("effective_to") == e.get("effective_to") else 0
    s += 1 if num_eq(c.get("tier_min"), e.get("tier_min")) else 0
    s += 1 if c.get("currency") == e.get("currency") else 0
    return s


def explain(f: str, ext, can) -> str:
    if f == "rate" and not _missing(ext) and not _missing(can) and float(can) != 0 and not num_eq(ext, can):
        ratio = float(ext) / float(can)
        if any(math.isclose(ratio, r, rel_tol=1e-6) for r in (0.01, 100.0, 0.001, 1000.0, 1e-4, 1e4)):
            return f"rate {float(ext):g} → {float(can):g} (unit conversion)"
        if any(math.isclose(ratio, r, rel_tol=1e-6) for r in (0.1, 10.0)):
            return f"rate {float(ext):g} → {float(can):g} (decimal-place error)"
        if math.isclose(ratio, -1.0, rel_tol=1e-6):
            return f"rate {float(ext):g} → {float(can):g} (sign of discount/rebate)"
    return f"{f}: {ext!r} → {can!r}"


def review_card(card_id: str, can_lines: list[dict], ext_lines: list[dict], *, analyst: str, reviewed_at,
                is_cross_language_copy: bool = False) -> list[dict]:
    """Greedy best-score assignment of extracted → canonical lines, then field-level comparison."""
    nc = [norm_canonical(c) for c in can_lines]
    ne = [norm_extracted(e) for e in ext_lines]
    pairs = sorted(((score(c, e), i, j) for i, c in enumerate(nc) for j, e in enumerate(ne)), key=lambda t: (-t[0], t[1], t[2]))
    used_c, used_e, match = set(), set(), {}
    for s, i, j in pairs:
        if s < MIN_MATCH_SCORE or i in used_c or j in used_e:
            continue
        used_c.add(i)
        used_e.add(j)
        match[i] = (j, s)
    out = []
    for i, c in enumerate(nc):
        src = can_lines[i]
        base = dict(card_id=card_id, fee_id=src["fee_id"], source_language=src.get("source_language"),
                    is_cross_language_copy=bool(src.get("is_cross_language_copy", is_cross_language_copy)),
                    reviewed_at=reviewed_at, analyst=analyst)
        if i in match:
            j, s = match[i]
            e, raw = ne[j], ext_lines[j]
            conf = raw.get("field_confidence") or {}
            comps, bad = [], []
            for f in COMPARE:
                ok = field_eq(f, e.get(f), c.get(f))
                comps.append(dict(field=f, canonical_value=None if c.get(f) is None else str(c.get(f)),
                                  extracted_value=None if e.get(f) is None else str(e.get(f)), is_match=bool(ok),
                                  confidence=conf.get(f)))
                if not ok:
                    bad.append(f)
            out.append({**base, "line_index": int(raw["line_index"]), "item_ref": raw.get("item_ref"),
                        "status": "CORRECTED" if bad else "MATCHED", "match_score": float(s), "mismatched_fields": bad,
                        "field_comparison": comps, "extraction_confidence": raw.get("extraction_confidence"),
                        "min_field_confidence": raw.get("min_field_confidence"), "evidence": raw.get("evidence"),
                        "corrected_by": analyst if bad else None,
                        "correction_reason": "; ".join(explain(f, e.get(f), c.get(f)) for f in bad) if bad else None})
        else:
            out.append({**base, "line_index": None, "item_ref": None, "status": "MISSED", "match_score": None,
                        "mismatched_fields": [], "field_comparison": [], "extraction_confidence": None,
                        "min_field_confidence": None, "evidence": None, "corrected_by": analyst,
                        "correction_reason": "Line not extracted — added manually from the source document"})
    for j, raw in enumerate(ext_lines):
        if j in used_e:
            continue
        out.append(dict(card_id=card_id, fee_id=None, source_language=raw.get("source_language"),
                        is_cross_language_copy=is_cross_language_copy, line_index=int(raw["line_index"]),
                        item_ref=raw.get("item_ref"), status="SPURIOUS", match_score=None, mismatched_fields=[],
                        field_comparison=[], extraction_confidence=raw.get("extraction_confidence"),
                        min_field_confidence=raw.get("min_field_confidence"), evidence=raw.get("evidence"),
                        corrected_by=analyst, correction_reason="Extracted line does not correspond to a fee in the document — rejected",
                        reviewed_at=reviewed_at, analyst=analyst))
    return out
