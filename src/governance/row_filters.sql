-- Desk-level row security for the Gold layer (workspace-local groups via is_member, account groups via is_account_group_member) (runs before the pipeline: the pipeline’s materialized views attach
-- cost_explain.gold.ce_desk_scope with WITH ROW FILTER). Desk heads see only the desks in gold.desk_entitlements,
-- everyone else (CFO office, FP&A analysts, the review app, the commentary agent) is unaffected.
-- Preferred on a customer workspace: the ABAC policy in abac.sql (governed tag ce_rls_scope) — same entitlement logic.

CREATE TABLE IF NOT EXISTS cost_explain.gold.desk_entitlements (
  group_name  STRING COMMENT 'Account group of a desk head',
  desk_code   STRING COMMENT 'Desk the group may see',
  granted_by  STRING,
  granted_at  TIMESTAMP
) COMMENT 'Entitlements behind the desk-head row filter: which account group may see which desk.';

MERGE INTO cost_explain.gold.desk_entitlements t
USING (SELECT * FROM VALUES ('ce_desk_head_eqd', 'HKED') AS v(group_name, desk_code)) s
ON t.group_name = s.group_name AND t.desk_code = s.desk_code
WHEN NOT MATCHED THEN INSERT (group_name, desk_code, granted_by, granted_at)
  VALUES (s.group_name, s.desk_code, current_user(), current_timestamp());

CREATE OR REPLACE FUNCTION cost_explain.gold.ce_desk_scope(row_desk STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: callers in no desk-head group see every row, desk heads see only rows for desks granted to their group in gold.desk_entitlements.'
RETURN NOT EXISTS (SELECT 1 FROM cost_explain.gold.desk_entitlements e WHERE (is_member(e.group_name) OR is_account_group_member(e.group_name)))
    OR EXISTS (SELECT 1 FROM cost_explain.gold.desk_entitlements e
               WHERE e.desk_code = row_desk AND (is_member(e.group_name) OR is_account_group_member(e.group_name)));
