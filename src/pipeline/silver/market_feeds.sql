-- FX, market data, revenue and plan, conformed.
USE SCHEMA silver;

CREATE OR REFRESH MATERIALIZED VIEW fx_rates (
  CONSTRAINT positive_rate EXPECT (rate_to_usd > 0) ON VIOLATION FAIL UPDATE
)
COMMENT 'Silver: FX rates, US$ per unit of local currency, monthly average (Group Treasury) and daily spot.'
AS SELECT currency, period, CAST(rate_date AS DATE) AS rate_date, rate_type, rate_to_usd, source FROM bronze.fx_rates_raw;

CREATE OR REFRESH MATERIALIZED VIEW fx_monthly
COMMENT 'Silver: monthly average FX (US$ per unit of local currency), the translation basis for actuals and the constant-currency bridge.'
AS SELECT currency, period, MAX(rate_to_usd) AS rate_to_usd FROM bronze.fx_rates_raw
WHERE rate_type = 'MONTHLY_AVERAGE' GROUP BY currency, period;

CREATE OR REFRESH MATERIALIZED VIEW market_data
COMMENT 'Silver: PRX Volatility Index (VHSI-like) and PRX 50 index closes.'
AS SELECT index_code, index_name, CAST(trade_date AS DATE) AS trade_date, close_value FROM bronze.market_data_raw;

CREATE OR REFRESH MATERIALIZED VIEW desk_revenue
COMMENT 'Silver: daily desk revenue (US$).'
AS SELECT desk_code, CAST(trade_date AS DATE) AS trade_date, period, revenue_usd, revenue_type FROM bronze.desk_revenue_raw;

CREATE OR REFRESH MATERIALIZED VIEW trade_cost_plan
COMMENT 'Silver: FY2026/27 budget — planned net borne trade cost and revenue by desk and month.'
AS SELECT desk_code, period, plan_cost_usd, plan_revenue_usd, plan_version FROM bronze.trade_cost_plan_raw;
