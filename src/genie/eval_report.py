"""Summarise a Genie benchmark eval run: per-question assessment, generated SQL and result-shape notes."""
import json
import sys
import time

from databricks.sdk import WorkspaceClient

sys.path.insert(0, "src/genie")
from build_space import hid  # noqa: E402
from queries import BENCHMARKS  # noqa: E402

SPACE = "01f1cda9f4a9153882ea4c4ecda34bc3"
w = WorkspaceClient(profile="fe-vm-zh-serverless")


def do(path, query=None):
    for a in range(4):
        try:
            return w.api_client.do("GET", path, query=query)
        except Exception as e:
            if "IP ACL" in str(e) and a < 3:
                time.sleep(30); continue
            raise


def report(run_id: str, verbose: bool = True) -> list[dict]:
    id2key = {hid("benchmark:" + k): k for k in BENCHMARKS}
    res = do(f"/api/2.0/genie/spaces/{SPACE}/eval-runs/{run_id}/results", {"page_size": 50})
    rows = []
    for r in res.get("eval_results", []):
        d = do(f"/api/2.0/genie/spaces/{SPACE}/eval-runs/{run_id}/results/{r['result_id']}")
        key = id2key.get(r["benchmark_question_id"], "?")
        rows.append({"key": key, "question": r.get("question"), "detail": d})
    rows.sort(key=lambda x: x["key"])
    for x in rows:
        d = x["detail"]
        assess = d.get("assessment") or d.get("evaluation_result") or {}
        print(f"\n### {x['key']} {x['question']}")
        keys = [k for k in d.keys() if k not in ("question", "benchmark_answer")]
        if verbose:
            print(json.dumps({k: d[k] for k in keys}, ensure_ascii=False)[:2500])
    return rows


if __name__ == "__main__":
    report(sys.argv[1])
