-- Trade-level expected cost: every execution × the analyst-approved fee schedule (silver.fee_schedule, published by the
-- fee-schedule extraction job). Same rules as the Python reference engine (src/datagen/meridian_datagen/engine.py):
--   venue EXCHANGE on member routes; venue LEVY / TAX on member routes and DMA all-in (passed through by the broker);
--   CCP CLEARING on member routes; SETTLEMENT on DIRECT / AGENCY_ALGO; BROKERAGE of the executing broker;
--   then capacity, side, effective dates, monthly tiers, per-trade floor / cap, GST split, recoverable pass-through,
--   intra-group elimination. Only the primary line of a (trade, cost type, fee basis) carries driver volume.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW expected_cost_trade
COMMENT 'Gold: trade-level expected cost = execution × contracted rate (one row per applicable fee line; GST split into recoverable and non-recoverable). Net borne = not recoverable and not intra-group.'
CLUSTER BY (period, desk_code)
WITH ROW FILTER ${catalog}.gold.ce_desk_scope ON (desk_code)
AS
WITH t AS (
  SELECT tr.*,
         tr.notional * fx.rate_to_usd             AS notional_usd,
         CASE WHEN tr.settles THEN 1 ELSE 0 END   AS n_instructions
  FROM silver.trades tr
  JOIN silver.fx_monthly fx ON fx.currency = tr.currency AND fx.period = tr.period
),
tier_measure AS (
  SELECT 'VENDOR_MONTHLY_TURNOVER_USD' AS tier_basis, period, exec_broker AS vendor_id,
         CAST(NULL AS STRING) AS product_family, SUM(notional_usd) AS measure
  FROM t WHERE exec_broker <> 'DIRECT' GROUP BY period, exec_broker
  UNION ALL
  SELECT 'MEMBER_MONTHLY_TURNOVER_LCY', period, venue, CAST(NULL AS STRING), SUM(notional)
  FROM t WHERE execution_type IN ('DIRECT', 'AGENCY_ALGO', 'GIVE_UP') GROUP BY period, venue
  UNION ALL
  SELECT 'MEMBER_MONTHLY_CONTRACTS', period, venue, product_family, CAST(SUM(contracts) AS DOUBLE)
  FROM t WHERE execution_type IN ('DIRECT', 'AGENCY_ALGO', 'GIVE_UP') GROUP BY period, venue, product_family
),
fs AS (
  SELECT * FROM silver.fee_schedule WHERE fee_basis <> 'FIXED_MONTHLY'
),
m AS (
  SELECT t.trade_id, t.trade_date, t.period, t.desk_code, t.book, t.legal_entity, t.product_family, t.product,
         t.instrument_id, t.venue, t.market, t.execution_type, t.exec_broker, t.ccp, t.capacity, t.side,
         t.counterparty_id, t.contracts, t.notional, t.n_instructions,
         fs.fee_id, fs.card_id, fs.vendor_id AS fee_vendor_id, fs.cost_type, fs.fee_basis, fs.rate,
         fs.currency AS cost_currency, fs.tier_basis, fs.tier_min, fs.tier_max, fs.floor_per_trade, fs.cap_per_trade,
         fs.is_pass_through, fs.is_discount_or_waiver, fs.gst_rate, fs.gst_recoverable_pct, fs.source_doc
  FROM t
  JOIN fs
    ON fs.product_family = t.product_family
   AND (   (fs.cost_type = 'EXCHANGE'       AND fs.vendor_id = t.venue         AND t.execution_type IN ('DIRECT', 'AGENCY_ALGO', 'GIVE_UP'))
        OR (fs.cost_type IN ('LEVY', 'TAX') AND fs.vendor_id = t.venue         AND t.execution_type IN ('DIRECT', 'AGENCY_ALGO', 'GIVE_UP', 'DMA_ALL_IN'))
        OR (fs.cost_type = 'CLEARING'       AND fs.vendor_id = t.ccp           AND t.execution_type IN ('DIRECT', 'AGENCY_ALGO', 'GIVE_UP'))
        OR (fs.cost_type = 'SETTLEMENT'     AND fs.vendor_id = t.settle_vendor AND t.execution_type IN ('DIRECT', 'AGENCY_ALGO'))
        OR (fs.cost_type = 'BROKERAGE'      AND fs.vendor_id = t.exec_broker))
   AND (fs.capacity = 'ALL' OR fs.capacity = t.capacity
        OR (fs.capacity = 'NON_MM' AND t.capacity IN ('HOUSE', 'CLIENT'))
        OR (fs.capacity = 'PRINCIPAL' AND t.capacity IN ('HOUSE', 'MM')))
   AND (fs.side = 'ALL' OR fs.side = t.side)
   AND t.trade_date >= fs.effective_from
   AND (fs.effective_to IS NULL OR t.trade_date <= fs.effective_to)
),
tiered AS (
  SELECT m.*
  FROM m
  LEFT JOIN tier_measure tm
    ON tm.tier_basis = m.tier_basis AND tm.period = m.period AND tm.vendor_id = m.fee_vendor_id
   AND (tm.product_family IS NULL OR tm.product_family = m.product_family)
  WHERE m.tier_basis = 'NONE'
     OR (COALESCE(tm.measure, 0) >= COALESCE(m.tier_min, 0)
         AND COALESCE(tm.measure, 0) < COALESCE(m.tier_max, CAST('Infinity' AS DOUBLE)))
),
fees AS (
  SELECT *,
         LEAST(GREATEST(volume * unit_rate, floor_per_trade), cap_per_trade)          AS cost_lcy,
         CASE WHEN execution_type = 'DMA_ALL_IN' AND cost_type IN ('LEVY', 'TAX') THEN exec_broker
              ELSE fee_vendor_id END                                                  AS billing_vendor_id,
         is_pass_through AND capacity = 'CLIENT'                                      AS is_recoverable,
         ROW_NUMBER() OVER (PARTITION BY trade_id, cost_type, fee_basis
                            ORDER BY is_discount_or_waiver, fee_id) = 1               AS is_volume_line
  FROM (
    SELECT *,
           CASE fee_basis WHEN 'PER_CONTRACT_SIDE'    THEN CAST(contracts AS DOUBLE)
                          WHEN 'BPS_NOTIONAL'         THEN notional
                          WHEN 'PER_TRADE'            THEN 1.0D
                          WHEN 'PER_INSTRUCTION'      THEN CAST(n_instructions AS DOUBLE)
                          WHEN 'PER_MILLION_NOTIONAL' THEN notional / 1e6 END        AS volume,
           CASE WHEN fee_basis = 'BPS_NOTIONAL' THEN rate / 1e4 ELSE rate END        AS unit_rate
    FROM tiered)
),
lines AS (
  SELECT trade_id, trade_date, period, desk_code, book, legal_entity, product_family, product, instrument_id, venue,
         market, execution_type, exec_broker, capacity, side, counterparty_id, fee_id, card_id, fee_vendor_id,
         billing_vendor_id, cost_type, cost_type AS base_cost_type, fee_basis, volume, is_volume_line, unit_rate, cost_lcy,
         cost_currency, is_recoverable, is_pass_through, is_discount_or_waiver, source_doc
  FROM fees
  UNION ALL
  SELECT trade_id, trade_date, period, desk_code, book, legal_entity, product_family, product, instrument_id, venue,
         market, execution_type, exec_broker, capacity, side, counterparty_id, fee_id, card_id, fee_vendor_id,
         billing_vendor_id, 'GST_NONREC', cost_type, fee_basis, volume, is_volume_line,
         unit_rate * gst_rate * (1 - gst_recoverable_pct), cost_lcy * gst_rate * (1 - gst_recoverable_pct), cost_currency,
         FALSE, FALSE, FALSE, source_doc
  FROM fees WHERE gst_rate > 0
  UNION ALL
  SELECT trade_id, trade_date, period, desk_code, book, legal_entity, product_family, product, instrument_id, venue,
         market, execution_type, exec_broker, capacity, side, counterparty_id, fee_id, card_id, fee_vendor_id,
         billing_vendor_id, 'GST_REC', cost_type, fee_basis, volume, is_volume_line,
         unit_rate * gst_rate * gst_recoverable_pct, cost_lcy * gst_rate * gst_recoverable_pct, cost_currency,
         TRUE, FALSE, FALSE, source_doc
  FROM fees WHERE gst_rate > 0
)
SELECT l.*,
       CASE WHEN l.is_volume_line THEN l.volume ELSE 0D END                         AS driver_volume,
       CASE l.fee_basis WHEN 'BPS_NOTIONAL'         THEN concat(l.cost_currency, ' notional')
                        WHEN 'PER_MILLION_NOTIONAL' THEN concat(l.cost_currency, ' notional (mn)')
                        WHEN 'PER_CONTRACT_SIDE'    THEN 'contract-sides'
                        WHEN 'PER_TRADE'            THEN 'trades'
                        WHEN 'PER_INSTRUCTION'      THEN 'instructions' END        AS volume_unit,
       COALESCE(v.is_affiliate, FALSE)                                               AS is_affiliate,
       NOT l.is_recoverable AND NOT COALESCE(v.is_affiliate, FALSE)                  AS in_net_borne,
       l.cost_lcy * fx.rate_to_usd                                                   AS cost_usd,
       CASE WHEN l.cost_currency = 'USD' THEN le.country
            ELSE element_at(map('HKD', 'HK', 'CNH', 'CN', 'SGD', 'SG', 'AUD', 'AU', 'INR', 'IN', 'KRW', 'KR', 'TWD', 'TW',
                                'MYR', 'MY'), l.cost_currency) END                   AS reporting_market
FROM lines l
JOIN silver.fx_monthly fx           ON fx.currency = l.cost_currency AND fx.period = l.period
LEFT JOIN silver.dim_vendor v       ON v.vendor_id = l.billing_vendor_id
LEFT JOIN silver.dim_legal_entity le ON le.legal_entity = l.legal_entity;
