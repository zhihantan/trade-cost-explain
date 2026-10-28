-- AP invoices as received (headers and lines), mapped to trade-system vendors.
USE SCHEMA silver;

CREATE OR REFRESH MATERIALIZED VIEW ap_invoices (
  CONSTRAINT invoice_id_present EXPECT (invoice_id IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Silver: AP invoice headers (vendor, entity, service period, received date, totals, AP status).'
AS SELECT h.invoice_id, h.vendor_invoice_number, h.vendor_id AS ap_vendor_id, m.vendor_id, h.legal_entity, h.currency,
          h.invoice_type, h.service_period, h.invoice_date, h.invoice_received_date, h.total_net, h.total_tax, h.total_gross,
          h.line_count, h.status, h.source_file
FROM bronze.ap_invoice_headers_raw h
LEFT JOIN map_vendor_counterparty m ON m.ap_vendor_id = h.vendor_id;

CREATE OR REFRESH MATERIALIZED VIEW ap_invoice_lines (
  CONSTRAINT line_has_invoice EXPECT (invoice_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT tax_not_above_net EXPECT (abs(tax_amount) <= abs(net_amount) * 0.25 + 1)
)
COMMENT 'Silver: AP invoice lines (vendor, invoice, service period, received date, cost type, qty, net amount, tax amount (GST), recoverable tax, currency).'
AS SELECT l.invoice_id, l.line_no, l.vendor_id AS ap_vendor_id, m.vendor_id, l.legal_entity, l.service_period,
          l.service_week_start, l.invoice_received_date, l.cost_type, l.fee_id, l.product_family, l.qty, l.unit_rate,
          l.net_amount, l.tax_amount, l.tax_recoverable, l.currency, l.line_type, l.description, l.source_file
FROM bronze.ap_invoice_lines_raw l
LEFT JOIN map_vendor_counterparty m ON m.ap_vendor_id = l.vendor_id;
