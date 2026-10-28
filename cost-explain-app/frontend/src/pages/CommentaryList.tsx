// Commentary register: every item with status, version and ownership. Status tabs carry live counts.
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Notice, Skeleton, StatusBadge } from "../components/common";
import { Icon } from "../components/Icon";
import { EmptyState, PageHeader, Person, Tabs } from "../components/layout";
import { sliceLabel, when } from "../format";
import { useComparisonLabel } from "../hooks";

const FILTERS = [["", "All"], ["draft", "Draft"], ["in_review", "In review"], ["approved", "Approved"], ["rejected", "Rejected"]] as const;
type Filter = (typeof FILTERS)[number][0];

export function CommentaryList() {
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") ?? "") as Filter;
  const label = useComparisonLabel();
  const list = useQuery({ queryKey: ["commentary", ""], queryFn: () => api.listCommentary() });
  const items = list.data ?? [];
  const shown = status ? items.filter((c) => c.status === status) : items;
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Close" }]}
        title="Commentary"
        sub="Variance commentary — agent-drafted, analyst-edited, approver-signed."
        actions={<Link className="btn" to="/"><Icon name="sparkle" />New draft from the Flux overview</Link>}
      />
      <div className="page-body">
        {list.isError && <Notice kind="err">{errorText(list.error)}</Notice>}
        <section className="card">
          <Tabs
            tabs={FILTERS.map(([k, label]) => ({ key: k, label, count: k ? items.filter((c) => c.status === k).length : items.length }))}
            value={status}
            onChange={(k) => setParams(k ? { status: k } : {})}
          />
          {list.isLoading ? <div className="card-body"><Skeleton h={160} /></div> : shown.length === 0 ? (
            <EmptyState icon="doc" title={status ? `No ${status.replace("_", " ")} commentary` : "No commentary yet"}>Start a draft from the Flux overview.</EmptyState>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Status</th><th>Commentary</th><th>Slice</th><th className="num">Version</th><th>Author</th><th>Last change</th></tr></thead>
                <tbody>
                  {shown.map((c) => (
                    <tr key={c.id}>
                      <td><StatusBadge status={c.status} /></td>
                      <td className="title-cell"><Link to={`/commentary/${c.id}`}>{c.title}</Link><div className="sub">{label(c.period)}</div></td>
                      <td>{sliceLabel(c.slice_key)}</td>
                      <td className="num">v{c.version}</td>
                      <td><Person email={c.author_email} /></td>
                      <td className="muted nowrap">{when(c.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
