-- Conformed settlement records (one per cash execution) with fail ageing and costs as reported by Operations.
USE SCHEMA silver;

CREATE OR REFRESH STREAMING TABLE settlements (
  CONSTRAINT settlement_has_trade   EXPECT (trade_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT fail_days_non_negative EXPECT (fail_days >= 0),
  CONSTRAINT fails_have_root_cause  EXPECT (settle_status = 'SETTLED' OR root_cause IS NOT NULL)
)
COMMENT 'Silver: settlement status per cash execution; fails carry ageing (fail_days), shortfall, Operations-reported fail / default / buy-in costs, recharges and root cause.'
CLUSTER BY (settle_due_date, market)
AS SELECT
  settlement_id, trade_id, market, settlement_location,
  CAST(settle_due_date AS DATE)   AS settle_due_date,
  CAST(settled_date AS DATE)      AS settled_date,
  settle_status,
  CAST(fail_days AS INT)          AS fail_days,
  CAST(shortfall_qty AS DOUBLE)   AS shortfall_qty,
  CAST(shortfall_value AS DOUBLE) AS shortfall_value,
  CAST(fail_fee AS DOUBLE)        AS fail_fee,
  CAST(default_fee AS DOUBLE)     AS default_fee,
  CAST(buy_in_cost AS DOUBLE)     AS buy_in_cost,
  CAST(close_out_cost AS DOUBLE)  AS close_out_cost,
  CAST(recharged_to_client AS DOUBLE) AS recharged_to_client,
  root_cause, root_cause_class, resolution, currency, counterparty_id,
  source_file, ingested_at
FROM STREAM(bronze.settlements_raw);
