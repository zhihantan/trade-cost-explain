-- Monthly cost views for dashboards and Genie: actual (GL, net borne) next to expected, gross, recoverable and intra-group;
-- desk KPIs: cost per trade, per US$M notional, bps of revenue (vs plan), fail rate.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW cost_monthly
COMMENT 'Gold: trade cost by month × business × desk × cost type × vendor × entity × currency: actual net borne (GL), expected net borne, gross, recoverable (statutory levies / taxes / GST recharged or recovered) and intra-group (eliminated).'
CLUSTER BY (period, desk_code)
WITH ROW FILTER ${catalog}.gold.ce_desk_scope ON (desk_code)
AS
WITH gl AS (
  SELECT period, desk_code, cost_type, COALESCE(vendor_id, ap_vendor_id) AS vendor_id, legal_entity, currency,
         SUM(IF(in_net_borne, amount_usd, 0D)) AS actual_net_borne_usd,
         SUM(IF(in_net_borne, amount_lcy, 0D)) AS actual_net_borne_lcy
  FROM gl_monthly GROUP BY ALL
),
ex AS (
  SELECT period, desk_code, CASE WHEN cost_type IN ('GST_REC') THEN 'GST_REC' ELSE cost_type END AS cost_type,
         billing_vendor_id AS vendor_id, legal_entity, cost_currency AS currency,
         SUM(IF(in_net_borne, cost_usd, 0D)) AS expected_net_borne_usd,
         SUM(cost_usd) AS gross_cost_usd,
         SUM(IF(is_recoverable, cost_usd, 0D)) AS recoverable_cost_usd,
         SUM(IF(is_affiliate, cost_usd, 0D)) AS intragroup_cost_usd
  FROM expected_cost_monthly GROUP BY ALL
),
k AS (SELECT period, desk_code, cost_type, vendor_id, legal_entity, currency FROM gl
      UNION SELECT period, desk_code, cost_type, vendor_id, legal_entity, currency FROM ex)
SELECT k.*, fc.month_label, fc.fiscal_year_label, fc.fiscal_quarter_id, fc.fiscal_quarter_label, fc.fiscal_half_id,
       d.business_code, d.business, d.desk_name,
       element_at(map('EXCHANGE', 'Exchange & clearing', 'CLEARING', 'Exchange & clearing', 'BROKERAGE', 'Brokerage',
                      'SETTLEMENT', 'Settlement & custody', 'LEVY', 'Levies & taxes', 'TAX', 'Levies & taxes',
                      'GST_NONREC', 'Non-recoverable GST', 'GST_REC', 'Recoverable GST', 'FAILS', 'Settlement fails',
                      'FIXED', 'Fixed fees'), k.cost_type) AS cost_category,
       v.vendor_name,
       COALESCE(gl.actual_net_borne_usd, 0D) AS actual_net_borne_usd,
       COALESCE(gl.actual_net_borne_lcy, 0D) AS actual_net_borne_lcy,
       COALESCE(ex.expected_net_borne_usd, 0D) AS expected_net_borne_usd,
       COALESCE(ex.gross_cost_usd, 0D) AS gross_cost_usd,
       COALESCE(ex.recoverable_cost_usd, 0D) AS recoverable_cost_usd,
       COALESCE(ex.intragroup_cost_usd, 0D) AS intragroup_cost_usd
FROM k
LEFT JOIN gl USING (period, desk_code, cost_type, vendor_id, legal_entity, currency)
LEFT JOIN ex USING (period, desk_code, cost_type, vendor_id, legal_entity, currency)
LEFT JOIN silver.dim_fiscal_calendar fc ON fc.period = k.period
LEFT JOIN (SELECT DISTINCT desk_code, desk_name, business_code, business FROM silver.dim_desk_hierarchy WHERE is_current) d
       ON d.desk_code = k.desk_code
LEFT JOIN silver.dim_vendor v ON v.vendor_id = k.vendor_id;

CREATE OR REFRESH MATERIALIZED VIEW cost_kpis
COMMENT 'Gold: desk KPIs by month — trades, contracts, notional (US$), net borne cost, cost per trade, cost per US$M notional, cost as bps of revenue (actual and plan), settlement fail rate and fail cost.'
WITH ROW FILTER ${catalog}.gold.ce_desk_scope ON (desk_code)
AS
WITH tr AS (
  SELECT t.period, t.desk_code, COUNT(*) AS trades, SUM(t.contracts) AS contracts,
         SUM(t.notional * fx.rate_to_usd) AS notional_usd
  FROM silver.trades t JOIN silver.fx_monthly fx ON fx.currency = t.currency AND fx.period = t.period
  GROUP BY ALL
),
cost AS (
  SELECT period, desk_code, SUM(actual_net_borne_usd) AS net_borne_cost_usd, SUM(expected_net_borne_usd) AS expected_cost_usd
  FROM cost_monthly GROUP BY ALL
),
rev AS (SELECT period, desk_code, SUM(revenue_usd) AS revenue_usd FROM silver.desk_revenue GROUP BY ALL),
pl AS (SELECT period, desk_code, SUM(plan_cost_usd) AS plan_cost_usd, SUM(plan_revenue_usd) AS plan_revenue_usd
       FROM silver.trade_cost_plan GROUP BY ALL),
st AS (
  SELECT date_format(s.settle_due_date, 'yyyy-MM') AS period, t.desk_code, COUNT(*) AS settlements,
         SUM(IF(s.settle_status <> 'SETTLED', 1, 0)) AS failed_settlements
  FROM silver.settlements s JOIN silver.trades t ON t.trade_id = s.trade_id GROUP BY ALL
),
fl AS (SELECT period, desk_code, SUM(net_usd) AS fail_cost_usd FROM fail_cost_daily GROUP BY ALL)
SELECT tr.period, fc.month_label, fc.fiscal_year_label, fc.fiscal_quarter_id, fc.fiscal_half_id,
       d.business_code, d.business, tr.desk_code, d.desk_name, d.hub,
       tr.trades, tr.contracts, tr.notional_usd, c.net_borne_cost_usd, c.expected_cost_usd, r.revenue_usd,
       p.plan_cost_usd, p.plan_revenue_usd, st.settlements, st.failed_settlements, COALESCE(fl.fail_cost_usd, 0D) AS fail_cost_usd,
       c.net_borne_cost_usd / NULLIF(tr.trades, 0)                       AS cost_per_trade_usd,
       c.net_borne_cost_usd / NULLIF(tr.notional_usd / 1e6, 0)           AS cost_per_usd_mn_notional,
       c.net_borne_cost_usd / NULLIF(r.revenue_usd, 0) * 1e4             AS cost_bps_of_revenue,
       p.plan_cost_usd / NULLIF(p.plan_revenue_usd, 0) * 1e4             AS plan_cost_bps_of_revenue,
       st.failed_settlements / NULLIF(st.settlements, 0)                 AS fail_rate
FROM tr
LEFT JOIN cost c USING (period, desk_code)
LEFT JOIN rev r  USING (period, desk_code)
LEFT JOIN pl p   USING (period, desk_code)
LEFT JOIN st     USING (period, desk_code)
LEFT JOIN fl     USING (period, desk_code)
LEFT JOIN silver.dim_fiscal_calendar fc ON fc.period = tr.period
LEFT JOIN (SELECT DISTINCT desk_code, desk_name, business_code, business, hub FROM silver.dim_desk_hierarchy WHERE is_current) d
       ON d.desk_code = tr.desk_code;
