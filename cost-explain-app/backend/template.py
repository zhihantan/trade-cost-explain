"""Deterministic commentary drafter built only from registry figures.

Used when the agent endpoint is unavailable (graceful degradation) and for local development. Every number in
the text is a chip `[[fig:<figure_key>]]`, so it can be traced back to Gold.
"""
from __future__ import annotations

import re
from typing import Optional

from .models import Figure

CHIP_RE = re.compile(r"\[\[fig:([^\]\[\n]{3,200})\]\]")


def usd(v: float, signed: bool = False) -> str:
    a = abs(v)
    sign = "−" if v < 0 else ("+" if signed and v > 0 else "")
    if a >= 995_000:
        body = f"US${a / 1e6:.2f}M"
    elif a >= 1_000:
        k = round(a / 1e3, 1)  # one decimal below US$100K so e.g. a US$25.5K threshold isn't shown as US$26K
        body = f"US${k:,.1f}K" if a < 100_000 and k != int(k) else f"US${a / 1e3:,.0f}K"
    else:
        body = f"US${a:,.0f}"
    return sign + body


def pct(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.0f}%" if abs(v) <= 1.5 else f"{v:.0f}%"


def chip_keys(text: str) -> list[str]:
    seen, out = set(), []
    for k in CHIP_RE.findall(text or ""):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def draft(comparison: dict, slice_key: str, slice_label: str, figs: dict[str, Figure]) -> str:
    cid = comparison["comparison_id"]

    def f(scope: str, metric: str) -> Optional[Figure]:
        return figs.get(f"{cid}|{scope}|{metric}")

    def chip(scope: str, metric: str) -> str:
        return f"[[fig:{cid}|{scope}|{metric}]]"

    p0, p1, flux = f(slice_key, "P0"), f(slice_key, "P1"), f(slice_key, "FLUX")
    if not (p0 and p1 and flux and p0.value is not None and p1.value is not None and flux.value is not None):
        return f"No published figures are available for {slice_label} ({cid})."
    pct_fig = f(slice_key, "FLUX_PCT")
    direction = "rose" if flux.value >= 0 else "fell"
    lines = [
        f"**{comparison['p1_label']} close — {slice_label} trade costs**",
        "",
        f"Net borne trade costs {direction} **{usd(abs(flux.value))}"
        f"{' (' + ('+' if flux.value >= 0 else '−') + pct(abs(pct_fig.value)) + ')' if pct_fig and pct_fig.value is not None else ''}** "
        f"{chip(slice_key, 'FLUX')} to {usd(p1.value)} {chip(slice_key, 'P1')} from {usd(p0.value)} "
        f"{chip(slice_key, 'P0')} in {comparison['p0_label']}.",
        "",
    ]
    rows = [  # scene-2 narrative order (CONTRACTS effect_order)
        ("VOLUME", "Volume (good flux)", "activity-driven; expected to be matched by revenue"),
        ("MIX", "Mix", "controllable: venue, capacity and product routing"),
        ("RATE", "Rate", "fee schedule, levy and discount changes"),
        ("FAILS", "Settlement fails", "controllable: Operations fix list"),
        ("TIMING", "Timing / accrual", "accrual true-ups and reversals"),
        ("FX", "FX", "translation of local-currency costs to US$"),
        ("FIXED", "Fixed fees", "participant, access and connectivity"),
        ("UNEXPLAINED", "Unexplained", "residual, monitored against the threshold"),
    ]
    for metric, label, why in rows:
        fig = f(slice_key, metric)
        if fig is None or fig.value is None or abs(fig.value) < 500:
            continue
        share = ""
        if metric == "VOLUME":
            g = f(slice_key, "GOOD_PCT")
            share = f" — {pct(g.value)} of the movement" if g and g.value is not None else ""
        if metric == "UNEXPLAINED":
            th = f(slice_key, "UNEXPLAINED_THRESHOLD")
            if th and th.value is not None:
                verdict = "within" if abs(fig.value) <= th.value else "above"
                why = f"residual, {verdict} the {usd(th.value)} threshold {chip(slice_key, 'UNEXPLAINED_THRESHOLD')}"
        lines.append(f"- **{label}: {usd(fig.value, signed=True)}** {chip(slice_key, metric)}{share} ({why}).")
    ctrl, ctrl_pct = f(slice_key, "CONTROLLABLE"), f(slice_key, "CONTROLLABLE_PCT")
    if ctrl and ctrl.value is not None:
        lines += ["", f"**Controllable flux (mix + fails): {usd(ctrl.value)}"
                      f"{' (' + pct(ctrl_pct.value) + ')' if ctrl_pct and ctrl_pct.value is not None else ''}** "
                      f"{chip(slice_key, 'CONTROLLABLE')}."]
    if slice_key == "APAC":
        ed = f("ED_EXCH_CLR", "FLUX")
        if ed and ed.value is not None:
            lines.append(f"Equity Derivatives exchange & clearing fees contributed {usd(ed.value, signed=True)} "
                         f"{chip('ED_EXCH_CLR', 'FLUX')}.")
    hotspots = sorted((k for k in figs if k.startswith("FAILS|") and k.endswith("|NET")),
                      key=lambda k: -(figs[k].value or 0))
    if hotspots and (figs[hotspots[0]].value or 0) >= 1_000 and slice_key in ("APAC", "REST", "BUS:CEQ", "DESK:AUCE"):
        hf = figs[hotspots[0]]
        lines.append(f"Largest fail hotspot: {hf.scope_label or 'one counterparty'}, {usd(hf.value)} net "
                     f"[[fig:{hotspots[0]}]].")
    # Invoice findings are division-level (vendors span desks): only cite them in APAC / Rest-of-APAC commentary.
    findings = [k for k in figs if k.startswith("INV|") and k.endswith("|VARIANCE")] if slice_key in ("APAC", "REST") else []
    for k in sorted(findings, key=lambda k: -abs(figs[k].value or 0)):
        fig = figs[k]
        if fig.value and fig.value >= 10_000:
            desc = fig.description or ""
            reason = desc.rsplit(": ", 1)[-1] if ": " in desc else "invoice reconciliation"
            lines += ["", f"Separately, {fig.scope_label or 'a vendor'} billed {usd(fig.value)} above expected cost "
                          f"[[fig:{k}]] ({reason}); this sits outside the {comparison['p1_label']} bridge."]
    return "\n".join(lines).strip()
