"""Demo seed: approved history for July and August, and the September APAC commentary awaiting approval.

Seeded items are authored by a fictional analyst so the presenter (an approver) can approve them without
breaching the four-eyes control. Figures come from the live registry when a user context is available
(so Delta versions are real), otherwise from the fixtures.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import fixtures, gold, repo, template
from .auth import User
from .models import Figure

log = logging.getLogger("cost_explain.seed")

ANALYST = "ava.chen@meridian-demo.example"
APPROVER = "priya.raman@meridian-demo.example"
MODEL = "databricks-claude-sonnet-5-5"


def _t(s: str) -> datetime:  # timestamps are written in UTC (SGT − 8h)
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


SEP_TEXT = """**September close — APAC Global Markets trade costs**

Net borne trade costs rose **US$1.20M (+24%)** [[fig:MOM_2026-09|APAC|FLUX]] to US$6.20M [[fig:MOM_2026-09|APAC|P1]] from US$5.00M [[fig:MOM_2026-09|APAC|P0]] in August.

- **Volume (good flux): +US$900K** [[fig:MOM_2026-09|APAC|VOLUME]] — 75% of the increase [[fig:MOM_2026-09|APAC|GOOD_PCT]]. Activity rose with the mid-September volatility spike; listed-derivative contracts were up about 18% and cash turnover rose in Hong Kong, Australia and India, matched by higher revenue.
- **Mix: +US$190K** [[fig:MOM_2026-09|APAC|MIX]] — controllable. Australian cash flow was routed to the higher-fee primary venue after the smart-order-router change, and Hong Kong index futures were booked in the house account rather than the market-maker account.
- **Rate: +US$100K** [[fig:MOM_2026-09|APAC|RATE]] — the PRX Tech Index futures discount ended on 31 August, and Indus Exchange moved to a uniform transaction charge on 1 September.
- **Settlement fails: +US$150K** [[fig:MOM_2026-09|APAC|FAILS]] — concentrated in Australia cash equities with one counterparty, Kestrel Asset Management (US$143K net [[fig:FAILS|2026-09|AUCE|C001|NET]], SSI static-data mismatch); Operations has the ranked fix list.
- **Timing: −US$50K** [[fig:MOM_2026-09|APAC|TIMING]] — reversal of the August accrual over-estimate; September accruals are now set at expected cost.
- **FX: −US$100K** [[fig:MOM_2026-09|APAC|FX]] — AUD, KRW, INR and TWD weaker against the US$.
- **Unexplained: +US$10K** [[fig:MOM_2026-09|APAC|UNEXPLAINED]] — GL from two vendors not yet mapped; well within the unexplained threshold [[fig:MOM_2026-09|APAC|UNEXPLAINED_THRESHOLD]] (greater of US$25K and 5% of the change).

**Controllable flux (mix + fails): US$340K (28%)** [[fig:MOM_2026-09|APAC|CONTROLLABLE]]. Equity Derivatives exchange & clearing fees contributed +US$510K [[fig:MOM_2026-09|ED_EXCH_CLR|FLUX]].

Separately, Broker C's August invoice is US$85K above expected cost [[fig:INV|2026-08|B03|VARIANCE]] (missed volume-tier rebate); a billing claim has been raised and it is excluded from the September bridge."""


def _figs(user: Optional[User], keys: list[str]) -> list[dict]:
    reg = fixtures.figure_registry()
    live: dict[str, Figure] = {}
    if user is not None:
        try:
            live = gold.figures_by_keys(user, keys)
        except Exception as exc:
            log.info("live figure lookup failed (%s); using fixtures", type(exc).__name__)
    out = []
    for k in keys:
        fig: Optional[Figure] = live.get(k)
        if fig is None and k in reg:
            r = reg[k]
            fig = Figure(figure_key=k, label=r["metric_label"], value=r["value"], unit=r["unit"],
                         source_table=r["source_table"], filter=r["filter_expr"], mode="fixtures")
        if fig is not None:
            out.append({"figure_key": k, "label": fig.label, "value": fig.value, "unit": fig.unit,
                        "source_table": fig.source_table, "filter": fig.filter, "delta_version": fig.delta_version,
                        "as_of_ts": fig.as_of_ts, "snapshot_ref": fig.snapshot_ref})
    return out


def _history_item(cid: str, comp: dict, approved_on: str, user: Optional[User]) -> dict:
    """Historical items are drafted by the template from the live registry when a user context is available, so the
    text and the figure snapshot always agree with Gold."""
    figs_for: dict[str, Figure] = {}
    if user is not None:
        try:
            figs_for = gold.figures_for(user, cid, "APAC", comp["period_p0"], comp["period_p1"])
        except Exception as exc:
            log.info("live figures unavailable for %s (%s); using fixtures", cid, type(exc).__name__)
    if not figs_for:
        figs_for = {k: Figure(figure_key=k, label=r["metric_label"], value=r["value"], unit=r["unit"],
                              source_table=r["source_table"], filter=r["filter_expr"], scope_label=r["scope_label"],
                              description=r["description"], mode="fixtures")
                    for k, r in fixtures.figure_registry().items() if r.get("comparison_id") == cid
                    and r.get("scope_key") in ("APAC", "ED_EXCH_CLR", "REST")}
    text = template.draft(comp, "APAC", "APAC Global Markets", figs_for)
    keys = template.chip_keys(text)
    d = approved_on
    return _item(cid, f"{comp['p1_label']} close — APAC Global Markets", "approved", text, keys, user, [
        ("created", 1, ANALYST, f"{d}T00:40:00", None, "draft", None),
        ("drafted", 2, ANALYST, f"{d}T00:41:30", "draft", "draft", f"model={MODEL}"),
        ("edited", 3, ANALYST, f"{d}T01:15:00", "draft", "draft", None),
        ("submitted", 3, ANALYST, f"{d}T01:20:00", "draft", "in_review", None),
        ("approved", 3, APPROVER, f"{d}T06:05:00", "in_review", "approved", "Agreed with desk heads. Approved for the CFO pack."),
    ])


def _item(period: str, title: str, status: str, text: str, keys: list[str], user: Optional[User],
          events: list[tuple]) -> dict:
    cid = uuid.uuid4()
    final_v = max(e[1] for e in events)
    figs = _figs(user, keys)
    created = _t(events[0][3])
    last = _t(events[-1][3])
    submitted = next((_t(e[3]) for e in events if e[0] == "submitted"), None)
    decided = next((_t(e[3]) for e in events if e[0] in ("approved", "rejected")), None)
    decider = next((e[2] for e in events if e[0] in ("approved", "rejected")), None)
    note = next((e[6] for e in events if e[0] in ("approved", "rejected")), None)
    return {
        "commentary": dict(id=cid, period=period, slice_key="APAC", title=title, version=final_v, status=status,
                           draft_text=text, edited_text=text, author_email=ANALYST, last_edited_by=ANALYST,
                           submitted_by=ANALYST if submitted else None, decided_by=decider, decision_note=note,
                           drafted_by_model=MODEL, created_at=created, updated_at=last, submitted_at=submitted,
                           decided_at=decided),
        "versions": [dict(version=1, text=None, change_type="created", actor_email=ANALYST, created_at=created),
                     dict(version=2, text=text, change_type=f"drafted:{MODEL}", actor_email=ANALYST,
                          created_at=_t(events[1][3])),
                     dict(version=3, text=text, change_type="edited", actor_email=ANALYST,
                          created_at=_t(events[2][3]))],
        "figures": {2: figs, 3: figs},
        "figures_captured_at": {2: _t(events[1][3]), 3: _t(events[2][3])},
        "events": [dict(action=a, version=v, actor_email=who, created_at=_t(ts), from_status=fs, to_status=ts2,
                        note=n, request_id=f"seed-{period}-{a}") for a, v, who, ts, fs, ts2, n in events],
    }


async def seed(user: Optional[User] = None, force: bool = False) -> int:
    if not force and await repo.count() > 0:
        return 0
    comps = {c["comparison_id"]: c for c in fixtures.comparisons()}
    if user is not None:
        try:
            comps.update({c.comparison_id: c.model_dump() for c in gold.comparisons(user)})
        except Exception as exc:
            log.info("live comparisons unavailable (%s); using fixtures", type(exc).__name__)
    items = [
        _history_item("MOM_2026-07", comps["MOM_2026-07"], "2026-08-05", user),
        _history_item("MOM_2026-08", comps["MOM_2026-08"], "2026-09-03", user),
        _item("MOM_2026-09", "September close — APAC Global Markets", "in_review", SEP_TEXT,
              template.chip_keys(SEP_TEXT), user, [
                  ("created", 1, ANALYST, "2026-10-05T00:30:00", None, "draft", None),
                  ("drafted", 2, ANALYST, "2026-10-05T00:31:10", "draft", "draft", f"model={MODEL}"),
                  ("edited", 3, ANALYST, "2026-10-05T01:05:00", "draft", "draft", None),
                  ("submitted", 3, ANALYST, "2026-10-05T01:12:00", "draft", "in_review",
                   "Ready for review — desk heads briefed on the AU routing change."),
              ]),
    ]
    for it in items:
        await repo.insert_seed(it)
    log.info("seeded %s demo commentary items", len(items))
    return len(items)
