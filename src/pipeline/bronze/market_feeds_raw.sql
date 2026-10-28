-- FX rates (Group Treasury monthly averages + daily spot), market data, desk revenue and the FY plan.
USE SCHEMA bronze;

CREATE OR REFRESH STREAMING TABLE fx_rates_raw
COMMENT 'Bronze: FX rates, US$ per unit of local currency (monthly average and daily spot), JSON lines.'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/fx/', format => 'json',
  schemaHints => 'currency STRING, period STRING, rate_date DATE, rate_type STRING, rate_to_usd DOUBLE, source STRING');

CREATE OR REFRESH STREAMING TABLE market_data_raw
COMMENT 'Bronze: PRX Volatility Index and PRX 50 index levels, JSON lines.'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/market/', format => 'json',
  schemaHints => 'index_code STRING, index_name STRING, trade_date DATE, close_value DOUBLE');

CREATE OR REFRESH STREAMING TABLE desk_revenue_raw
COMMENT 'Bronze: desk revenue (commissions and trading revenue), daily.'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/revenue/', format => 'csv', header => true,
  schemaHints => 'desk_code STRING, trade_date DATE, period STRING, revenue_usd DOUBLE, revenue_type STRING');

CREATE OR REFRESH STREAMING TABLE trade_cost_plan_raw
COMMENT 'Bronze: FY2026/27 budget for net borne trade cost and revenue by desk and month.'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/plan/', format => 'csv', header => true,
  schemaHints => 'desk_code STRING, period STRING, plan_cost_usd DOUBLE, plan_revenue_usd DOUBLE, plan_version STRING');
