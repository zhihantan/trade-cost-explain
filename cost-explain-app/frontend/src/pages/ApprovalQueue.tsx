// Screen 3 — Approval queue: items awaiting review, each with an excerpt; approve or reject with a reason.
// Four-eyes is enforced server-side too; the reason a decision is blocked is shown on the card.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { Commentary } from "../api/types";
import { Notice, ReasonModal, Skeleton, StatusBadge } from "../components/common";
import { Icon } from "../components/Icon";
import { EmptyState, PageHeader, Person } from "../components/layout";
import { sliceLabel, when } from "../format";
import { useComparisonLabel, useMe } from "../hooks";

// Plain-text excerpt: a leading bold heading line (it repeats the card title), figure chips and bold markers removed.
function excerpt(text: string | null): string {
  return (text ?? "").replace(/^\s*\*\*[^*\n]+\*\*\s*\n/, "").replace(/\[\[fig:[^\]]+\]\]/g, "").replace(/\*\*/g, "")
    .replace(/^\s*[-*]\s+/gm, "").replace(/\s+/g, " ").replace(/\s+([,.;)])/g, "$1").trim();
}

export function ApprovalQueue() {
  const qc = useQueryClient();
  const me = useMe();
  const label = useComparisonLabel();
  const queue = useQuery({ queryKey: ["approvals"], queryFn: api.approvals, refetchInterval: 15_000 });
  const [pending, setPending] = useState<{ c: Commentary; kind: "approve" | "reject" } | null>(null);
  const [msg, setMsg] = useState<{ kind: "info" | "err"; text: string } | null>(null);
  const decide = useMutation({
    mutationFn: ({ c, kind, note }: { c: Commentary; kind: "approve" | "reject"; note: string }) =>
      kind === "approve" ? api.approve(c.id, c.version, note || undefined) : api.reject(c.id, c.version, note),
    onSuccess: (c) => { setMsg({ kind: "info", text: `“${c.title}” ${c.status}.` }); setPending(null); qc.invalidateQueries(); },
    onError: (e) => { setMsg({ kind: "err", text: errorText(e) }); setPending(null); },
  });
  const blocker = (c: Commentary): string | null => {
    if (!me.data?.is_approver) return "Requires the approver role";
    if (c.author_email === me.data.email) return "Four-eyes: you authored this item";
    if (c.last_edited_by === me.data.email) return "Four-eyes: you edited the current version";
    return null;
  };
  const items = queue.data ?? [];
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Close" }]}
        title="Approvals"
        badge={items.length > 0 ? <span className="badge in_review">{items.length} awaiting</span> : undefined}
        sub="Commentary awaiting sign-off. The author, or the last editor, cannot approve their own item."
      />
      <div className="page-body">
        {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
        {queue.isError && <Notice kind="err">{errorText(queue.error)}</Notice>}
        {queue.isLoading ? <Skeleton h={160} /> : items.length === 0 ? (
          <section className="card"><EmptyState icon="check" title="Nothing awaiting approval">Submitted commentary appears here for sign-off.</EmptyState></section>
        ) : (
          <div className="queue">
            {items.map((c) => {
              const b = blocker(c);
              return (
                <article key={c.id} className="card queue-card">
                  <div style={{ minWidth: 0 }}>
                    <div className="top"><StatusBadge status={c.status} /><span>{label(c.period)}</span><span>·</span><span>{sliceLabel(c.slice_key)}</span><span>·</span><span>v{c.version}</span></div>
                    <h2><Link to={`/commentary/${c.id}`}>{c.title}</Link></h2>
                    <p className="excerpt">{excerpt(c.edited_text)}</p>
                    <div className="meta"><Person email={c.author_email} /><span>· submitted {when(c.submitted_at)}</span></div>
                  </div>
                  <div className="actions">
                    <Link className="btn" to={`/commentary/${c.id}`}><Icon name="doc" />Review</Link>
                    <div className="btn-row">
                      <button className="btn ok" disabled={!!b || decide.isPending} title={b ?? undefined} onClick={() => setPending({ c, kind: "approve" })}><Icon name="check" />Approve</button>
                      <button className="btn danger" disabled={!!b || decide.isPending} title={b ?? undefined} onClick={() => setPending({ c, kind: "reject" })}>Reject</button>
                    </div>
                    {b && <div className="blocker">{b}</div>}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
      {pending && (
        <ReasonModal title={`${pending.kind === "approve" ? "Approve" : "Reject"} “${pending.c.title}”`} cta={pending.kind === "approve" ? "Approve" : "Reject"}
          required={pending.kind === "reject"} onClose={() => setPending(null)} onSubmit={(note) => decide.mutate({ ...pending, note })} />
      )}
    </>
  );
}
