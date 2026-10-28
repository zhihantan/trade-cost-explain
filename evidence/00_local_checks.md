# 00 — Local checks (re-run 2026-10-28, no workspace needed)

Run from this repository on a macOS laptop at 2026-10-28T08:51Z. Output below is copied from the terminal unchanged.

## Unit tests — 17 passed

| Suite | Command | Python | Result |
|---|---|---|---|
| App backend (routes, roles, four-eyes, figure chips) | `cd cost-explain-app && .venv/bin/python -m pytest tests/test_unit.py -q` | 3.11.15 | `6 passed, 1 warning in 6.15s` |
| Fee-schedule review logic | `python -m pytest src/extraction/test_review_logic.py -q` | 3.12.13 | `3 passed in 0.35s` |
| Planted-bridge design | `python -m pytest tests/test_design.py -q` | 3.12.13 | `8 passed in 2.94s` |

The one warning is a third-party deprecation notice (`StarletteDeprecationWarning` from `fastapi.testclient`).

## Synthetic data + independent tie-out verifier — RESULT: PASS

The generator lands the raw files that the Lakeflow pipeline ingests (Auto Loader from the landing Volume). The verifier then
rebuilds the September vs August bridge **from the landed files** with an implementation that is independent of the
pipeline SQL, and fails unless every planted cell ties.

```
$ cd src/datagen && python -m meridian_datagen.main --out ../../.local_out/raw
[    1.8s] plan solved: 1,482 sub-flow-month-side rows
[   27.9s] realized 3,280,842 executions
[   35.1s] settlements 2,596,015, fails 3,906
[   75.5s] expected cost computed for every execution
[   75.6s] GL 9,340 lines; FX solve AUD -4.719% KRW -2.739%
[   11.8s] landed files under ../../.local_out/raw
{
  "trades": 3280842,
  "settlements": 2596015,
  "fails": 3906,
  "gl_lines": 9340,
  "ap_invoices": 640,
  "ap_invoice_lines": 5434
}

TIE-OUT  September 2026 vs August 2026 (US$K; volume / mix / rate at constant currency)
slice        P0       P1      volume         mix        rate       fails       fixed      timing          fx unexplained      flux
ED       2170.0   2680.0     389.997      89.999      60.000       0.000       0.000     -20.000     -10.000       0.000     510.0
REST     2830.0   3520.0     510.000     100.000      40.000     150.000       0.000     -30.000     -90.000      10.000     690.0
APAC     5000.0   6200.0     899.997     189.999     100.000     150.000       0.000     -50.000    -100.000      10.000    1200.0
good (volume) 75.0% · controllable (mix + fails) 28.3% · external / timing / residual -3.3%
Broker C August: expected 425.0K, invoiced 510.0K, over-billed 85.00K
RESULT: PASS
real 100.15
```

These are the same figures the deployed Gold layer, dashboard, Genie space and agent report (`01`, `04`, `05`).
