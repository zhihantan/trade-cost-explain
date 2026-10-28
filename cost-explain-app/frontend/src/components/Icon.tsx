// Minimal stroke icon set (20×20 grid, 1.6px strokes, currentColor). Decorative: always paired with a text label
// or an aria-label on the control that holds it.
const PATHS: Record<string, string[]> = {
  bridge: ["M3 17.5h14", "M4 10h3v7H4z", "M8.5 5.5h3v4h-3z", "M13 5.5h3v11.5h-3z"],
  doc: ["M6 2.75h5.5L15.5 6.75V16.5a.75.75 0 0 1-.75.75H6a.75.75 0 0 1-.75-.75V3.5A.75.75 0 0 1 6 2.75z", "M11.5 2.75v4h4", "M7.75 10.5h5", "M7.75 13.5h5"],
  check: ["M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0z", "M7 10.25l2 2 4-4.5"],
  clock: ["M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0z", "M10 6.5V10l2.5 1.5"],
  sparkle: ["M10 2.75l1.65 4.6 4.6 1.65-4.6 1.65L10 15.25l-1.65-4.6-4.6-1.65 4.6-1.65z", "M15.5 13.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z"],
  palette: ["M3.5 6.5h5v5h-5z", "M8.5 3.5h5v5h-5z", "M11.5 11.5h5v5h-5z"],
  reset: ["M4.2 10a5.8 5.8 0 1 0 1.7-4.1", "M4 3.75V7h3.25"],
  external: ["M11.5 3.75h4.75V8.5", "M16.25 3.75L9.5 10.5", "M14.25 11.5v4.75H3.75V5.75H8.5"],
  chevron: ["M6.5 8l3.5 3.5L13.5 8"],
  chevronUp: ["M6.5 12l3.5-3.5 3.5 3.5"],
  download: ["M10 3.75v9", "M6.5 9.5l3.5 3.5 3.5-3.5", "M4 16.25h12"],
  edit: ["M4 16l1-3.75 7.75-7.75 2.75 2.75-7.75 7.75z", "M11.25 6l2.75 2.75"],
  genie: ["M3.75 4.75h12.5v8.5H9l-3.25 3v-3h-2z", "M7 8.5h6", "M7 10.75h3.5"],
  lineage: ["M7 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0z", "M17 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0z", "M17 15a2 2 0 1 1-4 0 2 2 0 0 1 4 0z", "M7 10h2.5l3.5-4.25", "M9.5 10l3.5 4.25"],
  info: ["M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0z", "M10 9.25v4.5", "M10 6.6v.05"],
  alert: ["M10 3.5l7 12.75H3z", "M10 8.75v3.5", "M10 14.4v.05"],
  database: ["M16 5c0 1.24-2.69 2.25-6 2.25S4 6.24 4 5s2.69-2.25 6-2.25S16 3.76 16 5z", "M4 5v10c0 1.24 2.69 2.25 6 2.25s6-1.01 6-2.25V5", "M4 10c0 1.24 2.69 2.25 6 2.25s6-1.01 6-2.25"],
  close: ["M5.5 5.5l9 9", "M14.5 5.5l-9 9"],
  tick: ["M5 10.5l3.25 3.25L15 6.75"],
  arrow: ["M4 10h12", "M11.5 5.5L16 10l-4.5 4.5"],
  inbox: ["M3.5 11.5l2-7h9l2 7v4.75h-13z", "M3.5 11.5h4l1 2h3l1-2h4"],
};

export function Icon({ name, size = 16, className = "" }: { name: keyof typeof PATHS | string; size?: number; className?: string }) {
  const d = PATHS[name] ?? PATHS.info;
  return (
    <svg className={`ico ${className}`} width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      {d.map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
}
