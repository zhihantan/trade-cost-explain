-- Unity Catalog metric views: one governed definition of every trade-cost metric, shared by the AI/BI dashboard,
-- the Genie space and the commentary agent. One fact source per view (Genie design rule) — the cost bridge itself is
-- precomputed and deterministic in gold.cost_flux_bridge — these views only aggregate it.

CREATE OR REPLACE VIEW cost_explain.gold.trade_cost_flux_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: cost_explain.gold.cost_flux_bridge
comment: >-
  Trade cost explain (cost bridge) for APAC Global Markets: why net borne trade costs moved between two periods, in US$.
  Every comparison (month vs prior month, fiscal quarter vs prior quarter) is decomposed into volume, mix, rate, FX,
  settlement fails, fixed fees, timing / accrual and an unexplained residual that add up exactly to the change.
  Volume, mix and rate are at constant currency (prior-period FX) — FX is measured separately. Default comparison is
  MOM_2026-09 (September vs August 2026, the half-year close). Synthetic data (Meridian Group).
joins:
  - name: dim_cmp
    source: cost_explain.gold.dim_comparison
    'on': source.comparison_id = dim_cmp.comparison_id
dimensions:
  - name: Comparison
    expr: source.comparison_id
    comment: "Comparison id: MOM_YYYY-MM (month vs prior month) or QOQ_FYyyyyQn (fiscal quarter vs prior quarter). MOM_2026-09 = September vs August 2026."
    display_name: Comparison
    synonyms: [period comparison, comparison id, flux period]
  - name: Comparison Label
    expr: dim_cmp.comparison_label
    comment: "Readable comparison, e.g. “Sep 2026 vs Aug 2026” or “FY2026/27 Q2 vs FY2026/27 Q1”."
    display_name: Comparison label
    synonyms: [period, versus, vs]
  - name: Comparison Type
    expr: dim_cmp.comparison_type
    comment: "MoM = month on month — QoQ = fiscal quarter on quarter (fiscal year April–March)."
    display_name: Comparison type
    synonyms: [month on month, quarter on quarter]
  - name: Prior Period
    expr: dim_cmp.p0_label
    comment: "Prior period of the comparison (P0), e.g. Aug 2026 or FY2026/27 Q1."
    display_name: Prior period
    synonyms: [P0, base period, previous month, last month]
  - name: Current Period
    expr: dim_cmp.p1_label
    comment: "Current period of the comparison (P1), e.g. Sep 2026 or FY2026/27 Q2."
    display_name: Current period
    synonyms: [P1, this month, reporting period]
  - name: Business
    expr: source.business
    comment: "Business line within APAC Global Markets: Cash Equities, Equity Derivatives, Prime & Delta One, Rates, Credit, FX & Emerging Markets."
    display_name: Business
    synonyms: [business line, division segment]
  - name: Desk
    expr: source.desk_name
    comment: "Trading desk, e.g. HK Equity Derivatives, Australia Cash Equities, India Equities."
    display_name: Desk
    synonyms: [trading desk, desk name]
  - name: Desk Code
    expr: source.desk_code
    comment: "Desk code, e.g. HKED (HK Equity Derivatives), AUCE (Australia Cash Equities)."
    display_name: Desk code
  - name: Legal Entity
    expr: source.legal_entity_name
    comment: "Booking legal entity, e.g. Meridian Securities (Hong Kong) Limited."
    display_name: Legal entity
    synonyms: [entity, booking entity, LE]
  - name: Cost Category
    expr: source.cost_category
    comment: "Exchange & clearing, Brokerage, Settlement & custody, Levies & taxes (borne), Non-recoverable GST, Settlement fails, Fixed fees."
    display_name: Cost category
    synonyms: [cost type group, fee category]
  - name: Cost Type
    expr: source.cost_type
    comment: "Detailed cost type: EXCHANGE, CLEARING, BROKERAGE, SETTLEMENT, LEVY, TAX, GST_NONREC, FAILS, FIXED."
    display_name: Cost type
  - name: Headline Slice
    expr: source.headline_slice
    comment: "“Equity Derivatives — exchange & clearing” (Equity Derivatives business, exchange and clearing fees) or “Rest of APAC Global Markets”."
    display_name: Headline slice
    synonyms: [equity derivatives exchange and clearing fees, ED exchange and clearing]
  - name: Vendor
    expr: source.vendor_name
    comment: "Vendor billing the cost: exchange, CCP, broker, connectivity provider, or an AP vendor not yet mapped to a counterparty."
    display_name: Vendor
    synonyms: [broker, exchange, venue, CCP, clearing house, counterparty vendor]
  - name: Vendor Type
    expr: source.vendor_type
    comment: "Exchange, CCP, Broker, Broker (intra-group), Connectivity, or “Unmapped AP vendor”."
    display_name: Vendor type
  - name: Market
    expr: source.market
    comment: "Market: HK, CN (Stock Connect), SG, AU, IN, KR, TW, MY."
    display_name: Market
    synonyms: [country, exchange market]
  - name: Currency
    expr: source.currency
    comment: "Local currency of the cost (USD, HKD, CNH, SGD, AUD, INR, KRW, TWD, MYR)."
    display_name: Currency
    synonyms: [local currency, LCY]
measures:
  - name: Prior Period Cost
    expr: SUM(source.p0_actual_usd)
    comment: "Net borne trade cost in the prior period, US$ at that period’s average FX."
    display_name: Prior period cost (US$)
    synonyms: [P0 cost, August cost, last month cost]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Current Period Cost
    expr: SUM(source.p1_actual_usd)
    comment: "Net borne trade cost in the current period, US$ at that period’s average FX."
    display_name: Current period cost (US$)
    synonyms: [P1 cost, September cost, this month cost, trade costs]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Current Period Cost at Constant Currency
    expr: SUM(source.p1_cc_usd)
    comment: "Current-period cost translated at prior-period FX (constant currency)."
    display_name: Current period cost at constant currency (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Cost Change
    expr: SUM(source.flux_usd)
    comment: "Change in net borne trade cost (current minus prior), US$. Equals the sum of all effects."
    display_name: Cost change (US$)
    synonyms: [flux, variance, increase, movement, why did costs go up]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Cost Change Pct
    expr: "MEASURE(`Cost Change`) / MEASURE(`Prior Period Cost`)"
    comment: "Cost change as a share of prior-period cost."
    display_name: Cost change (%)
    synonyms: [flux percent, percentage change]
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Volume Effect
    expr: SUM(source.volume_usd)
    comment: "Cost change from activity volume (contracts, turnover, trade counts) at prior unit cost, constant currency. Volume-driven (“good”) flux."
    display_name: Volume effect (US$)
    synonyms: [volume, activity, volume driven]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Mix Effect
    expr: SUM(source.mix_usd)
    comment: "Cost change from shifts in venue, capacity (house / client / market maker), broker, product or market within the same volume group — routing and booking choices. Controllable."
    display_name: Mix effect (US$)
    synonyms: [mix, routing, venue mix, capacity mix]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Rate Effect
    expr: SUM(source.rate_usd)
    comment: "Cost change from unit-rate changes at current volume: fee schedule changes, discounts ending, levy or tax changes, rebate tiers."
    display_name: Rate effect (US$)
    synonyms: [rate, price, fee change, tariff change]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: FX Effect
    expr: SUM(source.fx_usd)
    comment: "Translation effect of local-currency costs: current-period local cost × (current FX − prior FX). Negative = local currencies weakened against the US$."
    display_name: FX effect (US$)
    synonyms: [FX, currency, translation]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Fails Effect
    expr: SUM(source.fails_usd)
    comment: "Change in settlement-fail cost (per-day fail fees, default fees, buy-ins, close-outs) net of client recharges, constant currency. Controllable."
    display_name: Fails effect (US$)
    synonyms: [fails, settlement fails, fail fees]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Fixed Fees Effect
    expr: SUM(source.fixed_usd)
    comment: "Change in contracted fixed fees (participant, access, connectivity) at constant currency — usually zero."
    display_name: Fixed fees effect (US$)
    synonyms: [fixed fees, membership, connectivity]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Timing Effect
    expr: SUM(source.timing_usd)
    comment: "Accrual / timing noise: change in (GL actual − driver-based cost) on mapped GL lines, e.g. an over-accrual in the prior month reversed in the current month."
    display_name: Timing / accrual effect (US$)
    synonyms: [timing, accrual, accrual reversal, true-up]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Unexplained
    expr: SUM(source.unexplained_usd)
    comment: "Residual not explained by drivers — by construction GL booked to AP vendors not yet mapped to a counterparty. Monitored against a US$25K / 5% threshold."
    display_name: Unexplained (US$)
    synonyms: [residual, unexplained residual, other]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Good Flux
    expr: SUM(source.volume_usd)
    comment: "Volume-driven (“good”) flux: the part of the change explained by activity volume, normally matched by revenue."
    display_name: Good flux — volume-driven (US$)
    synonyms: [good flux, volume driven cost]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Controllable Flux
    expr: SUM(source.mix_usd + source.fails_usd)
    comment: "Controllable (“bad”) flux = mix + fails: routing / booking choices and settlement fails that Operations and the desks can fix."
    display_name: Controllable flux — mix + fails (US$)
    synonyms: [bad flux, controllable cost, controllable]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: External Timing and Residual
    expr: SUM(source.rate_usd + source.fx_usd + source.timing_usd + source.fixed_usd + source.unexplained_usd)
    comment: "Rate + FX + timing + fixed + unexplained: external price changes, translation and accrual noise."
    display_name: External, timing and residual (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Good Flux Share
    expr: "MEASURE(`Good Flux`) / MEASURE(`Cost Change`)"
    comment: "Share of the cost change that is volume-driven."
    display_name: Good flux share (%)
    format: {type: percentage, decimal_places: {type: max, places: 0}}
  - name: Controllable Flux Share
    expr: "MEASURE(`Controllable Flux`) / MEASURE(`Cost Change`)"
    comment: "Share of the cost change that is controllable (mix + fails)."
    display_name: Controllable flux share (%)
    format: {type: percentage, decimal_places: {type: max, places: 0}}
$$;

CREATE OR REPLACE VIEW cost_explain.gold.trade_cost_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: cost_explain.gold.cost_monthly
comment: >-
  Monthly trade costs for APAC Global Markets (GL account line "Commissions and floor brokerage"), US$: actual net borne
  cost from the GL next to expected cost (every trade × contracted rate), gross cost, recoverable statutory levies,
  taxes and GST, and intra-group charges eliminated on consolidation. Fiscal year April–March. Synthetic data.
dimensions:
  - name: Month
    expr: source.period
    comment: "Calendar month YYYY-MM (13 months, Sep 2025 – Sep 2026)."
    display_name: Month
    synonyms: [period, calendar month]
  - name: Month Label
    expr: source.month_label
    comment: "Month as text, e.g. “Sep 2026”."
    display_name: Month label
  - name: Fiscal Year
    expr: source.fiscal_year_label
    comment: "Fiscal year April–March, e.g. FY2026/27 = Apr 2026 – Mar 2027."
    display_name: Fiscal year
    synonyms: [FY]
  - name: Fiscal Quarter
    expr: source.fiscal_quarter_label
    comment: "Fiscal quarter, e.g. “FY2026/27 Q2” = Jul–Sep 2026."
    display_name: Fiscal quarter
    synonyms: [quarter, fiscal Q2, Q1]
  - name: Fiscal Half
    expr: source.fiscal_half_id
    comment: "Fiscal half, e.g. FY2026H1 = Apr–Sep 2026 (half-year close in September)."
    display_name: Fiscal half
    synonyms: [H1, half year, year to date]
  - name: Business
    expr: source.business
    comment: "Business line within APAC Global Markets."
    display_name: Business
  - name: Desk
    expr: source.desk_name
    comment: "Trading desk."
    display_name: Desk
  - name: Cost Category
    expr: source.cost_category
    comment: "Exchange & clearing, Brokerage, Settlement & custody, Levies & taxes (gross — use the net borne and recoverable measures to split), Non-recoverable GST, Recoverable GST, Settlement fails, Fixed fees."
    display_name: Cost category
  - name: Cost Type
    expr: source.cost_type
    comment: "Detailed cost type."
    display_name: Cost type
  - name: Vendor
    expr: COALESCE(source.vendor_name, source.vendor_id)
    comment: "Vendor billing the cost (exchange, CCP, broker, connectivity, or unmapped AP vendor id)."
    display_name: Vendor
    synonyms: [broker, exchange, venue]
  - name: Legal Entity
    expr: source.legal_entity
    comment: "Booking legal entity code (MSHK, MSSG, MSAU, MSIN, MSKR, MSTW, MSMY)."
    display_name: Legal entity
  - name: Currency
    expr: source.currency
    comment: "Local currency of the cost."
    display_name: Currency
measures:
  - name: Net Borne Trade Cost
    expr: SUM(source.actual_net_borne_usd)
    comment: "Actual net borne trade cost from the GL (US$): excludes recharged statutory levies / taxes, recoverable GST and intra-group charges."
    display_name: Net borne trade cost (US$)
    synonyms: [trade costs, actual cost, net cost, commissions and floor brokerage]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Expected Trade Cost
    expr: SUM(source.expected_net_borne_usd)
    comment: "Expected net borne trade cost = executions × contracted rates from the approved fee schedule (US$)."
    display_name: Expected trade cost (US$)
    synonyms: [expected cost, driver-based cost, should-cost]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Gross Trade Cost
    expr: SUM(source.gross_cost_usd)
    comment: "Expected gross cost including recoverable levies, taxes, GST and intra-group charges (US$)."
    display_name: Gross trade cost (US$)
    synonyms: [gross cost]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Recoverable Levies and Taxes
    expr: SUM(source.recoverable_cost_usd)
    comment: "Statutory levies, stamp duty / transaction taxes recharged to clients and recoverable GST (US$)."
    display_name: Recoverable levies, taxes and GST (US$)
    synonyms: [recharged levies, recoverable tax, stamp duty recharged, pass-through]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Intra-group Charges Eliminated
    expr: SUM(source.intragroup_cost_usd)
    comment: "Intra-group agency execution charges (Meridian Execution Services) eliminated on consolidation (US$)."
    display_name: Intra-group charges eliminated (US$)
    synonyms: [affiliate charges, intercompany]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Actual vs Expected
    expr: SUM(source.actual_net_borne_usd - source.expected_net_borne_usd)
    comment: "GL actual minus expected net borne cost (accrual noise, fails, fixed fees, unmapped GL) (US$)."
    display_name: Actual minus expected (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
$$;

CREATE OR REPLACE VIEW cost_explain.gold.desk_cost_kpi_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: cost_explain.gold.cost_kpis
comment: >-
  Desk trade-cost KPIs by month: activity (trades, contracts, US$ notional), net borne trade cost, revenue and the
  FY2026/27 plan, with cost per trade, cost per US$ million notional, cost as basis points of revenue (actual and plan)
  and settlement fail rate. Synthetic data.
dimensions:
  - name: Month
    expr: source.period
    comment: "Calendar month YYYY-MM."
    display_name: Month
  - name: Fiscal Quarter
    expr: source.fiscal_quarter_id
    comment: "Fiscal quarter id, e.g. FY2026Q2 = Jul–Sep 2026."
    display_name: Fiscal quarter
  - name: Fiscal Half
    expr: source.fiscal_half_id
    comment: "Fiscal half id, e.g. FY2026H1 = Apr–Sep 2026."
    display_name: Fiscal half
    synonyms: [H1, year to date]
  - name: Business
    expr: source.business
    comment: "Business line."
    display_name: Business
  - name: Desk
    expr: source.desk_name
    comment: "Trading desk."
    display_name: Desk
  - name: Hub
    expr: source.hub
    comment: "Desk hub city: Hong Kong, Singapore, Sydney, Mumbai or Seoul / Taipei."
    display_name: Hub
    synonyms: [location, city, booking hub]
measures:
  - name: Trades
    expr: SUM(source.trades)
    comment: "Number of executions."
    display_name: Trades
    synonyms: [executions, trade count]
    format: {type: number, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Contracts
    expr: SUM(source.contracts)
    comment: "Listed-derivative contract-sides traded."
    display_name: Contracts
    format: {type: number, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Notional
    expr: SUM(source.notional_usd)
    comment: "Traded notional / turnover in US$."
    display_name: Notional (US$)
    synonyms: [turnover, consideration]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Trade Cost
    expr: SUM(source.net_borne_cost_usd)
    comment: "Net borne trade cost (US$, GL actual)."
    display_name: Trade cost (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Revenue
    expr: SUM(source.revenue_usd)
    comment: "Desk revenue (commissions and trading revenue), US$."
    display_name: Revenue (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Plan Trade Cost
    expr: SUM(source.plan_cost_usd)
    comment: "FY2026/27 budget for net borne trade cost (US$) — available from April 2026."
    display_name: Plan trade cost (US$)
    synonyms: [budget, plan]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Plan Revenue
    expr: SUM(source.plan_revenue_usd)
    comment: "FY2026/27 budget revenue (US$)."
    display_name: Plan revenue (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Cost per Trade
    expr: "MEASURE(`Trade Cost`) / MEASURE(`Trades`)"
    comment: "Net borne trade cost per execution (US$)."
    display_name: Cost per trade (US$)
    synonyms: [unit cost, cost per execution]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 2}}
  - name: Cost per USD Million Notional
    expr: "MEASURE(`Trade Cost`) / (MEASURE(`Notional`) / 1000000)"
    comment: "Net borne trade cost per US$ million of notional traded."
    display_name: Cost per US$M notional (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 2}}
  - name: Cost bps of Revenue
    expr: "MEASURE(`Trade Cost`) / MEASURE(`Revenue`) * 10000"
    comment: "Trade cost as basis points of revenue."
    display_name: Cost (bps of revenue)
    synonyms: [cost to revenue, cost income, bps of revenue]
    format: {type: number, decimal_places: {type: max, places: 0}}
  - name: Plan Cost bps of Revenue
    expr: "MEASURE(`Plan Trade Cost`) / MEASURE(`Plan Revenue`) * 10000"
    comment: "Planned trade cost as basis points of planned revenue."
    display_name: Plan cost (bps of revenue)
    format: {type: number, decimal_places: {type: max, places: 0}}
  - name: Failed Settlements
    expr: SUM(source.failed_settlements)
    comment: "Number of settlements that failed on the due date."
    display_name: Failed settlements
    format: {type: number, decimal_places: {type: max, places: 0}}
  - name: Settlements
    expr: SUM(source.settlements)
    comment: "Number of settlement instructions due."
    display_name: Settlements
    format: {type: number, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Fail Rate
    expr: "MEASURE(`Failed Settlements`) / MEASURE(`Settlements`)"
    comment: "Share of settlements that failed."
    display_name: Fail rate (%)
    format: {type: percentage, decimal_places: {type: max, places: 2}}
$$;

CREATE OR REPLACE VIEW cost_explain.gold.invoice_recon_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: cost_explain.gold.invoice_recon
comment: >-
  Invoice reconciliation: expected cost (every trade × contracted rate, net of volume-tier rebates) versus vendor
  invoices, per vendor × legal entity × service month × cost type, in US$ at the service month’s FX. Lagged one
  period — invoices arrive after month end, so at the September 2026 close August is the latest reconcilable month.
  Synthetic data.
dimensions:
  - name: Service Period
    expr: source.service_period
    comment: "Month the vendor’s service relates to (YYYY-MM)."
    display_name: Service period
    synonyms: [invoice month, billing month]
  - name: Vendor
    expr: COALESCE(source.vendor_name, source.vendor_id)
    comment: "Vendor (exchange, CCP, broker, connectivity). Cobalt Securities is “Broker C”."
    display_name: Vendor
    synonyms: [broker, Broker C, exchange, CCP]
  - name: Vendor Type
    expr: source.vendor_type
    comment: "Exchange, CCP, Broker, Broker (intra-group), Connectivity."
    display_name: Vendor type
  - name: Legal Entity
    expr: source.legal_entity
    comment: "Billed legal entity code."
    display_name: Legal entity
  - name: Cost Type
    expr: source.cost_type
    comment: "Cost type on the invoice (BROKERAGE, EXCHANGE, CLEARING, SETTLEMENT, LEVY, TAX, FAILS, FIXED)."
    display_name: Cost type
  - name: Recon Status
    expr: source.recon_status
    comment: "MATCHED, OVERBILLED, UNDERBILLED or PENDING_INVOICE."
    display_name: Reconciliation status
    synonyms: [status, overbilled, underbilled, pending]
  - name: Variance Reason
    expr: source.variance_reason
    comment: "Inferred reason, e.g. billed at the standard tier instead of the qualifying volume tier (missed rebate)."
    display_name: Variance reason
    synonyms: [reason, finding]
  - name: Currency
    expr: source.currency
    comment: "Invoice currency."
    display_name: Currency
measures:
  - name: Expected Amount
    expr: SUM(source.expected_net_usd)
    comment: "Expected cost net of tax (US$)."
    display_name: Expected (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Invoiced Amount
    expr: SUM(source.invoiced_net_usd)
    comment: "Invoiced amount net of tax (US$)."
    display_name: Invoiced (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Invoice Variance
    expr: SUM(source.variance_usd)
    comment: "Invoiced minus expected including tax (US$). Positive = vendor over-billed."
    display_name: Invoice variance (US$)
    synonyms: [overbilling, billing error, variance]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Overbilled Amount
    expr: SUM(source.variance_usd) FILTER (WHERE source.recon_status = 'OVERBILLED')
    comment: "Over-billing to recover from vendors (US$)."
    display_name: Over-billed (US$)
    synonyms: [billing recovery, claims]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Reconciled Lines
    expr: COUNT(1)
    comment: "Vendor × entity × month × cost-type lines reconciled."
    display_name: Reconciled lines
    format: {type: number, decimal_places: {type: max, places: 0}}
  - name: Lines With Variance
    expr: COUNT(1) FILTER (WHERE source.recon_status IN ('OVERBILLED', 'UNDERBILLED'))
    comment: "Lines outside tolerance."
    display_name: Lines with variance
    format: {type: number, decimal_places: {type: max, places: 0}}
$$;

CREATE OR REPLACE VIEW cost_explain.gold.settlement_fail_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: cost_explain.gold.fail_cost_summary
comment: >-
  Settlement-fail cost by month, desk, legal entity, market (depository / clearing house), counterparty and root
  cause — the Operations fix list. Fail cost accrues daily from fail ageing using each market’s fail_cost_rule
  (per-day fees with min / max, default fees, buy-ins, close-outs) and is reported net of client recharges — funding
  and borrow costs are shown separately. Synthetic data.
dimensions:
  - name: Month
    expr: source.period
    comment: "Month the fail cost accrued (YYYY-MM)."
    display_name: Month
  - name: Desk
    expr: source.desk_code
    comment: "Desk code of the failed trade (e.g. AUCE = Australia Cash Equities)."
    display_name: Desk
  - name: Desk Name
    expr: source.desk_name
    comment: "Desk name of the failed trade, e.g. Australia Cash Equities."
    display_name: Desk name
  - name: Legal Entity
    expr: source.legal_entity
    comment: "Booking legal entity."
    display_name: Legal entity
  - name: Market
    expr: source.market
    comment: "Settlement market."
    display_name: Market
  - name: Settlement Location
    expr: source.settlement_location
    comment: "Depository / clearing house, e.g. SXC-CHESS, PRC-CCASS, MRC-CDP."
    display_name: Settlement location
    synonyms: [depository, CSD, clearing house]
  - name: Counterparty
    expr: source.counterparty_name
    comment: "Counterparty of the failed settlement."
    display_name: Counterparty
    synonyms: [client, street counterparty]
  - name: Root Cause
    expr: source.root_cause
    comment: "Fail root cause, e.g. “Meridian SSI static-data mismatch after counterparty custodian change”."
    display_name: Root cause
    synonyms: [reason, cause]
  - name: Root Cause Class
    expr: source.root_cause_class
    comment: "client, internal or agent."
    display_name: Root cause class
measures:
  - name: Net Fail Cost
    expr: SUM(source.net_cost_usd)
    comment: "Fail cost borne by Meridian after client recharges (US$)."
    display_name: Net fail cost (US$)
    synonyms: [fail cost, settlement fail cost, fails]
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Gross Fail Cost
    expr: SUM(source.gross_cost_usd)
    comment: "Fail cost before recharges (US$)."
    display_name: Gross fail cost (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Recharged to Clients
    expr: SUM(source.gross_cost_usd - source.net_cost_usd)
    comment: "Fail cost recharged to clients and counterparties (US$)."
    display_name: Recharged (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Failed Settlements
    expr: SUM(source.failed_settlements)
    comment: "Number of failed settlements."
    display_name: Failed settlements
    format: {type: number, decimal_places: {type: max, places: 0}}
  - name: Fail Days
    expr: SUM(source.fail_days)
    comment: "Business days of fail ageing (per-day fee days)."
    display_name: Fail days
    format: {type: number, decimal_places: {type: max, places: 0}}
  - name: Buy-ins
    expr: SUM(source.buy_ins)
    comment: "Number of buy-ins executed."
    display_name: Buy-ins
    format: {type: number, decimal_places: {type: max, places: 0}}
  - name: Funding Cost
    expr: SUM(source.funding_cost_usd)
    comment: "Illustrative funding cost of failed settlements at 4.5% p.a. (US$), shown separately from trade cost."
    display_name: Funding cost (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
  - name: Borrow Cost
    expr: SUM(source.borrow_cost_usd)
    comment: "Illustrative securities-borrow cost to cover failed deliveries at 1.5% p.a. (US$), shown separately."
    display_name: Borrow cost (US$)
    format: {type: currency, currency_code: USD, decimal_places: {type: max, places: 0}, abbreviation: compact}
$$;
