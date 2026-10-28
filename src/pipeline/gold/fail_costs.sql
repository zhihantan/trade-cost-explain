-- Settlement-fail cost accrued daily from fail ageing using the market fail_cost_rule (not waiting for invoices):
-- per business day the shortfall persists (min / max per day), one-off default fee, auction close-out (India),
-- buy-in on the last day. Client-caused fails on client capacity are recharged. Funding and borrow shown separately.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW fail_cost_daily
COMMENT 'Gold: fail cost per fail day and component (PER_DAY_FEE, DEFAULT_FEE, CLOSE_OUT, BUY_IN), gross, recharged and net, with illustrative funding and borrow costs.'
CLUSTER BY (fail_date, market)
AS
WITH cal AS (
  SELECT market, calendar_date, ROW_NUMBER() OVER (PARTITION BY market ORDER BY calendar_date) AS bd_seq
  FROM silver.business_calendar WHERE is_business_day
),
f AS (
  SELECT s.*, t.desk_code, t.legal_entity, t.capacity, t.book, t.side, t.trade_date, t.product_family,
         r.vendor_id AS rule_vendor_id, r.rule_type, r.pct_per_day, r.min_per_day, r.max_per_day
  FROM silver.settlements s
  JOIN silver.trades t          ON t.trade_id = s.trade_id
  JOIN silver.fail_cost_rule r  ON r.market = s.market
  WHERE s.settle_status <> 'SETTLED'
),
d AS (
  SELECT f.*, c2.calendar_date AS fail_date, c2.bd_seq - c1.bd_seq + 1 AS fail_day_no
  FROM f
  JOIN cal c1 ON c1.market = f.market AND c1.calendar_date = f.settle_due_date
  JOIN cal c2 ON c2.market = f.market AND c2.bd_seq BETWEEN c1.bd_seq AND c1.bd_seq + greatest(f.fail_days, 1) - 1
),
comp AS (
  SELECT *, 'PER_DAY_FEE' AS component,
         LEAST(GREATEST(pct_per_day * shortfall_value, COALESCE(min_per_day, 0D)),
               COALESCE(max_per_day, CAST('Infinity' AS DOUBLE)))         AS amount_lcy
  FROM d WHERE rule_type = 'PER_DAY_PCT'
  UNION ALL
  SELECT *, 'DEFAULT_FEE', default_fee FROM d WHERE fail_day_no = 1 AND default_fee > 0
  UNION ALL
  SELECT *, 'CLOSE_OUT', GREATEST(pct_per_day * shortfall_value, COALESCE(min_per_day, 0D))
  FROM d WHERE rule_type = 'CLOSE_OUT_PCT' AND fail_day_no = 1
  UNION ALL
  SELECT *, 'BUY_IN', buy_in_cost FROM d WHERE fail_day_no = greatest(fail_days, 1) AND buy_in_cost > 0
)
SELECT c.trade_id, c.settlement_id, c.fail_date, date_format(c.fail_date, 'yyyy-MM') AS period, c.fail_day_no, c.fail_days,
       c.desk_code, c.book, c.legal_entity, c.market, c.settlement_location, c.capacity, c.side, c.counterparty_id,
       c.rule_vendor_id, c.currency, c.root_cause, c.root_cause_class, c.resolution, c.shortfall_value, c.component,
       c.amount_lcy,
       IF(c.recharged_to_client > 0, c.amount_lcy, 0D)                                   AS recharged_lcy,
       c.amount_lcy - IF(c.recharged_to_client > 0, c.amount_lcy, 0D)                     AS net_lcy,
       (c.amount_lcy - IF(c.recharged_to_client > 0, c.amount_lcy, 0D)) * fx.rate_to_usd  AS net_usd,
       c.amount_lcy * fx.rate_to_usd                                                      AS gross_usd,
       IF(c.component = 'PER_DAY_FEE', c.shortfall_value * 0.045 / 365, 0D) * fx.rate_to_usd AS funding_cost_usd,
       IF(c.component = 'PER_DAY_FEE' AND c.side = 'SELL', c.shortfall_value * 0.015 / 365, 0D) * fx.rate_to_usd AS borrow_cost_usd
FROM comp c
JOIN silver.fx_monthly fx ON fx.currency = c.currency AND fx.period = date_format(c.fail_date, 'yyyy-MM');

CREATE OR REFRESH MATERIALIZED VIEW fail_cost_summary
COMMENT 'Gold: settlement-fail cost by month × desk × legal entity × market (depository / CCP) × counterparty × root cause — the Operations fix list.'
WITH ROW FILTER ${catalog}.gold.ce_desk_scope ON (desk_code)
AS SELECT f.period, f.desk_code, d.desk_name, f.legal_entity, f.market, f.settlement_location, f.rule_vendor_id, f.counterparty_id,
          cp.counterparty_name, cp.lei AS counterparty_lei, f.root_cause, f.root_cause_class, f.currency,
          COUNT(DISTINCT f.trade_id)                      AS failed_settlements,
          SUM(IF(f.component = 'PER_DAY_FEE', 1, 0))      AS fail_days,
          SUM(IF(f.component = 'BUY_IN', 1, 0))           AS buy_ins,
          SUM(f.amount_lcy)                               AS gross_cost_lcy,
          SUM(f.recharged_lcy)                            AS recharged_lcy,
          SUM(f.net_lcy)                                  AS net_cost_lcy,
          SUM(f.gross_usd)                                AS gross_cost_usd,
          SUM(f.net_usd)                                  AS net_cost_usd,
          SUM(f.funding_cost_usd)                         AS funding_cost_usd,
          SUM(f.borrow_cost_usd)                          AS borrow_cost_usd
FROM fail_cost_daily f
LEFT JOIN silver.dim_counterparty cp ON cp.counterparty_id = f.counterparty_id
LEFT JOIN (SELECT DISTINCT desk_code, desk_name FROM silver.dim_desk_hierarchy WHERE is_current) d ON d.desk_code = f.desk_code
GROUP BY ALL;
