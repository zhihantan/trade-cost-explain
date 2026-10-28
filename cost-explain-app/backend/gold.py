"""Reads from Gold (as the signed-in user) or from fixtures.

`DATA_MODE=auto` falls back to fixtures only when a Gold object does not exist yet. Permission errors always
surface; the app never substitutes data a user is not entitled to see.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional, TypeVar

from fastapi import HTTPException

from . import db_sql, fixtures
from .auth import User
from .config import get_settings
from .models import (Comparison, DataSource, Effect, Figure, FluxResponse, FluxRow, FluxTotals, SliceOption,
                     check_comparison, check_slice)

log = logging.getLogger("cost_explain.gold")

# Scene-2 narrative order — mirrors gold.cost_flux_effects.effect_order (docs/CONTRACTS.md §2).
EFFECTS = [("VOLUME", "Volume", 1, "Good (volume-driven)"), ("MIX", "Mix", 2, "Controllable"),
           ("RATE", "Rate", 3, "External, timing & residual"), ("FAILS", "Fails", 4, "Controllable"),
           ("TIMING", "Timing / accrual", 5, "External, timing & residual"),
           ("FX", "FX", 6, "External, timing & residual"), ("FIXED", "Fixed fees", 7, "External, timing & residual"),
           ("UNEXPLAINED", "Unexplained", 8, "External, timing & residual")]
MEASURES = ["p0", "p1", "p1_cc", "volume", "mix", "rate", "fx", "fails", "fixed", "timing", "unexplained", "flux"]
BREAKDOWNS = {"business": "business", "desk": "desk_name", "cost_category": "cost_category",
              "cost_type": "cost_type", "vendor": "vendor_name", "market": "market",
              "legal_entity": "legal_entity_name", "currency": "currency"}
DEFAULT_BREAKDOWN = {"APAC": "business", "ED_EXCH_CLR": "vendor", "REST": "business"}


def _gold(name: str) -> str:
    return db_sql.safe_table(f"{get_settings().gold_schema}.{name}")


def slice_predicate(slice_key: str) -> tuple[str, dict]:
    check_slice(slice_key)
    if slice_key == "APAC":
        return "TRUE", {}
    if slice_key == "ED_EXCH_CLR":
        return "business_code = 'EQD' AND cost_category = 'Exchange & clearing'", {}
    if slice_key == "REST":
        return "NOT (business_code = 'EQD' AND cost_category = 'Exchange & clearing')", {}
    kind, code = slice_key.split(":", 1)
    return ("business_code = :slice_code" if kind == "BUS" else "desk_code = :slice_code"), {"slice_code": code}


def _mode() -> str:
    return get_settings().data_mode


def _fallback(exc: Exception):
    if _mode() == "live":
        raise HTTPException(status_code=503, detail="Gold tables are not available yet") from None
    log.info("Gold object missing; serving fixtures (%s)", str(exc)[:120])


# ------------------------------------------------------------------ per-user read cache
# Gold only changes when the pipeline refreshes, but every warehouse round trip costs seconds (more when the
# warehouse is waking up). Results are cached per signed-in user — row filters make them identity-specific —
# and only successful reads are kept. Concurrent requests for the same entry share one load.
T = TypeVar("T")
COMPARISONS_TTL_S, SLICES_TTL_S, FLUX_TTL_S, FIGURE_TTL_S = 600, 600, 120, 120
_cache: dict[tuple, tuple[float, object]] = {}
_inflight: dict[tuple, Future] = {}
_clock = threading.Lock()
_io = ThreadPoolExecutor(max_workers=8, thread_name_prefix="gold-io")  # overlaps independent lookups


def _cached(user: User, key: tuple, ttl: float, load: Callable[[], T]) -> T:
    k = (user.email, *key)
    with _clock:
        hit = _cache.get(k)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]  # type: ignore[return-value]
        pending = _inflight.get(k)
        if pending is None:
            _inflight[k] = mine = Future()
    if pending is not None:
        return pending.result()  # re-raises the loader's error
    try:
        value = load()
    except BaseException as exc:
        with _clock:
            _inflight.pop(k, None)
        mine.set_exception(exc)
        raise
    with _clock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[k] = (time.time(), value)
        _inflight.pop(k, None)
    mine.set_result(value)
    return value


# ------------------------------------------------------------------ data snapshot of a source table
_versions: dict[str, tuple[float, Optional[int], Optional[str], Optional[str]]] = {}
_vlock = threading.Lock()
_not_delta: set[str] = set()  # pipeline materialized views: DESCRIBE HISTORY always fails, so skip that round trip
_UPDATE_RE = re.compile(r"/pipelines/([0-9a-f-]{36})/updates/([0-9a-f-]{36})")


def table_version(user: User, table: str) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """(delta_version, as_of_ts, snapshot_ref). Delta tables answer DESCRIBE HISTORY; pipeline materialized views
    don't, so for those the snapshot is the latest pipeline update id and its refresh timestamp."""
    table = db_sql.safe_table(table)
    now = time.time()
    with _vlock:
        hit = _versions.get(table)
        if hit and now - hit[0] < 60:
            return hit[1], hit[2], hit[3]
    version = ts = ref = None
    try:
        if table in _not_delta:
            raise LookupError("materialized view")
        rows = db_sql.query_as_user(user, f"DESCRIBE HISTORY {table} LIMIT 1")
        if rows:
            version = int(rows[0]["version"])
            ts = rows[0]["timestamp"].isoformat() if rows[0].get("timestamp") else None
            ref = f"delta:v{version}"
    except db_sql.TableMissing:
        return None, None, None
    except Exception as exc:
        if "EXPECT_TABLE_NOT_VIEW" in str(exc):
            _not_delta.add(table)
        try:  # materialized view: '# Refresh Information' section of DESCRIBE TABLE EXTENDED
            info = {str(r.get("col_name") or "").strip(): str(r.get("data_type") or "").strip()
                    for r in db_sql.query_as_user(user, f"DESCRIBE TABLE EXTENDED {table}")}
            ts = info.get("Last Refreshed") or None
            m = _UPDATE_RE.search(info.get("Latest Refresh", ""))
            if m:
                ref = f"pipeline:{m.group(1)}/update:{m.group(2)}"
        except Exception as exc:
            log.info("no snapshot info for %s: %s", table, type(exc).__name__)
    with _vlock:
        _versions[table] = (now, version, ts, ref)
    return version, ts, ref


# ------------------------------------------------------------------ comparisons and slices
def comparisons(user: User) -> list[Comparison]:
    return _cached(user, ("comparisons",), COMPARISONS_TTL_S, lambda: _comparisons(user))


def _comparisons(user: User) -> list[Comparison]:
    if _mode() != "fixtures":
        try:
            rows = db_sql.query_as_user(user, f"""SELECT comparison_id, comparison_type, period_p0, period_p1,
                p0_label, p1_label, sort_order, is_default, comparison_label FROM {_gold('dim_comparison')}""")
            return _sorted([Comparison(**r) for r in rows])
        except db_sql.TableMissing as exc:
            _fallback(exc)
    return _sorted([Comparison(**c) for c in fixtures.comparisons()])


def _sorted(comps: list[Comparison]) -> list[Comparison]:
    """Month-on-month first, newest first; then quarter-on-quarter, newest first."""
    return sorted(comps, key=lambda c: (c.comparison_type != "MoM", -c.sort_order))


def slice_options(user: User, comparison_id: str) -> list[SliceOption]:
    check_comparison(comparison_id)
    return _cached(user, ("slices", comparison_id), SLICES_TTL_S, lambda: _slice_options(user, comparison_id))


def _slice_options(user: User, comparison_id: str) -> list[SliceOption]:
    base = [SliceOption(key="APAC", label="APAC Global Markets", group="Headline"),
            SliceOption(key="ED_EXCH_CLR", label="Equity Derivatives — exchange & clearing", group="Headline"),
            SliceOption(key="REST", label="Rest of APAC Global Markets", group="Headline")]
    rows: list[dict]
    if _mode() != "fixtures":
        try:
            rows = db_sql.query_as_user(user, f"""SELECT DISTINCT business_code, business, desk_code, desk_name
                FROM {_gold('cost_flux_bridge')} WHERE comparison_id = :cid ORDER BY business, desk_name""",
                                        {"cid": comparison_id})
        except db_sql.TableMissing as exc:
            _fallback(exc)
            rows = []
        else:
            return base + _options(rows)
    rows = sorted({(r["business_code"], r["business"], r["desk_code"], r["desk_name"])
                   for r in fixtures.bridge_rows() if r["comparison_id"] == comparison_id}, key=lambda t: (t[1], t[3]))
    return base + _options([dict(business_code=a, business=b, desk_code=c, desk_name=d) for a, b, c, d in rows])


def _options(rows: list[dict]) -> list[SliceOption]:
    seen, out = set(), []
    for r in rows:
        if r["business_code"] not in seen:
            seen.add(r["business_code"])
            out.append(SliceOption(key=f"BUS:{r['business_code']}", label=r["business"], group="Business"))
    for r in rows:
        out.append(SliceOption(key=f"DESK:{r['desk_code']}", label=r["desk_name"], group="Desk"))
    return out


def slice_label(slice_key: str) -> str:
    return fixtures.scope_label(slice_key)


# ------------------------------------------------------------------ flux
def _sum_rows(rows: list[dict]) -> dict:
    return {m: float(sum((r.get(m) or 0.0) for r in rows)) for m in MEASURES}


def flux(user: User, comparison_id: str, slice_key: str, breakdown: Optional[str]) -> FluxResponse:
    check_comparison(comparison_id)
    check_slice(slice_key)
    bkey = breakdown or DEFAULT_BREAKDOWN.get(slice_key) or ("desk" if slice_key.startswith("BUS:") else
                                                             "cost_category")
    if bkey not in BREAKDOWNS:
        raise HTTPException(status_code=422, detail="invalid breakdown")
    return _cached(user, ("flux", comparison_id, slice_key, bkey), FLUX_TTL_S,
                   lambda: _flux(user, comparison_id, slice_key, bkey))


def _comparison(listing: Future, comparison_id: str) -> Comparison:
    comp = next((c for c in listing.result() if c.comparison_id == comparison_id), None)
    if comp is None:
        raise HTTPException(status_code=404, detail="Unknown comparison")
    return comp


def _flux(user: User, comparison_id: str, slice_key: str, bkey: str) -> FluxResponse:
    pred, params = slice_predicate(slice_key)
    col = BREAKDOWNS[bkey]
    listing = _io.submit(comparisons, user)  # comparison labels, fetched alongside the bridge query
    table = _gold("cost_flux_bridge")
    source: DataSource
    rows: list[dict] = []
    if _mode() != "fixtures":
        try:
            snapshot = _io.submit(table_version, user, table)  # runs alongside the bridge query
            rows = db_sql.query_as_user(user, f"""
                SELECT {col} AS key, SUM(p0_actual_usd) AS p0, SUM(p1_actual_usd) AS p1, SUM(p1_cc_usd) AS p1_cc,
                       SUM(volume_usd) AS volume, SUM(mix_usd) AS mix, SUM(rate_usd) AS rate, SUM(fx_usd) AS fx,
                       SUM(fails_usd) AS fails, SUM(fixed_usd) AS fixed, SUM(timing_usd) AS timing,
                       SUM(unexplained_usd) AS unexplained, SUM(flux_usd) AS flux
                FROM {table} WHERE comparison_id = :cid AND {pred}
                GROUP BY {col} ORDER BY ABS(SUM(flux_usd)) DESC""", {"cid": comparison_id, **params})
            version, ts, ref = snapshot.result()
            source = DataSource(table=table, mode="live", delta_version=version, as_of_ts=ts, snapshot_ref=ref)
        except db_sql.TableMissing as exc:
            _fallback(exc)
            rows = []
            source = None  # type: ignore[assignment]
        else:
            return _flux_payload(_comparison(listing, comparison_id), slice_key, bkey, rows, source)
    _, fpred = fixtures.scope_filter(slice_key)
    sel = [r for r in fixtures.bridge_rows() if r["comparison_id"] == comparison_id and fpred(r)]
    groups: dict[str, list[dict]] = {}
    for r in sel:
        groups.setdefault(str(r[col]), []).append(r)
    rows = []
    for k, rs in groups.items():
        rows.append({"key": k, "p0": sum(x["p0_actual_usd"] for x in rs), "p1": sum(x["p1_actual_usd"] for x in rs),
                     "p1_cc": sum(x["p1_cc_usd"] for x in rs),
                     **{e: sum(x[f"{e}_usd"] for x in rs) for e in
                        ["volume", "mix", "rate", "fx", "fails", "fixed", "timing", "unexplained", "flux"]}})
    rows.sort(key=lambda r: -abs(r["flux"]))
    source = DataSource(table=table, mode="fixtures", note="Fixture data — Gold not yet published")
    return _flux_payload(_comparison(listing, comparison_id), slice_key, bkey, rows, source)


def _flux_payload(comp: Comparison, slice_key: str, bkey: str, rows: list[dict], source: DataSource) -> FluxResponse:
    """Waterfall and table are built from the same rows, so the chart always ties to the table."""
    tot = _sum_rows(rows)
    effects = [Effect(effect=e, label=lbl, amount=tot[e.lower()], order=o, flux_class=fc)
               for e, lbl, o, fc in EFFECTS]
    classes = {"good": tot["volume"], "controllable": tot["mix"] + tot["fails"],
               "external": tot["rate"] + tot["fx"] + tot["timing"] + tot["unexplained"] + tot["fixed"]}
    return FluxResponse(
        comparison=comp, slice_key=slice_key, slice_label=slice_label(slice_key), breakdown=bkey,
        totals=FluxTotals(p0=tot["p0"], p1=tot["p1"], p1_cc=tot["p1_cc"], flux=tot["p1"] - tot["p0"],
                          flux_pct=((tot["p1"] - tot["p0"]) / tot["p0"]) if tot["p0"] else None),
        effects=effects, classes=classes,
        rows=[FluxRow(key=str(r["key"]), **{m: float(r.get(m) or 0.0) for m in MEASURES if m not in ("p1_cc",)})
              for r in rows],
        source=source)


def expected_desks(slice_key: str) -> list[str]:
    """Desks a slice covers, from the static hierarchy (docs/CONTRACTS.md §1) — independent of row filters."""
    if slice_key in ("APAC", "REST"):
        return sorted(fixtures.DESK)
    if slice_key == "ED_EXCH_CLR":
        return ["HKED"]
    kind, code = slice_key.split(":", 1)
    if kind == "BUS":
        return sorted(d for d, b in fixtures.DESK_BUS.items() if b == code)
    return [code]


def slice_access_check(user: User, comparison_id: str, slice_key: str) -> tuple[bool, list[str]]:
    """Entitlement pre-check run with the user's identity before the agent drafts. The agent may read Gold under its
    own principal, so the user must be able to see *every* desk in the slice, not just some of it."""
    if _mode() == "fixtures":
        return True, []
    desks = expected_desks(slice_key)
    try:  # ask the governance function itself (the row filter on desk_code)
        values = ", ".join(f"(:d{i})" for i in range(len(desks)))
        rows = db_sql.query_as_user(user, f"""SELECT d AS desk_code, {_gold('ce_desk_scope')}(d) AS ok
                                            FROM VALUES {values} AS t(d)""", {f"d{i}": d for i, d in enumerate(desks)})
        hidden = sorted(r["desk_code"] for r in rows if not r["ok"])
    except db_sql.TableMissing as exc:
        _fallback(exc)
        return True, []
    except Exception:  # no EXECUTE on the function: compare desks visible in the bridge with the hierarchy
        pred, params = slice_predicate(slice_key)
        rows = db_sql.query_as_user(user, f"""SELECT DISTINCT desk_code FROM {_gold('cost_flux_bridge')}
                                            WHERE comparison_id = :cid AND {pred}""", {"cid": comparison_id, **params})
        visible = {r["desk_code"] for r in rows}
        hidden = sorted(d for d in desks if d not in visible)
    return not hidden, hidden


# ------------------------------------------------------------------ figures
def _figure_from_row(r: dict, mode: str) -> Figure:
    return Figure(figure_key=r["figure_key"], comparison_id=r.get("comparison_id"), scope_key=r.get("scope_key"),
                  scope_label=r.get("scope_label"), metric=r.get("metric"), metric_label=r.get("metric_label"),
                  label=r.get("metric_label") or r["figure_key"],
                  value=float(r["value"]) if r.get("value") is not None else None, unit=r.get("unit") or "USD",
                  source_table=r.get("source_table") or "", filter=r.get("filter_expr") or "",
                  description=r.get("description"), mode=mode)  # type: ignore[arg-type]


def _attach_snapshot(user: User, figs: list[Figure]) -> None:
    tables = sorted({f.source_table for f in figs if f.source_table})
    versions = dict(zip(tables, _io.map(lambda t: table_version(user, t), tables)))  # one lookup per table, overlapped
    for f in figs:
        if f.source_table in versions:
            f.delta_version, f.as_of_ts, f.snapshot_ref = versions[f.source_table]


def _figure_group(key: str) -> tuple[str, str]:
    """Registry rows are fetched a comparison (or a findings period) at a time: every query on the
    commentary_figures view costs seconds however narrow the filter, and the chips in a commentary cluster."""
    head, _, rest = key.partition("|")
    if head in ("INV", "FAILS"):
        return "prefix", f"{head}|{rest.split('|', 1)[0]}|"
    return "comparison", head


def _figure_group_load(user: User, group: tuple[str, str], with_version: bool) -> dict[str, Figure]:
    kind, value = group
    if _mode() != "fixtures":
        try:
            where, params = (("comparison_id = :v", {"v": value}) if kind == "comparison"
                             else ("figure_key LIKE :v", {"v": f"{value}%"}))
            rows = db_sql.query_as_user(user, f"SELECT * FROM {_gold('commentary_figures')} WHERE {where}", params)
            out = {r["figure_key"]: _figure_from_row(r, "live") for r in rows}
            if with_version:
                _attach_snapshot(user, list(out.values()))
            return out
        except db_sql.TableMissing as exc:
            _fallback(exc)
    reg = fixtures.figure_registry()
    return {k: _figure_from_row(r, "fixtures") for k, r in reg.items()
            if (r.get("comparison_id") == value if kind == "comparison" else k.startswith(value))}


def figure(user: User, key: str, with_version: bool = True) -> Figure:
    group = _figure_group(key)
    figs = _cached(user, ("figures", group, with_version), FIGURE_TTL_S,
                   lambda: _figure_group_load(user, group, with_version))
    fig = figs.get(key) or _figure(user, key, with_version)  # not in its group's rows: look the key up directly
    return fig.model_copy()  # callers may annotate the figure; keep the cached copy pristine


def _figure(user: User, key: str, with_version: bool) -> Figure:
    if _mode() != "fixtures":
        try:
            rows = db_sql.query_as_user(user, f"SELECT * FROM {_gold('commentary_figures')} WHERE figure_key = :k",
                                        {"k": key})
            if not rows:
                raise HTTPException(status_code=404, detail="Figure not found")
            fig = _figure_from_row(rows[0], "live")
            if with_version:
                _attach_snapshot(user, [fig])
            return fig
        except db_sql.TableMissing as exc:
            _fallback(exc)
    reg = fixtures.figure_registry()
    if key not in reg:
        raise HTTPException(status_code=404, detail="Figure not found")
    return _figure_from_row(reg[key], "fixtures")


def figures_by_keys(user: User, keys: list[str]) -> dict[str, Figure]:
    """Batch registry lookup (one query) — unknown keys are simply absent from the result."""
    keys = [k for k in dict.fromkeys(keys) if k]
    if not keys:
        return {}
    if _mode() != "fixtures":
        try:
            ph = ", ".join(f":k{i}" for i in range(len(keys)))
            rows = db_sql.query_as_user(user, f"SELECT * FROM {_gold('commentary_figures')} WHERE figure_key IN ({ph})",
                                        {f"k{i}": k for i, k in enumerate(keys)})
            out = {r["figure_key"]: _figure_from_row(r, "live") for r in rows}
            _attach_snapshot(user, list(out.values()))
            return out
        except db_sql.TableMissing as exc:
            _fallback(exc)
    reg = fixtures.figure_registry()
    return {k: _figure_from_row(reg[k], "fixtures") for k in keys if k in reg}


def figures_for(user: User, comparison_id: str, slice_key: str, p0: str, p1: str) -> dict[str, Figure]:
    """Every figure the drafter may cite for this comparison and slice (plus period findings)."""
    scopes = [slice_key] + (["ED_EXCH_CLR", "REST"] if slice_key == "APAC" else [])
    inv_prefix, fails_prefix = f"INV|{p0}|%", f"FAILS|{p1}|%"
    if _mode() != "fixtures":
        try:
            ph = ", ".join(f":s{i}" for i in range(len(scopes)))
            rows = db_sql.query_as_user(user, f"""SELECT * FROM {_gold('commentary_figures')}
                WHERE (comparison_id = :cid AND scope_key IN ({ph})) OR figure_key LIKE :inv OR figure_key LIKE :fails""",
                                        {"cid": comparison_id, "inv": inv_prefix, "fails": fails_prefix,
                                         **{f"s{i}": s for i, s in enumerate(scopes)}})
            out = {r["figure_key"]: _figure_from_row(r, "live") for r in rows}
            _attach_snapshot(user, list(out.values()))
            return out
        except db_sql.TableMissing as exc:
            _fallback(exc)
    reg = fixtures.figure_registry()
    out = {}
    for k, r in reg.items():
        if (r.get("comparison_id") == comparison_id and r.get("scope_key") in scopes) or \
                k.startswith(f"INV|{p0}|") or k.startswith(f"FAILS|{p1}|"):
            out[k] = _figure_from_row(r, "fixtures")
    return out
