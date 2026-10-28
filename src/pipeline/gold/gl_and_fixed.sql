-- GL by month × GL key (mapped to desk / cost type / vendor) and contracted fixed fees by month.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW gl_monthly
COMMENT 'Gold: GL actuals by fiscal period × account × cost centre × AP vendor × entity × currency, mapped to desk, cost type and trade-system vendor.'
CLUSTER BY (period)
AS SELECT fiscal_period AS period, gl_account, gl_account_name, cost_type, in_net_borne, is_intragroup, cost_centre, desk_code,
          ap_vendor_id, ap_vendor_name, vendor_id, is_vendor_mapped, legal_entity, currency,
          SUM(amount_lcy) AS amount_lcy, SUM(amount_usd) AS amount_usd,
          SUM(IF(is_accrual, amount_usd, 0D)) AS accrual_usd
FROM silver.gl_actuals
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW fixed_fee_monthly
COMMENT 'Gold: contracted fixed fees (participant, access, connectivity) by month, vendor and host desk (shown in the bridge only when they move).'
AS SELECT fc.period, f.fee_id, f.vendor_id, f.legal_entity, f.currency, f.rate AS amount_lcy, f.description,
          m.cost_centre, cc.desk_code, f.rate * fx.rate_to_usd AS amount_usd
FROM silver.fee_schedule f
JOIN silver.dim_fiscal_calendar fc
  ON to_date(concat(fc.period, '-01')) >= f.effective_from
 AND (f.effective_to IS NULL OR to_date(concat(fc.period, '-01')) <= f.effective_to)
JOIN silver.fx_monthly fx                ON fx.currency = f.currency AND fx.period = fc.period
LEFT JOIN silver.map_fixed_fee_costcentre m ON m.fee_id = f.fee_id
LEFT JOIN silver.map_costcentre_desk cc   ON cc.cost_centre = m.cost_centre
WHERE f.fee_basis = 'FIXED_MONTHLY';
