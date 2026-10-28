// Typed client for the FastAPI backend. Same origin (no CORS); mutating calls carry the CSRF header.
import type {
  AuditResponse, Commentary, CommentaryDetail, Comparison, Figure, FluxResponse, GenieAnswer, Job, Me, SliceOption,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown, public requestId: string | null) {
    super(typeof detail === "string" ? detail : (detail as { message?: string })?.message ?? `HTTP ${status}`);
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Requested-With": "cost-explain-app", ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail, res.headers.get("x-request-id"));
  }
  return (await res.json()) as T;
}

const body = (b: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(b) });
const enc = encodeURIComponent;

export const api = {
  me: () => call<Me>("/me"),
  comparisons: () => call<Comparison[]>("/comparisons"),
  slices: (period: string) => call<SliceOption[]>(`/slices?period=${enc(period)}`),
  flux: (period: string, slice: string, breakdown?: string) =>
    call<FluxResponse>(`/flux?period=${enc(period)}&slice=${enc(slice)}${breakdown ? `&breakdown=${enc(breakdown)}` : ""}`),
  figure: (key: string) => call<Figure>(`/figures/${enc(key)}`),
  listCommentary: (status?: string) => call<Commentary[]>(`/commentary${status ? `?status=${status}` : ""}`),
  createCommentary: (period: string, slice_key: string) => call<Commentary>("/commentary", body({ period, slice_key })),
  getCommentary: (id: string) => call<CommentaryDetail>(`/commentary/${id}`),
  saveCommentary: (id: string, version: number, edited_text: string) =>
    call<Commentary>(`/commentary/${id}`, { method: "PUT", body: JSON.stringify({ version, edited_text }) }),
  draft: (id: string) => call<{ job_id: string; status: string }>(`/commentary/${id}/draft`, { method: "POST" }),
  job: (jobId: string) => call<Job>(`/jobs/${jobId}`),
  submit: (id: string, version: number, note?: string) => call<Commentary>(`/commentary/${id}/submit`, body({ version, note })),
  approve: (id: string, version: number, note?: string) => call<Commentary>(`/commentary/${id}/approve`, body({ version, note })),
  reject: (id: string, version: number, note: string) => call<Commentary>(`/commentary/${id}/reject`, body({ version, note })),
  approvals: () => call<Commentary[]>("/approvals"),
  audit: (commentaryId?: string) => call<AuditResponse>(`/audit${commentaryId ? `?commentary_id=${commentaryId}` : ""}`),
  demoReset: () => call<{ seeded: number }>("/admin/demo-reset", { method: "POST" }),
  genieAsk: (question: string, figure_key?: string) =>
    call<{ conversation_id: string; message_id: string }>("/genie/ask", body({ question, figure_key })),
  geniePoll: (c: string, m: string) => call<GenieAnswer>(`/genie/${enc(c)}/${enc(m)}`),
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const rid = e.requestId ? ` (request ${e.requestId.slice(0, 8)})` : "";
    return `${e.message}${rid}`;
  }
  return e instanceof Error ? e.message : String(e);
}
