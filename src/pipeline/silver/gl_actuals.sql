-- GL journal lines conformed and mapped to drivers. Mapping coverage is measured, not assumed:
-- the vendor_mapped expectation warns (and counts) every net-borne line whose AP vendor has no counterparty mapping.
USE SCHEMA silver;

CREATE OR REFRESH MATERIALIZED VIEW gl_actuals (
  CONSTRAINT account_in_scope   EXPECT (cost_type IS NOT NULL),
  CONSTRAINT cost_centre_mapped EXPECT (desk_code IS NOT NULL),
  CONSTRAINT vendor_mapped      EXPECT (is_vendor_mapped OR NOT in_net_borne)
)
COMMENT 'Silver: GL actuals at journal-line grain (account × cost centre × vendor × period) with legal entity, fiscal period, accrual flag, LCY and US$ amounts, mapped to cost type, desk and trade-system vendor.'
CLUSTER BY (fiscal_period, cost_centre)
AS SELECT
  g.journal_id, g.journal_line, g.posting_date, g.fiscal_period,
  fc.fiscal_year_label, fc.fiscal_quarter_id, fc.fiscal_half_id,
  g.gl_account, a.gl_account_name, a.cost_type, a.in_net_borne, a.is_intragroup, a.fs_line,
  g.cost_centre, cc.desk_code,
  g.vendor_id                       AS ap_vendor_id,
  av.ap_vendor_name,
  m.vendor_id                       AS vendor_id,
  m.vendor_id IS NOT NULL           AS is_vendor_mapped,
  g.legal_entity, g.currency, g.amount_lcy, g.amount_usd, g.is_accrual, g.journal_type, g.description, g.service_period,
  g.source_file, g.ingested_at
FROM bronze.gl_journal_lines_raw g
LEFT JOIN map_gl_cost_type a           ON a.gl_account = g.gl_account
LEFT JOIN map_costcentre_desk cc       ON cc.cost_centre = g.cost_centre
LEFT JOIN ap_vendor av                 ON av.ap_vendor_id = g.vendor_id
LEFT JOIN map_vendor_counterparty m    ON m.ap_vendor_id = g.vendor_id
LEFT JOIN dim_fiscal_calendar fc       ON fc.period = g.fiscal_period;
