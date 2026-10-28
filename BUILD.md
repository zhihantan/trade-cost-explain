# How I built it — decisions, trade-offs and where AI helped

## The customer problem

At half-year close, a sell-side bank's APAC Global Markets division sees trade costs jump from US$5.0M to US$6.2M
(+24%) in September vs August. Finance has to explain why — to the dollar, by desk and by driver — before results are
reported, with evidence an auditor would accept. Today that is spreadsheets, days of analyst time and an unexplained
residual nobody can defend.

- **Executive sponsor:** Global Markets CFO / Head of FP&A — needs one number that ties, and controls behind it.
- **Domain owner:** Business Finance and Product Control — need the drivers, the drill to trades, and a fast review.
- **KPIs the build moves:** time to explain the flux; unexplained residual (kept under the greater of US$25K and 5% of
  flux); over-billing found (Broker C, US$85K); fail costs attributed (Kestrel, US$145K); approvals under four-eyes.

## One journey across the platform

Raw files land in a Unity Catalog Volume → **Lakeflow** SDP pipeline (Auto Loader bronze, silver expectations, Gold
materialized views) → **Unity Catalog** row filters on Gold, metric views and lineage → the **Genie** space, the AI/BI
dashboard and the **agent**'s UC function tools all read the same governed Gold → the agent drafts commentary in which
every number is a figure chip → the **Databricks App** shows it to the analyst with their own permissions → edits and
the four-eyes approval are written to **Lakebase** → job `ce_review_sync` replicates them to Unity Catalog → an
evidence view re-checks every cited figure against Gold.

## Decisions and trade-offs

1. **Make "the bars must add up" testable.** The data is designed backwards from the bridge: a calibrated,
   deterministic generator plants each driver, an independent verifier rebuilds the bridge from the landed files, and
   a 56-check SQL tie-out gate ends every build and fails it on any miss. Trade-off: I used a numpy generator instead
   of pure Spark — exact tie-out matters more than purity — and it still lands raw files for Auto Loader.
2. **Put governance in the data, not the app.** Row filters sit on the Gold materialized views, so the dashboard,
   Genie, the agent's tools and the app inherit them. ABAC was my first choice, but this shared account had hit its
   governed-tag limit, so I kept the same entitlement logic as row filters (`abac.sql` stays for a customer
   workspace) and proved it with a desk-head persona: 12 desks become 1.
3. **Use Lakebase for the human in the loop.** Drafts, versions, approvals and the audit trail need transactional
   writes with a four-eyes rule, so they go to Lakebase, not to Delta. Lakehouse Sync does not support Default Storage
   catalogs, so a MERGE job replicates the history to Unity Catalog (approval visible there 35 s after the click).
4. **Ground the agent by construction.** Its tools are Unity Catalog SQL functions over Gold; it may only state
   numbers as figure chips that a tool returned; a verify-and-repair round drops anything else; a template fallback
   covers failed calls. The serving endpoint keeps it model-agnostic.
5. **Tune Genie like a model.** I used the benchmark eval API, kept benchmark repairs apart from space tuning, and
   changed one lever per run: 5/10 → 10/10, final 11/11. Run 9 regressed; run 10 fixed it with a ranking note.
6. **Treat documents as data.** Fee schedules arrive as PDFs in three languages, so they go through
   `ai_parse_document` → `ai_extract` → analyst review. The second prompt added generic field semantics and a glossary,
   nothing card-specific: 49.6% → 73.4% of lines fully right, 98.6% of fields. The review step stays, because the
   Korean card is still the weakest.
7. **Act as the right identity.** Reads use the signed-in user's token, so their row filters apply; writes use the
   app service principal; every write records the actor; the app fails closed.
8. **Package for redeployment.** One bundle holds every asset, all serverless. I built in us-west-2 for feature
   coverage; moving to an APAC region is a redeploy, not a rewrite.

## Where AI helped — and where I did not trust it

I wrote the spec first (data design, planted stories, acceptance tests) and built against it with AI assistance.
I did not take the generated output on trust: the verifier, the tie-out gate, the dashboard re-validation, the Genie
benchmarks, the agent eval and the unit tests had to pass. They caught real problems:

- the spec's `fetchall_arrow()` snippet fails on `databricks-sql-connector` 4.x (no pyarrow), so the app uses `fetchall()`;
- the serving endpoint rejects `temperature`, so the agent passes sampling options only when configured;
- early agent probes returned an empty message or an `EXECUTE` permission error, which the template fallback covered;
- extraction prompt v1 misused the schema (a rate copied into `floor_per_trade`, % typed as "per million");
- Genie's run 9 ranked across all months and returned one desk.

## What I would do next with a real customer

Run `abac.sql` with account groups, deploy to an APAC region, land the real GL through Lakeflow Connect, switch to
Lakehouse Sync when the catalog supports it, and confirm the four-eyes control and audience in discovery.
