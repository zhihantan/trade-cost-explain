-- Fine-grained access for desk heads (ABAC, GA April 2026): rows carrying a column tagged ce_rls_scope = 'desk' are
-- visible to desk-head groups only for the desks they are entitled to. The policy is scoped TO the desk-head groups,
-- so the CFO office, FP&A analysts, the review app and the commentary agent are not affected.
-- Prerequisite (account-level, once): governed tag ce_rls_scope with allowed values desk / legal_entity / market
-- (scripts/governance.sh creates it with `databricks tag-policies create-tag-policy`).

CREATE TABLE IF NOT EXISTS cost_explain.gold.desk_entitlements (
  group_name  STRING COMMENT 'Account group of a desk head',
  desk_code   STRING COMMENT 'Desk the group may see',
  granted_by  STRING,
  granted_at  TIMESTAMP
) COMMENT 'Entitlements behind the desk-head ABAC row filter: which account group may see which desk.';

MERGE INTO cost_explain.gold.desk_entitlements t
USING (SELECT * FROM VALUES ('ce_desk_head_eqd', 'HKED') AS v(group_name, desk_code)) s
ON t.group_name = s.group_name AND t.desk_code = s.desk_code
WHEN NOT MATCHED THEN INSERT (group_name, desk_code, granted_by, granted_at)
  VALUES (s.group_name, s.desk_code, current_user(), current_timestamp());

CREATE OR REPLACE FUNCTION cost_explain.gold.ce_desk_scope(row_desk STRING)
RETURNS BOOLEAN
COMMENT 'ABAC row filter: TRUE when the caller is in a group entitled to the row''s desk (gold.desk_entitlements).'
RETURN EXISTS (
  SELECT 1 FROM cost_explain.gold.desk_entitlements e
  WHERE e.desk_code = row_desk AND (is_member(e.group_name) OR is_account_group_member(e.group_name))
);

-- Tag the desk columns of the desk-grained Gold tables.
ALTER TABLE cost_explain.gold.cost_flux_bridge  ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');
ALTER TABLE cost_explain.gold.cost_flux_slice   ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');
ALTER TABLE cost_explain.gold.cost_monthly      ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');
ALTER TABLE cost_explain.gold.cost_kpis         ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');
ALTER TABLE cost_explain.gold.expected_cost_trade ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');
ALTER TABLE cost_explain.gold.expected_cost_daily ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');
ALTER TABLE cost_explain.gold.fail_cost_summary ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');
ALTER TABLE cost_explain.gold.fail_cost_daily   ALTER COLUMN desk_code SET TAGS ('ce_rls_scope' = 'desk');

CREATE OR REPLACE POLICY ce_desk_scope
ON SCHEMA cost_explain.gold
COMMENT 'Desk heads see only the desks in gold.desk_entitlements (rows matched by columns tagged ce_rls_scope = desk).'
ROW FILTER cost_explain.gold.ce_desk_scope
TO `ce_desk_head_eqd`
FOR TABLES
MATCH COLUMNS has_tag_value('ce_rls_scope', 'desk') AS desk_col
USING COLUMNS (desk_col);
