-- Masters and mappings (small, static CSVs from the reference-data store). "Usually the missing link" (spec §5).
USE SCHEMA silver;

CREATE OR REFRESH MATERIALIZED VIEW dim_legal_entity COMMENT 'Silver: Meridian Group APAC legal entities.'
AS SELECT * FROM read_files('${landing_root}/ref/legal_entities.csv', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW dim_desk_hierarchy COMMENT 'Silver: book → desk → business → division → legal entity (SCD2: valid_from / valid_to / is_current).'
AS SELECT * FROM read_files('${landing_root}/ref/dim_desk_hierarchy.csv', format => 'csv', header => true,
  schemaHints => 'valid_from DATE, valid_to DATE, is_current BOOLEAN');

CREATE OR REFRESH MATERIALIZED VIEW map_costcentre_desk COMMENT 'Silver: cost centre ↔ desk, effective-dated for reorganisations.'
AS SELECT * FROM read_files('${landing_root}/ref/map_costcentre_desk.csv', format => 'csv', header => true,
  schemaHints => 'cost_centre STRING, effective_from DATE, effective_to DATE');

CREATE OR REFRESH MATERIALIZED VIEW map_fixed_fee_costcentre COMMENT 'Silver: host cost centre for each fixed membership / connectivity fee (allocation key).'
AS SELECT * FROM read_files('${landing_root}/ref/map_fixed_fee_costcentre.csv', format => 'csv', header => true,
  schemaHints => 'cost_centre STRING');

CREATE OR REFRESH MATERIALIZED VIEW dim_vendor COMMENT 'Silver: venues, CCPs, brokers (one intra-group affiliate) and connectivity vendors (trade-system view).'
AS SELECT * FROM read_files('${landing_root}/ref/vendors.csv', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW ap_vendor COMMENT 'Silver: AP vendor master (ERP view), one per billing entity.'
AS SELECT * FROM read_files('${landing_root}/ref/ap_vendors.csv', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW map_vendor_counterparty (
  CONSTRAINT one_mapping_per_ap_vendor EXPECT (ap_vendor_id IS NOT NULL)
) COMMENT 'Silver: AP vendor ID ↔ trade-system counterparty / LEI, with the is_affiliate flag for intra-group charges.'
AS SELECT * FROM read_files('${landing_root}/ref/map_vendor_counterparty.csv', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW dim_counterparty COMMENT 'Silver: trade-system clients and street counterparties with LEIs.'
AS SELECT * FROM read_files('${landing_root}/ref/counterparties.csv', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW map_gl_cost_type COMMENT 'Silver: GL account ↔ cost type; all accounts roll to the US GAAP line "Commissions and floor brokerage".'
AS SELECT * FROM read_files('${landing_root}/ref/map_gl_cost_type.csv', format => 'csv', header => true,
  schemaHints => 'gl_account STRING, in_net_borne BOOLEAN, is_intragroup BOOLEAN');

CREATE OR REFRESH MATERIALIZED VIEW dim_fiscal_calendar COMMENT 'Silver: calendar month → fiscal year / quarter / half (April–March).'
AS SELECT * FROM read_files('${landing_root}/ref/dim_fiscal_calendar.csv', format => 'csv', header => true,
  schemaHints => 'period STRING, calendar_year INT, calendar_month INT, month_label STRING, fiscal_year INT, fiscal_year_label STRING, fiscal_period_num INT, fiscal_quarter STRING, fiscal_quarter_id STRING, fiscal_quarter_label STRING, fiscal_half STRING, fiscal_half_id STRING, is_fiscal_year_end BOOLEAN, is_half_year_end BOOLEAN');

CREATE OR REFRESH MATERIALIZED VIEW business_calendar COMMENT 'Silver: business days by market (fail ageing and settlement cycles).'
AS SELECT market, CAST(calendar_date AS DATE) AS calendar_date, CAST(is_business_day AS BOOLEAN) AS is_business_day
FROM read_files('${landing_root}/ref/business_calendar.csv', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW dim_instrument COMMENT 'Silver: instruments by product family.'
AS SELECT * FROM read_files('${landing_root}/ref/instruments.csv', format => 'csv', header => true);
