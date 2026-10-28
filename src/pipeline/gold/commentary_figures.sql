-- Figure registry behind commentary chips: every number the agent or an analyst may cite, with its source table and
-- filter so the app can resolve value + Delta version at draft time (spec §4 commentary_figure).
USE SCHEMA gold;

CREATE VIEW commentary_figures
COMMENT 'Gold: figure registry — figure_key = {comparison_id}|{scope_key}|{metric} (scope APAC, ED_EXCH_CLR, REST, BUS:<code>, DESK:<code>, CAT:<category>, VENDOR:<id>, MKT:<market>, DSL:<slice>:<desk>, PF:<desk>:<product family>, PSL:<slice>:<desk>:<product family>), plus findings INV|{period}|{vendor}|VARIANCE and FAILS|{period}|{desk}|{counterparty}|NET.'
AS
WITH scoped AS (
  SELECT comparison_id, 'APAC' AS scope_key, 'APAC Global Markets' AS scope_label, '' AS scope_filter, b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
  UNION ALL
  SELECT comparison_id, CASE WHEN headline_slice LIKE 'Equity%' THEN 'ED_EXCH_CLR' ELSE 'REST' END, headline_slice,
         concat(" AND headline_slice = '", headline_slice, "'"), b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
  UNION ALL
  SELECT comparison_id, concat('BUS:', business_code), business, concat(" AND business_code = '", business_code, "'"), b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
  UNION ALL
  SELECT comparison_id, concat('DESK:', desk_code), desk_name, concat(" AND desk_code = '", desk_code, "'"), b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
  UNION ALL
  SELECT comparison_id, concat('CAT:', cost_category), cost_category, concat(" AND cost_category = '", cost_category, "'"), b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
  UNION ALL
  SELECT comparison_id, concat('VENDOR:', vendor_id), vendor_name, concat(" AND vendor_id = '", vendor_id, "'"), b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
  UNION ALL
  SELECT comparison_id, concat('MKT:', market), market, concat(" AND market = '", market, "'"), b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
  UNION ALL
  SELECT comparison_id,
         concat('DSL:', IF(headline_slice LIKE 'Equity%', 'ED_EXCH_CLR', 'REST'), ':', desk_code),
         concat(desk_name, ' — ', headline_slice),
         concat(" AND headline_slice = '", headline_slice, "' AND desk_code = '", desk_code, "'"), b.* EXCEPT (comparison_id)
  FROM cost_flux_bridge b
),
agg AS (
  SELECT comparison_id, scope_key, MAX(scope_label) AS scope_label, MAX(scope_filter) AS scope_filter,
         SUM(p0_actual_usd) AS p0, SUM(p1_actual_usd) AS p1, SUM(flux_usd) AS flux,
         SUM(volume_usd) AS volume, SUM(mix_usd) AS mix, SUM(rate_usd) AS rate, SUM(fx_usd) AS fx, SUM(fails_usd) AS fails,
         SUM(fixed_usd) AS fixed, SUM(timing_usd) AS timing, SUM(unexplained_usd) AS unexplained
  FROM scoped GROUP BY comparison_id, scope_key
),
metrics AS (
  SELECT a.comparison_id, a.scope_key, a.scope_label, a.scope_filter, m.metric, m.metric_label, m.value, m.unit
  FROM agg a
  LATERAL VIEW STACK(18,
    'P0', 'Prior-period trade cost', p0, 'USD',
    'P1', 'Current-period trade cost', p1, 'USD',
    'FLUX', 'Change in trade cost', flux, 'USD',
    'FLUX_PCT', 'Change in trade cost (%)', flux / NULLIF(p0, 0), 'PCT',
    'VOLUME', 'Volume effect', volume, 'USD',
    'MIX', 'Mix effect (venue / capacity / product / market)', mix, 'USD',
    'RATE', 'Rate effect (fee schedule, levy and tax changes)', rate, 'USD',
    'FX', 'FX translation effect', fx, 'USD',
    'FAILS', 'Settlement fails', fails, 'USD',
    'FIXED', 'Fixed fees', fixed, 'USD',
    'TIMING', 'Timing / accrual effect', timing, 'USD',
    'UNEXPLAINED', 'Unexplained residual', unexplained, 'USD',
    'GOOD', 'Good flux (volume-driven)', volume, 'USD',
    'CONTROLLABLE', 'Controllable flux (mix + fails)', mix + fails, 'USD',
    'EXTERNAL', 'External, timing and residual (rate + FX + timing + fixed + unexplained)', rate + fx + timing + fixed + unexplained, 'USD',
    'GOOD_PCT', 'Good flux share of the change', volume / NULLIF(flux, 0), 'PCT',
    'CONTROLLABLE_PCT', 'Controllable share of the change', (mix + fails) / NULLIF(flux, 0), 'PCT',
    'UNEXPLAINED_THRESHOLD', 'Unexplained threshold (greater of US$25K and 5% of the change)', greatest(25000D, abs(flux) * 0.05), 'USD'
  ) m AS metric, metric_label, value, unit
)
SELECT concat(comparison_id, '|', scope_key, '|', metric) AS figure_key, comparison_id, scope_key, scope_label, metric,
       metric_label, value, unit, '${catalog}.gold.cost_flux_bridge' AS source_table,
       concat("comparison_id = '", comparison_id, "'", scope_filter) AS filter_expr,
       concat(metric_label, ' — ', scope_label, ', ', comparison_id) AS description
FROM metrics
UNION ALL
SELECT concat(comparison_id, '|PF:', desk_code, ':', product_family, '|', m.metric), comparison_id,
       concat('PF:', desk_code, ':', product_family), concat(desk_code, ' ', product_family), m.metric, m.metric_label,
       m.value, 'USD', '${catalog}.gold.cost_flux_slice',
       concat("comparison_id = '", comparison_id, "' AND desk_code = '", desk_code, "' AND product_family = '", product_family, "'"),
       concat(m.metric_label, ' — ', desk_code, ' ', product_family, ', ', comparison_id)
FROM (SELECT comparison_id, desk_code, product_family, SUM(volume_usd) AS v, SUM(mix_usd) AS x, SUM(rate_usd) AS r
      FROM cost_flux_slice GROUP BY comparison_id, desk_code, product_family)
LATERAL VIEW STACK(3, 'VOLUME', 'Volume effect', v, 'MIX', 'Mix effect', x, 'RATE', 'Rate effect', r) m AS metric, metric_label, value
UNION ALL
SELECT concat(comparison_id, '|PSL:', sl, ':', desk_code, ':', product_family, '|', m.metric), comparison_id,
       concat('PSL:', sl, ':', desk_code, ':', product_family), concat(desk_code, ' ', product_family, ' (', sl, ')'), m.metric,
       m.metric_label, m.value, 'USD', '${catalog}.gold.cost_flux_slice',
       concat("comparison_id = '", comparison_id, "' AND desk_code = '", desk_code, "' AND product_family = '", product_family,
              "' AND ", IF(sl = 'ED_EXCH_CLR', "desk_code = 'HKED' AND cost_type IN ('EXCHANGE', 'CLEARING')",
                                               "NOT (desk_code = 'HKED' AND cost_type IN ('EXCHANGE', 'CLEARING'))")),
       concat(m.metric_label, ' — ', desk_code, ' ', product_family, ' (', sl, '), ', comparison_id)
FROM (SELECT comparison_id,
             IF(desk_code = 'HKED' AND cost_type IN ('EXCHANGE', 'CLEARING'), 'ED_EXCH_CLR', 'REST') AS sl,
             desk_code, product_family, SUM(volume_usd) AS v, SUM(mix_usd) AS x, SUM(rate_usd) AS r
      FROM cost_flux_slice GROUP BY ALL)
LATERAL VIEW STACK(3, 'VOLUME', 'Volume effect', v, 'MIX', 'Mix effect', x, 'RATE', 'Rate effect', r) m AS metric, metric_label, value
UNION ALL
SELECT concat('INV|', service_period, '|', vendor_id, '|VARIANCE'), CAST(NULL AS STRING), concat('VENDOR:', vendor_id),
       MAX(vendor_name), 'VARIANCE', 'Invoiced minus expected (all entities and cost types)', SUM(variance_usd), 'USD',
       '${catalog}.gold.invoice_recon', concat("service_period = '", service_period, "' AND vendor_id = '", vendor_id, "'"),
       concat('Invoice variance — ', MAX(vendor_name), ', service period ', service_period, ': ', MAX(variance_reason))
FROM invoice_recon WHERE recon_status IN ('OVERBILLED', 'UNDERBILLED')
GROUP BY service_period, vendor_id
UNION ALL
SELECT concat('FAILS|', period, '|', desk_code, '|', counterparty_id, '|NET'), CAST(NULL AS STRING),
       concat('DESK:', desk_code), MAX(counterparty_name), 'NET', 'Net settlement-fail cost', SUM(net_cost_usd), 'USD',
       '${catalog}.gold.fail_cost_summary',
       concat("period = '", period, "' AND desk_code = '", desk_code, "' AND counterparty_id = '", counterparty_id, "'"),
       concat('Net fail cost — ', MAX(counterparty_name), ', ', desk_code, ', ', period, ' (', MAX(root_cause), ')')
FROM fail_cost_summary
GROUP BY period, desk_code, counterparty_id
HAVING SUM(net_cost_usd) > 10000;
