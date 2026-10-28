"""Builds src/dashboards/trade_cost_explain.lvdash.json (AI/BI dashboard "Trade Cost Explain — APAC Global Markets").

Datasets use bare Gold table names (catalog / schema come from the dashboard's dataset_catalog / dataset_schema) and
`silver.<table>` for the two Silver reads. Governed metrics come straight from the UC metric views.
    python src/dashboards/build_dashboard.py
    CE_CATALOG=<catalog> python src/dashboards/build_dashboard.py   # deploying to a catalog not named cost_explain
"""
from __future__ import annotations

import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent / "trade_cost_explain.lvdash.json"
# Metric views are referenced as UC assets by full name, which dataset_catalog does not rewrite.
MV = f"{os.environ.get('CE_CATALOG', 'cost_explain')}.gold"

USD = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 2}}
USD0 = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
USD_EXACT = {"type": "number-currency", "currencyCode": "USD", "decimalPlaces": {"type": "exact", "places": 0}}
PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
NUM = {"type": "number", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
INT = {"type": "number", "decimalPlaces": {"type": "max", "places": 0}}
RATE = {"type": "number", "decimalPlaces": {"type": "max", "places": 6}}

FLUX_CLASS_COLORS = [{"value": "Good (volume-driven)", "color": "#17A589"}, {"value": "Controllable", "color": "#E15F41"},
                     {"value": "External, timing & residual", "color": "#8C9BA5"}, {"value": "Prior period", "color": "#1F4E79"}]
STEP_ORDER = ["Prior period", "Volume", "Mix", "Rate", "Fails", "Timing / accrual", "FX", "Fixed fees", "Unexplained"]
DEFAULT_COMPARISON = "Sep 2026 vs Aug 2026"


def q(*lines: str) -> list[str]:
    return [ln if ln.endswith((" ", "\n")) else ln + "\n" for ln in lines]


DATASETS = [
    {"name": "ds_flux", "displayName": "Cost bridge (metric view)", "asset_name": f"{MV}.trade_cost_flux_metrics"},
    {"name": "ds_trend", "displayName": "Desk KPIs (metric view)", "asset_name": f"{MV}.desk_cost_kpi_metrics"},
    {"name": "ds_recon", "displayName": "Invoice reconciliation (metric view)", "asset_name": f"{MV}.invoice_recon_metrics"},
    {"name": "ds_fails", "displayName": "Settlement fails (metric view)", "asset_name": f"{MV}.settlement_fail_metrics"},
    {"name": "ds_steps", "displayName": "Bridge steps (prior period + effects)", "queryLines": q(
        "SELECT c.comparison_label, b.comparison_id, b.business, b.desk_name, b.headline_slice, b.cost_category, b.market, b.currency,",
        "       'Prior period' AS step, 0 AS step_order, 'Prior period' AS flux_class, b.p0_actual_usd AS amount_usd",
        "FROM cost_flux_bridge b JOIN dim_comparison c ON c.comparison_id = b.comparison_id",
        "UNION ALL",
        "SELECT c.comparison_label, e.comparison_id, e.business, e.desk_name, e.headline_slice, e.cost_category, e.market, e.currency,",
        "       e.effect_label AS step, e.effect_order AS step_order, e.flux_class, e.amount_usd",
        "FROM cost_flux_effects e JOIN dim_comparison c ON c.comparison_id = e.comparison_id")},
    {"name": "ds_slice", "displayName": "Driver slices (volume / mix / rate)", "queryLines": q(
        "SELECT c.comparison_label, s.comparison_id, s.desk_code, s.product_family, concat(s.desk_code, ' · ', s.product_family) AS desk_product,",
        "       concat(s.venue, ' · ', s.capacity) AS venue_capacity, s.cost_type, s.vendor_id, s.venue, s.capacity, s.market, s.currency,",
        "       s.volume_unit, s.v0, s.v1, s.unit_cost0_usd, s.unit_cost1_cc_usd, s.c0_usd, s.c1_cc_usd, s.volume_usd, s.mix_usd,",
        "       s.rate_usd, s.delta_usd, abs(s.mix_usd) AS abs_mix_usd",
        "FROM cost_flux_slice s JOIN dim_comparison c ON c.comparison_id = s.comparison_id",
        "ORDER BY abs(s.mix_usd) DESC")},
    {"name": "ds_mix_groups", "displayName": "Mix by desk × product family", "queryLines": q(
        "SELECT c.comparison_label, concat(s.desk_code, ' · ', s.product_family) AS desk_product,",
        "       SUM(s.volume_usd) AS volume_usd, SUM(s.mix_usd) AS mix_usd, SUM(s.rate_usd) AS rate_usd",
        "FROM cost_flux_slice s JOIN dim_comparison c ON c.comparison_id = s.comparison_id",
        "GROUP BY c.comparison_label, concat(s.desk_code, ' · ', s.product_family)",
        "HAVING abs(SUM(s.mix_usd)) >= 1000")},
    {"name": "ds_trades", "displayName": "September executions — planted mix groups", "queryLines": q(
        "SELECT e.trade_id, e.trade_date, e.desk_code, e.product_family, e.product, e.venue, e.capacity, e.cost_type, e.fee_id,",
        "       e.volume, e.volume_unit, e.unit_rate, e.cost_currency, e.cost_lcy, e.cost_usd, e.counterparty_id,",
        "       CASE WHEN e.desk_code = 'HKED' AND e.capacity = 'HOUSE' THEN 'PRX 50 futures booked to the house account'",
        "            WHEN e.desk_code = 'AUCE' AND e.venue = 'SXA' THEN 'AU cash equities routed to Southern Cross (SXA)'",
        "            ELSE 'Rest of the same volume group' END AS story_slice",
        "FROM expected_cost_trade e",
        "WHERE e.period = '2026-09' AND e.in_net_borne AND e.cost_type = 'EXCHANGE'",
        "  AND ((e.desk_code = 'HKED' AND e.product_family = 'PRX50_FUT') OR (e.desk_code = 'AUCE' AND e.product_family = 'AU_CASH_EQ'))",
        "ORDER BY e.cost_usd DESC")},
    {"name": "ds_vol", "displayName": "PRX Volatility Index vs Equity Derivatives cost (daily)", "queryLines": q(
        "WITH vi AS (",
        "  SELECT trade_date, close_value AS prx_vol_index FROM silver.market_data",
        "  WHERE index_code = 'PRXVI' AND trade_date BETWEEN DATE'2026-08-01' AND DATE'2026-09-30'),",
        "ed AS (",
        "  SELECT trade_date, SUM(net_borne_cost_usd) AS ed_exch_clearing_cost_usd FROM expected_cost_daily",
        "  WHERE desk_code = 'HKED' AND cost_type IN ('EXCHANGE', 'CLEARING') AND trade_date BETWEEN DATE'2026-08-01' AND DATE'2026-09-30'",
        "  GROUP BY trade_date)",
        "SELECT COALESCE(vi.trade_date, ed.trade_date) AS trade_date, vi.prx_vol_index, ed.ed_exch_clearing_cost_usd",
        "FROM vi FULL OUTER JOIN ed ON vi.trade_date = ed.trade_date")},
    {"name": "ds_recon_tbl", "displayName": "Invoice reconciliation lines needing attention", "queryLines": q(
        "SELECT service_period, COALESCE(vendor_name, vendor_id) AS vendor, legal_entity, cost_type, recon_status, variance_reason,",
        "       expected_net_usd, IF(recon_status = 'PENDING_INVOICE', NULL, invoiced_net_usd) AS invoiced_net_usd,",
        "       IF(recon_status = 'PENDING_INVOICE', NULL, variance_usd) AS variance_usd, invoice_ids, invoice_received_date,",
        "       monthly_turnover_usd, CASE recon_status WHEN 'OVERBILLED' THEN 0 WHEN 'UNDERBILLED' THEN 1 ELSE 2 END AS status_rank",
        "FROM invoice_recon WHERE recon_status <> 'MATCHED'",
        "ORDER BY status_rank, service_period DESC, abs(variance_usd) DESC")},
    {"name": "ds_recon_line", "displayName": "Broker C (Cobalt Securities) — August invoice by fee code", "queryLines": q(
        "SELECT l.legal_entity, l.currency, l.fee_id, l.fee_description, l.contracted_rate, l.in_expected, l.in_invoice,",
        "       l.expected_qty, l.invoiced_qty, l.expected_net, l.invoiced_net, l.invoiced_net - l.expected_net AS variance_lcy,",
        "       l.expected_net * fx.rate_to_usd AS expected_net_usd, l.invoiced_net * fx.rate_to_usd AS invoiced_net_usd,",
        "       (l.invoiced_net - l.expected_net) * fx.rate_to_usd AS variance_usd, l.invoice_ids,",
        "       CASE WHEN l.in_invoice AND NOT l.in_expected THEN 'Billed — not the contracted rate for this volume'",
        "            WHEN l.in_expected AND NOT l.in_invoice THEN 'Expected — not billed'",
        "            ELSE 'Billed as expected' END AS line_status",
        "FROM invoice_recon_line l JOIN silver.fx_monthly fx ON fx.currency = l.currency AND fx.period = l.service_period",
        "WHERE l.vendor_id = 'B03' AND l.service_period = '2026-08' AND l.cost_type = 'BROKERAGE'",
        "ORDER BY l.legal_entity, l.fee_id")},
    {"name": "ds_fails_trend", "displayName": "Net fail cost by month", "queryLines": q(
        "SELECT period AS month, 'Kestrel Asset Management · AUCE' AS fail_group,",
        "       SUM(IF(counterparty_id = 'C001' AND desk_code = 'AUCE', net_cost_usd, 0D)) AS net_fail_cost_usd",
        "FROM fail_cost_summary GROUP BY period",
        "UNION ALL",
        "SELECT period, 'All other fails', SUM(IF(counterparty_id = 'C001' AND desk_code = 'AUCE', 0D, net_cost_usd))",
        "FROM fail_cost_summary GROUP BY period ORDER BY 1")},
    {"name": "ds_fee_cal", "displayName": "Fee and regime calendar", "queryLines": q(
        "SELECT event_date, event_type, status, COALESCE(vendor_name, vendor_id) AS vendor, product_family, description,",
        "       monthly_impact_usd, fee_ids_before, fee_id_after, source_doc",
        "FROM fee_calendar ORDER BY event_date")},
    {"name": "ds_tie", "displayName": "Tie-out checks", "queryLines": q(
        "SELECT check_type, check_name, expected, actual, passed, CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END AS result,",
        "       IF(passed, 1, 0) AS passed_flag, IF(passed, 0, 1) AS failed_flag, checked_at",
        "FROM tie_out_results ORDER BY passed, check_type, check_name")},
    {"name": "ds_coverage", "displayName": "GL mapping coverage by month", "queryLines": q(
        "SELECT period AS month, SUM(IF(is_vendor_mapped, amount_usd, 0D)) / SUM(amount_usd) AS mapped_share,",
        "       SUM(IF(is_vendor_mapped, 0D, amount_usd)) AS unmapped_usd",
        "FROM gl_monthly WHERE in_net_borne GROUP BY period ORDER BY period")},
]


# ── widget helpers ───────────────────────────────────────────────────────────────────────────────────
def pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def text(name, lines, x, y, w, h):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": lines}}, "position": pos(x, y, w, h)}


def frame(title, description=None):
    f = {"showTitle": True, "title": title}
    if description:
        f.update(showDescription=True, description=description)
    return f


def query(ds, fields, disaggregated=False, filters=None, orders=None):
    qq = {"datasetName": ds, "fields": [{"name": n, "expression": e} for n, e in fields], "disaggregated": disaggregated}
    if filters:
        qq["filters"] = [{"expression": f} for f in filters]
    if orders:
        qq["orders"] = orders
    return [{"name": "main_query", "query": qq}]


def measure(m):
    return (f"measure({m})", f"MEASURE(`{m}`)")


def dim(d):
    return (d, f"`{d}`")


def counter(name, ds, field, title, fmt, x, y, w=3, h=3, filters=None, description=None):
    n, e = field
    enc = {"fieldName": n, "displayName": title}
    if fmt:
        enc["format"] = fmt
    return {"widget": {"name": name, "queries": query(ds, [field], filters=filters),
                       "spec": {"version": 2, "widgetType": "counter", "encodings": {"value": enc},
                                "frame": frame(title, description)}}, "position": pos(x, y, w, h)}


def table(name, ds, cols, title, x, y, w, h, filters=None, orders=None, description=None, disaggregated=True):
    fields = [(c[0], c[1]) for c in cols]
    enc_cols = []
    for c in cols:
        col = {"fieldName": c[0], "displayName": c[2]}
        if len(c) > 3 and c[3]:
            col["format"] = c[3]
        if len(c) > 4 and c[4]:
            col["style"] = c[4]
        enc_cols.append(col)
    return {"widget": {"name": name, "queries": query(ds, fields, disaggregated=disaggregated, filters=filters, orders=orders),
                       "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": enc_cols},
                                "frame": frame(title, description)}}, "position": pos(x, y, w, h)}


def bar(name, ds, xf, yfs, title, x, y, w, h, horizontal=False, color=None, filters=None, sort=None, stacked=True,
        description=None, x_type="categorical", yfmt=USD, label=False):
    fields = [xf] + [(yf[0], yf[1]) for yf in yfs] + ([color[0]] if color else [])
    cat = {"fieldName": xf[0], "scale": {"type": x_type}}
    if sort:
        cat["scale"]["sort"] = sort
    if len(yfs) == 1:
        val = {"fieldName": yfs[0][0], "scale": {"type": "quantitative"}, "displayName": yfs[0][2], "format": yfmt}
    else:
        val = {"scale": {"type": "quantitative"}, "fields": [{"fieldName": yf[0], "displayName": yf[2]} for yf in yfs],
               "format": yfmt}
    enc = {"x": val, "y": cat} if horizontal else {"x": cat, "y": val}
    if color:
        cfield, cdisplay, mappings = color[0][0], color[1], color[2] if len(color) > 2 else None
        enc["color"] = {"fieldName": cfield, "scale": {"type": "categorical", **({"mappings": mappings} if mappings else {})},
                        "displayName": cdisplay}
    if label:
        enc["label"] = {"show": True}
    spec = {"version": 3, "widgetType": "bar", "encodings": enc, "frame": frame(title, description)}
    if not stacked:
        spec["mark"] = {"layout": "group"}
    return {"widget": {"name": name, "queries": query(ds, fields, filters=filters), "spec": spec}, "position": pos(x, y, w, h)}


def combo(name, ds, xf, bars, lines, title, x, y, w, h, x_type="temporal", description=None, filters=None):
    fields = [xf] + [(b[0], b[1]) for b in bars] + [(ln[0], ln[1]) for ln in lines]
    spec = {"version": 1, "widgetType": "combo",
            "encodings": {"x": {"fieldName": xf[0], "scale": {"type": x_type}},
                          "y": {"scale": {"type": "quantitative"},
                                "primary": {"fields": [{"fieldName": b[0], "displayName": b[2]} for b in bars]},
                                "secondary": {"fields": [{"fieldName": ln[0], "displayName": ln[2]} for ln in lines]}},
                          "label": {"show": False}},
            "frame": frame(title, description)}
    return {"widget": {"name": name, "queries": query(ds, fields, filters=filters), "spec": spec}, "position": pos(x, y, w, h)}


def waterfall(name, ds, xf, yf, title, x, y, w, h, order, filters=None, description=None):
    spec = {"version": 1, "widgetType": "waterfall",
            "encodings": {"x": {"fieldName": xf[0], "scale": {"type": "categorical",
                                                             "sort": {"by": "custom-order", "orderedValues": order}}},
                          "y": {"fieldName": yf[0], "scale": {"type": "quantitative"}, "format": USD0, "displayName": yf[2]}},
            "frame": frame(title, description)}
    return {"widget": {"name": name, "queries": query(ds, [xf, (yf[0], yf[1])], filters=filters), "spec": spec},
            "position": pos(x, y, w, h)}


def flt(name, kind, bindings, title, x, y, w=4, h=2, default=None):
    """bindings: list of (query_name, dataset, field_expr_name)."""
    queries = [{"name": qn, "query": {"datasetName": ds, "fields": [{"name": f, "expression": f"`{f}`"}], "disaggregated": False}}
               for qn, ds, f in bindings]
    spec = {"version": 2, "widgetType": kind,
            "encodings": {"fields": [{"fieldName": f, "displayName": title, "queryName": qn} for qn, ds, f in bindings]},
            "frame": frame(title)}
    if default:
        spec["selection"] = {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": v} for v in default]}}}
    return {"widget": {"name": name, "queries": queries, "spec": spec}, "position": pos(x, y, w, h)}


SYNTH = "*Synthetic data — Meridian Group; all figures illustrative. Venues, brokers and fee changes are fictional.*"
EFFECT_COLS = [("Volume Effect", "Volume"), ("Mix Effect", "Mix"), ("Rate Effect", "Rate"), ("Fails Effect", "Fails"),
               ("Timing Effect", "Timing"), ("FX Effect", "FX"), ("Fixed Fees Effect", "Fixed"), ("Unexplained", "Unexplained")]


def bridge_cols(prefix_dims):
    cols = [(d, f"`{d}`", lbl) for d, lbl in prefix_dims]
    cols += [(measure("Prior Period Cost")[0], measure("Prior Period Cost")[1], "Prior (US$)", USD),
             (measure("Current Period Cost")[0], measure("Current Period Cost")[1], "Current (US$)", USD),
             (measure("Cost Change")[0], measure("Cost Change")[1], "Change (US$)", USD)]
    cols += [(measure(m)[0], measure(m)[1], lbl, USD) for m, lbl in EFFECT_COLS]
    return cols


# ── pages ─────────────────────────────────────────────────────────────────────────────────────────────
p_flux = [
    text("flux_header", ["# Trade Cost Explain — APAC Global Markets\n", "\n",
                         "Net borne trade cost (US GAAP line *Commissions and floor brokerage*), explained driver by driver: "
                         "volume, mix and rate at constant currency, then FX, settlement fails, fixed fees, timing / accrual and an "
                         "unexplained residual — the bars add up to the change. Pick the comparison in the global **Filters** panel "
                         "(default: September vs August 2026, the half-year close). ", SYNTH], 0, 0, 12, 3),
    flt("flux_f_slice", "filter-multi-select", [("q_flux_slice", "ds_flux", "Headline Slice"),
                                                ("q_steps_slice", "ds_steps", "headline_slice")], "Headline slice", 0, 3, 6, 2),
    flt("flux_f_business", "filter-multi-select", [("q_flux_bus", "ds_flux", "Business"),
                                                   ("q_steps_bus", "ds_steps", "business")], "Business", 6, 3, 6, 2),
    counter("kpi_prior", "ds_flux", measure("Prior Period Cost"), "Prior period cost", USD, 0, 5),
    counter("kpi_current", "ds_flux", measure("Current Period Cost"), "Current period cost", USD, 3, 5),
    counter("kpi_change", "ds_flux", measure("Cost Change"), "Change", USD, 6, 5),
    counter("kpi_change_pct", "ds_flux", measure("Cost Change Pct"), "Change (%)", PCT, 9, 5),
    waterfall("flux_waterfall", "ds_steps", ("step", "`step`"), ("sum(amount_usd)", "SUM(`amount_usd`)", "US$"),
              "Cost bridge — prior period to current period", 0, 8, 8, 7, STEP_ORDER,
              description="Prior-period cost, then each effect in order; the last bar lands on current-period cost. "
                          "Volume / mix / rate at prior-period FX; FX measured on every local-currency GL line."),
    bar("flux_by_driver", "ds_steps", ("step", "`step`"), [("sum(amount_usd)", "SUM(`amount_usd`)", "Change (US$)")],
        "Change by driver (adds up to the change)", 8, 8, 4, 7, horizontal=True,
        color=(("flux_class", "`flux_class`"), "Flux class", FLUX_CLASS_COLORS), filters=["`step_order` > 0"],
        sort={"by": "custom-order", "orderedValues": STEP_ORDER[1:]}, label=True),
    table("flux_slice_table", "ds_flux", bridge_cols([("Headline Slice", "Slice")]),
          "Equity Derivatives exchange & clearing vs the rest", 0, 15, 12, 4, disaggregated=False),
    table("flux_desk_table", "ds_flux", bridge_cols([("Business", "Business"), ("Desk", "Desk")]),
          "By business and desk", 0, 19, 12, 7, disaggregated=False),
    bar("flux_by_market", "ds_steps", ("market", "`market`"), [("sum(amount_usd)", "SUM(`amount_usd`)", "Change (US$)")],
        "Change by market and driver", 0, 26, 6, 6, color=(("step", "`step`"), "Driver"), filters=["`step_order` > 0"]),
    bar("flux_by_currency", "ds_flux", dim("Currency"),
        [(measure("Cost Change")[0], measure("Cost Change")[1], "Change (US$)"),
         (measure("FX Effect")[0], measure("FX Effect")[1], "of which FX (US$)")],
        "Local-currency drill: change and FX effect by currency", 6, 26, 6, 6, stacked=False),
]

p_good_bad = [
    text("gb_header", ["## Good vs bad flux\n", "\n",
                       "**Good** = volume-driven, matched by activity and revenue. **Controllable** = mix (routing / booking) + "
                       "settlement fails — what Operations and the desks can fix. **External, timing & residual** = rate, FX, "
                       "timing / accrual, fixed fees, unexplained. ", SYNTH], 0, 0, 12, 2),
    counter("gb_good", "ds_flux", measure("Good Flux"), "Good flux — volume-driven", USD, 0, 2),
    counter("gb_good_pct", "ds_flux", measure("Good Flux Share"), "Good share of the change", PCT, 3, 2),
    counter("gb_ctrl", "ds_flux", measure("Controllable Flux"), "Controllable flux — mix + fails", USD, 6, 2),
    counter("gb_ctrl_pct", "ds_flux", measure("Controllable Flux Share"), "Controllable share of the change", PCT, 9, 2),
    bar("gb_by_driver", "ds_steps", ("step", "`step`"), [("sum(amount_usd)", "SUM(`amount_usd`)", "Change (US$)")],
        "Change by driver", 0, 5, 6, 6, color=(("flux_class", "`flux_class`"), "Flux class", FLUX_CLASS_COLORS),
        filters=["`step_order` > 0"], sort={"by": "custom-order", "orderedValues": STEP_ORDER[1:]}, label=True),
    bar("gb_by_class", "ds_steps", ("flux_class", "`flux_class`"), [("sum(amount_usd)", "SUM(`amount_usd`)", "Change (US$)")],
        "Change by flux class", 6, 5, 6, 6, color=(("flux_class", "`flux_class`"), "Flux class", FLUX_CLASS_COLORS),
        filters=["`step_order` > 0"],
        sort={"by": "custom-order", "orderedValues": ["Good (volume-driven)", "Controllable", "External, timing & residual"]},
        label=True),
    combo("gb_cost_vs_revenue", "ds_trend", dim("Month"),
          [(measure("Trade Cost")[0], measure("Trade Cost")[1], "Net borne trade cost (US$)")],
          [(measure("Revenue")[0], measure("Revenue")[1], "Revenue (US$)")],
          "Trade cost vs revenue — 13 months", 0, 11, 12, 6, x_type="categorical",
          description="Volume-driven cost moves with revenue; September's spike is matched by revenue."),
    combo("gb_vol_vs_ed", "ds_vol", ("trade_date", "`trade_date`"),
          [("sum(ed_exch_clearing_cost_usd)", "SUM(`ed_exch_clearing_cost_usd`)", "Equity Derivatives exchange & clearing cost (US$)")],
          [("avg(prx_vol_index)", "AVG(`prx_vol_index`)", "PRX Volatility Index")],
          "Volatility spike drives Equity Derivatives activity (Aug–Sep 2026, daily)", 0, 17, 6, 6,
          description="PRX Volatility Index (VHSI-like) vs daily expected exchange and clearing cost of HK Equity Derivatives."),
    bar("gb_bps_vs_plan", "ds_trend", dim("Desk"),
        [(measure("Cost bps of Revenue")[0], measure("Cost bps of Revenue")[1], "Actual (bps of revenue)"),
         (measure("Plan Cost bps of Revenue")[0], measure("Plan Cost bps of Revenue")[1], "Plan (bps of revenue)")],
        "Trade cost as bps of revenue vs plan — September 2026", 6, 17, 6, 6, stacked=False, filters=["`Month` = '2026-09'"],
        yfmt={"type": "number", "decimalPlaces": {"type": "max", "places": 0}}),
]

p_drill = [
    text("drill_header", ["## Drill to the trade\n", "\n",
                          "Mix is computed inside groups that share a volume unit (cost type × fee basis × product family). Two "
                          "groups carry the September mix: **HK Equity Derivatives · PRX 50 Index Futures** (contracts booked to the "
                          "house account at HK$10.00 instead of the registered market-maker account at HK$5.00) and **Australia "
                          "Cash Equities** (smart-order-router change: flow from Tasman Alternative Market at 0.20 bp to Southern "
                          "Cross at 0.60 bp). ", SYNTH], 0, 0, 12, 3),
    bar("drill_mix_groups", "ds_mix_groups", ("desk_product", "`desk_product`"),
        [("sum(mix_usd)", "SUM(`mix_usd`)", "Mix effect (US$)")], "Mix by desk × product family", 0, 3, 6, 6,
        horizontal=True, sort={"by": "value"}, label=True),
    bar("drill_mix_slices", "ds_slice", ("venue_capacity", "`venue_capacity`"),
        [("sum(mix_usd)", "SUM(`mix_usd`)", "Mix effect (US$)")], "Mix by venue · capacity within those groups", 6, 3, 6, 6,
        horizontal=True, color=(("desk_product", "`desk_product`"), "Desk · product"),
        filters=["`desk_product` IN ('HKED · PRX50_FUT', 'AUCE · AU_CASH_EQ')"], sort={"by": "value"}),
    table("drill_slice_table", "ds_slice", [
        ("desk_code", "`desk_code`", "Desk"), ("product_family", "`product_family`", "Product family"),
        ("cost_type", "`cost_type`", "Cost type"), ("vendor_id", "`vendor_id`", "Vendor"), ("venue", "`venue`", "Venue"),
        ("capacity", "`capacity`", "Capacity"), ("volume_unit", "`volume_unit`", "Volume unit"),
        ("v0", "`v0`", "Prior volume", NUM), ("v1", "`v1`", "Current volume", NUM),
        ("unit_cost0_usd", "`unit_cost0_usd`", "Unit cost prior (US$)", RATE),
        ("unit_cost1_cc_usd", "`unit_cost1_cc_usd`", "Unit cost current, const. FX (US$)", RATE),
        ("volume_usd", "`volume_usd`", "Volume (US$)", USD), ("mix_usd", "`mix_usd`", "Mix (US$)", USD),
        ("rate_usd", "`rate_usd`", "Rate (US$)", USD), ("delta_usd", "`delta_usd`", "Change (US$)", USD)],
        "Driver slices (largest mix first)", 0, 9, 12, 7,
        ),
    flt("drill_f_story", "filter-multi-select", [("q_trades_story", "ds_trades", "story_slice")], "Story slice", 0, 16, 3, 2,
        default=["PRX 50 futures booked to the house account", "AU cash equities routed to Southern Cross (SXA)"]),
    flt("drill_f_desk", "filter-multi-select", [("q_trades_desk", "ds_trades", "desk_code")], "Desk", 3, 16, 3, 2),
    flt("drill_f_venue", "filter-multi-select", [("q_trades_venue", "ds_trades", "venue")], "Venue", 6, 16, 3, 2),
    flt("drill_f_capacity", "filter-multi-select", [("q_trades_cap", "ds_trades", "capacity")], "Capacity", 9, 16, 3, 2),
    table("drill_trades", "ds_trades", [
        ("trade_id", "`trade_id`", "Trade"), ("trade_date", "`trade_date`", "Trade date"), ("desk_code", "`desk_code`", "Desk"),
        ("product", "`product`", "Product"), ("venue", "`venue`", "Venue"), ("capacity", "`capacity`", "Capacity"),
        ("fee_id", "`fee_id`", "Fee code"), ("volume", "`volume`", "Volume", NUM), ("volume_unit", "`volume_unit`", "Unit"),
        ("unit_rate", "`unit_rate`", "Contracted rate (LCY / unit)", RATE), ("cost_currency", "`cost_currency`", "CCY"),
        ("cost_lcy", "`cost_lcy`", "Exchange fee (LCY)", {"type": "number", "decimalPlaces": {"type": "exact", "places": 2}}),
        ("cost_usd", "`cost_usd`", "Exchange fee (US$)", {"type": "number-currency", "currencyCode": "USD",
                                                           "decimalPlaces": {"type": "exact", "places": 2}}),
        ("story_slice", "`story_slice`", "Story slice")],
        "September 2026 executions behind the mix (exchange fees)", 0, 18, 12, 8,
        description="One click from the ledger line to the trades: each row is an execution × the contracted exchange fee."),
]

p_invoice = [
    text("inv_header", ["## Invoice vs expected\n", "\n",
                        "Expected cost = every execution × the contracted rate, net of volume-tier rebates. Vendor invoices "
                        "arrive after month end, so at the September close the latest reconcilable month is **August** — "
                        "Cobalt Securities' (*Broker C*) August invoice arrived on 28 September. ", SYNTH], 0, 0, 12, 2),
    flt("inv_f_period", "filter-multi-select", [("q_recon_period", "ds_recon", "Service Period"),
                                                ("q_recon_tbl_period", "ds_recon_tbl", "service_period")],
        "Service period", 0, 2, 4, 2),
    text("inv_note", ["**Over-billing sits outside the September bridge** — it is a billing-correction claim on August, and the "
                      "September accrual re-bases to expected cost automatically."], 4, 2, 8, 2),
    counter("inv_kpi_over", "ds_recon", measure("Overbilled Amount"), "Over-billed — August 2026 invoices", USD, 0, 4, 4, 3,
            filters=["`Service Period` = '2026-08'"]),
    counter("inv_kpi_lines", "ds_recon", measure("Lines With Variance"), "Lines outside tolerance (all months)", None, 4, 4, 4, 3),
    counter("inv_kpi_pending", "ds_recon", measure("Reconciled Lines"), "Lines awaiting the vendor invoice", None, 8, 4, 4, 3,
            filters=["`Recon Status` = 'PENDING_INVOICE'"]),
    bar("inv_by_vendor", "ds_recon", dim("Vendor"), [(measure("Invoice Variance")[0], measure("Invoice Variance")[1],
                                                      "Invoice variance (US$)")],
        "Invoice variance by vendor (over / under billing)", 0, 7, 6, 6, horizontal=True,
        filters=["`Recon Status` IN ('OVERBILLED', 'UNDERBILLED')"], sort={"by": "value"}, label=True),
    table("inv_broker_c", "ds_recon_line", [
        ("legal_entity", "`legal_entity`", "Entity"), ("fee_id", "`fee_id`", "Fee code"),
        ("fee_description", "`fee_description`", "Fee line"), ("line_status", "`line_status`", "Status"),
        ("expected_net_usd", "`expected_net_usd`", "Expected (US$)", USD),
        ("invoiced_net_usd", "`invoiced_net_usd`", "Invoiced (US$)", USD),
        ("variance_usd", "`variance_usd`", "Variance (US$)", USD)],
        "Broker C (Cobalt Securities) — August commission by fee code", 6, 7, 6, 6,
        description="Billed at the standard 3.0 bp tier; August turnover of US$1.70bn qualified for tier 2 (2.5 bp)."),
    table("inv_table", "ds_recon_tbl", [
        ("service_period", "`service_period`", "Service period"), ("vendor", "`vendor`", "Vendor"),
        ("legal_entity", "`legal_entity`", "Entity"), ("cost_type", "`cost_type`", "Cost type"),
        ("recon_status", "`recon_status`", "Status"), ("expected_net_usd", "`expected_net_usd`", "Expected (US$)", USD),
        ("invoiced_net_usd", "`invoiced_net_usd`", "Invoiced (US$)", USD), ("variance_usd", "`variance_usd`", "Variance (US$)", USD),
        ("variance_reason", "`variance_reason`", "Reason"), ("invoice_received_date", "`invoice_received_date`", "Received"),
        ("invoice_ids", "`invoice_ids`", "Invoices")],
        "Reconciliation lines needing attention", 0, 13, 12, 8,
        ),
]

p_fails = [
    text("fails_header", ["## Settlement fails\n", "\n",
                          "Fail cost accrues daily from fail ageing using each market's rule (Southern Cross: 0.10% of the shortfall "
                          "per business day, A$100–5,000, buy-in after 5 days), net of client recharges. Funding and borrow costs "
                          "are shown separately. ", SYNTH], 0, 0, 12, 2),
    flt("fails_f_month", "filter-single-select", [("q_fails_month", "ds_fails", "Month")], "Month", 0, 2, 4, 2,
        default=["2026-09"]),
    text("fails_note", ["**September:** the increase is concentrated in **Australia Cash Equities** with **Kestrel Asset "
                        "Management** — root cause a Meridian SSI static-data mismatch after Kestrel changed custodian."],
         4, 2, 8, 2),
    counter("fails_kpi_net", "ds_fails", measure("Net Fail Cost"), "Net fail cost", USD, 0, 4),
    counter("fails_kpi_n", "ds_fails", measure("Failed Settlements"), "Failed settlements", None, 3, 4),
    counter("fails_kpi_funding", "ds_fails", measure("Funding Cost"), "Funding cost (shown separately)", USD, 6, 4),
    counter("fails_kpi_borrow", "ds_fails", measure("Borrow Cost"), "Borrow cost (shown separately)", USD, 9, 4),
    bar("fails_by_cpty", "ds_fails", dim("Counterparty"), [(measure("Net Fail Cost")[0], measure("Net Fail Cost")[1],
                                                           "Net fail cost (US$)")],
        "By counterparty", 0, 7, 6, 6, horizontal=True, sort={"by": "value"}),
    bar("fails_by_cause", "ds_fails", dim("Root Cause"), [(measure("Net Fail Cost")[0], measure("Net Fail Cost")[1],
                                                          "Net fail cost (US$)")],
        "By root cause", 6, 7, 6, 6, horizontal=True, sort={"by": "value"}),
    bar("fails_by_location", "ds_fails", dim("Settlement Location"),
        [(measure("Net Fail Cost")[0], measure("Net Fail Cost")[1], "Net fail cost (US$)")],
        "By market (depository / clearing house) and desk", 0, 13, 6, 6, color=(("Desk", "`Desk`"), "Desk")),
    bar("fails_trend", "ds_fails_trend", ("month", "`month`"), [("sum(net_fail_cost_usd)", "SUM(`net_fail_cost_usd`)",
                                                                 "Net fail cost (US$)")],
        "Net fail cost by month", 6, 13, 6, 6, color=(("fail_group", "`fail_group`"), "Fails",
                                                      [{"value": "Kestrel Asset Management · AUCE", "color": "#E15F41"},
                                                       {"value": "All other fails", "color": "#8C9BA5"}])),
    table("fails_fix_list", "ds_fails", [
        ("Counterparty", "`Counterparty`", "Counterparty"), ("Desk", "`Desk`", "Desk"), ("Legal Entity", "`Legal Entity`", "Entity"),
        ("Market", "`Market`", "Market"), ("Settlement Location", "`Settlement Location`", "Settlement location"),
        ("Root Cause", "`Root Cause`", "Root cause"),
        (measure("Failed Settlements")[0], measure("Failed Settlements")[1], "Failed", None),
        (measure("Fail Days")[0], measure("Fail Days")[1], "Fail days", None),
        (measure("Buy-ins")[0], measure("Buy-ins")[1], "Buy-ins", None),
        (measure("Net Fail Cost")[0], measure("Net Fail Cost")[1], "Net fail cost (US$)", USD),
        (measure("Recharged to Clients")[0], measure("Recharged to Clients")[1], "Recharged (US$)", USD)],
        "Operations fix list (largest net fail cost first)", 0, 19, 12, 7, disaggregated=False,
        orders=[{"direction": "DESC", "expression": "MEASURE(`Net Fail Cost`)"}]),
]

p_controls = [
    text("ctl_header", ["## Fee calendar & controls\n", "\n",
                        "Announced fee changes, discounts and waivers ending, and regime changes — with their monthly cost at "
                        "current volumes. The tie-out gate proves the bridge adds up after every build (control evidence). ", SYNTH],
         0, 0, 12, 2),
    table("ctl_fee_calendar", "ds_fee_cal", [
        ("event_date", "`event_date`", "Effective"), ("event_type", "`event_type`", "Event"), ("status", "`status`", "Status"),
        ("vendor", "`vendor`", "Vendor"), ("product_family", "`product_family`", "Product family"),
        ("description", "`description`", "Fee line"),
        ("monthly_impact_usd", "`monthly_impact_usd`", "Monthly impact at current volumes (US$)", USD),
        ("source_doc", "`source_doc`", "Rate card")],
        "Fee and regime calendar", 0, 2, 12, 6),
    counter("ctl_passed", "ds_tie", ("sum(passed_flag)", "SUM(`passed_flag`)"), "Tie-out checks passed", None, 0, 8, 4, 3),
    counter("ctl_failed", "ds_tie", ("sum(failed_flag)", "SUM(`failed_flag`)"), "Tie-out checks failed", None, 4, 8, 4, 3),
    counter("ctl_coverage", "ds_coverage", ("avg(mapped_share)", "AVG(`mapped_share`)"),
            "GL mapped to a counterparty — Sep 2026", {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 2}},
            8, 8, 4, 3, filters=["`month` = '2026-09'"]),
    table("ctl_tie_out", "ds_tie", [
        ("result", "`result`", "Result"), ("check_type", "`check_type`", "Type"), ("check_name", "`check_name`", "Check"),
        ("expected", "`expected`", "Expected", {"type": "number", "decimalPlaces": {"type": "max", "places": 2}}),
        ("actual", "`actual`", "Actual", {"type": "number", "decimalPlaces": {"type": "max", "places": 3}}),
        ("checked_at", "`checked_at`", "Checked at")],
        "Tie-out results (gold.tie_out_results)", 0, 11, 8, 8,
        ),
    bar("ctl_unmapped", "ds_coverage", ("month", "`month`"), [("sum(unmapped_usd)", "SUM(`unmapped_usd`)", "Unmapped GL (US$)")],
        "GL booked to unmapped AP vendors (the unexplained residual)", 8, 11, 4, 8, yfmt=USD),
]

p_filters = [
    flt("g_comparison", "filter-single-select",
        [("q_g_flux", "ds_flux", "Comparison Label"), ("q_g_steps", "ds_steps", "comparison_label"),
         ("q_g_slice", "ds_slice", "comparison_label"), ("q_g_mix", "ds_mix_groups", "comparison_label")],
        "Comparison", 0, 0, 4, 2, default=[DEFAULT_COMPARISON]),
]

DASHBOARD = {
    "datasets": DATASETS,
    "pages": [
        {"name": "flux", "displayName": "Flux", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": p_flux},
        {"name": "good_bad", "displayName": "Good vs bad flux", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
         "layout": p_good_bad},
        {"name": "drill", "displayName": "Drill to trade", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
         "layout": p_drill},
        {"name": "invoice", "displayName": "Invoice vs expected", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
         "layout": p_invoice},
        {"name": "fails", "displayName": "Fails", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": p_fails},
        {"name": "controls", "displayName": "Fee calendar & controls", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
         "layout": p_controls},
        {"name": "filters", "displayName": "Filters", "pageType": "PAGE_TYPE_GLOBAL_FILTERS", "layoutVersion": "GRID_V1",
         "layout": p_filters},
    ],
    "uiSettings": {"theme": {
        "canvasBackgroundColor": {"light": "#F7F9FB", "dark": "#1B232A"},
        "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#11171C"},
        "widgetBorderColor": {"light": "#FFFFFF", "dark": "#11171C"},
        "fontColor": {"light": "#13212E", "dark": "#E8ECF0"},
        "selectionColor": {"light": "#2272B4", "dark": "#8ACAFF"},
        "visualizationColors": ["#1F4E79", "#F5A623", "#17A589", "#8E6BBF", "#E15F41", "#4FA3D9", "#B5835A", "#8C9BA5"],
        "widgetHeaderAlignment": "LEFT",
    }},
}

if __name__ == "__main__":
    OUT.write_text(json.dumps(DASHBOARD, indent=2, ensure_ascii=False))
    n_widgets = sum(len(p["layout"]) for p in DASHBOARD["pages"])
    print(f"wrote {OUT} — {len(DATASETS)} datasets, {len(DASHBOARD['pages'])} pages, {n_widgets} widgets")
