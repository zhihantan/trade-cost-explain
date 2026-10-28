-- Replicates the review app's Lakebase store into Unity Catalog Delta tables (control evidence).
-- Fallback for Lakehouse Sync, which does not support Default Storage catalogs.
-- Source: cost_explain_lakebase.cost_explain_app.*  (Lakebase database registered in UC)
-- Target: cost_explain.review.*
-- History tables are append-only replicas: a demo reset of the operational store never removes UC history.

CREATE TABLE IF NOT EXISTS cost_explain.review.commentary (
  id STRING, period STRING, slice_key STRING, title STRING, version INT, status STRING, draft_text STRING,
  edited_text STRING, author_email STRING, last_edited_by STRING, submitted_by STRING, decided_by STRING,
  decision_note STRING, drafted_by_model STRING, agent_trace_id STRING, created_at TIMESTAMP, updated_at TIMESTAMP,
  submitted_at TIMESTAMP, decided_at TIMESTAMP, _synced_at TIMESTAMP)
COMMENT 'Variance commentary — current state per item (replica of Lakebase cost_explain_app.commentary).';

CREATE TABLE IF NOT EXISTS cost_explain.review.commentary_version (
  commentary_id STRING, version INT, text STRING, change_type STRING, actor_email STRING, request_id STRING,
  created_at TIMESTAMP, _synced_at TIMESTAMP)
COMMENT 'Append-only text history: one row per commentary version (who changed what, when).';

CREATE TABLE IF NOT EXISTS cost_explain.review.commentary_figure (
  commentary_id STRING, version INT, figure_key STRING, label STRING, value DOUBLE, unit STRING, source_table STRING,
  filter STRING, delta_version BIGINT, as_of_ts TIMESTAMP, snapshot_ref STRING, captured_at TIMESTAMP, _synced_at TIMESTAMP)
COMMENT 'Append-only figure snapshots: every number in a commentary version with its source table, filter and data snapshot (Delta version, or pipeline update id for materialized views).';

CREATE TABLE IF NOT EXISTS cost_explain.review.approval_event (
  event_id BIGINT, commentary_id STRING, version INT, action STRING, from_status STRING, to_status STRING,
  actor_email STRING, request_id STRING, note STRING, created_at TIMESTAMP, _synced_at TIMESTAMP)
COMMENT 'Append-only approval events (created, drafted, edited, submitted, approved, rejected) attributed to named users.';

MERGE INTO cost_explain.review.commentary AS t
USING cost_explain_lakebase.cost_explain_app.commentary AS s
ON t.id = s.id
WHEN MATCHED AND (t.version <> s.version OR t.status <> s.status OR t.updated_at <> s.updated_at) THEN UPDATE SET
  t.period = s.period, t.slice_key = s.slice_key, t.title = s.title, t.version = s.version, t.status = s.status,
  t.draft_text = s.draft_text, t.edited_text = s.edited_text, t.author_email = s.author_email,
  t.last_edited_by = s.last_edited_by, t.submitted_by = s.submitted_by, t.decided_by = s.decided_by,
  t.decision_note = s.decision_note, t.drafted_by_model = s.drafted_by_model, t.agent_trace_id = s.agent_trace_id,
  t.created_at = s.created_at, t.updated_at = s.updated_at, t.submitted_at = s.submitted_at,
  t.decided_at = s.decided_at, t._synced_at = current_timestamp()
WHEN NOT MATCHED THEN INSERT (id, period, slice_key, title, version, status, draft_text, edited_text, author_email,
  last_edited_by, submitted_by, decided_by, decision_note, drafted_by_model, agent_trace_id, created_at, updated_at,
  submitted_at, decided_at, _synced_at)
  VALUES (s.id, s.period, s.slice_key, s.title, s.version, s.status, s.draft_text, s.edited_text, s.author_email,
  s.last_edited_by, s.submitted_by, s.decided_by, s.decision_note, s.drafted_by_model, s.agent_trace_id, s.created_at,
  s.updated_at, s.submitted_at, s.decided_at, current_timestamp())
WHEN NOT MATCHED BY SOURCE THEN DELETE;

MERGE INTO cost_explain.review.commentary_version AS t
USING cost_explain_lakebase.cost_explain_app.commentary_version AS s
ON t.commentary_id = s.commentary_id AND t.version = s.version
WHEN NOT MATCHED THEN INSERT (commentary_id, version, text, change_type, actor_email, request_id, created_at, _synced_at)
  VALUES (s.commentary_id, s.version, s.text, s.change_type, s.actor_email, s.request_id, s.created_at, current_timestamp());

MERGE INTO cost_explain.review.commentary_figure AS t
USING cost_explain_lakebase.cost_explain_app.commentary_figure AS s
ON t.commentary_id = s.commentary_id AND t.version = s.version AND t.figure_key = s.figure_key
WHEN NOT MATCHED THEN INSERT (commentary_id, version, figure_key, label, value, unit, source_table, filter, delta_version,
  as_of_ts, snapshot_ref, captured_at, _synced_at)
  VALUES (s.commentary_id, s.version, s.figure_key, s.label, s.value, s.unit, s.source_table, s.filter, s.delta_version,
  s.as_of_ts, s.snapshot_ref, s.captured_at, current_timestamp());

MERGE INTO cost_explain.review.approval_event AS t
USING cost_explain_lakebase.cost_explain_app.approval_event AS s
ON t.commentary_id = s.commentary_id AND t.event_id = s.event_id
WHEN NOT MATCHED THEN INSERT (event_id, commentary_id, version, action, from_status, to_status, actor_email, request_id,
  note, created_at, _synced_at)
  VALUES (s.event_id, s.commentary_id, s.version, s.action, s.from_status, s.to_status, s.actor_email, s.request_id,
  s.note, s.created_at, current_timestamp());
