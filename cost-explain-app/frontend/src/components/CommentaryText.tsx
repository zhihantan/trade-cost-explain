// Markdown-lite renderer (paragraphs, bullets, **bold**) with figure chips for [[fig:<figure_key>]].
// Rendered as React elements — never as HTML — so commentary text cannot inject markup.
import type { ReactNode } from "react";
import type { CommentaryFigure } from "../api/types";
import { figureValue, snapshotLabel } from "../format";

export const CHIP_RE = /\[\[fig:([^\]\[\n]{3,200})\]\]/g;

export function chipKeys(text: string): string[] {
  return Array.from(new Set(Array.from(text.matchAll(CHIP_RE), (m) => m[1])));
}

interface Props {
  text: string;
  figures: Record<string, CommentaryFigure>;
  active?: string | null;
  onChip?: (key: string) => void;
}

function inline(text: string, props: Props, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\[\[fig:[^\]\[\n]{3,200}\]\])/g;
  let last = 0;
  let i = 0;
  for (const m of text.matchAll(re)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push(text.slice(last, idx));
    const tok = m[0];
    if (tok.startsWith("**")) {
      out.push(<strong key={`${keyBase}-b${i}`}>{inline(tok.slice(2, -2), props, `${keyBase}-b${i}`)}</strong>);
    } else {
      const key = tok.slice(6, -2);
      const f = props.figures[key];
      out.push(
        <button
          type="button"
          key={`${keyBase}-c${i}`}
          className={`chip ${f ? "" : "missing"} ${props.active === key ? "active" : ""}`}
          title={f ? `${f.label ?? key}: ${figureValue(f.value, f.unit)} — ${f.source_table} (${snapshotLabel(f.delta_version, f.snapshot_ref, f.as_of_ts)})` : `Not in figure snapshot: ${key}`}
          onClick={() => props.onChip?.(key)}
          aria-label={`Figure ${key}`}
        >
          <span className="chip-mark" aria-hidden="true">◆</span>{f ? figureValue(f.value, f.unit) : "?"}
        </button>,
      );
    }
    last = idx + tok.length;
    i += 1;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function CommentaryText(props: Props) {
  const blocks = props.text.replace(/\r/g, "").split(/\n\s*\n/);
  return (
    <div className="commentary">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim().length > 0);
        if (lines.length && lines.every((l) => /^\s*[-*]\s+/.test(l))) {
          return (
            <ul key={bi}>
              {lines.map((l, li) => (
                <li key={li}>{inline(l.replace(/^\s*[-*]\s+/, ""), props, `${bi}-${li}`)}</li>
              ))}
            </ul>
          );
        }
        return <p key={bi}>{lines.map((l, li) => <span key={li}>{li > 0 && <br />}{inline(l, props, `${bi}-${li}`)}</span>)}</p>;
      })}
    </div>
  );
}
