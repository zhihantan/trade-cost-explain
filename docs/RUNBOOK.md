# Runbook — before, during and after the demo

Profile `fe-vm-zh-serverless` · catalog `cost_explain` · warehouse `cost-explain-wh` (`5f36ded0f9befdd1`).

## T−60 min: rebuild (only if anything changed)
```bash
databricks bundle deploy -t dev --profile fe-vm-zh-serverless
databricks bundle run ce_build -t dev --profile fe-vm-zh-serverless          # ≈25 min; ends with the tie-out gate
```
Check: `SELECT * FROM cost_explain.gold.tie_out_results WHERE NOT passed` returns no rows.

Changed an agent tool function (`src/agent/tools.sql`)? Ship it only with `databricks bundle run ce_agent_deploy` (≈15 min),
never by running `tools.sql` on its own: the endpoint's credentials are bound to the function objects that existed at
deploy time, so a replaced function fails inside the agent with `INSUFFICIENT_PERMISSIONS` even though `account users`
still holds EXECUTE. Then re-run `src/agent/eval_agent.py` (5 scenarios).
Changed only the agent code or prompt? `databricks bundle run ce_agent_deploy --only log_and_deploy` skips recreating the
functions, so the serving version keeps working through the rollout. (A full run breaks the live version's tools from the
moment `tools.sql` runs until the new version takes traffic; the app drafts with its template fallback meanwhile.)

## T−20 min: warm everything
| Component | Action | Why |
|---|---|---|
| SQL warehouse | Open the dashboard once (or run any query) | Serverless warehouse auto-stops after 30 min |
| Commentary agent | Send one request (below) or set scale-to-zero off for the day | Endpoint scales to zero; a cold start took 68 s on 2026-10-22, then 19–34 s per draft |
| App | Open the app URL once; confirm the Flux screen loads live figures (pick Light or Dark in the header) | First load after the warehouse idles takes ~15 s (the page says so); repeat views are cached |
| Genie | Ask the scene-2 question once | Warms the space and the warehouse |
| Demo state | In the app (approver), **Reset demo**, then `databricks bundle run ce_review_sync -t dev` | Restores Ava Chen's seeded in-review item and history; the reset itself does not sync to Unity Catalog (approve / submit / reject do, within a minute) |

Warm the agent:
```python
from databricks.sdk import WorkspaceClient; import requests
w = WorkspaceClient(profile="fe-vm-zh-serverless")
requests.post(f"{w.config.host}/serving-endpoints/ce-commentary-agent/invocations", headers=w.config.authenticate(), timeout=300,
              json={"input": [{"role": "user", "content": "ping"}], "custom_inputs": {"comparison_id": "MOM_2026-09", "slice": "APAC"}})
```
(The CLI `serving-endpoints query` drops `custom_inputs` and times out after 60 s — use the REST call.)

## During the demo — fallbacks
| If… | Then |
|---|---|
| The agent is slow or unavailable | The app drafts with the deterministic template drafter (same figures, same chips) and records `fallback_reason` |
| Genie phrases an answer differently | Point to the effects table it returns; the bars still add up. Backup: the dashboard Flux page |
| A query hits an IP-ACL block (`Source IP … blocked`) | Your VPN egress changed — reconnect and retry |
| Something looks off | `cost_explain.gold.tie_out_results` shows every check with expected vs actual |

## Persona for the governance scene
Service principal `ce-persona-eqd-desk-head` (member of `ce_desk_head_eqd`, read-only on `cost_explain.gold`) sees only
HK Equity Derivatives. To demonstrate live, create a short-lived OAuth secret
(`databricks service-principal-secrets-proxy create <sp-id>`), query as the SP, then delete the secret. Recorded evidence:
`docs/GOVERNANCE.md`.

## After the demo
- Delete any persona secrets you created.
- Optional cost hygiene: stop the app compute and leave the agent endpoint on scale-to-zero.
- Nothing customer-specific is stored; all data is synthetic.
