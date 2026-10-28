-- Tie-check and lineage bridge: every figure cited in a commentary version, joined to the governed figure registry
-- in Gold. Run once Gold is published (it references cost_explain.gold.commentary_figures).
-- Lineage: review.v_commentary_figure_evidence -> gold.commentary_figures -> gold.cost_flux_bridge -> silver -> bronze.
CREATE OR REPLACE VIEW cost_explain.review.v_commentary_figure_evidence
COMMENT 'Each commentary figure with the value captured at drafting vs the current governed value (tie-check).'
AS
SELECT
  c.period                             AS comparison_id,
  c.slice_key,
  c.title,
  c.status,
  f.commentary_id,
  f.version,
  f.figure_key,
  f.label,
  f.value                              AS value_at_capture,
  g.value                              AS value_now,
  CASE WHEN g.figure_key IS NULL THEN 'NOT_IN_REGISTRY'
       WHEN f.value IS NULL OR g.value IS NULL THEN 'UNKNOWN'
       WHEN abs(f.value - g.value) <= 0.5 THEN 'TIES'
       ELSE 'CHANGED' END              AS tie_status,
  f.source_table,
  f.filter                             AS filter_at_capture,
  g.filter_expr                        AS filter_now,
  f.delta_version                      AS delta_version_at_capture,
  f.snapshot_ref                       AS snapshot_ref_at_capture,
  f.as_of_ts                           AS as_of_at_capture,
  f.captured_at
FROM cost_explain.review.commentary_figure AS f
-- current items only: figures of items removed by a demo reset stay in the append-only history tables
JOIN cost_explain.review.commentary AS c ON c.id = f.commentary_id
LEFT JOIN cost_explain.gold.commentary_figures AS g ON g.figure_key = f.figure_key;
