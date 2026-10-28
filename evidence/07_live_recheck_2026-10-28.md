# 07 — Live re-check on 2026-10-28 (workspace `fe-vm-zh-serverless`)

Re-run today against the deployed build. Endpoint `ce-commentary-agent` READY · app `cost-explain-app` RUNNING ·
pipeline `ce_medallion` last update `0ddcac31-9918-4913-8c8c-227874399266` COMPLETED 2026-10-22T05:15:25Z.

## Tie-out results and the bridge, queried live from Gold (09:31 UTC, warehouse `cost-explain-wh`)

Results as returned; the third query's column list is abbreviated here. A query for failing rows
(`WHERE NOT passed`) returned 0 rows.

```
SELECT COUNT(*) AS checks, COUNT_IF(passed) AS passed, COUNT_IF(NOT passed) AS failed FROM cost_explain.gold.tie_out_results
{'checks': '56', 'passed': '56', 'failed': '0'}
DESCRIBE HISTORY cost_explain.gold.tie_out_results LIMIT 1
{'version': '2', 'timestamp': '2026-10-22T05:19:58.000Z', 'operation': 'CREATE OR REPLACE TABLE AS SELECT', 'userName': 'zhihan.tan@databricks.com'}
SELECT ROUND(SUM(p0_actual_usd)/1e3,1) AS p0_k, … ROUND(SUM(flux_usd)/1e3,1) AS flux_k FROM cost_explain.gold.cost_flux_bridge WHERE comparison_id = 'MOM_2026-09'
{'p0_k': '5000.0', 'p1_k': '6200.0', 'volume_k': '900.0', 'mix_k': '190.0', 'rate_k': '100.0', 'fails_k': '150.0', 'timing_k': '-50.0', 'fx_k': '-100.0', 'fixed_k': '0.0', 'unexplained_k': '10.0', 'flux_k': '1200.0'}
```

## Genie, asked live (benchmark B01; COMPLETED in 25 s)

Question: *Why did APAC trade costs go up in September vs August?* Generated SQL (over the metric view):

```sql
SELECT
  MEASURE(`Prior Period Cost`) AS `prior_period_cost`,
  MEASURE(`Current Period Cost`) AS `current_period_cost`,
  MEASURE(`Cost Change`) AS `cost_change`,
  MEASURE(`Cost Change Pct`) AS `cost_change_pct`,
  MEASURE(`Volume Effect`) AS `volume_effect`,
  MEASURE(`Mix Effect`) AS `mix_effect`,
  MEASURE(`Rate Effect`) AS `rate_effect`,
  MEASURE(`Fails Effect`) AS `fails_effect`,
  MEASURE(`Timing Effect`) AS `timing_effect`,
  MEASURE(`FX Effect`) AS `fx_effect`,
  MEASURE(`Fixed Fees Effect`) AS `fixed_fees_effect`,
  MEASURE(`Unexplained`) AS `unexplained`
FROM `cost_explain`.`gold`.`trade_cost_flux_metrics`
WHERE `Comparison` = 'MOM_2026-09'
GROUP BY ALL
```

Answer: "APAC trade costs increased from **US$5.00M** in August to **US$6.20M** in September, a rise of **US$1.20M** or
**24%**. The September vs August bridge is: Volume **+US$900K**, Mix **+US$190K**, Rate **+US$100K**, Fails
**+US$150K**, Timing / accrual **-US$50K**, FX **-US$100K**, Fixed fees **US$0K**, and Unexplained **+US$10K**. The
biggest driver of the increase was **Volume +US$900K**, which accounted for most of the month-on-month rise."

## Commentary agent eval — PASSED 5/5 (`src/agent/eval_agent.py`, 09:34 UTC)

Pass = HTTP 200, at least 5 figure chips, every chip resolves in `gold.commentary_figures` with no value mismatch,
every planted driver named, no out-of-scope desk mentioned. Logged as MLflow run `45237b5ca3a5468790920e7bcb4a905c`.

```
{"scenario": "apac_sep", "http_ok": true, "latency_s": 122.2, "chips": 21, "unresolved_chips": [], "value_mismatches": [], "coverage": 1.0, "scope_leaks": [], "passed": true}
{"scenario": "ed_exch_clearing_sep", "http_ok": true, "latency_s": 25.7, "chips": 14, "unresolved_chips": [], "value_mismatches": [], "coverage": 1.0, "scope_leaks": [], "passed": true}
{"scenario": "rest_sep", "http_ok": true, "latency_s": 23.2, "chips": 18, "unresolved_chips": [], "value_mismatches": [], "coverage": 1.0, "scope_leaks": [], "passed": true}
{"scenario": "au_cash_desk_sep", "http_ok": true, "latency_s": 26.5, "chips": 15, "unresolved_chips": [], "value_mismatches": [], "coverage": 1.0, "scope_leaks": [], "passed": true}
{"scenario": "qoq_q2", "http_ok": true, "latency_s": 27.8, "chips": 25, "unresolved_chips": [], "value_mismatches": [], "coverage": 1.0, "scope_leaks": [], "passed": true}
PASSED 5/5
```
