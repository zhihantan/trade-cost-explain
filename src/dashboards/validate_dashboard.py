"""Runs every widget query in trade_cost_explain.lvdash.json the way the dashboard runs it: dataset SQL as written (bare
Gold names, `silver.<table>`), in the dashboard's default catalog / schema, with each filter's default selection applied
(global filters on every page, page filters on their own page). Exits 1 if any query fails or returns no rows.
    src/agent/.venv/bin/python src/dashboards/validate_dashboard.py --profile fe-vm-zh-serverless
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from databricks.sdk import WorkspaceClient

SRC = Path(__file__).resolve().parent / "trade_cost_explain.lvdash.json"
AGG = re.compile(r"^(SUM|AVG|COUNT|MIN|MAX|MEASURE)\(", re.I)


def default_predicates(pages: list[dict]) -> dict:
    """{page name, or None for the global filters: {dataset: [predicate]}} from the filters' default selections."""
    out: dict = {}
    for page in pages:
        scope = None if page["pageType"] == "PAGE_TYPE_GLOBAL_FILTERS" else page["name"]
        for item in page["layout"]:
            spec = item["widget"].get("spec", {})
            values = spec.get("selection", {}).get("defaultSelection", {}).get("values", {}).get("values")
            if not spec.get("widgetType", "").startswith("filter") or not values:
                continue
            literals = ", ".join("'" + v["value"].replace("'", "\\'") + "'" for v in values)
            for wq in item["widget"]["queries"]:
                q = wq["query"]
                out.setdefault(scope, {}).setdefault(q["datasetName"], []).append(
                    f"{q['fields'][0]['expression']} IN ({literals})")
    return out


def widget_queries(dash: dict) -> list[tuple[str, str]]:
    datasets = {d["name"]: d for d in dash["datasets"]}
    defaults = default_predicates(dash["pages"])
    out = []
    for page in dash["pages"]:
        on_canvas = page["pageType"] == "PAGE_TYPE_CANVAS"
        for item in page["layout"]:
            widget = item["widget"]
            for wq in widget.get("queries", []):
                q = wq["query"]
                ds = datasets[q["datasetName"]]
                source = ds["asset_name"] if "asset_name" in ds else "(" + "".join(ds["queryLines"]) + ") t"
                where = [f["expression"] for f in q.get("filters", [])]
                if on_canvas:
                    for scope in (None, page["name"]):
                        where += defaults.get(scope, {}).get(q["datasetName"], [])
                fields = q["fields"]
                sql = "SELECT " + ", ".join(f"{f['expression']} AS `{f['name']}`" for f in fields) + f" FROM {source}"
                if where:
                    sql += " WHERE " + " AND ".join(where)
                has_agg = any(AGG.match(f["expression"]) for f in fields)
                has_dim = any(not AGG.match(f["expression"]) for f in fields)
                if not q.get("disaggregated") and has_dim and (has_agg or "asset_name" in ds):
                    sql += " GROUP BY ALL"
                out.append((f"{page['displayName']} / {widget['name']}", sql + " LIMIT 5"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--warehouse-id", default="5f36ded0f9befdd1")
    ap.add_argument("--catalog", default="cost_explain")
    ap.add_argument("--schema", default="gold")
    args = ap.parse_args()

    w = WorkspaceClient(profile=args.profile)

    def run(job: tuple[str, str]) -> tuple[str, str, int, str]:
        name, sql = job
        r = w.statement_execution.execute_statement(statement=sql, warehouse_id=args.warehouse_id, catalog=args.catalog,
                                                    schema=args.schema, wait_timeout="50s")
        while r.status.state.value in ("PENDING", "RUNNING"):
            time.sleep(2)
            r = w.statement_execution.get_statement(r.statement_id)
        rows = len(r.result.data_array or []) if r.result else 0
        return name, r.status.state.value, rows, r.status.error.message if r.status.error else ""

    jobs = widget_queries(json.loads(SRC.read_text()))
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(run, jobs))
    failed = [r for r in results if r[1] != "SUCCEEDED"]
    empty = [r for r in results if r[1] == "SUCCEEDED" and r[2] == 0]
    for name, state, _, err in failed:
        print(f"FAIL  {name}: {state} {err[:300]}")
    for name, *_ in empty:
        print(f"EMPTY {name}")
    print(f"{len(results)} widget queries: {len(failed)} failed, {len(empty)} empty")
    return 1 if failed or empty else 0


if __name__ == "__main__":
    sys.exit(main())
