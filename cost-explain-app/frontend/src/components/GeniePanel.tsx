// "Ask Genie about this figure", inside the review rail. Runs as the signed-in user (genie scope): start, then poll.
import { useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import type { GenieAnswer } from "../api/types";
import { Icon } from "./Icon";

const DONE = ["COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"];

export function GeniePanel({ figureKey }: { figureKey: string | null }) {
  const [question, setQuestion] = useState("");
  const [ids, setIds] = useState<{ c: string; m: string } | null>(null);
  const [answer, setAnswer] = useState<GenieAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setQuestion(figureKey ? `Explain the drivers behind ${figureKey.split("|").slice(1).join(" ")} for ${figureKey.split("|")[0]}` : "");
    setIds(null);
    setAnswer(null);
  }, [figureKey]);

  useEffect(() => {
    if (!ids) return;
    let stop = false;
    const tick = async () => {
      try {
        const a = await api.geniePoll(ids.c, ids.m);
        if (stop) return;
        setAnswer(a);
        if (!DONE.includes(a.status)) setTimeout(tick, 2000);
      } catch (e) {
        if (!stop) setError(errorText(e));
      }
    };
    tick();
    return () => {
      stop = true;
    };
  }, [ids]);

  const ask = async () => {
    setError(null);
    setAnswer(null);
    try {
      const r = await api.genieAsk(question, figureKey ?? undefined);
      setIds({ c: r.conversation_id, m: r.message_id });
    } catch (e) {
      setError(errorText(e));
    }
  };
  const busy = !!ids && !!answer && !DONE.includes(answer.status);

  return (
    <div className="genie">
      <div className="small muted">{figureKey ? <>About <span className="mono">{figureKey}</span></> : "Ask about any figure in this commentary — select one in the Figures tab to start from it."}</div>
      <textarea value={question} onChange={(e) => setQuestion(e.target.value)} aria-label="Question for Genie" placeholder="Which brokers billed more than expected in fiscal Q2?" />
      <div className="btn-row">
        <button className="btn primary" disabled={question.trim().length < 3 || busy} onClick={ask}><Icon name="genie" />Ask Genie</button>
        {(busy || (ids && !answer)) && <span className="muted small"><span className="spinner" /> {answer?.status.toLowerCase() ?? "starting"}</span>}
      </div>
      {error && <div className="notice err">{error}</div>}
      {answer?.text && <div className="answer">{answer.text}</div>}
      {answer && answer.rows.length > 0 && (
        <div className="table-wrap" style={{ maxHeight: 240 }}>
          <table className="data small">
            <thead><tr>{answer.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{answer.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
      {answer?.sql && <details><summary>Generated SQL</summary><pre>{answer.sql}</pre></details>}
    </div>
  );
}
