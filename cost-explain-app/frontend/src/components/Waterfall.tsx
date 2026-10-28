// Bridge chart: P0 -> effects -> P1. Increases and decreases take the validated diverging pair; totals neutral.
// Thin columns with a rounded data-end, a solid hairline grid, values in text ink (never the series colour) and a
// per-column tooltip. The slice table below the chart is its table view.
import { Bar, BarChart, CartesianGrid, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Effect } from "../api/types";
import { usd } from "../format";
import { useCssVars } from "../theme";

interface Props {
  p0: number;
  p1: number;
  p0Label: string;
  p1Label: string;
  effects: Effect[];
  onSelect?: (effect: string) => void;
  selected?: string | null;
}

interface WBar {
  name: string;
  effect: string;
  base: number;
  value: number;
  amount: number;
  kind: "total" | "up" | "down";
}

const VARS = ["viz-up", "viz-down", "viz-total", "viz-grid", "viz-axis", "viz-label", "viz-tick", "viz-hover", "viz-connector", "ink"] as const;

// 4px rounded data-end: totals and increases round the top, decreases the bottom (where the running total
// lands); the other end stays square.
function columnPath(x: number, y: number, w: number, h: number, top: number, bottom: number): string {
  return `M${x},${y + top}A${top},${top} 0 0 1 ${x + top},${y}H${x + w - top}A${top},${top} 0 0 1 ${x + w},${y + top}` +
    `V${y + h - bottom}A${bottom},${bottom} 0 0 1 ${x + w - bottom},${y + h}H${x + bottom}A${bottom},${bottom} 0 0 1 ${x},${y + h - bottom}Z`;
}

const share = (v: number) => `${v < 0 ? "−" : ""}${Math.abs(Math.round(v * 100))}%`;

function Tip({ active, payload, flux }: { active?: boolean; payload?: { payload?: WBar }[]; flux: number }) {
  const b = payload?.[0]?.payload;
  if (!active || !b) return null;
  return (
    <div className="viz-tip">
      <div className="v">{b.kind === "total" ? usd(b.amount) : usd(b.amount, { signed: true })}</div>
      <div className="k">{b.name}{b.kind !== "total" && flux ? ` · ${share(b.amount / flux)} of the change` : ""}</div>
    </div>
  );
}

export function Waterfall({ p0, p1, p0Label, p1Label, effects, onSelect, selected }: Props) {
  const c = useCssVars(VARS);
  const fill = { total: c["viz-total"], up: c["viz-up"], down: c["viz-down"] };
  const bars: WBar[] = [{ name: p0Label, effect: "P0", base: 0, value: p0, amount: p0, kind: "total" }];
  const ends: number[] = [p0]; // running total after each column — the level its connector carries to the next
  let running = p0;
  for (const e of [...effects].sort((a, b) => a.order - b.order)) {
    if (e.effect === "FIXED" && Math.abs(e.amount) < 1) continue; // fixed fees shown only when they move
    const start = running;
    const end = running + e.amount;
    bars.push({ name: e.label, effect: e.effect, base: Math.min(start, end), value: Math.abs(e.amount), amount: e.amount, kind: e.amount >= 0 ? "up" : "down" });
    ends.push(end);
    running = end;
  }
  bars.push({ name: p1Label, effect: "P1", base: 0, value: p1, amount: p1, kind: "total" });

  const lows = bars.map((b) => (b.kind === "total" ? b.value : b.base));
  const highs = bars.map((b) => b.base + b.value);
  const span = Math.max(...highs) - Math.min(...lows);
  const step = span > 2e6 ? 500_000 : span > 5e5 ? 250_000 : 100_000;
  const lo = Math.max(0, Math.floor((Math.min(...lows) - span * 0.6) / step) * step);
  const hi = Math.ceil((Math.max(...highs) + span * 0.08) / step) * step;
  const ticks: number[] = [];
  for (let t = lo; t <= hi + 1; t += step) ticks.push(t);

  return (
    <div style={{ width: "100%", height: 380 }} role="img" aria-label="Cost bridge waterfall chart — every value is also in the slice table below">
      <ResponsiveContainer>
        <BarChart data={bars} margin={{ top: 24, right: 12, left: 8, bottom: 4 }} barCategoryGap="18%">
          <CartesianGrid vertical={false} stroke={c["viz-grid"]} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: c["viz-label"] }} interval={0} tickLine={false} axisLine={{ stroke: c["viz-axis"] }} />
          <YAxis domain={[lo, hi]} ticks={ticks} allowDataOverflow tickFormatter={(v: number) => usd(v, { compact: true })} tick={{ fontSize: 11, fill: c["viz-tick"] }} width={54} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: c["viz-hover"] }} content={<Tip flux={p1 - p0} />} isAnimationActive={false} />
          {/* connectors carry each running total to the next column; drawn before the bars so they sit underneath */}
          {bars.slice(0, -1).map((b, i) => (
            <ReferenceLine key={`c-${b.effect}`} segment={[{ x: b.name, y: ends[i] }, { x: bars[i + 1].name, y: ends[i] }]}
              stroke={c["viz-connector"]} strokeWidth={1} ifOverflow="visible" />
          ))}
          <Bar dataKey="base" stackId="w" fill="transparent" maxBarSize={24} isAnimationActive={false} />
          <Bar
            dataKey="value"
            stackId="w"
            maxBarSize={24}
            isAnimationActive={false}
            cursor={onSelect ? "pointer" : undefined}
            onClick={(_d: unknown, index: number) => onSelect?.(bars[index].effect)}
            shape={(p: { x?: number; y?: number; width?: number; height?: number; payload?: WBar }) => {
              const { x = 0, y = 0, width = 0, height = 0, payload: b } = p;
              if (!b || height <= 0 || width <= 0) return <g />;
              const r = Math.min(4, height / 2, width / 2);
              const dim = selected && selected !== b.effect && b.kind !== "total";
              return <path d={columnPath(x, y, width, height, b.kind === "down" ? 0 : r, b.kind === "down" ? r : 0)} fill={fill[b.kind]} fillOpacity={dim ? 0.35 : 1} />;
            }}
          >
            <LabelList
              dataKey="amount"
              content={(p: { x?: number | string; y?: number | string; width?: number | string; index?: number }) => {
                const b = bars[p.index ?? 0];
                const x = Number(p.x ?? 0) + Number(p.width ?? 0) / 2;
                const y = Number(p.y ?? 0) - 8;
                const total = b.kind === "total";
                return (
                  <text x={x} y={y} textAnchor="middle" fontSize={11} fontWeight={total ? 650 : 600} fill={total ? c.ink : c["viz-label"]}>
                    {total ? usd(b.amount) : usd(b.amount, { signed: true })}
                  </text>
                );
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
