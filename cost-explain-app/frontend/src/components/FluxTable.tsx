// Slice table rendered from the same payload as the waterfall, so the chart always ties to the table.
// It is also the chart's table view: every value the chart shows is readable here.
import type { FluxRow } from "../api/types";
import { pct, usdK } from "../format";

// Scene-2 narrative order, same as the waterfall (gold.cost_flux_effects.effect_order).
export const COLS: { key: keyof FluxRow; label: string }[] = [
  { key: "volume", label: "Volume" },
  { key: "mix", label: "Mix" },
  { key: "rate", label: "Rate" },
  { key: "fails", label: "Fails" },
  { key: "timing", label: "Timing" },
  { key: "fx", label: "FX" },
  { key: "fixed", label: "Fixed" },
  { key: "unexplained", label: "Unexpl." },
];

export function visibleCols(rows: FluxRow[]) {
  return COLS.filter((c) => c.key !== "fixed" || rows.some((r) => Math.abs(r.fixed) >= 1));
}

// Diverging bar around a centre line: positive grows right in the increase colour, negative left in the decrease
// colour; half the track is the largest absolute value in view.
export function DBar({ value, max }: { value: number; max: number }) {
  const w = max ? Math.min(50, (Math.abs(value) / max) * 50) : 0;
  return <span className="dbar" aria-hidden="true"><i className={value >= 0 ? "pos" : "neg"} style={{ width: `${w}%` }} /></span>;
}

export function FluxTable({ rows, breakdownLabel, highlight }: { rows: FluxRow[]; breakdownLabel: string; highlight?: string | null }) {
  const cols = visibleCols(rows);
  const total = (k: keyof FluxRow) => rows.reduce((s, r) => s + (r[k] as number), 0);
  const cls = (v: number) => (v > 50 ? "up" : v < -50 ? "down" : "");
  const hl = highlight?.toLowerCase();
  const maxFlux = Math.max(0, ...rows.map((r) => Math.abs(r.flux)));
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th className="sticky-col">{breakdownLabel}</th>
            <th className="num">Prior</th>
            {cols.map((c) => <th key={c.key} className={`num ${hl === c.key ? "hl" : ""}`}>{c.label}</th>)}
            <th className="num">Current</th>
            <th className="num">Flux</th>
            <th className="num">Flux %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="sticky-col row-key">{r.key}</td>
              <td className="num">{usdK(r.p0)}</td>
              {cols.map((c) => (
                <td key={c.key} className={`num ${cls(r[c.key] as number)} ${hl === c.key ? "hl" : ""}`}>{usdK(r[c.key] as number, true)}</td>
              ))}
              <td className="num">{usdK(r.p1)}</td>
              <td className="num"><span className="flux-cell"><DBar value={r.flux} max={maxFlux} /><b className={cls(r.flux)}>{usdK(r.flux, true)}</b></span></td>
              <td className="num muted">{r.p0 ? pct(r.flux / r.p0, true) : "—"}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td className="sticky-col">Total (US$K)</td>
            <td className="num">{usdK(total("p0"))}</td>
            {cols.map((c) => <td key={c.key} className={`num ${hl === c.key ? "hl" : ""}`}>{usdK(total(c.key), true)}</td>)}
            <td className="num">{usdK(total("p1"))}</td>
            <td className="num">{usdK(total("flux"), true)}</td>
            <td className="num">{total("p0") ? pct(total("flux") / total("p0"), true) : "—"}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
