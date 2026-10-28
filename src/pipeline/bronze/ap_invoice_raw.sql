-- AP invoice headers and lines (vendor invoices received after month end), one CSV per received month.
USE SCHEMA bronze;

CREATE OR REFRESH STREAMING TABLE ap_invoice_headers_raw
COMMENT 'Bronze: AP invoice headers as received.'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/ap/', format => 'csv', header => true, pathGlobFilter => 'ap_invoice_headers_*.csv',
  schemaHints => 'service_period STRING, vendor_id STRING, legal_entity STRING, currency STRING, invoice_type STRING, total_net DOUBLE, total_tax DOUBLE, line_count INT, invoice_received_date DATE, invoice_date DATE, invoice_id STRING, vendor_invoice_number STRING, total_gross DOUBLE, status STRING');

CREATE OR REFRESH STREAMING TABLE ap_invoice_lines_raw
COMMENT 'Bronze: AP invoice lines as received (fee code × product × trade week, GST as tax).'
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/ap/', format => 'csv', header => true, pathGlobFilter => 'ap_invoice_lines_*.csv',
  schemaHints => 'invoice_id STRING, line_no INT, vendor_id STRING, legal_entity STRING, service_period STRING, service_week_start DATE, invoice_received_date DATE, cost_type STRING, fee_id STRING, product_family STRING, qty DOUBLE, unit_rate DOUBLE, net_amount DOUBLE, tax_amount DOUBLE, tax_recoverable DOUBLE, currency STRING, line_type STRING, description STRING');
