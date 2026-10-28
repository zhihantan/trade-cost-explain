-- Conformed executions: typed, fiscal period derived, quality rules enforced.
USE SCHEMA silver;

CREATE OR REFRESH STREAMING TABLE trades (
  CONSTRAINT trade_id_present   EXPECT (trade_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT positive_notional  EXPECT (notional > 0) ON VIOLATION DROP ROW,
  CONSTRAINT known_capacity     EXPECT (capacity IN ('HOUSE', 'CLIENT', 'MM')),
  CONSTRAINT known_currency     EXPECT (currency IN ('USD', 'HKD', 'CNH', 'SGD', 'AUD', 'INR', 'KRW', 'TWD', 'MYR')),
  CONSTRAINT listed_has_contracts EXPECT (CASE WHEN product_family LIKE '%FUT' OR product_family LIKE '%OPT' THEN contracts > 0 ELSE TRUE END)
)
COMMENT 'Silver: executions (trade_id, trade_date, book, desk, product, venue, exec / clearing broker, CCP, qty, notional, currency, market, capacity, settlement location, affiliate and give-up flags).'
CLUSTER BY (trade_date, desk_code)
AS SELECT
  trade_id,
  CAST(trade_date AS DATE)                 AS trade_date,
  date_format(trade_date, 'yyyy-MM')       AS period,
  exec_time_local, book, desk_code, legal_entity, product_family, instrument_id, product, venue, market,
  execution_type, exec_broker, clearing_broker, ccp, settle_vendor, settlement_location, capacity, side,
  CAST(qty AS DOUBLE)                      AS qty,
  CAST(price AS DOUBLE)                    AS price,
  CAST(contracts AS BIGINT)                AS contracts,
  CAST(notional AS DOUBLE)                 AS notional,
  currency, counterparty_id,
  CAST(is_affiliate AS BOOLEAN)            AS is_affiliate,
  CAST(give_up_flag AS BOOLEAN)            AS give_up_flag,
  settlement_location <> 'CUSTODIAN'       AS settles,
  source_file, ingested_at
FROM STREAM(bronze.trades_raw);
