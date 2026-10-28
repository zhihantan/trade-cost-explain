-- Aggregates of the trade-level expected cost used by the bridge, the invoice reconciliation and the dashboards.
USE SCHEMA gold;

CREATE OR REFRESH MATERIALIZED VIEW expected_cost_monthly
COMMENT 'Gold: expected cost by month × driver slice (cost type × fee basis × product family × desk × vendor × venue × capacity × entity × currency). driver_volume is in the slice volume unit.'
CLUSTER BY (period, desk_code)
AS SELECT period, desk_code, legal_entity, billing_vendor_id, venue, capacity, cost_type, fee_basis, product_family,
          volume_unit, cost_currency, reporting_market, in_net_borne, is_recoverable, is_affiliate,
          SUM(driver_volume) AS driver_volume, SUM(cost_lcy) AS cost_lcy, SUM(cost_usd) AS cost_usd,
          COUNT(DISTINCT trade_id) AS trades
FROM expected_cost_trade
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW expected_cost_daily
COMMENT 'Gold: expected cost by trade date × desk × cost type × vendor × venue × capacity × market (net borne, gross, recoverable, intra-group).'
CLUSTER BY (trade_date, desk_code)
WITH ROW FILTER ${catalog}.gold.ce_desk_scope ON (desk_code)
AS SELECT trade_date, period, desk_code, legal_entity, billing_vendor_id, venue, capacity, cost_type, product_family,
          reporting_market, cost_currency,
          SUM(cost_usd)                                            AS gross_cost_usd,
          SUM(IF(in_net_borne, cost_usd, 0D))                      AS net_borne_cost_usd,
          SUM(IF(is_recoverable, cost_usd, 0D))                    AS recoverable_cost_usd,
          SUM(IF(is_affiliate, cost_usd, 0D))                      AS intragroup_cost_usd,
          SUM(IF(in_net_borne, cost_lcy, 0D))                      AS net_borne_cost_lcy,
          COUNT(DISTINCT trade_id)                                 AS trades
FROM expected_cost_trade
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW expected_cost_invoice_grain
COMMENT 'Gold: expected cost at vendor invoice grain (service month × billing vendor × entity × currency × cost type × fee code × product), GST as tax.'
AS SELECT period AS service_period, billing_vendor_id AS vendor_id, legal_entity, cost_currency AS currency,
          base_cost_type AS cost_type, fee_id, product_family,
          SUM(IF(cost_type NOT IN ('GST_NONREC', 'GST_REC'), cost_lcy, 0D)) AS expected_net,
          SUM(IF(cost_type IN ('GST_NONREC', 'GST_REC'), cost_lcy, 0D))     AS expected_tax,
          SUM(IF(cost_type NOT IN ('GST_NONREC', 'GST_REC'), volume, 0D))   AS expected_qty
FROM expected_cost_trade
GROUP BY ALL;
