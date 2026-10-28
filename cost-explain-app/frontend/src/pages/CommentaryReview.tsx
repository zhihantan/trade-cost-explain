// Screen 2 — Commentary review: the draft as a document, beside a rail with the figures it cites, its history and
// Ask Genie. Edit, save, submit (and decide, for approvers).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useBlocker, useParams, useSearchParams } from "react-router-dom";
import { ApiError, api, errorText } from "../api/client";
import type { CommentaryDetail, CommentaryFigure } from "../api/types";
import { CommentaryText, chipKeys } from "../components/CommentaryText";
import { FigureRow, Modal, Notice, ReasonModal, Skeleton, StatusBadge } from "../components/common";
import { GeniePanel } from "../components/GeniePanel";
import { Icon } from "../components/Icon";
import { EmptyState, PageHeader, Tabs } from "../components/layout";
import { sliceLabel, when } from "../format";
import { useComparisonLabel, useMe } from "../hooks";

type Decision = "approve" | "reject" | null;
type RailTab = "figures" | "history" | "genie";

const words = (t: string) => t.replace(/\[\[fig:[^\]]+\]\]/g, "").replace(/[*#-]/g, " ").split(/\s+/).filter(Boolean).length;

export function CommentaryReview() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const me = useMe();
  const label = useComparisonLabel();
  const detail = useQuery({ queryKey: ["commentary", id], queryFn: () => api.getCommentary(id) });
  const audit = useQuery({ queryKey: ["audit", id], queryFn: () => api.audit(id) });

  const [text, setText] = useState("");
  const [base, setBase] = useState<{ version: number; text: string } | null>(null);
  const [mode, setMode] = useState<"preview" | "edit">("preview");
  const [conflict, setConflict] = useState<number | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [decision, setDecision] = useState<Decision>(null);
  const [activeFig, setActiveFig] = useState<string | null>(null);
  const [genieFor, setGenieFor] = useState<string | null>(null);
  const [tab, setTab] = useState<RailTab>("figures");
  const [message, setMessage] = useState<{ kind: "info" | "err" | "warn"; text: string } | null>(null);
  const autodrafted = useRef(false);

  const d = detail.data;
  const dirty = !!base && text !== base.text;

  // Adopt server text when a new version arrives and there are no local edits.
  useEffect(() => {
    if (!d) return;
    if (!base || (!dirty && d.version !== base.version)) {
      setText(d.edited_text ?? "");
      setBase({ version: d.version, text: d.edited_text ?? "" });
    }
  }, [d?.version, d?.edited_text]); // eslint-disable-line react-hooks/exhaustive-deps

  // Unsaved-changes guard (in-app navigation and tab close).
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["commentary", id] });
    qc.invalidateQueries({ queryKey: ["audit", id] });
    qc.invalidateQueries({ queryKey: ["commentary"] });
  };
  const onError = (e: unknown) => {
    if (e instanceof ApiError && e.status === 409 && typeof e.detail === "object" && e.detail && "current_version" in e.detail) {
      setConflict(Number((e.detail as { current_version: number }).current_version));
    } else setMessage({ kind: "err", text: errorText(e) });
  };

  const draft = useMutation({ mutationFn: () => api.draft(id), onSuccess: (r) => { setJobId(r.job_id); setMessage(null); }, onError });
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["succeeded", "failed"].includes(q.state.data.status) ? false : 2000),
  });
  useEffect(() => {
    const j = job.data;
    if (!j || !jobId) return;
    if (j.status === "succeeded") {
      const r = j.result ?? {};
      const fallback = r.fallback_reason ? ` — template drafter used (${String(r.fallback_reason)})` : "";
      const mism = Array.isArray(r.value_mismatches) && r.value_mismatches.length ? ` · ${r.value_mismatches.length} agent values corrected to Gold` : "";
      setMessage({ kind: "info", text: `Draft ready: ${String(r.figures ?? 0)} figures cited by ${String(r.model ?? "agent")}${fallback}${mism}.` });
      setJobId(null);
      setMode("preview");
      refresh();
    } else if (j.status === "failed") {
      setMessage({ kind: "err", text: j.error ?? "Drafting failed" });
      setJobId(null);
    }
  }, [job.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-start the agent when arriving from "Draft commentary" on the flux page.
  useEffect(() => {
    if (d && params.get("autodraft") && !autodrafted.current && d.permissions.draft && !(d.edited_text ?? "").trim()) {
      autodrafted.current = true;
      setParams({}, { replace: true });
      draft.mutate();
    }
  }, [d]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = useMutation({
    mutationFn: () => api.saveCommentary(id, base?.version ?? 0, text),
    onSuccess: (c) => { setBase({ version: c.version, text: c.edited_text ?? "" }); setConflict(null); setMessage({ kind: "info", text: `Saved as v${c.version}.` }); refresh(); },
    onError,
  });
  const submit = useMutation({ mutationFn: () => api.submit(id, d?.version ?? 0), onSuccess: () => { setMessage({ kind: "info", text: "Submitted for review." }); refresh(); }, onError });
  const decide = useMutation({
    mutationFn: ({ kind, note }: { kind: "approve" | "reject"; note: string }) =>
      kind === "approve" ? api.approve(id, d?.version ?? 0, note || undefined) : api.reject(id, d?.version ?? 0, note),
    onSuccess: (c) => { setDecision(null); setMessage({ kind: "info", text: `Commentary ${c.status}.` }); refresh(); qc.invalidateQueries({ queryKey: ["approvals"] }); },
    onError: (e) => { setDecision(null); onError(e); },
  });

  // Figures: the snapshot for the current version, plus live lookups for chips added in unsaved edits.
  const snapshot = useMemo(() => Object.fromEntries((d?.figures ?? []).map((f) => [f.figure_key, f])), [d?.figures]);
  const missing = useMemo(() => chipKeys(text).filter((k) => !snapshot[k]), [text, snapshot]);
  const live = useQuery({
    queryKey: ["figs", missing.join(",")],
    queryFn: () => Promise.all(missing.map((k) => api.figure(k).catch(() => null))),
    enabled: missing.length > 0,
  });
  const figures: Record<string, CommentaryFigure> = { ...snapshot };
  live.data?.forEach((f) => { if (f) figures[f.figure_key] = { ...f, label: `${f.label} (live — not yet saved)` }; });
  const cited = chipKeys(text).map((k) => figures[k]).filter(Boolean) as CommentaryFigure[];

  if (detail.isError) return <div className="page-body"><Notice kind="err">{errorText(detail.error)}</Notice></div>;
  if (!d) return <div className="page-body"><Skeleton h={480} /></div>;
  const drafting = draft.isPending || !!jobId;
  const host = me.data?.workspace_host ?? "";
  const events = audit.data?.events ?? [];
  const openFigure = (k: string) => {
    setActiveFig(k);
    setTab("figures");
    setTimeout(() => document.getElementById(`fig-${k}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 0);
  };

  return (
    <>
      <PageHeader
        crumbs={[{ label: "Commentary", to: "/commentary" }, { label: label(d.period) }]}
        title={d.title}
        badge={<StatusBadge status={d.status} />}
        sub={<>
          {sliceLabel(d.slice_key)} · v{d.version} · author {d.author_email}
          {d.last_edited_by && d.last_edited_by !== d.author_email ? ` · last edit ${d.last_edited_by}` : ""}
          {d.drafted_by_model ? ` · drafted by ${d.drafted_by_model}` : ""}
        </>}
        actions={<Actions d={d} dirty={dirty} drafting={drafting} onDraft={() => draft.mutate()} onSave={() => save.mutate()}
          onSubmit={() => submit.mutate()} onDecide={setDecision} busy={save.isPending || submit.isPending || decide.isPending} />}
      />
      <div className="page-body">
        {(conflict !== null || message || drafting || dirty || d.blockers.decide) && (
          <div className="notices">
            {conflict !== null && (
              <Notice kind="warn">
                Version conflict: this commentary is now at v{conflict}. Your edits are kept in the editor.{" "}
                <button className="btn small" onClick={() => { setConflict(null); setBase(null); refresh(); }}>Discard my edits and reload</button>
              </Notice>
            )}
            {message && <Notice kind={message.kind}>{message.text}</Notice>}
            {drafting && <Notice kind="info"><span className="spinner" /> The commentary agent is drafting from the Gold bridge (job {jobId?.slice(0, 8) ?? "starting"}, {job.data?.status ?? "queued"}).</Notice>}
            {dirty && <Notice kind="warn">Unsaved changes, based on v{base?.version}.</Notice>}
            {d.blockers.decide && <Notice kind="info">{d.blockers.decide}</Notice>}
          </div>
        )}

        <div className="grid-review">
          <section className="card">
            <div className="card-head">
              <div className="doc-meta">
                <span>{words(text)} words</span><span>·</span><span>{cited.length} figures cited</span><span>·</span><span>updated {when(d.updated_at)}</span>
              </div>
              {d.permissions.edit && (
                <div className="seg" role="group" aria-label="View">
                  <button className={mode === "preview" ? "on" : ""} aria-pressed={mode === "preview"} onClick={() => setMode("preview")}>Preview</button>
                  <button className={mode === "edit" ? "on" : ""} aria-pressed={mode === "edit"} onClick={() => setMode("edit")}><Icon name="edit" size={13} /> Edit</button>
                </div>
              )}
            </div>
            <div className="doc">
              {mode === "edit" ? (
                <>
                  <textarea value={text} onChange={(e) => setText(e.target.value)} aria-label="Commentary text" />
                  <div className="small muted" style={{ marginTop: 8 }}>Cite figures as <span className="mono">[[fig:&lt;figure_key&gt;]]</span>. Unknown figure keys are rejected on save.</div>
                </>
              ) : text.trim() ? (
                <CommentaryText text={text} figures={figures} active={activeFig} onChip={openFigure} />
              ) : (
                <EmptyState icon="sparkle" title="No text yet">{d.permissions.draft ? "Use “Draft with agent” to generate commentary from the bridge." : ""}</EmptyState>
              )}
              {d.decision_note && <div style={{ marginTop: 14 }}><Notice kind={d.status === "rejected" ? "err" : "info"}>Decision note from {d.decided_by}: {d.decision_note}</Notice></div>}
            </div>
          </section>

          <aside className="card sticky-rail" aria-label="Figures, history and Genie">
            <Tabs<RailTab>
              tabs={[
                { key: "figures", label: "Figures", count: cited.length },
                { key: "history", label: "History", count: events.length },
                ...(me.data?.features.genie ? [{ key: "genie" as const, label: "Ask Genie" }] : []),
              ]}
              value={tab}
              onChange={setTab}
            />
            {tab === "figures" && (cited.length === 0 ? <EmptyState icon="info" title="No figure chips in the text" /> : (
              <>
                <div className="small muted" style={{ padding: "10px var(--pad) 0" }}>Each number links to the Gold table, filter and data snapshot it came from.</div>
                <ul className="fig-list">
                  {cited.map((f) => (
                    <FigureRow key={f.figure_key} f={f} host={host} active={activeFig === f.figure_key}
                      onSelect={(k) => setActiveFig(k === activeFig ? null : k)}
                      onAskGenie={me.data?.features.genie ? (k) => { setGenieFor(k); setTab("genie"); } : undefined} />
                  ))}
                </ul>
              </>
            ))}
            {tab === "history" && (
              <ul className="timeline">
                {events.map((e) => (
                  <li key={e.event_id}>
                    <div><b>{e.action}</b> · v{e.version} · {e.actor_email}</div>
                    <div className="when">{when(e.created_at)}{e.note ? ` — ${e.note}` : ""}</div>
                  </li>
                ))}
              </ul>
            )}
            {tab === "genie" && <GeniePanel figureKey={genieFor ?? activeFig} />}
          </aside>
        </div>
      </div>

      {decision && (
        <ReasonModal title={decision === "approve" ? "Approve commentary" : "Reject commentary"} cta={decision === "approve" ? "Approve" : "Reject"}
          required={decision === "reject"} onClose={() => setDecision(null)} onSubmit={(note) => decide.mutate({ kind: decision, note })} />
      )}
      {blocker.state === "blocked" && (
        <Modal title="Discard unsaved changes?" onClose={() => blocker.reset?.()}>
          <p style={{ marginBottom: 16 }}>You have edits that are not saved.</p>
          <div className="btn-row" style={{ justifyContent: "flex-end" }}>
            <button className="btn ghost" onClick={() => blocker.reset?.()}>Stay</button>
            <button className="btn danger" onClick={() => blocker.proceed?.()}>Discard and leave</button>
          </div>
        </Modal>
      )}
    </>
  );
}

function Actions({ d, dirty, drafting, onDraft, onSave, onSubmit, onDecide, busy }: {
  d: CommentaryDetail; dirty: boolean; drafting: boolean;
  onDraft: () => void; onSave: () => void; onSubmit: () => void; onDecide: (k: Decision) => void; busy: boolean;
}) {
  const p = d.permissions;
  return (
    <>
      {p.draft && (
        <button className="btn" disabled={drafting || dirty} title={dirty ? "Save or discard edits first" : undefined} onClick={onDraft}>
          {drafting ? <><span className="spinner" /> Drafting…</> : <><Icon name="sparkle" />{d.edited_text ? "Redraft with agent" : "Draft with agent"}</>}
        </button>
      )}
      {p.edit && <button className="btn" disabled={!dirty || busy} onClick={onSave}>Save</button>}
      {(p.submit || (p.edit && d.status === "draft")) && (
        <button className="btn primary" disabled={dirty || busy || !p.submit} title={dirty ? "Save first" : undefined} onClick={onSubmit}>Submit for review</button>
      )}
      {d.status === "in_review" && (
        <>
          <button className="btn danger" disabled={!p.decide || busy} title={d.blockers.decide} onClick={() => onDecide("reject")}>Reject</button>
          <button className="btn primary" disabled={!p.decide || busy} title={d.blockers.decide} onClick={() => onDecide("approve")}><Icon name="check" />Approve</button>
        </>
      )}
    </>
  );
}
