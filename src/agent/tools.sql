-- Unity Catalog SQL functions used as governed tools by the commentary agent (and available to Genie / other agents).
-- Every row returns a figure_key from gold.commentary_figures so each number in a draft is traceable to Gold.

CREATE OR REPLACE FUNCTION cost_explain.gold.get_cost_bridge(comparison STRING, scope STRING)
RETURNS TABLE (figure_key STRING, metric STRING, metric_label STRING, value DOUBLE, unit STRING, scope_label STRING)
COMMENT 'Cost bridge for one comparison (e.g. MOM_2026-09) and scope (APAC, ED_EXCH_CLR, REST, BUS:<code>, DESK:<code>, CAT:<category>, VENDOR:<id>, MKT:<market>): prior / current cost, change, volume, mix, rate, FX, fails, fixed, timing, unexplained, good / controllable flux and shares, with figure keys.'
RETURN SELECT figure_key, metric, metric_label, value, unit, scope_label
       FROM cost_explain.gold.commentary_figures
       WHERE comparison_id = comparison AND scope_key = scope;

CREATE OR REPLACE FUNCTION cost_explain.gold.get_top_contributors(comparison STRING, effect STRING, group_by STRING, top_n INT)
RETURNS TABLE (dimension STRING, member STRING, member_label STRING, amount_usd DOUBLE, figure_key STRING)
COMMENT 'Largest contributors to one effect (VOLUME, MIX, RATE, FX, FAILS, TIMING, FIXED, UNEXPLAINED or FLUX) grouped by DESK, BUS, VENDOR, MKT, CAT, or PF (desk × product family, volume / mix / rate only), largest absolute first, with figure keys.'
RETURN SELECT upper(group_by) AS dimension, substr(scope_key, length(upper(group_by)) + 2) AS member, scope_label AS member_label,
              value AS amount_usd, figure_key
       FROM (SELECT f.*, ROW_NUMBER() OVER (ORDER BY abs(f.value) DESC) AS rn
             FROM cost_explain.gold.commentary_figures f
             WHERE f.comparison_id = comparison AND f.metric = upper(effect)
               AND f.scope_key LIKE concat(upper(group_by), ':%') AND abs(f.value) >= 1)
       WHERE rn <= top_n;

CREATE OR REPLACE FUNCTION cost_explain.gold.get_invoice_findings(service_month STRING)
RETURNS TABLE (figure_key STRING, vendor STRING, variance_usd DOUBLE, finding STRING, legal_entities STRING, invoice_received DATE)
COMMENT 'Invoice-vs-expected findings (over / under billing) for a service month (invoices lag one month: at the September close use 2026-08), largest first, with figure keys.'
RETURN SELECT concat('INV|', r.service_period, '|', r.vendor_id, '|VARIANCE'), MAX(r.vendor_name), SUM(r.variance_usd),
              MAX(r.variance_reason), array_join(collect_set(r.legal_entity), ', '), MAX(r.invoice_received_date)
       FROM cost_explain.gold.invoice_recon r
       WHERE r.service_period = service_month AND r.recon_status IN ('OVERBILLED', 'UNDERBILLED')
       GROUP BY r.service_period, r.vendor_id;

CREATE OR REPLACE FUNCTION cost_explain.gold.get_fail_hotspots(fail_month STRING, top_n INT)
RETURNS TABLE (figure_key STRING, desk STRING, market STRING, counterparty STRING, root_cause STRING, failed_settlements BIGINT, net_cost_usd DOUBLE)
COMMENT 'Largest material settlement-fail cost hotspots (net cost above US$10K) for a month (YYYY-MM) by desk × counterparty × root cause (the Operations fix list), with figure keys.'
RETURN SELECT figure_key, desk, market, counterparty, root_cause, failed_settlements, net_cost_usd
       FROM (SELECT concat('FAILS|', s.period, '|', s.desk_code, '|', s.counterparty_id, '|NET') AS figure_key,
                    s.desk_code AS desk, MAX(s.market) AS market, MAX(s.counterparty_name) AS counterparty,
                    max_by(s.root_cause, s.net_cost_usd) AS root_cause, SUM(s.failed_settlements) AS failed_settlements,
                    SUM(s.net_cost_usd) AS net_cost_usd,
                    ROW_NUMBER() OVER (ORDER BY SUM(s.net_cost_usd) DESC) AS rn
             FROM cost_explain.gold.fail_cost_summary s
             WHERE s.period = fail_month
             GROUP BY s.period, s.desk_code, s.counterparty_id
             -- same materiality threshold as the FAILS rows of gold.commentary_figures, so every key returned resolves
             HAVING SUM(s.net_cost_usd) > 10000)
       WHERE rn <= top_n;

CREATE OR REPLACE FUNCTION cost_explain.gold.get_fee_events()
RETURNS TABLE (event_type STRING, event_date DATE, vendor STRING, product_family STRING, description STRING, status STRING, monthly_impact_usd DOUBLE)
COMMENT 'Fee schedule events — discounts / waivers ending, rate and regime changes — with estimated monthly cost impact at current volumes.'
RETURN SELECT event_type, event_date, vendor_name, product_family, description, status, monthly_impact_usd
       FROM cost_explain.gold.fee_calendar;

CREATE OR REPLACE FUNCTION cost_explain.gold.get_mix_detail(comparison STRING, slice_scope STRING, top_n INT)
RETURNS TABLE (figure_key STRING, desk STRING, product_family STRING, mix_usd DOUBLE, shifted_towards STRING, shifted_away_from STRING)
COMMENT 'Mechanism behind the largest mix effects by desk × product family within a slice (ALL, ED_EXCH_CLR or REST): the venue · capacity the flow shifted towards (largest positive mix, all fee types combined) and away from (largest negative), with the matching figure key.'
RETURN WITH s AS (
         SELECT desk_code, product_family, concat(venue, ' · ', capacity) AS slice_label, SUM(mix_usd) AS mix
         FROM cost_explain.gold.cost_flux_slice
         WHERE comparison_id = comparison
           AND (slice_scope = 'ALL'
                OR (slice_scope = 'ED_EXCH_CLR' AND desk_code = 'HKED' AND cost_type IN ('EXCHANGE', 'CLEARING'))
                OR (slice_scope = 'REST' AND NOT (desk_code = 'HKED' AND cost_type IN ('EXCHANGE', 'CLEARING'))))
         GROUP BY desk_code, product_family, venue, capacity),
       pf AS (
         SELECT desk_code, product_family, SUM(mix) AS mix, max_by(slice_label, mix) AS towards, min_by(slice_label, mix) AS away,
                ROW_NUMBER() OVER (ORDER BY abs(SUM(mix)) DESC) AS rn
         FROM s GROUP BY desk_code, product_family)
       SELECT CASE WHEN slice_scope = 'ALL' THEN concat(comparison, '|PF:', desk_code, ':', product_family, '|MIX')
                   ELSE concat(comparison, '|PSL:', slice_scope, ':', desk_code, ':', product_family, '|MIX') END,
              desk_code, product_family, mix, towards, away
       FROM pf WHERE rn <= top_n AND abs(mix) >= 1000;

-- Re-creating a function resets its privileges: grant EXECUTE explicitly so the agent endpoint’s identity (and Genie /
-- analysts) keep access. The functions only read Gold, and the Gold row filters still apply to every caller.
GRANT EXECUTE ON FUNCTION cost_explain.gold.get_cost_bridge TO `account users`;
GRANT EXECUTE ON FUNCTION cost_explain.gold.get_top_contributors TO `account users`;
GRANT EXECUTE ON FUNCTION cost_explain.gold.get_invoice_findings TO `account users`;
GRANT EXECUTE ON FUNCTION cost_explain.gold.get_fail_hotspots TO `account users`;
GRANT EXECUTE ON FUNCTION cost_explain.gold.get_fee_events TO `account users`;
GRANT EXECUTE ON FUNCTION cost_explain.gold.get_mix_detail TO `account users`;
