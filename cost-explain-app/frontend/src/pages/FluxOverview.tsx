// Screen 1 — Flux overview: why trade costs moved. Filter bar, KPI strip, the bridge with an "explain" panel that
// drills into any effect, and the breakdown table (the chart's table view) with CSV export.
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { FluxResponse, FluxRow } from "../api/types";
import { Notice, Skeleton } from "../components/common";
import { DBar, FluxTable, visibleCols } from "../components/FluxTable";
import { Icon } from "../components/Icon";
import { Card, PageHeader } from "../components/layout";
import { Waterfall } from "../components/Waterfall";
import { pct, snapshotLabel, usd } from "../format";
import { useComparisons, useMe, useSlow } from "../hooks";

const BREAKDOWNS = [
  ["business", "Business"], ["desk", "Desk"], ["cost_category", "Cost category"], ["vendor", "Vendor"],
  ["market", "Market"], ["legal_entity", "Legal entity"], ["currency", "Currency"],
] as const;
// The three headline slices are fixed (backend gold.slice_options), so they render before any data arrives.
const HEADLINE = [["APAC", "APAC"], ["ED_EXCH_CLR", "Eq Derivs exch & clearing"], ["REST", "Rest of APAC"]] as const;
const EFFECT_KEY: Record<string, keyof FluxRow> = {
  VOLUME: "volume", MIX: "mix", RATE: "rate", FAILS: "fails", TIMING: "timing", FX: "fx", FIXED: "fixed", UNEXPLAINED: "unexplained",
};
const CLASS_SHORT: Record<string, string> = { "Good (volume-driven)": "Good", Controllable: "Controllable", "External, timing & residual": "External" };
const share = (v: number) => (Number.isFinite(v) ? `${v < 0 ? "−" : ""}${Math.abs(Math.round(v * 100))}%` : "—");
const tone = (v: number) => (v > 500 ? "up" : v < -500 ? "down" : "");

function downloadCsv(d: FluxResponse, breakdownLabel: string) {
  const cols = visibleCols(d.rows);
  const head = [breakdownLabel, "Prior", ...cols.map((c) => c.label), "Current", "Flux", "Flux %"];
  const esc = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const num = (v: number) => v.toFixed(2);
  const lines = [head.map(esc).join(",")].concat(d.rows.map((r) => [
    esc(r.key), num(r.p0), ...cols.map((c) => num(r[c.key] as number)), num(r.p1), num(r.flux), r.p0 ? (100 * r.flux / r.p0).toFixed(1) : "",
  ].join(",")));
  const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `trade-cost-flux_${d.comparison.comparison_id}_${d.slice_key.replace(":", "-")}_${d.breakdown}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function Explain({ d, selected, onSelect, breakdownLabel }: {
  d: FluxResponse; selected: string | null; onSelect: (e: string | null) => void; breakdownLabel: string;
}) {
  const effects = [...d.effects].sort((a, b) => a.order - b.order).filter((e) => e.effect !== "FIXED" || Math.abs(e.amount) >= 1);
  const max = Math.max(0, ...effects.map((e) => Math.abs(e.amount)));
  const flux = d.totals.flux;
  const sel = effects.find((e) => e.effect === selected);
  const key = sel ? EFFECT_KEY[sel.effect] : null;
  const contributors = key
    ? [...d.rows].filter((r) => Math.abs(r[key] as number) >= 500).sort((a, b) => Math.abs(b[key] as number) - Math.abs(a[key] as number)).slice(0, 5)
    : [];
  return (
    <Card title="Explain the change" sub={`${usd(flux, { signed: true })} · ${share(flux / d.totals.p0)}`}>
      <div className="class-sum" aria-label="Flux classes">
        <div><span>Good</span><b>{share(d.classes.good / flux)}</b><span>{usd(d.classes.good)}</span></div>
        <div><span>Controllable</span><b>{share(d.classes.controllable / flux)}</b><span>{usd(d.classes.controllable)}</span></div>
        <div><span>External</span><b>{share(d.classes.external / flux)}</b><span>{usd(d.classes.external, { signed: true })}</span></div>
      </div>
      <ul className="effects">
        {effects.map((e) => (
          <li key={e.effect}>
            <button className={`effect ${selected === e.effect ? "on" : ""}`} aria-pressed={selected === e.effect} onClick={() => onSelect(e.effect === selected ? null : e.effect)}>
              <span className="name">{e.label}<span className="class-tag">{CLASS_SHORT[e.flux_class] ?? e.flux_class}</span></span>
              <span className={`amt ${tone(e.amount)}`}>{usd(e.amount, { signed: true })}</span>
              <span className="meta"><DBar value={e.amount} max={max} /><span className="share">{flux ? share(e.amount / flux) : ""}</span></span>
            </button>
          </li>
        ))}
      </ul>
      <div className="explain-detail">
        {sel && key ? (
          <>
            <h3>{sel.label} · top contributors by {breakdownLabel.toLowerCase()}</h3>
            {contributors.length ? (
              <ul className="contrib">
                {contributors.map((r) => (
                  <li key={r.key}><span>{r.key}</span><b className={tone(r[key] as number)}>{usd(r[key] as number, { signed: true })}</b></li>
                ))}
              </ul>
            ) : <div className="muted small" style={{ marginTop: 8 }}>No {breakdownLabel.toLowerCase()} moves this effect by more than US$0.5K.</div>}
          </>
        ) : (
          <div className="muted small">Good = volume-driven · Controllable = mix + fails · External = rate, FX, timing and the residual. Select an effect to see what drives it by {breakdownLabel.toLowerCase()}.</div>
        )}
      </div>
    </Card>
  );
}

export function FluxOverview() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const me = useMe();
  const comps = useComparisons();
  // Start from the default comparison sent with /api/me, so the bridge loads alongside the comparison list
  // instead of after it; fall back to the list's own default if the configured one is not in it.
  const preferred = me.data?.default_comparison;
  const listDefault = comps.data?.find((c) => c.is_default)?.comparison_id ?? comps.data?.[0]?.comparison_id;
  const period = params.get("period")
    ?? (preferred && (!comps.data || comps.data.some((c) => c.comparison_id === preferred)) ? preferred : listDefault)
    ?? "";
  const slice = params.get("slice") ?? "APAC";
  const breakdown = params.get("breakdown") ?? undefined;
  const [selected, setSelected] = useState<string | null>(null);

  const slices = useQuery({ queryKey: ["slices", period], queryFn: () => api.slices(period), enabled: !!period, placeholderData: keepPreviousData });
  const flux = useQuery({ queryKey: ["flux", period, slice, breakdown], queryFn: () => api.flux(period, slice, breakdown), enabled: !!period, placeholderData: keepPreviousData });
  const slow = useSlow(!flux.data && !flux.isError, 4000);
  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    if (k !== "breakdown" && k !== "period") next.delete("breakdown");
    if (!next.get("period") && period) next.set("period", period);
    setParams(next, { replace: true });
  };
  const create = useMutation({
    mutationFn: () => api.createCommentary(period, slice),
    onSuccess: (c) => navigate(`/commentary/${c.id}?autodraft=1`),
  });

  const d = flux.data;
  const refetching = flux.isPlaceholderData ? "refetching" : "";
  const other = slices.data?.filter((s) => s.group !== "Headline") ?? [];
  const bLabel = BREAKDOWNS.find(([k]) => k === d?.breakdown)?.[1] ?? "Business";
  const compLabel = d ? `${d.comparison.p1_label} vs ${d.comparison.p0_label}` : "…";

  return (
    <>
      <PageHeader
        crumbs={[{ label: "Analysis" }]}
        title="Trade cost flux"
        sub={<>Net borne trade costs · US$ · {compLabel} · constant currency except FX</>}
        actions={me.data?.is_analyst && (
          <button className="btn primary" disabled={!d || create.isPending} onClick={() => create.mutate()}>
            <Icon name="sparkle" />{create.isPending ? "Creating…" : "Draft commentary"}
          </button>
        )}
      />
      <div className="page-body">
        <section className="card" aria-label="Filters">
          <div className="filter-bar">
          <label className="field">Comparison
            <select value={period} onChange={(e) => set("period", e.target.value)}>
              {!comps.data && period && <option value={period}>{d ? `${compLabel} (${d.comparison.comparison_type})` : "Loading…"}</option>}
              {comps.data?.map((c) => <option key={c.comparison_id} value={c.comparison_id}>{c.comparison_label ?? `${c.p1_label} vs ${c.p0_label}`} ({c.comparison_type})</option>)}
            </select>
          </label>
          <div className="field">Slice
            <div className="seg" role="group" aria-label="Headline slice">
              {HEADLINE.map(([key, label]) => (
                <button key={key} className={slice === key ? "on" : ""} aria-pressed={slice === key} onClick={() => set("slice", key)}>{label}</button>
              ))}
            </div>
          </div>
          <label className="field">Business / desk
            <select value={other.some((s) => s.key === slice) ? slice : ""} onChange={(e) => set("slice", e.target.value || "APAC")} disabled={!slices.data}>
              <option value="">{slices.data ? "All in slice" : "Loading…"}</option>
              {["Business", "Desk"].map((g) => (
                <optgroup key={g} label={g}>
                  {other.filter((s) => s.group === g).map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          </div>
          <div className="filter-foot">
            {d ? (
              <span className="provenance">
                {flux.isFetching ? <span className="spinner" aria-label="Updating" /> : <span className="live-dot" aria-hidden="true" />}
                <span>{d.source.mode === "live" ? "Live" : "Fixtures"} · <span className="mono">{d.source.table}</span></span>
                {d.source.mode === "live" && <span>· {snapshotLabel(d.source.delta_version, d.source.snapshot_ref, d.source.as_of_ts)}</span>}
              </span>
            ) : <span className="provenance"><span className="spinner" aria-hidden="true" />Loading from Unity Catalog…</span>}
            <span className="grow" />
            <span>Read with your identity — Unity Catalog row filters apply</span>
          </div>
        </section>

        {(slow || create.isError || flux.isError || d?.source.mode === "fixtures") && (
          <div className="notices">
            {slow && <Notice kind="info">Starting the SQL warehouse — the first load after it has been idle takes 15–20 seconds. Later views are cached.</Notice>}
            {create.isError && <Notice kind="err">{errorText(create.error)}</Notice>}
            {flux.isError && <Notice kind="err">Could not load the bridge: {errorText(flux.error)}</Notice>}
            {d?.source.mode === "fixtures" && <Notice kind="warn">{d.source.note ?? "Fixture data"} (local development only).</Notice>}
          </div>
        )}

        <section className={`card kpi-strip ${refetching}`} aria-label="Key figures">
          <div className="kpi"><div className="kpi-label">{d?.comparison.p0_label ?? "Prior"} · prior</div><div className="kpi-value">{d ? usd(d.totals.p0) : <Skeleton h={28} w={140} />}</div><div className="kpi-sub">{d?.slice_label ?? " "}</div></div>
          <div className="kpi"><div className="kpi-label">{d?.comparison.p1_label ?? "Current"} · current</div><div className="kpi-value">{d ? usd(d.totals.p1) : <Skeleton h={28} w={140} />}</div><div className="kpi-sub">{d ? `${usd(d.totals.p1_cc)} at constant currency` : " "}</div></div>
          <div className="kpi"><div className="kpi-label">Change</div>
            <div className="kpi-value">{d ? <><span className={d.totals.flux > 0 ? "up" : "down"}>{usd(d.totals.flux, { signed: true })}</span><span className={`delta ${d.totals.flux > 0 ? "up" : "down"}`}>{pct(d.totals.flux_pct, true)}</span></> : <Skeleton h={28} w={160} />}</div>
            <div className="kpi-sub">{d ? `vs ${d.comparison.p0_label}` : " "}</div>
          </div>
          <div className="kpi"><div className="kpi-label">Volume-driven share</div>
            <div className="kpi-value">{d ? (d.totals.flux ? pct(d.classes.good / d.totals.flux) : "—") : <Skeleton h={28} w={90} />}</div>
            <div className="kpi-sub">{d && d.totals.flux ? `${usd(d.classes.controllable)} controllable · ${pct(d.classes.controllable / d.totals.flux)} of the change` : " "}</div>
          </div>
        </section>

        <div className={`grid-main ${refetching}`}>
          <Card
            title={<>Bridge — {d?.slice_label ?? "…"}</>}
            actions={<div className="legend"><span><i className="sw-total" />Total</span><span><i className="sw-up" />Cost increase</span><span><i className="sw-down" />Cost decrease</span></div>}
            foot={d && (selected
              ? <>Selected <b>{d.effects.find((e) => e.effect === selected)?.label}</b> — highlighted in the table below. <button className="btn ghost small" onClick={() => setSelected(null)}>Clear</button></>
              : <>Click a column, or an effect on the right, to highlight it in the breakdown.</>)}
          >
            {d ? (
              <Waterfall p0={d.totals.p0} p1={d.totals.p1} p0Label={d.comparison.p0_label} p1Label={d.comparison.p1_label} effects={d.effects}
                selected={selected} onSelect={(e) => setSelected(e === selected || e === "P0" || e === "P1" ? null : e)} />
            ) : <Skeleton h={320} />}
          </Card>
          {d ? <Explain d={d} selected={selected} onSelect={setSelected} breakdownLabel={bLabel} /> : <Card title="Explain the change"><Skeleton h={320} /></Card>}
        </div>

        <section className={`card ${refetching}`}>
          <div className="card-head">
            <div className="card-title"><h2>Breakdown</h2><span className="card-sub">US$K · {d?.slice_label ?? ""}</span></div>
            <div className="btn-row">
              <div className="seg" role="group" aria-label="Breakdown">
                {BREAKDOWNS.map(([k, label]) => (
                  <button key={k} className={(d?.breakdown ?? "") === k ? "on" : ""} aria-pressed={(d?.breakdown ?? "") === k} onClick={() => set("breakdown", k)}>{label}</button>
                ))}
              </div>
              <button className="btn" disabled={!d} onClick={() => d && downloadCsv(d, bLabel)} title="Download this table as CSV"><Icon name="download" />CSV</button>
            </div>
          </div>
          <div className="card-body">
            {d ? <FluxTable rows={d.rows} breakdownLabel={bLabel} highlight={selected} /> : <Skeleton h={220} />}
          </div>
        </section>
      </div>
    </>
  );
}
