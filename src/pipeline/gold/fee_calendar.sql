-- Fee and regime calendar: discounts / waivers ending, rate changes and regime changes from the approved fee schedule,
-- with the monthly cost impact at current volumes (latest month of executions on the affected fee lines).
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW fee_calendar
COMMENT 'Gold: fee schedule events (DISCOUNT_ENDS, RATE_CHANGE, REGIME_CHANGE) with effective date and estimated monthly cost impact (US$) at current volumes. as_of_date marks the September 2026 close.'
AS
WITH fs AS (SELECT * FROM silver.fee_schedule WHERE fee_basis <> 'FIXED_MONTHLY'),
last_month AS (SELECT MAX(period) AS period FROM silver.trades),
vol AS (   -- current-month volume and cost on each fee line (line volume, so discount overlays carry the base volume)
  SELECT e.fee_id, e.cost_currency, SUM(e.volume) AS volume, SUM(e.cost_lcy) AS cost_lcy
  FROM expected_cost_trade e JOIN last_month lm ON e.period = lm.period
  WHERE e.cost_type NOT IN ('GST_NONREC', 'GST_REC') GROUP BY ALL
),
base_vol AS (   -- current volume on the base (non-discount) lines of the same vendor / product / cost type / capacity scope
  SELECT f.vendor_id, f.product_family, f.cost_type, f.capacity, SUM(v.volume) AS volume
  FROM fs f JOIN vol v ON v.fee_id = f.fee_id
  WHERE NOT f.is_discount_or_waiver GROUP BY ALL
),
pairs AS (
  SELECT o.fee_id AS old_fee_id, n.fee_id AS new_fee_id, o.vendor_id, o.product_family, o.cost_type, o.capacity, o.fee_basis,
         n.effective_from AS event_date, o.rate AS old_rate, n.rate AS new_rate, n.currency,
         concat('New rate from ', date_format(n.effective_from, 'd MMM yyyy'), ': ', n.description) AS new_description,
         o.description AS old_description, o.source_doc
  FROM fs o JOIN fs n
    ON n.vendor_id = o.vendor_id AND n.cost_type = o.cost_type AND n.product_family = o.product_family
   AND n.capacity = o.capacity AND n.fee_basis = o.fee_basis AND n.effective_from = date_add(o.effective_to, 1)
   AND n.tier_basis = o.tier_basis AND COALESCE(n.tier_min, -1) = COALESCE(o.tier_min, -1)
),
regime AS (   -- ending lines replaced by a differently-structured line (e.g. slab-wise → uniform)
  SELECT o.vendor_id, o.product_family, o.cost_type, n.effective_from AS event_date, n.fee_id AS new_fee_id, n.rate AS new_rate,
         n.fee_basis, n.currency, n.description AS new_description, n.source_doc,
         array_join(collect_list(o.fee_id), ', ') AS old_fee_ids, collect_list(o.fee_id) AS old_fee_id_list
  FROM fs o JOIN fs n
    ON n.vendor_id = o.vendor_id AND n.cost_type = o.cost_type AND n.product_family = o.product_family
   AND n.effective_from = date_add(o.effective_to, 1) AND n.tier_basis <> o.tier_basis
  GROUP BY ALL
),
ev AS (
  SELECT 'RATE_CHANGE' AS event_type, p.event_date, p.vendor_id, p.product_family, p.cost_type, p.capacity,
         p.old_fee_id AS fee_ids_before, p.new_fee_id AS fee_id_after, p.new_description AS description, p.currency,
         CASE WHEN p.fee_basis = 'BPS_NOTIONAL' THEN (p.new_rate - p.old_rate) / 1e4 ELSE p.new_rate - p.old_rate END
           * COALESCE(vn.volume, vo.volume, 0D) AS monthly_impact_lcy, p.source_doc
  FROM pairs p
  LEFT JOIN vol vn ON vn.fee_id = p.new_fee_id
  LEFT JOIN vol vo ON vo.fee_id = p.old_fee_id
  UNION ALL
  SELECT 'DISCOUNT_ENDS', date_add(o.effective_to, 1), o.vendor_id, o.product_family, o.cost_type, o.capacity,
         o.fee_id, CAST(NULL AS STRING),
         concat('Discount / waiver ended ', date_format(o.effective_to, 'd MMM yyyy'), ' (full rate from ',
                date_format(date_add(o.effective_to, 1), 'd MMM yyyy'), '): ', o.description), o.currency,
         -(CASE WHEN o.fee_basis = 'BPS_NOTIONAL' THEN o.rate / 1e4 ELSE o.rate END) * COALESCE(bv.volume, 0D), o.source_doc
  FROM fs o
  LEFT JOIN base_vol bv ON bv.vendor_id = o.vendor_id AND bv.product_family = o.product_family
                       AND bv.cost_type = o.cost_type AND bv.capacity = o.capacity
  WHERE o.is_discount_or_waiver AND o.rate < 0 AND o.effective_to IS NOT NULL
  UNION ALL
  SELECT 'REGIME_CHANGE', r.event_date, r.vendor_id, r.product_family, r.cost_type, 'ALL', r.old_fee_ids, r.new_fee_id,
         concat('Regime change from ', date_format(r.event_date, 'd MMM yyyy'), ': ', r.new_description), r.currency,
         (CASE WHEN r.fee_basis = 'BPS_NOTIONAL' THEN r.new_rate / 1e4 ELSE r.new_rate END - oe.old_unit_rate)
           * COALESCE(vn.volume, 0D), r.source_doc
  FROM regime r
  LEFT JOIN vol vn ON vn.fee_id = r.new_fee_id
  LEFT JOIN (
    SELECT r2.new_fee_id, SUM(e.cost_lcy) / NULLIF(SUM(e.volume), 0) AS old_unit_rate
    FROM regime r2 JOIN expected_cost_trade e
      ON array_contains(r2.old_fee_id_list, e.fee_id) AND e.period = date_format(date_sub(r2.event_date, 1), 'yyyy-MM')
    WHERE e.cost_type NOT IN ('GST_NONREC', 'GST_REC')
    GROUP BY r2.new_fee_id
  ) oe ON oe.new_fee_id = r.new_fee_id
)
SELECT ev.*, vd.vendor_name,
       ev.monthly_impact_lcy * fx.rate_to_usd AS monthly_impact_usd,
       DATE'${as_of_date}' AS as_of_date,
       CASE WHEN ev.event_date > DATE'${as_of_date}' THEN 'UPCOMING' ELSE 'IN_EFFECT' END AS status,
       months_between(ev.event_date, DATE'${as_of_date}') AS months_from_as_of
FROM ev
CROSS JOIN last_month lm
LEFT JOIN silver.fx_monthly fx ON fx.currency = ev.currency AND fx.period = lm.period
LEFT JOIN silver.dim_vendor vd ON vd.vendor_id = ev.vendor_id
WHERE ev.event_date >= DATE'2025-10-01';
