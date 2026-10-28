// Number formatting for a US$-reporting finance audience (US$K unless large).

export function usd(v: number | null | undefined, opts: { signed?: boolean; compact?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : opts.signed && v > 0 ? "+" : "";
  let body: string;
  if (a >= 995_000) body = `${(a / 1e6).toFixed(2)}M`;
  else if (a >= 1_000) {
    const k = Math.round(a / 100) / 10; // one decimal below US$100K (US$25.5K, not US$26K)
    body = a < 100_000 && !Number.isInteger(k) ? `${k.toFixed(1)}K` : `${Math.round(a / 1e3).toLocaleString("en-US")}K`;
  }
  else body = `${Math.round(a).toLocaleString("en-US")}`;
  return `${sign}${opts.compact ? "" : "US$"}${body}`;
}

export function usdK(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined) return "—";
  const k = Math.round(v / 1e3);
  if (k === 0) return "0";
  const sign = k < 0 ? "−" : signed ? "+" : "";
  return `${sign}${Math.abs(k).toLocaleString("en-US")}`;
}

export function pct(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined) return "—";
  const p = Math.abs(v) <= 1.5 ? v * 100 : v; // registry PCT values are fractions (0.24)
  const sign = p < 0 ? "−" : signed && p > 0 ? "+" : "";
  return `${sign}${Math.abs(p).toFixed(Math.abs(p) < 10 ? 1 : 0)}%`;
}

export function figureValue(value: number | null | undefined, unit: string | null | undefined): string {
  return unit === "PCT" ? pct(value) : usd(value);
}

export function when(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString("en-SG", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function statusLabel(s: string): string {
  return s.replace("_", " ");
}

export function sliceLabel(key: string): string {
  if (key === "APAC") return "APAC Global Markets";
  if (key === "ED_EXCH_CLR") return "Equity Derivatives — exchange & clearing";
  if (key === "REST") return "Rest of APAC Global Markets";
  return key.replace("BUS:", "Business ").replace("DESK:", "Desk ");
}

export function ucTableUrl(host: string, table: string | null | undefined): string | null {
  if (!host || !table) return null;
  const [c, s, t] = table.split(".");
  return c && s && t ? `${host}/explore/data/${c}/${s}/${t}` : null;
}

// Data snapshot behind a figure: Delta version for tables, pipeline update for materialized views.
export function snapshotLabel(delta_version: number | null | undefined, snapshot_ref: string | null | undefined, as_of_ts: string | null | undefined): string {
  let base: string;
  if (delta_version !== null && delta_version !== undefined) base = `Delta v${delta_version}`;
  else if (snapshot_ref && snapshot_ref.includes("update:")) base = `pipeline update ${snapshot_ref.split("update:")[1].slice(0, 8)}`;
  else base = "unversioned (fixture / seed)";
  return as_of_ts ? `${base} · ${when(as_of_ts)}` : base;
}
