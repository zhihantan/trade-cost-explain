-- ERP general-ledger journal lines (trade-cost accounts), one CSV per fiscal period.
USE SCHEMA bronze;

CREATE OR REFRESH STREAMING TABLE gl_journal_lines_raw
COMMENT 'Bronze: ERP GL journal lines for the Commissions and floor brokerage accounts (CSV extract).'
AS SELECT
  *,
  _metadata.file_path AS source_file,
  current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/gl/', format => 'csv', header => true,
  schemaHints => 'journal_id STRING, journal_line INT, posting_date DATE, fiscal_period STRING, gl_account STRING, cost_centre STRING, vendor_id STRING, legal_entity STRING, currency STRING, amount_lcy DOUBLE, amount_usd DOUBLE, is_accrual BOOLEAN, journal_type STRING, description STRING, service_period STRING, source_system STRING');
