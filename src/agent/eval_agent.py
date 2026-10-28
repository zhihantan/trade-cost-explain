"""Evaluate the deployed commentary agent against Gold: grounding (every chip resolves, values match the registry) and
coverage (the planted drivers are named). Logs one MLflow run with per-scenario results.

    python src/agent/eval_agent.py --endpoint ce-commentary-agent --warehouse-id <id> [--profile <profile>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time

import mlflow
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

CHIP = re.compile(r"\[\[fig:([^\]]+)\]\]")
SCENARIOS = [
    {"name": "apac_sep", "comparison_id": "MOM_2026-09", "slice": "APAC",
     "must_mention": [["Kestrel"], ["Cobalt", "Broker C"], ["market-maker", "market maker"], ["SXA", "Southern Cross"],
                      ["Tech"], ["accrual"]]},
    {"name": "ed_exch_clearing_sep", "comparison_id": "MOM_2026-09", "slice": "ED_EXCH_CLR",
     "must_mention": [["market-maker", "market maker"], ["Tech"]], "must_not_mention": ["Kestrel"]},
    {"name": "rest_sep", "comparison_id": "MOM_2026-09", "slice": "REST",
     "must_mention": [["Kestrel"], ["SXA", "Southern Cross"], ["IGX", "Indus", "uniform"]]},
    {"name": "au_cash_desk_sep", "comparison_id": "MOM_2026-09", "slice": "DESK:AUCE",
     "must_mention": [["Kestrel"], ["SXA", "Southern Cross"]]},
    {"name": "qoq_q2", "comparison_id": "QOQ_FY2026Q2", "slice": "APAC", "must_mention": [["Q2", "quarter"]]},
]


def registry(w: WorkspaceClient, warehouse: str, keys: list[str]) -> dict:
    if not keys:
        return {}
    params = [StatementParameterListItem(name=f"k{i}", value=k, type="STRING") for i, k in enumerate(keys)]
    r = w.statement_execution.execute_statement(
        warehouse_id=warehouse, parameters=params, wait_timeout="50s",
        statement="SELECT figure_key, value FROM cost_explain.gold.commentary_figures WHERE figure_key IN ("
                  + ", ".join(f":k{i}" for i in range(len(keys))) + ")")
    return {k: (float(v) if v is not None else None) for k, v in (r.result.data_array or [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="ce-commentary-agent")
    ap.add_argument("--warehouse-id", required=True)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--experiment", default="/Shared/trade-cost-explain/ce_commentary_agent")
    a = ap.parse_args()
    if a.profile:  # MLflow's artifact upload builds its own SDK config from the environment, ignoring the tracking URI
        os.environ["DATABRICKS_CONFIG_PROFILE"] = a.profile
    w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
    mlflow.set_tracking_uri("databricks" if not a.profile else f"databricks://{a.profile}")
    mlflow.set_experiment(a.experiment)
    results = []
    for sc in SCENARIOS:
        body = {"input": [{"role": "user", "content": "Draft the month-end variance commentary."}],
                "custom_inputs": {"comparison_id": sc["comparison_id"], "slice": sc["slice"], "audience": "CFO", "max_words": 220}}
        t0 = time.time()
        r = requests.post(f"{w.config.host}/serving-endpoints/{a.endpoint}/invocations", json=body,
                          headers=w.config.authenticate(), timeout=300)
        latency = time.time() - t0
        ok = r.status_code == 200
        co = (r.json().get("custom_outputs") or {}) if ok else {}
        text = co.get("commentary_markdown", "")
        chips = list(dict.fromkeys(CHIP.findall(text)))
        reg = registry(w, a.warehouse_id, chips)
        unresolved = [k for k in chips if k not in reg]
        returned = {f["figure_key"]: f.get("value") for f in co.get("figures", [])}
        mismatched = [k for k, v in returned.items() if k in reg and v is not None and reg[k] is not None and abs(v - reg[k]) > 0.5]
        coverage = [any(t.lower() in text.lower() for t in group) for group in sc.get("must_mention", [])]
        leaks = [t for t in sc.get("must_not_mention", []) if t.lower() in text.lower()]
        res = {"scenario": sc["name"], "http_ok": ok, "latency_s": round(latency, 1), "chips": len(chips),
               "unresolved_chips": unresolved, "value_mismatches": mismatched,
               "coverage": round(sum(coverage) / len(coverage), 2) if coverage else 1.0, "scope_leaks": leaks,
               "passed": ok and len(chips) >= 5 and not unresolved and not mismatched and all(coverage) and not leaks}
        results.append(res)
        print(json.dumps(res))
    with mlflow.start_run(run_name="commentary_agent_eval"):
        mlflow.log_metric("scenarios_passed", sum(r["passed"] for r in results))
        mlflow.log_metric("scenarios_total", len(results))
        mlflow.log_metric("mean_latency_s", sum(r["latency_s"] for r in results) / len(results))
        mlflow.log_metric("unresolved_chips", sum(len(r["unresolved_chips"]) for r in results))
        mlflow.log_dict({"results": results}, "eval_results.json")
    print(f"PASSED {sum(r['passed'] for r in results)}/{len(results)}")


if __name__ == "__main__":
    main()
