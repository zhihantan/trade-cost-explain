-- The cost explain. Constant currency first (P0 average FX); FX is measured separately on every GL line so nothing is
-- counted twice. Layer 1 (drivers): volume / mix / rate from expected cost inside groups that share a volume unit.
-- Layer 2: fails (one-off, rule-based), fixed fees, timing = Δ(GL − driver cost) on mapped GL keys, unexplained = residual
-- (by construction: GL booked to vendors not yet in map_vendor_counterparty). Identity per row:
--   flux = volume + mix + rate + fx + fails + fixed + timing + unexplained.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW cost_flux_slice
COMMENT 'Gold: driver decomposition per comparison × slice (group = cost type × fee basis × product family × volume unit; slice = group × desk × vendor × venue × capacity × entity × currency). volume + mix + rate = c1 − c0 at constant currency.'
CLUSTER BY (comparison_id, desk_code)
WITH ROW FILTER ${catalog}.gold.ce_desk_scope ON (desk_code)
AS
WITH e AS (
  SELECT cp.comparison_id, cp.role, m.*,
         m.cost_lcy * IF(cp.role = 'P0', fxa.rate_to_usd, fx0.fx0) AS c
  FROM expected_cost_monthly m
  JOIN comparison_period cp     ON cp.period = m.period
  JOIN silver.fx_monthly fxa    ON fxa.currency = m.cost_currency AND fxa.period = m.period
  JOIN comparison_fx fx0        ON fx0.comparison_id = cp.comparison_id AND fx0.currency = m.cost_currency
  WHERE m.in_net_borne
),
s AS (
  SELECT comparison_id, cost_type, fee_basis, product_family, volume_unit, desk_code, billing_vendor_id AS vendor_id, venue,
         capacity, legal_entity, cost_currency AS currency, MAX(reporting_market) AS market,
         SUM(IF(role = 'P0', driver_volume, 0D)) AS v0, SUM(IF(role = 'P1', driver_volume, 0D)) AS v1,
         SUM(IF(role = 'P0', c, 0D)) AS c0_usd,          SUM(IF(role = 'P1', c, 0D)) AS c1_cc_usd
  FROM e GROUP BY ALL
),
g AS (
  SELECT comparison_id, cost_type, fee_basis, product_family, volume_unit, SUM(v0) AS group_v0, SUM(v1) AS group_v1
  FROM s GROUP BY ALL
),
x AS (
  SELECT s.*, g.group_v0, g.group_v1,
         CASE WHEN g.group_v0 <= 0 THEN s.c1_cc_usd ELSE (g.group_v1 / g.group_v0 - 1) * s.c0_usd END AS volume_usd,
         CASE WHEN g.group_v0 > 0 AND s.v0 > 0 AND s.v1 > 0 THEN s.v1 * (s.c1_cc_usd / s.v1 - s.c0_usd / s.v0) ELSE 0D END AS rate_usd
  FROM s JOIN g USING (comparison_id, cost_type, fee_basis, product_family, volume_unit)
)
SELECT x.*,
       (x.c1_cc_usd - x.c0_usd) - x.volume_usd - x.rate_usd     AS mix_usd,
       x.c1_cc_usd - x.c0_usd                                    AS delta_usd,
       IF(x.v0 > 0, x.c0_usd / x.v0, NULL)                       AS unit_cost0_usd,
       IF(x.v1 > 0, x.c1_cc_usd / x.v1, NULL)                    AS unit_cost1_cc_usd,
       IF(x.group_v0 > 0, x.group_v1 / x.group_v0 - 1, NULL)     AS group_volume_growth
FROM x;

CREATE OR REFRESH MATERIALIZED VIEW cost_flux_bridge
COMMENT 'Gold: period-on-period cost bridge (US$) per comparison × business × desk × cost type × vendor × market × legal entity × currency: P0, P1, P1 at constant currency and the effects volume, mix, rate, fx, fails, fixed, timing, unexplained. Precomputed and deterministic — Genie, dashboards, the agent and the app read it; none of them recompute it.'
CLUSTER BY (comparison_id, desk_code)
WITH ROW FILTER ${catalog}.gold.ce_desk_scope ON (desk_code)
AS
WITH roles AS (
  SELECT cp.comparison_id, cp.role, cp.period, fx0.currency, fx0.fx0, fxa.rate_to_usd AS fx_actual
  FROM comparison_period cp
  JOIN comparison_fx fx0     ON fx0.comparison_id = cp.comparison_id
  JOIN silver.fx_monthly fxa ON fxa.currency = fx0.currency AND fxa.period = cp.period
),
drv AS (
  SELECT comparison_id, desk_code, cost_type, vendor_id AS vendor_key, legal_entity, currency,
         SUM(volume_usd) AS volume_usd, SUM(mix_usd) AS mix_usd, SUM(rate_usd) AS rate_usd,
         SUM(c0_usd) AS e0, SUM(c1_cc_usd) AS e1
  FROM cost_flux_slice GROUP BY ALL
),
fl AS (
  SELECT r.comparison_id, f.desk_code, 'FAILS' AS cost_type, f.rule_vendor_id AS vendor_key, f.legal_entity, f.currency,
         SUM(IF(r.role = 'P0', f.net_lcy * r.fx_actual, 0D)) AS f0, SUM(IF(r.role = 'P1', f.net_lcy * r.fx0, 0D)) AS f1
  FROM fail_cost_daily f JOIN roles r ON r.period = f.period AND r.currency = f.currency
  GROUP BY ALL
),
fx_ AS (
  SELECT r.comparison_id, x.desk_code, 'FIXED' AS cost_type, x.vendor_id AS vendor_key, x.legal_entity, x.currency,
         SUM(IF(r.role = 'P0', x.amount_lcy * r.fx_actual, 0D)) AS x0, SUM(IF(r.role = 'P1', x.amount_lcy * r.fx0, 0D)) AS x1
  FROM fixed_fee_monthly x JOIN roles r ON r.period = x.period AND r.currency = x.currency
  GROUP BY ALL
),
gl AS (
  SELECT r.comparison_id, g.desk_code, g.cost_type, COALESCE(g.vendor_id, g.ap_vendor_id) AS vendor_key, g.is_vendor_mapped,
         g.legal_entity, g.currency,
         SUM(IF(r.role = 'P0', g.amount_usd, 0D))           AS gl0,
         SUM(IF(r.role = 'P1', g.amount_usd, 0D))           AS gl1,
         SUM(IF(r.role = 'P1', g.amount_lcy * r.fx0, 0D))   AS gl1_cc
  FROM gl_monthly g JOIN roles r ON r.period = g.period AND r.currency = g.currency
  WHERE g.in_net_borne
  GROUP BY ALL
),
k AS (
  SELECT comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency FROM drv
  UNION SELECT comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency FROM fl
  UNION SELECT comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency FROM fx_
  UNION SELECT comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency FROM gl
),
j AS (
  SELECT k.*,
         COALESCE(gl.is_vendor_mapped, TRUE) AS is_vendor_mapped,
         COALESCE(gl.gl0, 0D) AS gl0, COALESCE(gl.gl1, 0D) AS gl1, COALESCE(gl.gl1_cc, 0D) AS gl1_cc,
         COALESCE(drv.volume_usd, 0D) AS volume_usd, COALESCE(drv.mix_usd, 0D) AS mix_usd, COALESCE(drv.rate_usd, 0D) AS rate_usd,
         COALESCE(drv.e0, 0D) AS e0, COALESCE(drv.e1, 0D) AS e1,
         COALESCE(fl.f0, 0D) AS f0, COALESCE(fl.f1, 0D) AS f1, COALESCE(fx_.x0, 0D) AS x0, COALESCE(fx_.x1, 0D) AS x1
  FROM k
  LEFT JOIN drv USING (comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency)
  LEFT JOIN fl  USING (comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency)
  LEFT JOIN fx_ USING (comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency)
  LEFT JOIN gl  USING (comparison_id, desk_code, cost_type, vendor_key, legal_entity, currency)
),
b AS (
  SELECT j.*,
         j.f1 - j.f0 AS fails_usd,
         j.x1 - j.x0 AS fixed_usd,
         IF(j.is_vendor_mapped, (j.gl1_cc - j.e1 - j.f1 - j.x1) - (j.gl0 - j.e0 - j.f0 - j.x0), 0D) AS timing_usd,
         j.gl1 - j.gl1_cc AS fx_usd,
         j.gl1 - j.gl0    AS flux_usd
  FROM j
)
SELECT b.comparison_id, 'APAC Global Markets' AS division,
       d.business_code, d.business, b.desk_code, d.desk_name,
       b.legal_entity, le.legal_entity_name,
       b.cost_type,
       element_at(map('EXCHANGE', 'Exchange & clearing', 'CLEARING', 'Exchange & clearing', 'BROKERAGE', 'Brokerage',
                      'SETTLEMENT', 'Settlement & custody', 'LEVY', 'Levies & taxes (borne)', 'TAX', 'Levies & taxes (borne)',
                      'GST_NONREC', 'Non-recoverable GST', 'FAILS', 'Settlement fails', 'FIXED', 'Fixed fees'), b.cost_type) AS cost_category,
       CASE WHEN d.business_code = 'EQD' AND b.cost_type IN ('EXCHANGE', 'CLEARING') THEN 'Equity Derivatives — exchange & clearing'
            ELSE 'Rest of APAC Global Markets' END                                    AS headline_slice,
       b.vendor_key AS vendor_id,
       COALESCE(v.vendor_name, av.ap_vendor_name)                                      AS vendor_name,
       CASE WHEN b.is_vendor_mapped THEN v.vendor_type ELSE 'Unmapped AP vendor' END   AS vendor_type,
       b.is_vendor_mapped,
       CASE WHEN b.currency = 'USD' THEN le.country
            ELSE element_at(map('HKD', 'HK', 'CNH', 'CN', 'SGD', 'SG', 'AUD', 'AU', 'INR', 'IN', 'KRW', 'KR', 'TWD', 'TW',
                                'MYR', 'MY'), b.currency) END                          AS market,
       b.currency,
       b.gl0 AS p0_actual_usd, b.gl1 AS p1_actual_usd, b.gl1_cc AS p1_cc_usd,
       b.volume_usd, b.mix_usd, b.rate_usd, b.fx_usd, b.fails_usd, b.fixed_usd, b.timing_usd,
       b.flux_usd - (b.volume_usd + b.mix_usd + b.rate_usd + b.fx_usd + b.fails_usd + b.fixed_usd + b.timing_usd) AS unexplained_usd,
       b.flux_usd,
       b.e0 AS p0_expected_usd, b.e1 AS p1_expected_cc_usd
FROM b
LEFT JOIN (SELECT DISTINCT desk_code, desk_name, business_code, business FROM silver.dim_desk_hierarchy WHERE is_current) d
       ON d.desk_code = b.desk_code
LEFT JOIN silver.dim_legal_entity le ON le.legal_entity = b.legal_entity
LEFT JOIN silver.dim_vendor v        ON v.vendor_id = b.vendor_key
LEFT JOIN silver.ap_vendor av        ON av.ap_vendor_id = b.vendor_key;

CREATE VIEW cost_flux_effects
COMMENT 'Gold: cost bridge in long form for waterfalls — one row per bridge row and effect, with effect order and flux class (Good = volume-driven; Controllable = mix + fails; External, timing & residual = rate + FX + timing + fixed + unexplained).'
AS SELECT b.* EXCEPT (volume_usd, mix_usd, rate_usd, fx_usd, fails_usd, fixed_usd, timing_usd, unexplained_usd),
          e.effect, e.effect_label, e.effect_order, e.flux_class, e.amount_usd
FROM cost_flux_bridge b
LATERAL VIEW STACK(8,
  'VOLUME', 'Volume', 1, 'Good (volume-driven)', volume_usd,
  'MIX', 'Mix', 2, 'Controllable', mix_usd,
  'RATE', 'Rate', 3, 'External, timing & residual', rate_usd,
  'FAILS', 'Fails', 4, 'Controllable', fails_usd,
  'TIMING', 'Timing / accrual', 5, 'External, timing & residual', timing_usd,
  'FX', 'FX', 6, 'External, timing & residual', fx_usd,
  'FIXED', 'Fixed fees', 7, 'External, timing & residual', fixed_usd,
  'UNEXPLAINED', 'Unexplained', 8, 'External, timing & residual', unexplained_usd
) e AS effect, effect_label, effect_order, flux_class, amount_usd;
