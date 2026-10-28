-- Period comparisons precomputed for the bridge: every month vs prior month, every full fiscal quarter vs prior quarter.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW dim_comparison
COMMENT 'Gold: comparisons available in the cost bridge (MoM for every month, QoQ for consecutive full fiscal quarters). MOM_2026-09 (Sep vs Aug 2026, H1 close) is the default.'
AS
WITH months AS (
  SELECT DISTINCT fx.period, fc.month_label, fc.fiscal_quarter_id, fc.fiscal_quarter_label
  FROM silver.fx_monthly fx JOIN silver.dim_fiscal_calendar fc ON fc.period = fx.period
),
quarters AS (
  SELECT fiscal_quarter_id, MAX(fiscal_quarter_label) AS label, MIN(period) AS first_period
  FROM months GROUP BY fiscal_quarter_id HAVING COUNT(*) = 3
),
q AS (SELECT *, ROW_NUMBER() OVER (ORDER BY first_period) AS qn FROM quarters)
SELECT concat('MOM_', p1.period) AS comparison_id, 'MoM' AS comparison_type, p0.period AS period_p0, p1.period AS period_p1,
       p0.month_label AS p0_label, p1.month_label AS p1_label,
       concat(p1.month_label, ' vs ', p0.month_label) AS comparison_label,
       CAST(replace(p1.period, '-', '') AS INT) AS sort_order, p1.period = '2026-09' AS is_default
FROM months p1
JOIN months p0 ON p0.period = date_format(add_months(to_date(concat(p1.period, '-01')), -1), 'yyyy-MM')
UNION ALL
SELECT concat('QOQ_', q1.fiscal_quarter_id), 'QoQ', q0.fiscal_quarter_id, q1.fiscal_quarter_id, q0.label, q1.label,
       concat(q1.label, ' vs ', q0.label), 900000 + q1.qn, FALSE
FROM q q1 JOIN q q0 ON q0.qn = q1.qn - 1;

CREATE OR REFRESH MATERIALIZED VIEW comparison_period
COMMENT 'Gold: calendar months making up P0 and P1 of each comparison.'
AS SELECT c.comparison_id, 'P0' AS role, fc.period
FROM dim_comparison c JOIN silver.dim_fiscal_calendar fc
  ON (c.comparison_type = 'MoM' AND fc.period = c.period_p0) OR (c.comparison_type = 'QoQ' AND fc.fiscal_quarter_id = c.period_p0)
UNION ALL
SELECT c.comparison_id, 'P1', fc.period
FROM dim_comparison c JOIN silver.dim_fiscal_calendar fc
  ON (c.comparison_type = 'MoM' AND fc.period = c.period_p1) OR (c.comparison_type = 'QoQ' AND fc.fiscal_quarter_id = c.period_p1);

CREATE OR REFRESH MATERIALIZED VIEW comparison_fx
COMMENT 'Gold: constant-currency basis per comparison — the average monthly rate over the P0 months.'
AS SELECT cp.comparison_id, fx.currency, AVG(fx.rate_to_usd) AS fx0
FROM comparison_period cp JOIN silver.fx_monthly fx ON fx.period = cp.period
WHERE cp.role = 'P0'
GROUP BY cp.comparison_id, fx.currency;
