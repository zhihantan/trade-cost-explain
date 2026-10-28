// Screen 4 — Audit trail: who drafted, edited and approved, when, and which data snapshot each figure came from.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Notice, Skeleton, StatusBadge } from "../components/common";
import { CommentaryText } from "../components/CommentaryText";
import { Icon } from "../components/Icon";
import { Card, EmptyState, PageHeader, Person } from "../components/layout";
import { figureValue, sliceLabel, snapshotLabel, ucTableUrl, when } from "../format";
import { useComparisonLabel, useMe } from "../hooks";

export function AuditTrail() {
  const [params, setParams] = useSearchParams();
  const me = useMe();
  const label = useComparisonLabel();
  const cid = params.get("commentary_id") ?? "";
  const list = useQuery({ queryKey: ["commentary", ""], queryFn: () => api.listCommentary() });
  const audit = useQuery({ queryKey: ["audit", cid], queryFn: () => api.audit(cid || undefined) });
  const [openVersion, setOpenVersion] = useState<number | null>(null);
  const a = audit.data;
  const versions = a ? Object.keys(a.figures_by_version).map(Number).sort((x, y) => y - x) : [];
  const figVersion = openVersion ?? versions[0] ?? null;
  const figs = figVersion != null ? a?.figures_by_version[String(figVersion)] ?? [] : [];
  const host = me.data?.workspace_host ?? "";
  const titleOf = (id: string) => list.data?.find((c) => c.id === id);

  return (
    <>
      <PageHeader
        crumbs={[{ label: "Close" }]}
        title="Audit trail"
        sub={<>Append-only approval events in Lakebase, replicated to <span className="mono">cost_explain.review</span>. Every write names the person and the request id.</>}
        actions={
          <label className="field">Commentary
            <select value={cid} onChange={(e) => { setOpenVersion(null); setParams(e.target.value ? { commentary_id: e.target.value } : {}); }}>
              <option value="">All recent events</option>
              {list.data?.map((c) => <option key={c.id} value={c.id}>{label(c.period)} · {sliceLabel(c.slice_key)} · {c.status.replace("_", " ")}</option>)}
            </select>
          </label>
        }
      />
      <div className="page-body">
        {audit.isError && <Notice kind="err">{errorText(audit.error)}</Notice>}
        {a?.commentary && (
          <section className="card card-pad">
            <div className="title-row" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h2 style={{ fontSize: 16 }}><Link to={`/commentary/${a.commentary.id}`}>{a.commentary.title}</Link></h2>
              <StatusBadge status={a.commentary.status} />
            </div>
            <div className="small muted" style={{ marginTop: 6 }}>Author {a.commentary.author_email} · v{a.commentary.version}{a.commentary.decided_by ? ` · decided by ${a.commentary.decided_by} on ${when(a.commentary.decided_at)}` : ""}</div>
          </section>
        )}
        <section className="card">
          <div className="card-head"><div className="card-title"><h2>Events</h2><span className="card-sub">{a ? `${a.events.length} events · newest first` : ""}</span></div></div>
          <div className="card-body" style={{ paddingLeft: 0, paddingRight: 0, paddingBottom: 0 }}>
            {audit.isLoading ? <div style={{ padding: "0 18px 18px" }}><Skeleton h={160} /></div> : !a?.events.length ? <EmptyState icon="clock" title="No events yet" /> : (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>When</th><th>Action</th><th>Person</th><th className="num">Version</th><th>Status</th><th>Note</th>{!cid && <th>Commentary</th>}<th>Request id</th></tr></thead>
                  <tbody>
                    {a.events.map((e) => (
                      <tr key={e.event_id}>
                        <td className="muted nowrap">{when(e.created_at)}</td>
                        <td><span className={`badge ${e.action}`}>{e.action}</span></td>
                        <td><Person email={e.actor_email} /></td>
                        <td className="num">v{e.version}</td>
                        <td><span className="transition">{e.from_status ? e.from_status.replace("_", " ") : "new"}<Icon name="arrow" size={12} />{e.to_status ? e.to_status.replace("_", " ") : "—"}</span></td>
                        <td className="small">{e.note ?? ""}</td>
                        {!cid && <td className="nowrap"><Link to={`/audit?commentary_id=${e.commentary_id}`}>{titleOf(e.commentary_id) ? label(titleOf(e.commentary_id)!.period) : e.commentary_id.slice(0, 8)}</Link></td>}
                        <td className="mono muted nowrap" title={e.request_id ?? ""}>{e.request_id?.slice(0, 18) ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
        {cid && a && (
          <div className="grid-review">
            <Card title="Versions" sub={`${a.versions.length} versions`}>
              <table className="data">
                <thead><tr><th className="num">Version</th><th>Change</th><th>Person</th><th>When</th><th /></tr></thead>
                <tbody>
                  {[...a.versions].reverse().map((v) => (
                    <tr key={v.version}>
                      <td className="num">v{v.version}</td><td><span className={`badge ${v.change_type}`}>{v.change_type}</span></td><td><Person email={v.actor_email} /></td><td className="muted nowrap">{when(v.created_at)}</td>
                      <td className="num"><button className={`btn small ${v.version === figVersion ? "primary" : ""}`} onClick={() => setOpenVersion(v.version)}>{v.version === figVersion ? "Viewing" : "View"}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {figVersion != null && (
                <div style={{ marginTop: 18 }}>
                  <h3 style={{ marginBottom: 10 }}>Text at v{figVersion}</h3>
                  <CommentaryText text={a.versions.find((v) => v.version === figVersion)?.text ?? ""} figures={Object.fromEntries(figs.map((f) => [f.figure_key, f]))} />
                </div>
              )}
            </Card>
            <Card title={`Figure snapshot${figVersion != null ? ` — v${figVersion}` : ""}`} sub={`${figs.length} figures`}>
              <div className="table-wrap" style={{ margin: "0 calc(var(--pad) * -1)" }}>
                <table className="data small">
                  <thead><tr><th>Figure</th><th className="num">Value</th><th>Source @ snapshot</th></tr></thead>
                  <tbody>
                    {figs.map((f) => {
                      const url = ucTableUrl(host, f.source_table);
                      return (
                        <tr key={f.figure_key}>
                          <td><div className="row-key">{f.label}</div><div className="mono muted">{f.figure_key}</div></td>
                          <td className="num">{figureValue(f.value, f.unit)}</td>
                          <td>{url ? <a href={url} target="_blank" rel="noreferrer" className="mono">{f.source_table?.split(".").pop()}</a> : f.source_table}<div className="muted">{snapshotLabel(f.delta_version, f.snapshot_ref, f.as_of_ts)}</div></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </div>
    </>
  );
}
