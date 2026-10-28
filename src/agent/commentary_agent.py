"""Month-end variance commentary agent for the Trade Cost Explain demo (MLflow ResponsesAgent, model-agnostic).

Flow per request (custom_inputs: comparison_id, slice, audience, max_words):
  1. ground   — fetch the governed facts in parallel through Unity Catalog SQL functions over Gold
                (bridge for the slice, headline split, top mix / rate / volume contributors, fail hotspots,
                prior-month invoice findings, fee events). Every row carries a figure_key.
  2. draft    — one LLM call writes the commentary, citing each number as [[fig:<figure_key>]]; the model may call the
                same tools for further drill-down (bounded rounds).
  3. verify   — every chip must be a figure the tools returned; one repair round, then unknown chips are dropped.
  4. resolve  — cited figures are resolved against gold.commentary_figures (value, source table, filter) and
                returned in custom_outputs so the review app can store them with the Delta version.
The bridge itself is precomputed and deterministic in Gold; the agent never recomputes it.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem, StatementState
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

DEFAULT_CONFIG = {
    "llm_endpoint": "databricks-claude-sonnet-5-5",
    "warehouse_id": "5f36ded0f9befdd1",
    "catalog": "cost_explain",
    "max_tool_rounds": 2,
    "temperature": None,   # some models (e.g. Claude Sonnet 5.5 on FMAPI) reject sampling parameters; set only if supported
}
CHIP = re.compile(r"\[\[fig:([^\]]+)\]\]")
BARE_CHIP = re.compile(r"\[\[(?!fig:)([^\]]+)\]\]")


def text_of(content) -> str:
    """Model content can be a string or a list of blocks (e.g. reasoning + text); keep only the text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for p in content:
        d = p if isinstance(p, dict) else (p.model_dump() if hasattr(p, "model_dump") else {})
        if d.get("type") in ("text", "output_text"):
            parts.append(d.get("text") or "")
    return "".join(parts)

TOOLS = [
    {"type": "function", "function": {
        "name": "get_cost_bridge",
        "description": "Cost bridge figures for a comparison and scope: prior / current cost, change, volume, mix, rate, FX, "
                       "fails, fixed, timing, unexplained, good / controllable flux. Scope: APAC, ED_EXCH_CLR, REST, BUS:<code>, "
                       "DESK:<code>, CAT:<category>, VENDOR:<id>, MKT:<market>.",
        "parameters": {"type": "object", "properties": {
            "comparison": {"type": "string", "description": "e.g. MOM_2026-09"},
            "scope": {"type": "string", "description": "e.g. APAC, ED_EXCH_CLR, DESK:HKED, VENDOR:SXA"}},
            "required": ["comparison", "scope"]}}},
    {"type": "function", "function": {
        "name": "get_top_contributors",
        "description": "Largest contributors to one effect (VOLUME, MIX, RATE, FX, FAILS, TIMING, FIXED, UNEXPLAINED, FLUX) grouped by "
                       "DESK, BUS, VENDOR, MKT, CAT, PF (desk × product family, volume / mix / rate only), or slice-split DSL:<ED_EXCH_CLR|REST> (desk) and PSL:<ED_EXCH_CLR|REST> (desk × product family).",
        "parameters": {"type": "object", "properties": {
            "comparison": {"type": "string"}, "effect": {"type": "string"}, "group_by": {"type": "string"},
            "top_n": {"type": "integer"}}, "required": ["comparison", "effect", "group_by", "top_n"]}}},
    {"type": "function", "function": {
        "name": "get_mix_detail",
        "description": "Mechanism behind the largest mix effects: which venue · capacity the flow shifted towards and away from, per desk × product family, within a slice (ALL, ED_EXCH_CLR or REST).",
        "parameters": {"type": "object", "properties": {"comparison": {"type": "string"}, "slice_scope": {"type": "string"},
                       "top_n": {"type": "integer"}}, "required": ["comparison", "slice_scope", "top_n"]}}},
    {"type": "function", "function": {
        "name": "get_fail_hotspots",
        "description": "Largest settlement-fail cost hotspots for a month (YYYY-MM) by desk × counterparty × root cause.",
        "parameters": {"type": "object", "properties": {"fail_month": {"type": "string"}, "top_n": {"type": "integer"}},
                       "required": ["fail_month", "top_n"]}}},
    {"type": "function", "function": {
        "name": "get_invoice_findings",
        "description": "Invoice-vs-expected findings for a service month (YYYY-MM). Invoices lag one month: at the September close use 2026-08.",
        "parameters": {"type": "object", "properties": {"service_month": {"type": "string"}}, "required": ["service_month"]}}},
    {"type": "function", "function": {
        "name": "get_fee_events",
        "description": "Fee schedule events (discounts ending, rate and regime changes) with estimated monthly cost impact at current volumes.",
        "parameters": {"type": "object", "properties": {}}}},
]
INT_PARAMS = {"top_n"}
DESK_BUSINESS = {"HKCE": "CEQ", "CNSC": "CEQ", "KTEQ": "CEQ", "AUCE": "CEQ", "INEQ": "CEQ", "HKED": "EQD", "D1PR": "PDO",
                 "FLCR": "CRD", "SGFX": "FXE", "SGRT": "RTS", "SGEM": "FXE", "AURF": "RTS"}

SYSTEM_PROMPT = """You are the business-finance (FP&A) analyst for Meridian Group, APAC Global Markets
(US GAAP, fiscal year April–March, US$ reporting). You draft month-end variance commentary on trade costs (the
"Commissions and floor brokerage" line) for the {audience}.

Rules — follow all of them:
1. Use ONLY figures returned by the tools. Never invent, estimate, add up or recompute numbers. Round for display only:
   US$ amounts as US$K with no decimals (or US$M with one decimal above US$1M); percentages as whole numbers.
2. Immediately after every number you state, cite it with a chip [[fig:<figure_key>]] using the exact figure_key from
   the tool results — one chip per number, always with the "fig:" prefix, e.g. "up US$1.2M [[fig:MOM_2026-09|APAC|FLUX]]".
   Do not cite a figure_key that the tools did not return. Counts and dates without a figure key are fine without a chip.
3. Structure, in this order:
   - Headline: prior → current cost, change and % change.
   - Volume ("good" flux, driven by activity — say what drove activity if the data shows it).
   - Controllable flux: mix (name the desk / product / venue or capacity behind it — e.g. routing to a higher-fee venue,
     booking in a higher-fee capacity) and settlement fails (name the counterparty, desk and root cause).
   - Rate (the fee schedule change behind it), timing / accrual (e.g. prior-month over-accrual reversed), FX
     (local currencies vs the US$), and the unexplained residual against its threshold.
   - Actions: billing recovery from invoice findings (they relate to the PRIOR month's invoices and sit outside the
     bridge), Operations fixes for fail hotspots, routing / booking reviews, and upcoming fee events.
   Name every bridge effect that rounds to US$1K or more, with its chip — small or negative ones such as timing /
   accrual and FX included. To stay near the word budget, shorten explanations; never drop an effect.
4. Explain mechanisms in plain business English. About {max_words} words. Short bold lead-ins are fine; at most six
   bullets; no tables.
5. Stay inside the requested scope: when the scope is a slice, desk or business, do not quote division-wide or other-scope
   figures as if they belonged to it.
6. Never mention any real company or regulator, and add no disclaimers about the data.
"""


class CommentaryAgent(ResponsesAgent):
    def __init__(self, config: dict | None = None):
        cfg = dict(DEFAULT_CONFIG)
        try:
            cfg.update(mlflow.models.ModelConfig(development_config=DEFAULT_CONFIG).to_dict())
        except Exception:  # noqa: BLE001 — running outside MLflow model serving
            pass
        cfg.update(config or {})
        self.cfg = cfg
        self._w = None
        self._llm = None

    # lazily created so the model can be logged without credentials
    @property
    def w(self) -> WorkspaceClient:
        if self._w is None:
            self._w = WorkspaceClient()
        return self._w

    @property
    def llm(self):
        if self._llm is None:
            self._llm = self.w.serving_endpoints.get_open_ai_client()
        return self._llm

    def _sampling(self) -> dict:
        return {} if self.cfg.get("temperature") is None else {"temperature": self.cfg["temperature"]}

    # ── tools ──────────────────────────────────────────────────────────────────────────────────────
    @mlflow.trace(span_type="TOOL")
    def call_tool(self, name: str, args: dict) -> list[dict]:
        fn = f"{self.cfg['catalog']}.gold.{name}"
        params = [StatementParameterListItem(name=k, value=str(v), type="INT" if k in INT_PARAMS else "STRING")
                  for k, v in args.items()]
        markers = ", ".join(f":{k}" for k in args)
        resp = self.w.statement_execution.execute_statement(
            warehouse_id=self.cfg["warehouse_id"], statement=f"SELECT * FROM {fn}({markers})",
            parameters=params or None, wait_timeout="50s")
        while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(1)
            resp = self.w.statement_execution.get_statement(resp.statement_id)
        if resp.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"{name} failed: {resp.status.error.message if resp.status.error else resp.status.state}")
        cols = [c.name for c in resp.manifest.schema.columns]
        rows = []
        for r in (resp.result.data_array or []) if resp.result else []:
            row = dict(zip(cols, r))
            for k in ("value", "amount_usd", "variance_usd", "net_cost_usd", "monthly_impact_usd", "mix_usd"):
                if row.get(k) is not None:
                    row[k] = round(float(row[k]), 2)
            rows.append(row)
        return rows

    def resolve_figures(self, keys: list[str]) -> list[dict]:
        if not keys:
            return []
        params = [StatementParameterListItem(name=f"k{i}", value=k, type="STRING") for i, k in enumerate(keys)]
        stmt = (f"SELECT figure_key, metric_label, scope_label, value, unit, source_table, filter_expr "
                f"FROM {self.cfg['catalog']}.gold.commentary_figures WHERE figure_key IN ({', '.join(':k%d' % i for i in range(len(keys)))})")
        resp = self.w.statement_execution.execute_statement(warehouse_id=self.cfg["warehouse_id"], statement=stmt,
                                                            parameters=params, wait_timeout="50s")
        cols = [c.name for c in resp.manifest.schema.columns]
        by_key = {r[0]: dict(zip(cols, r)) for r in (resp.result.data_array or [])}
        out = []
        for k in keys:
            r = by_key.get(k)
            if r:
                out.append({"figure_key": k, "label": f"{r['metric_label']} — {r['scope_label']}",
                            "value": float(r["value"]) if r["value"] is not None else None, "unit": r["unit"],
                            "source_table": r["source_table"], "filter": r["filter_expr"]})
        return out

    # ── grounding ──────────────────────────────────────────────────────────────────────────────────
    def ground(self, comparison: str, scope: str) -> dict[str, Any]:
        """Scope-safe facts: slice scopes use slice-split figures (DSL / PSL); desk and business scopes are post-filtered."""
        month = comparison.split("_", 1)[1] if comparison.startswith("MOM_") else None
        prior = None
        if month:
            y, m = map(int, month.split("-"))
            prior = f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"
        top = lambda effect, by, n: ("get_top_contributors", {"comparison": comparison, "effect": effect, "group_by": by, "top_n": n})
        jobs = {"bridge": ("get_cost_bridge", {"comparison": comparison, "scope": scope}), "fee_events": ("get_fee_events", {})}
        if scope in ("ED_EXCH_CLR", "REST"):
            jobs.update({
                "top_volume_by_desk": top("VOLUME", f"DSL:{scope}", 4),
                "top_mix_by_desk_product": top("MIX", f"PSL:{scope}", 4),
                "top_rate_by_desk_product": top("RATE", f"PSL:{scope}", 3),
                "top_timing_by_desk": top("TIMING", f"DSL:{scope}", 3),
                "top_fx_by_desk": top("FX", f"DSL:{scope}", 3),
                "mix_mechanism": ("get_mix_detail", {"comparison": comparison, "slice_scope": scope, "top_n": 3}),
            })
        else:
            jobs.update({
                "top_mix_by_desk_product": top("MIX", "PF", 6),
                "top_rate_by_desk_product": top("RATE", "PF", 4),
                "top_timing_by_desk": top("TIMING", "DESK", 6),
                "mix_mechanism": ("get_mix_detail", {"comparison": comparison, "slice_scope": "ALL", "top_n": 6}),
            })
            if scope == "APAC":
                jobs["top_volume_by_business"] = top("VOLUME", "BUS", 4)
                jobs["top_fx_by_market"] = top("FX", "MKT", 3)
                jobs["headline_split_ed"] = ("get_cost_bridge", {"comparison": comparison, "scope": "ED_EXCH_CLR"})
        if month and scope != "ED_EXCH_CLR":   # listed derivatives clear at a CCP: no settlement fails in that slice
            jobs["fail_hotspots"] = ("get_fail_hotspots", {"fail_month": month, "top_n": 3})
        if month and scope in ("APAC", "REST") or (month and scope.startswith("BUS:")):
            jobs["prior_month_invoice_findings"] = ("get_invoice_findings", {"service_month": prior})
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {k: ex.submit(self.call_tool, n, a) for k, (n, a) in jobs.items()}
            facts = {k: f.result() for k, f in futs.items()}
        # desk / business scopes: keep only contributors that belong to the scope
        desks = None
        if scope.startswith("DESK:"):
            desks = {scope.split(":", 1)[1]}
        elif scope.startswith("BUS:"):
            desks = {d for d, b in DESK_BUSINESS.items() if b == scope.split(":", 1)[1]}
        if desks is not None:
            for k, rows in facts.items():
                if k.startswith("top_") or k == "mix_mechanism" or k == "fail_hotspots":
                    facts[k] = [r for r in rows if (r.get("desk") or str(r.get("member", "")).split(":")[0]) in desks]
        return facts

    # ── ResponsesAgent ─────────────────────────────────────────────────────────────────────────────
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        ci = dict(request.custom_inputs or {})
        comparison = ci.get("comparison_id") or "MOM_2026-09"
        scope = ci.get("slice") or "APAC"
        audience = ci.get("audience") or "CFO and desk heads"
        max_words = int(ci.get("max_words") or 250)
        ask = ""
        for item in request.input:
            d = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            if d.get("role") == "user":
                c = d.get("content")
                ask = c if isinstance(c, str) else " ".join(p.get("text", "") for p in c if isinstance(p, dict))

        facts = self.ground(comparison, scope)
        known = {r["figure_key"] for rows in facts.values() for r in rows if r.get("figure_key")}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(audience=audience, max_words=max_words)},
            {"role": "user", "content": (
                f"{ask or 'Draft the month-end variance commentary.'}\n\nComparison: {comparison}. Scope: {scope}.\n"
                f"Grounding facts from the governed Gold layer (JSON):\n{json.dumps(facts, default=str)}")},
        ]
        text, rounds = "", 0
        while True:
            kwargs = {"tools": TOOLS} if rounds < self.cfg["max_tool_rounds"] else {}
            resp = self.llm.chat.completions.create(model=self.cfg["llm_endpoint"], messages=messages, max_tokens=6000,
                                                    **kwargs, **self._sampling())
            msg = resp.choices[0].message
            if getattr(msg, "tool_calls", None) and rounds < self.cfg["max_tool_rounds"]:
                rounds += 1
                messages.append({"role": "assistant", "content": msg.content if msg.content is not None else "",
                                 "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
                for tc in msg.tool_calls:
                    try:
                        rows = self.call_tool(tc.function.name, json.loads(tc.function.arguments or "{}"))
                        known |= {r["figure_key"] for r in rows if r.get("figure_key")}
                        content = json.dumps(rows, default=str)
                    except Exception as e:  # noqa: BLE001 — surface tool errors to the model
                        content = json.dumps({"error": str(e)})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
                continue
            text = text_of(msg.content)
            break

        text = BARE_CHIP.sub(lambda m: f"[[fig:{m.group(1)}]]" if m.group(1) in known else m.group(0), text)
        unknown = [k for k in CHIP.findall(text) if k not in known]
        if unknown:  # one repair round, then drop anything still unknown
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": "These chips are not figures returned by the tools: "
                          + ", ".join(sorted(set(unknown))) + ". Rewrite the commentary citing only these figure keys: "
                          + ", ".join(sorted(known)) + ". Keep everything else the same."}]
            text = text_of(self.llm.chat.completions.create(model=self.cfg["llm_endpoint"], messages=messages, max_tokens=6000,
                                                            **self._sampling()).choices[0].message.content) or text
            text = CHIP.sub(lambda m: m.group(0) if m.group(1) in known else "", text)

        cited = list(dict.fromkeys(CHIP.findall(text)))
        figures = self.resolve_figures(cited)
        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=text, id=f"msg_{uuid.uuid4().hex[:12]}")],
            custom_outputs={"commentary_markdown": text, "figures": figures, "model": self.cfg["llm_endpoint"],
                            "comparison_id": comparison, "slice": scope, "tool_rounds": rounds,
                            "grounding_sources": sorted(facts.keys())},
        )


mlflow.openai.autolog()
AGENT = CommentaryAgent()
mlflow.models.set_model(AGENT)
