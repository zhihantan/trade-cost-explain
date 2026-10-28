-- Planted-story acceptance test (spec §6 "the bars must add up"), run as the last task of the build job.
-- Every check is recorded in gold.tie_out_results (control evidence for the demo) — the final statement fails the run
-- if any check fails.

CREATE OR REPLACE TABLE cost_explain.gold.tie_out_results
COMMENT 'Control evidence: automated tie-out of the September 2026 vs August 2026 cost bridge to the planted targets, plus identity, mapping-coverage and residual-threshold checks.'
AS
WITH bridge AS (
  SELECT COALESCE(headline_slice, 'APAC Global Markets') AS slice,
         SUM(p0_actual_usd) AS p0, SUM(p1_actual_usd) AS p1, SUM(volume_usd) AS volume, SUM(mix_usd) AS mix,
         SUM(rate_usd) AS rate, SUM(fails_usd) AS fails, SUM(timing_usd) AS timing, SUM(fx_usd) AS fx,
         SUM(fixed_usd) AS fixed, SUM(unexplained_usd) AS unexplained, SUM(flux_usd) AS flux
  FROM cost_explain.gold.cost_flux_bridge
  WHERE comparison_id = 'MOM_2026-09'
  GROUP BY ROLLUP (headline_slice)
),
actual AS (
  SELECT slice, metric, value
  FROM bridge
  LATERAL VIEW STACK(11, 'P0', p0, 'P1', p1, 'VOLUME', volume, 'MIX', mix, 'RATE', rate, 'FAILS', fails, 'TIMING', timing,
                     'FX', fx, 'FIXED', fixed, 'UNEXPLAINED', unexplained, 'FLUX', flux) s AS metric, value
),
target AS (
  SELECT * FROM VALUES
    ('Equity Derivatives — exchange & clearing', 'P0', 2170), ('Equity Derivatives — exchange & clearing', 'P1', 2680),
    ('Equity Derivatives — exchange & clearing', 'VOLUME', 390), ('Equity Derivatives — exchange & clearing', 'MIX', 90),
    ('Equity Derivatives — exchange & clearing', 'RATE', 60), ('Equity Derivatives — exchange & clearing', 'FAILS', 0),
    ('Equity Derivatives — exchange & clearing', 'TIMING', -20), ('Equity Derivatives — exchange & clearing', 'FX', -10),
    ('Equity Derivatives — exchange & clearing', 'FIXED', 0), ('Equity Derivatives — exchange & clearing', 'UNEXPLAINED', 0),
    ('Equity Derivatives — exchange & clearing', 'FLUX', 510),
    ('Rest of APAC Global Markets', 'P0', 2830), ('Rest of APAC Global Markets', 'P1', 3520),
    ('Rest of APAC Global Markets', 'VOLUME', 510), ('Rest of APAC Global Markets', 'MIX', 100),
    ('Rest of APAC Global Markets', 'RATE', 40), ('Rest of APAC Global Markets', 'FAILS', 150),
    ('Rest of APAC Global Markets', 'TIMING', -30), ('Rest of APAC Global Markets', 'FX', -90),
    ('Rest of APAC Global Markets', 'FIXED', 0), ('Rest of APAC Global Markets', 'UNEXPLAINED', 10),
    ('Rest of APAC Global Markets', 'FLUX', 690),
    ('APAC Global Markets', 'P0', 5000), ('APAC Global Markets', 'P1', 6200), ('APAC Global Markets', 'VOLUME', 900),
    ('APAC Global Markets', 'MIX', 190), ('APAC Global Markets', 'RATE', 100), ('APAC Global Markets', 'FAILS', 150),
    ('APAC Global Markets', 'TIMING', -50), ('APAC Global Markets', 'FX', -100), ('APAC Global Markets', 'FIXED', 0),
    ('APAC Global Markets', 'UNEXPLAINED', 10), ('APAC Global Markets', 'FLUX', 1200)
  AS t(slice, metric, target_k)
),
cells AS (
  SELECT concat('bridge: ', t.slice, ' · ', t.metric) AS check_name, 'planted target (US$K)' AS check_type,
         CAST(t.target_k AS DOUBLE) AS expected, ROUND(a.value / 1e3, 3) AS actual,
         abs(a.value / 1e3 - t.target_k) <= 0.05 AS passed          -- within US$50 of the planted target
  FROM target t LEFT JOIN actual a ON a.slice = t.slice AND a.metric = t.metric
),
shares AS (
  SELECT 'shares: good (volume) share of flux' AS check_name, 'planted target (%)' AS check_type, 75D AS expected,
         ROUND(volume / flux * 100, 1) AS actual, round(volume / flux * 100) = 75 AS passed
  FROM bridge WHERE slice = 'APAC Global Markets'
  UNION ALL
  SELECT 'shares: controllable (mix + fails) share of flux', 'planted target (%)', 28D, ROUND((mix + fails) / flux * 100, 1),
         round((mix + fails) / flux * 100) = 28
  FROM bridge WHERE slice = 'APAC Global Markets'
  UNION ALL
  SELECT 'shares: external, timing and residual share of flux', 'planted target (%)', -3D,
         ROUND((rate + fx + timing + fixed + unexplained) / flux * 100, 1),
         round((rate + fx + timing + fixed + unexplained) / flux * 100) = -3
  FROM bridge WHERE slice = 'APAC Global Markets'
),
findings AS (
  SELECT 'finding: Broker C (Cobalt) August over-billing, US$' AS check_name, 'planted target (US$)' AS check_type,
         85000D AS expected, ROUND(SUM(variance_usd), 2) AS actual, abs(SUM(variance_usd) - 85000) <= 500 AS passed
  FROM cost_explain.gold.invoice_recon WHERE service_period = '2026-08' AND vendor_id = 'B03'
  UNION ALL
  SELECT 'finding: Kestrel / AU cash equities fails carry the September fails increase (share of +US$150K)',
         'story check (%)', 90D, ROUND(SUM(net_cost_usd) / 150000 * 100, 1), SUM(net_cost_usd) / 150000 >= 0.85
  FROM cost_explain.gold.fail_cost_summary
  WHERE period = '2026-09' AND counterparty_id = 'C001' AND desk_code = 'AUCE'
),
identity AS (
  SELECT 'identity: flux = sum of effects on every bridge row, every comparison (max abs error, US$)' AS check_name,
         'identity' AS check_type, 0D AS expected,
         ROUND(MAX(abs(flux_usd - (volume_usd + mix_usd + rate_usd + fx_usd + fails_usd + fixed_usd + timing_usd + unexplained_usd))), 6) AS actual,
         MAX(abs(flux_usd - (volume_usd + mix_usd + rate_usd + fx_usd + fails_usd + fixed_usd + timing_usd + unexplained_usd))) < 0.01 AS passed
  FROM cost_explain.gold.cost_flux_bridge
),
residual AS (
  SELECT concat('threshold: unexplained within max(US$25K, 5% of flux) — ', comparison_id) AS check_name,
         'residual threshold' AS check_type, greatest(25000D, abs(SUM(flux_usd)) * 0.05) AS expected,
         ROUND(abs(SUM(unexplained_usd)), 2) AS actual,
         abs(SUM(unexplained_usd)) <= greatest(25000D, abs(SUM(flux_usd)) * 0.05) AS passed
  FROM cost_explain.gold.cost_flux_bridge GROUP BY comparison_id
),
coverage AS (
  SELECT 'coverage: share of September net borne GL mapped to a counterparty (%)' AS check_name,
         'mapping coverage' AS check_type, 99D AS expected,
         ROUND(SUM(IF(is_vendor_mapped, amount_usd, 0D)) / SUM(amount_usd) * 100, 2) AS actual,
         SUM(IF(is_vendor_mapped, amount_usd, 0D)) / SUM(amount_usd) >= 0.99 AS passed
  FROM cost_explain.gold.gl_monthly WHERE period = '2026-09' AND in_net_borne
  UNION ALL
  SELECT 'coverage: approved fee schedule lines (count)', 'reference data', 119D, CAST(COUNT(*) AS DOUBLE), COUNT(*) = 119
  FROM cost_explain.silver.fee_schedule
)
SELECT *, current_timestamp() AS checked_at
FROM (SELECT * FROM cells UNION ALL SELECT * FROM shares UNION ALL SELECT * FROM findings
      UNION ALL SELECT * FROM identity UNION ALL SELECT * FROM residual UNION ALL SELECT * FROM coverage);

SELECT IF(COUNT_IF(NOT passed OR passed IS NULL) = 0,
          concat('TIE-OUT PASSED: ', COUNT(*), ' checks'),
          raise_error(concat('TIE-OUT FAILED: ', COUNT_IF(NOT passed OR passed IS NULL), ' of ', COUNT(*), ' checks failed — see cost_explain.gold.tie_out_results')))
       AS tie_out
FROM cost_explain.gold.tie_out_results;
