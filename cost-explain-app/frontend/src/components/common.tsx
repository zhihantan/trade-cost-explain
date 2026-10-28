import { useState, type ReactNode } from "react";
import type { CommentaryFigure, Status } from "../api/types";
import { figureValue, snapshotLabel, statusLabel, ucTableUrl } from "../format";
import { Icon } from "./Icon";

export function StatusBadge({ status }: { status: Status | string }) {
  return <span className={`badge ${status}`}>{statusLabel(status)}</span>;
}

const NOTICE_ICON = { warn: "alert", err: "alert", info: "info" } as const;

export function Notice({ kind, children }: { kind: "warn" | "err" | "info"; children: ReactNode }) {
  return (
    <div className={`notice ${kind}`} role={kind === "err" ? "alert" : "status"}>
      <Icon name={NOTICE_ICON[kind]} />
      <div>{children}</div>
    </div>
  );
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-back" onClick={onClose} role="dialog" aria-modal="true" aria-label={title}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ReasonModal({ title, cta, required, onSubmit, onClose }: {
  title: string; cta: string; required: boolean; onSubmit: (note: string) => void; onClose: () => void;
}) {
  const [note, setNote] = useState("");
  const ok = !required || note.trim().length >= 3;
  return (
    <Modal title={title} onClose={onClose}>
      <label className="field" style={{ marginBottom: 14 }}>
        {required ? "Reason (required)" : "Note (optional)"}
        <textarea value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
      </label>
      <div className="btn-row" style={{ justifyContent: "flex-end" }}>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className={`btn ${cta === "Reject" ? "danger" : "primary"}`} disabled={!ok} onClick={() => onSubmit(note.trim())}>{cta}</button>
      </div>
    </Modal>
  );
}

// One cited figure in the review rail: label and value; source and data snapshot underneath; details on select.
export function FigureRow({ f, host, active, onSelect, onAskGenie }: {
  f: CommentaryFigure; host: string; active?: boolean; onSelect?: (key: string) => void; onAskGenie?: (key: string) => void;
}) {
  const url = ucTableUrl(host, f.source_table);
  const table = f.source_table?.split(".").pop() ?? "—";
  const snap = snapshotLabel(f.delta_version, f.snapshot_ref, f.as_of_ts);
  return (
    <li className={`fig-row ${active ? "active" : ""}`} id={`fig-${f.figure_key}`} onClick={() => onSelect?.(f.figure_key)}>
      <div className="top">
        <span className="lbl">{f.label ?? f.figure_key}</span>
        <span className="val">{figureValue(f.value, f.unit)}</span>
      </div>
      <div className="src" title={`${f.source_table} · ${snap}`}><span className="mono">{table}</span> · {snap}</div>
      {active && (
        <>
          <dl className="kv">
            <dt>Figure</dt><dd className="mono">{f.figure_key}</dd>
            <dt>Source</dt><dd className="mono">{url ? <a href={url} target="_blank" rel="noreferrer">{f.source_table}</a> : f.source_table ?? "—"}</dd>
            <dt>Filter</dt><dd className="mono">{f.filter || "—"}</dd>
            {f.snapshot_ref && <><dt>Snapshot</dt><dd className="mono">{f.snapshot_ref}</dd></>}
          </dl>
          <div className="btn-row" style={{ marginTop: 10 }}>
            {url && <a className="btn small" href={`${url}?activeTab=lineage`} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}><Icon name="lineage" size={14} />Lineage</a>}
            {onAskGenie && <button className="btn small" onClick={(e) => { e.stopPropagation(); onAskGenie(f.figure_key); }}><Icon name="genie" size={14} />Ask Genie</button>}
          </div>
        </>
      )}
    </li>
  );
}

export function Skeleton({ h = 16, w = "100%" }: { h?: number; w?: number | string }) {
  return <div className="skeleton" style={{ height: h, width: w }} />;
}
