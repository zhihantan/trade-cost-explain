-- Read access for demo viewers (dashboard with viewer credentials, Genie, the app’s user-authorized reads).
-- Gold is readable by everyone in the account; desk row filters still apply. Only the two Silver tables the dashboard
-- reads directly are exposed; bronze and the rest of silver stay owner-only.
GRANT USE CATALOG ON CATALOG cost_explain TO `account users`;
GRANT USE SCHEMA ON SCHEMA cost_explain.gold TO `account users`;
GRANT SELECT ON SCHEMA cost_explain.gold TO `account users`;
GRANT USE SCHEMA ON SCHEMA cost_explain.silver TO `account users`;
GRANT SELECT ON TABLE cost_explain.silver.market_data TO `account users`;
GRANT SELECT ON TABLE cost_explain.silver.fx_monthly TO `account users`;
