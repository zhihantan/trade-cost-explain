"""Log, register and (optionally) deploy the commentary agent.

    python src/agent/deploy_agent.py --agent-file src/agent/commentary_agent.py --warehouse-id <id> [--deploy]
Runs locally (DATABRICKS_CONFIG_PROFILE) or as the serverless task of job ce_agent_deploy.
"""
from __future__ import annotations

import argparse
import json

import mlflow
from mlflow.models.resources import (DatabricksFunction, DatabricksServingEndpoint, DatabricksSQLWarehouse,
                                     DatabricksTable)
from mlflow.tracking import MlflowClient

TOOLS = ("get_cost_bridge", "get_top_contributors", "get_mix_detail", "get_invoice_findings", "get_fail_hotspots", "get_fee_events")
TABLES = ("commentary_figures", "cost_flux_bridge", "cost_flux_slice", "invoice_recon", "fail_cost_summary", "fee_calendar")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-file", required=True)
    ap.add_argument("--warehouse-id", required=True)
    ap.add_argument("--catalog", default="cost_explain")
    ap.add_argument("--llm-endpoint", default="databricks-claude-sonnet-5-5")
    ap.add_argument("--endpoint-name", default="ce-commentary-agent")
    ap.add_argument("--experiment", default="/Shared/trade-cost-explain/ce_commentary_agent")
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()

    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(a.experiment)
    model_name = f"{a.catalog}.gold.commentary_agent"
    config = {"llm_endpoint": a.llm_endpoint, "warehouse_id": a.warehouse_id, "catalog": a.catalog,
              "max_tool_rounds": 2, "temperature": None}
    resources = [DatabricksServingEndpoint(endpoint_name=a.llm_endpoint), DatabricksSQLWarehouse(warehouse_id=a.warehouse_id),
                 *[DatabricksFunction(function_name=f"{a.catalog}.gold.{f}") for f in TOOLS],
                 *[DatabricksTable(table_name=f"{a.catalog}.gold.{t}") for t in TABLES]]
    example = {"input": [{"role": "user", "content": "Draft the month-end variance commentary for the CFO."}],
               "custom_inputs": {"comparison_id": "MOM_2026-09", "slice": "APAC", "audience": "CFO and desk heads", "max_words": 250}}
    with mlflow.start_run(run_name="commentary_agent"):
        info = mlflow.pyfunc.log_model(name="commentary_agent", python_model=a.agent_file, model_config=config,
                                       resources=resources, input_example=example,
                                       pip_requirements=["mlflow>=3.4", "databricks-sdk>=0.60", "openai>=1.60", "httpx>=0.27"],
                                       registered_model_name=model_name)
    version = info.registered_model_version
    MlflowClient(registry_uri="databricks-uc").set_registered_model_alias(model_name, "champion", version)
    out = {"model": model_name, "version": version, "model_uri": info.model_uri}
    if a.deploy:
        from databricks import agents
        dep = agents.deploy(model_name, version, endpoint_name=a.endpoint_name, scale_to_zero=True,
                            tags={"project": "trade-cost-explain"})
        out.update(endpoint=dep.endpoint_name, query_endpoint=dep.query_endpoint)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
