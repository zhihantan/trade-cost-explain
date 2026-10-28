"""Benchmark and example SQL for the Trade Cost Explain Genie space (validated read-only against the warehouse)."""
MV = "cost_explain.gold"
BRIDGE_COLS = ("MEASURE(trade_cost_flux_metrics.`Prior Period Cost`) AS prior_period_cost, "
               "MEASURE(trade_cost_flux_metrics.`Current Period Cost`) AS current_period_cost, "
               "MEASURE(trade_cost_flux_metrics.`Cost Change`) AS cost_change, "
               "MEASURE(trade_cost_flux_metrics.`Cost Change Pct`) AS cost_change_pct, "
               "MEASURE(trade_cost_flux_metrics.`Volume Effect`) AS volume_effect, "
               "MEASURE(trade_cost_flux_metrics.`Mix Effect`) AS mix_effect, "
               "MEASURE(trade_cost_flux_metrics.`Rate Effect`) AS rate_effect, "
               "MEASURE(trade_cost_flux_metrics.`Fails Effect`) AS fails_effect, "
               "MEASURE(trade_cost_flux_metrics.`Timing Effect`) AS timing_effect, "
               "MEASURE(trade_cost_flux_metrics.`FX Effect`) AS fx_effect, "
               "MEASURE(trade_cost_flux_metrics.`Fixed Fees Effect`) AS fixed_fees_effect, "
               "MEASURE(trade_cost_flux_metrics.`Unexplained`) AS unexplained")
HK = "'HK Cash Equities', 'HK Equity Derivatives', 'Stock Connect / China Flow', 'Delta One / Prime', 'Flow Credit'"
SG = "'Singapore FX', 'Singapore Rates', 'Singapore EM (incl. Malaysia)'"
AU = "'Australia Cash Equities', 'Australia Rates & Futures'"

BENCHMARKS = {
    "B01": ("Why did APAC trade costs go up in September vs August?",
            f"SELECT {BRIDGE_COLS} FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'MOM_2026-09'",
            "Must give prior US$5.0M, current US$6.2M, change +US$1.2M (+24%) and the effects volume +900K, mix +190K, rate +100K, fails +150K, timing -50K, FX -100K, unexplained +10K (fixed 0); the effects must sum to the change."),
    "B02": ("9月亞太區交易成本上升的主要原因是什麼？",
            f"SELECT {BRIDGE_COLS} FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'MOM_2026-09'",
            "Same answer as the English question for September vs August 2026 (MOM_2026-09)."),
    "B03": ("Which desks have the highest cost per trade, and how has it trended?",
            f"WITH m AS (SELECT desk_cost_kpi_metrics.`Desk` AS desk, desk_cost_kpi_metrics.`Month` AS month, MEASURE(desk_cost_kpi_metrics.`Cost per Trade`) AS cost_per_trade FROM {MV}.desk_cost_kpi_metrics GROUP BY ALL), "
            "top AS (SELECT desk, RANK() OVER (ORDER BY cost_per_trade DESC) AS rnk FROM m WHERE month = '2026-09') "
            "SELECT m.desk, m.month, m.cost_per_trade FROM m JOIN top ON top.desk = m.desk WHERE top.rnk <= 5 ORDER BY m.desk, m.month",
            "Rank desks by September 2026 cost per trade (top five, HK Equity Derivatives highest) and show each one's monthly trend, Sep 2025 – Sep 2026."),
    "B04": ("How much of the trade cost increase is matched by revenue growth?",
            f"WITH rev AS (SELECT desk_cost_kpi_metrics.`Month` AS month, MEASURE(desk_cost_kpi_metrics.`Revenue`) AS revenue FROM {MV}.desk_cost_kpi_metrics WHERE desk_cost_kpi_metrics.`Month` IN ('2026-08', '2026-09') GROUP BY ALL), "
            f"flux AS (SELECT MEASURE(trade_cost_flux_metrics.`Cost Change`) AS cost_change, MEASURE(trade_cost_flux_metrics.`Good Flux`) AS volume_driven_change, MEASURE(trade_cost_flux_metrics.`Good Flux Share`) AS volume_driven_share FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'MOM_2026-09') "
            "SELECT flux.cost_change, flux.volume_driven_change, flux.volume_driven_share, MAX(IF(rev.month = '2026-08', rev.revenue, NULL)) AS revenue_aug, MAX(IF(rev.month = '2026-09', rev.revenue, NULL)) AS revenue_sep, MAX(IF(rev.month = '2026-09', rev.revenue, NULL)) - MAX(IF(rev.month = '2026-08', rev.revenue, NULL)) AS revenue_change FROM flux CROSS JOIN rev GROUP BY flux.cost_change, flux.volume_driven_change, flux.volume_driven_share",
            "Should state that US$900K (75%) of the US$1.2M increase is volume-driven (good flux) and compare it with revenue growth from August to September 2026."),
    "B05": ("Which brokers billed more than the expected cost in fiscal Q2 (July–September)?",
            f"SELECT invoice_recon_metrics.`Vendor`, MEASURE(invoice_recon_metrics.`Invoice Variance`) AS invoice_variance FROM {MV}.invoice_recon_metrics WHERE invoice_recon_metrics.`Service Period` BETWEEN '2026-07' AND '2026-09' AND invoice_recon_metrics.`Vendor Type` LIKE 'Broker%' AND invoice_recon_metrics.`Recon Status` = 'OVERBILLED' GROUP BY ALL ORDER BY invoice_variance DESC",
            "Should list Cobalt Securities (Broker C, August, about US$85K, volume-tier rebate not applied) and Dunmore Capital Markets (July, about US$68K, possible duplicate line); September invoices are not yet received."),
    "B06": ("What are the top 5 counterparties by settlement-fail cost this month?",
            f"SELECT settlement_fail_metrics.`Counterparty`, MEASURE(settlement_fail_metrics.`Net Fail Cost`) AS net_fail_cost FROM {MV}.settlement_fail_metrics WHERE settlement_fail_metrics.`Month` = '2026-09' GROUP BY ALL ORDER BY net_fail_cost DESC LIMIT 5",
            "This month = September 2026. Kestrel Asset Management must be first by a wide margin."),
    "B07": ("Show trade costs as bps of revenue by desk vs. plan.",
            f"SELECT desk_cost_kpi_metrics.`Desk`, MEASURE(desk_cost_kpi_metrics.`Cost bps of Revenue`) AS cost_bps_of_revenue, MEASURE(desk_cost_kpi_metrics.`Plan Cost bps of Revenue`) AS plan_cost_bps_of_revenue FROM {MV}.desk_cost_kpi_metrics WHERE desk_cost_kpi_metrics.`Month` = '2026-09' GROUP BY ALL ORDER BY cost_bps_of_revenue DESC",
            "Default period is September 2026 (latest month); an H1 (FY2026H1) view is also acceptable if stated."),
    "B08": ("Compare cost per trade in Hong Kong, Singapore and Australia.",
            f"WITH d AS (SELECT desk_cost_kpi_metrics.`Desk` AS desk, MEASURE(desk_cost_kpi_metrics.`Trade Cost`) AS trade_cost, MEASURE(desk_cost_kpi_metrics.`Trades`) AS trades FROM {MV}.desk_cost_kpi_metrics WHERE desk_cost_kpi_metrics.`Month` = '2026-09' GROUP BY ALL) "
            f"SELECT CASE WHEN d.desk IN ({HK}) THEN 'Hong Kong' WHEN d.desk IN ({SG}) THEN 'Singapore' WHEN d.desk IN ({AU}) THEN 'Australia' END AS hub, SUM(d.trade_cost) / SUM(d.trades) AS cost_per_trade FROM d WHERE d.desk IN ({HK}, {SG}, {AU}) GROUP BY 1 ORDER BY 1",
            "Hubs group desks (Hong Kong: HK Cash Equities, HK Equity Derivatives, Stock Connect, Delta One / Prime, Flow Credit; Singapore: FX, Rates, EM; Australia: Cash Equities, Rates & Futures); September 2026 by default."),
    "B09": ("Which fee discounts, waivers or regime changes expire in the next six months, and what is the cost impact at current volumes?",
            f"SELECT fee_calendar.event_type, fee_calendar.event_date, fee_calendar.vendor_name, fee_calendar.product_family, fee_calendar.description, fee_calendar.monthly_impact_usd FROM {MV}.fee_calendar WHERE fee_calendar.event_date > fee_calendar.as_of_date AND fee_calendar.event_date <= add_months(fee_calendar.as_of_date, 6) ORDER BY fee_calendar.event_date",
            "Two changes on 1 Jan 2027: the Mini PRX 50 market-maker concession ends (about +US$29K a month) and the Merlion China 50 clearing fee rises (about +US$11K a month)."),
    "B10": ("How much of our cost is statutory levies and taxes, and how much of that do we recharge?",
            f"SELECT MEASURE(trade_cost_metrics.`Gross Trade Cost`) AS gross_levies_and_taxes, MEASURE(trade_cost_metrics.`Recoverable Levies and Taxes`) AS recharged_to_clients, MEASURE(trade_cost_metrics.`Net Borne Trade Cost`) AS borne_by_meridian FROM {MV}.trade_cost_metrics WHERE trade_cost_metrics.`Month` = '2026-09' AND trade_cost_metrics.`Cost Category` = 'Levies & taxes (borne)'",
            "Default period September 2026: gross statutory levies and transaction taxes, the part recharged to clients, and the part borne."),
    "B11": ("Why did equity derivatives exchange and clearing fees go up in September vs August?",
            f"SELECT {BRIDGE_COLS} FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'MOM_2026-09' AND trade_cost_flux_metrics.`Headline Slice` = 'Equity Derivatives — exchange & clearing'",
            "Must give US$2.17M to US$2.68M (+US$510K): volume +390K, mix +90K, rate +60K, timing -20K, FX -10K, fails 0 (listed derivatives clear at a CCP)."),
}

EXAMPLES = {
    "E01": ("What drove the change in trade costs in fiscal Q2 versus Q1?",
            f"SELECT trade_cost_flux_metrics.`Comparison Label`, {BRIDGE_COLS} FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'QOQ_FY2026Q2' GROUP BY ALL",
            "Cost bridge for one comparison: prior, current, change, change % and every effect in narrative order."),
    "E02": ("Break down the August versus July movement in Cash Equities exchange and clearing fees.",
            f"SELECT {BRIDGE_COLS} FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'MOM_2026-08' AND trade_cost_flux_metrics.`Business` = 'Cash Equities' AND trade_cost_flux_metrics.`Cost Category` = 'Exchange & clearing'",
            "Cost bridge for a slice: filter dimensions (business, desk, cost category, headline slice, market, vendor) in WHERE."),
    "E03": ("Which desks drove the mix effect in September?",
            f"SELECT trade_cost_flux_metrics.`Desk`, MEASURE(trade_cost_flux_metrics.`Mix Effect`) AS mix_effect FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'MOM_2026-09' GROUP BY ALL HAVING abs(MEASURE(trade_cost_flux_metrics.`Mix Effect`)) >= 1000 ORDER BY abs(mix_effect) DESC",
            "Contributors to one effect: group by the dimension, filter small values with HAVING, order by absolute size."),
    "E04": ("Which vendors were over-billed for July 2026 services?",
            f"WITH f AS (SELECT invoice_recon_metrics.`Vendor` AS vendor, invoice_recon_metrics.`Service Period` AS service_period, invoice_recon_metrics.`Variance Reason` AS variance_reason, MEASURE(invoice_recon_metrics.`Invoice Variance`) AS invoice_variance FROM {MV}.invoice_recon_metrics WHERE invoice_recon_metrics.`Service Period` = '2026-07' AND invoice_recon_metrics.`Recon Status` = 'OVERBILLED' GROUP BY ALL) "
            "SELECT f.vendor, f.service_period, SUM(f.invoice_variance) AS invoice_variance, max_by(f.variance_reason, f.invoice_variance) AS main_reason FROM f GROUP BY f.vendor, f.service_period ORDER BY invoice_variance DESC",
            "Invoice findings per vendor and service month: the reason text differs by legal entity, so total by vendor and attach the main reason instead of grouping by it."),
    "E05": ("Compare the settlement fail rate of Hong Kong and Australia desks in August.",
            f"WITH d AS (SELECT desk_cost_kpi_metrics.`Desk` AS desk, MEASURE(desk_cost_kpi_metrics.`Failed Settlements`) AS failed, MEASURE(desk_cost_kpi_metrics.`Settlements`) AS settlements FROM {MV}.desk_cost_kpi_metrics WHERE desk_cost_kpi_metrics.`Month` = '2026-08' GROUP BY ALL) "
            f"SELECT CASE WHEN d.desk IN ({HK}) THEN 'Hong Kong' WHEN d.desk IN ({AU}) THEN 'Australia' END AS hub, SUM(d.failed) / SUM(d.settlements) AS fail_rate FROM d WHERE d.desk IN ({HK}, {AU}) GROUP BY 1",
            "Hub comparisons: aggregate measures by desk in a CTE, then map desks to hubs and re-aggregate ratios from their components."),
    "E06": ("Which fee schedule changes have taken effect since July and what do they cost per month?",
            f"SELECT fee_calendar.event_type, fee_calendar.event_date, fee_calendar.vendor_name, fee_calendar.product_family, fee_calendar.monthly_impact_usd FROM {MV}.fee_calendar WHERE fee_calendar.status = 'IN_EFFECT' AND fee_calendar.event_date >= DATE'2026-07-01' ORDER BY fee_calendar.event_date",
            "Fee calendar lookups: filter by status (IN_EFFECT / UPCOMING) and event date."),
    "E07": ("Show net borne trade cost and expected cost by fiscal quarter.",
            f"SELECT trade_cost_metrics.`Fiscal Quarter`, MEASURE(trade_cost_metrics.`Net Borne Trade Cost`) AS net_borne_trade_cost, MEASURE(trade_cost_metrics.`Expected Trade Cost`) AS expected_trade_cost FROM {MV}.trade_cost_metrics GROUP BY ALL ORDER BY trade_cost_metrics.`Fiscal Quarter`",
            "Trend over the fiscal calendar using the fiscal dimensions."),
    "E08": ("What share of the fiscal Q2 versus Q1 cost increase came from higher activity, and how did revenue move?",
            f"WITH rev AS (SELECT desk_cost_kpi_metrics.`Fiscal Quarter` AS fiscal_quarter, MEASURE(desk_cost_kpi_metrics.`Revenue`) AS revenue FROM {MV}.desk_cost_kpi_metrics WHERE desk_cost_kpi_metrics.`Fiscal Quarter` IN ('FY2026Q1', 'FY2026Q2') GROUP BY ALL), "
            f"flux AS (SELECT MEASURE(trade_cost_flux_metrics.`Cost Change`) AS cost_change, MEASURE(trade_cost_flux_metrics.`Good Flux`) AS good_flux, MEASURE(trade_cost_flux_metrics.`Good Flux Share`) AS good_flux_share FROM {MV}.trade_cost_flux_metrics WHERE trade_cost_flux_metrics.`Comparison` = 'QOQ_FY2026Q2') "
            "SELECT flux.cost_change, flux.good_flux, flux.good_flux_share, MAX(IF(rev.fiscal_quarter = 'FY2026Q1', rev.revenue, NULL)) AS revenue_q1, MAX(IF(rev.fiscal_quarter = 'FY2026Q2', rev.revenue, NULL)) AS revenue_q2, MAX(IF(rev.fiscal_quarter = 'FY2026Q2', rev.revenue, NULL)) - MAX(IF(rev.fiscal_quarter = 'FY2026Q1', rev.revenue, NULL)) AS revenue_change FROM flux CROSS JOIN rev GROUP BY flux.cost_change, flux.good_flux, flux.good_flux_share",
            "The part of a cost increase matched (justified) by revenue growth is the Good Flux (volume effect) and its share of the change; show it next to revenue for the same two periods. Never divide revenue growth by the cost change."),
}
