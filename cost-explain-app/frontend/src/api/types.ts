// Mirrors backend/models.py. Keep in sync (or generate from /openapi.json with openapi-typescript).

export type Status = "draft" | "in_review" | "approved" | "rejected";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface Comparison {
  comparison_id: string;
  comparison_type: string;
  period_p0: string;
  period_p1: string;
  p0_label: string;
  p1_label: string;
  sort_order: number;
  is_default: boolean;
  comparison_label?: string | null;
}

export interface Effect {
  effect: string;
  label: string;
  amount: number;
  order: number;
  flux_class: string;
}

export interface FluxRow {
  key: string;
  p0: number;
  p1: number;
  volume: number;
  mix: number;
  rate: number;
  fx: number;
  fails: number;
  fixed: number;
  timing: number;
  unexplained: number;
  flux: number;
}

export interface DataSource {
  table: string;
  mode: "live" | "fixtures";
  delta_version: number | null;
  as_of_ts: string | null;
  snapshot_ref?: string | null;
  note: string | null;
}

export interface FluxResponse {
  comparison: Comparison;
  slice_key: string;
  slice_label: string;
  breakdown: string;
  totals: { p0: number; p1: number; p1_cc: number; flux: number; flux_pct: number | null };
  effects: Effect[];
  classes: { good: number; controllable: number; external: number };
  rows: FluxRow[];
  source: DataSource;
}

export interface SliceOption {
  key: string;
  label: string;
  group: string;
}

export interface Figure {
  figure_key: string;
  comparison_id: string | null;
  scope_key: string | null;
  scope_label: string | null;
  metric: string | null;
  metric_label: string | null;
  label: string;
  value: number | null;
  unit: string;
  source_table: string;
  filter: string;
  description: string | null;
  delta_version: number | null;
  as_of_ts: string | null;
  snapshot_ref?: string | null;
  mode: "live" | "fixtures" | "snapshot";
}

export interface CommentaryFigure {
  figure_key: string;
  label: string | null;
  value: number | null;
  unit: string | null;
  source_table: string | null;
  filter: string | null;
  delta_version: number | null;
  as_of_ts: string | null;
  snapshot_ref?: string | null;
}

export interface Commentary {
  id: string;
  period: string;
  slice_key: string;
  title: string;
  version: number;
  status: Status;
  draft_text: string | null;
  edited_text: string | null;
  author_email: string;
  last_edited_by: string | null;
  submitted_by: string | null;
  decided_by: string | null;
  decision_note: string | null;
  drafted_by_model: string | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  decided_at: string | null;
}

export interface CommentaryDetail extends Commentary {
  figures: CommentaryFigure[];
  permissions: Record<string, boolean>;
  blockers: Record<string, string>;
}

export interface Job {
  job_id: string;
  commentary_id: string;
  status: JobStatus;
  error: string | null;
  requested_by: string;
  result: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface AuditEvent {
  event_id: number;
  commentary_id: string;
  version: number;
  action: string;
  from_status: string | null;
  to_status: string | null;
  actor_email: string;
  request_id: string | null;
  note: string | null;
  created_at: string;
}

export interface CommentaryVersion {
  version: number;
  text: string | null;
  change_type: string;
  actor_email: string;
  created_at: string;
}

export interface AuditResponse {
  commentary: Commentary | null;
  events: AuditEvent[];
  versions: CommentaryVersion[];
  figures_by_version: Record<string, CommentaryFigure[]>;
}

export interface Me {
  email: string;
  display_name: string | null;
  roles: string[];
  is_analyst: boolean;
  is_approver: boolean;
  workspace_host: string;
  features: Record<string, boolean>;
  data_mode: string;
  default_comparison: string;
}

export interface GenieAnswer {
  status: string;
  text: string | null;
  sql: string | null;
  columns: string[];
  rows: (string | null)[][];
}
