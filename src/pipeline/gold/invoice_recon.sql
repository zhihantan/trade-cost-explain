-- Expected vs invoiced per vendor × entity × service period × cost type. Lagged one period: invoices arrive after month
-- end, so the latest reconcilable month at the September close is August. Variance reasons are inferred line by line:
-- a fee code billed that the contract did not produce (e.g. standard tier instead of the qualifying volume tier),
-- tax-only differences (GST), quantity differences (duplicate lines), discount lines not applied, rate differences.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW invoice_recon_line
COMMENT 'Gold: invoice reconciliation at fee-code grain (service period × vendor × entity × currency × cost type × fee code).'
AS
WITH exp AS (
  SELECT service_period, vendor_id, legal_entity, currency, cost_type, fee_id,
         SUM(expected_net) AS expected_net, SUM(expected_tax) AS expected_tax, SUM(expected_qty) AS expected_qty
  FROM expected_cost_invoice_grain GROUP BY ALL
  UNION ALL
  SELECT period, vendor_id, legal_entity, currency, 'FIXED', fee_id, SUM(amount_lcy), 0D, 1D
  FROM fixed_fee_monthly GROUP BY ALL
  UNION ALL
  SELECT period, rule_vendor_id, legal_entity, currency, 'FAILS', concat('FAIL-', component), SUM(amount_lcy), 0D,
         CAST(COUNT(DISTINCT trade_id) AS DOUBLE)
  FROM fail_cost_daily GROUP BY ALL
),
inv AS (
  SELECT service_period, vendor_id, legal_entity, currency, cost_type, fee_id,
         SUM(net_amount) AS invoiced_net, SUM(tax_amount) AS invoiced_tax, SUM(qty) AS invoiced_qty,
         MAX(invoice_received_date) AS invoice_received_date, array_join(array_sort(collect_set(invoice_id)), ', ') AS invoice_ids
  FROM silver.ap_invoice_lines GROUP BY ALL
)
SELECT COALESCE(e.service_period, i.service_period) AS service_period,
       COALESCE(e.vendor_id, i.vendor_id)           AS vendor_id,
       COALESCE(e.legal_entity, i.legal_entity)     AS legal_entity,
       COALESCE(e.currency, i.currency)             AS currency,
       COALESCE(e.cost_type, i.cost_type)           AS cost_type,
       COALESCE(e.fee_id, i.fee_id)                 AS fee_id,
       fs.description                               AS fee_description,
       fs.rate                                      AS contracted_rate,
       COALESCE(e.expected_net, 0D) AS expected_net, COALESCE(i.invoiced_net, 0D) AS invoiced_net,
       COALESCE(e.expected_tax, 0D) AS expected_tax, COALESCE(i.invoiced_tax, 0D) AS invoiced_tax,
       COALESCE(e.expected_qty, 0D) AS expected_qty, COALESCE(i.invoiced_qty, 0D) AS invoiced_qty,
       i.invoice_received_date, i.invoice_ids,
       e.fee_id IS NOT NULL AS in_expected, i.fee_id IS NOT NULL AS in_invoice
FROM exp e
FULL OUTER JOIN inv i
  ON i.service_period = e.service_period AND i.vendor_id = e.vendor_id AND i.legal_entity = e.legal_entity
 AND i.currency = e.currency AND i.cost_type = e.cost_type AND i.fee_id = e.fee_id
LEFT JOIN silver.fee_schedule fs ON fs.fee_id = COALESCE(e.fee_id, i.fee_id);

CREATE OR REFRESH MATERIALIZED VIEW invoice_recon
COMMENT 'Gold: expected vs invoiced per vendor × legal entity × service period × cost type (lagged one period), with variance (LCY and US$), status (MATCHED, OVERBILLED, UNDERBILLED, PENDING_INVOICE) and an inferred variance reason.'
AS
WITH l AS (SELECT * FROM invoice_recon_line WHERE vendor_id IS NOT NULL),
agg AS (
  SELECT service_period, vendor_id, legal_entity, currency, cost_type,
         SUM(expected_net) AS expected_net, SUM(invoiced_net) AS invoiced_net,
         SUM(expected_tax) AS expected_tax, SUM(invoiced_tax) AS invoiced_tax,
         SUM(expected_qty) AS expected_qty, SUM(invoiced_qty) AS invoiced_qty,
         MAX(invoice_received_date) AS invoice_received_date,
         array_join(array_distinct(flatten(collect_list(split(invoice_ids, ', ')))), ', ') AS invoice_ids,
         MAX(in_invoice) AS has_invoice,
         MAX(NOT in_expected AND in_invoice AND invoiced_net <> 0) AS has_unexpected_fee,
         MAX(in_expected AND NOT in_invoice AND expected_net <> 0) AS has_unbilled_fee,
         array_join(collect_set(IF(NOT in_expected AND in_invoice, fee_description, NULL)), '; ') AS billed_fee_text,
         array_join(collect_set(IF(in_expected AND NOT in_invoice, fee_description, NULL)), '; ') AS qualifying_fee_text,
         MAX(in_expected AND in_invoice AND abs(invoiced_net - expected_net) > greatest(1D, abs(expected_net) * 0.0025)
             AND fee_id LIKE '%DSC%') AS discount_line_diff,
         MAX(in_expected AND in_invoice AND invoiced_qty > expected_qty * 1.001) AS qty_over
  FROM l GROUP BY ALL
),
turnover AS (   -- broker tier measure (US$ turnover per month) for the variance narrative
  SELECT t.period, t.exec_broker AS vendor_id, SUM(t.notional * fx.rate_to_usd) AS monthly_turnover_usd
  FROM silver.trades t JOIN silver.fx_monthly fx ON fx.currency = t.currency AND fx.period = t.period
  WHERE t.exec_broker <> 'DIRECT' GROUP BY ALL
)
SELECT a.*,
       a.invoiced_net - a.expected_net                                      AS variance_net_lcy,
       a.invoiced_tax - a.expected_tax                                      AS variance_tax_lcy,
       (a.invoiced_net + a.invoiced_tax) - (a.expected_net + a.expected_tax) AS variance_lcy,
       a.expected_net * fx.rate_to_usd                                      AS expected_net_usd,
       a.invoiced_net * fx.rate_to_usd                                      AS invoiced_net_usd,
       ((a.invoiced_net + a.invoiced_tax) - (a.expected_net + a.expected_tax)) * fx.rate_to_usd AS variance_usd,
       v.vendor_name, v.vendor_type, tv.monthly_turnover_usd,
       CASE WHEN NOT a.has_invoice THEN 'PENDING_INVOICE'
            WHEN abs((a.invoiced_net + a.invoiced_tax) - (a.expected_net + a.expected_tax)) * fx.rate_to_usd
                 <= greatest(25D, abs(a.expected_net) * fx.rate_to_usd * 0.0025) THEN 'MATCHED'
            WHEN (a.invoiced_net + a.invoiced_tax) > (a.expected_net + a.expected_tax) THEN 'OVERBILLED'
            ELSE 'UNDERBILLED' END                                          AS recon_status,
       CASE WHEN NOT a.has_invoice THEN 'Invoice not yet received (invoices arrive after month end)'
            WHEN a.has_unexpected_fee AND a.has_unbilled_fee
              THEN concat('Billed "', a.billed_fee_text, '" instead of "', a.qualifying_fee_text, '"',
                          IF(tv.monthly_turnover_usd IS NOT NULL,
                             concat(' — monthly turnover US$', format_number(tv.monthly_turnover_usd / 1e9, 2), 'bn qualifies for the lower tier: volume-tier rebate not applied'), ''))
            WHEN a.discount_line_diff THEN 'Contracted discount / waiver not applied in full'
            WHEN a.qty_over THEN 'Billed quantity above traded quantity (possible duplicate line)'
            WHEN abs(a.invoiced_tax - a.expected_tax) > greatest(1D, abs(a.expected_tax) * 0.01)
                 AND abs(a.invoiced_net - a.expected_net) <= greatest(1D, abs(a.expected_net) * 0.0025)
              THEN 'GST charged incorrectly'
            WHEN abs(a.invoiced_net - a.expected_net) > greatest(1D, abs(a.expected_net) * 0.0025)
              THEN 'Billed rate differs from the contracted rate card'
            ELSE 'Within tolerance' END                                     AS variance_reason,
       concat('INV|', a.service_period, '|', a.vendor_id)                   AS finding_key
FROM agg a
JOIN silver.fx_monthly fx ON fx.currency = a.currency AND fx.period = a.service_period
LEFT JOIN silver.dim_vendor v ON v.vendor_id = a.vendor_id
LEFT JOIN turnover tv ON tv.period = a.service_period AND tv.vendor_id = a.vendor_id AND a.cost_type = 'BROKERAGE';
