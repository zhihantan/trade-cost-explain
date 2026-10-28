# Deck brief — Trade Cost Explain (for Claude Design)

**How to use this file.** Paste the whole file into Claude Design and ask: *"Build a 16:9 presentation from this brief:
one slide per `## Slide` block, appendix slides after the main deck. Put the Headline and On-slide content on the slide,
draw the Visual, and put the Speaker notes in the notes."* Then export to **PDF** and attach it to the FE Bar build
submission (the scorer reads the PDF's text, so every key number must be **on** the slide, not only in the notes).

---

## Design direction

- **Format:** 16:9, light theme, executive finance style. One idea per slide, big numbers, charts over text, generous
  white space. At most 4 bullets per slide, each under 12 words.
- **Palette:** text `#111827` on white; headers and "prior period" `#1F4E79`. Flux drivers always use the same colours
  as the live dashboard: **good (volume) `#17A589`**, **controllable (mix, fails) `#E15F41`**, **external / timing /
  residual `#8C9BA5`**. Increases vs decreases in waterfalls follow those meanings, not red/green.
- **Type:** a clean sans (e.g. Inter) with tabular figures; numbers as `US$1.2M`, `US$900K`, `+24%`.
- **Footer on every slide (small):** *Synthetic data — Meridian Group; all figures illustrative · Databricks*.
- **No real company names or logos.** Meridian Group, its brokers (Cobalt Securities, Dunmore Capital Markets), the
  counterparty Kestrel Asset Management and the venues (PRX, Southern Cross Exchange, Tasman Alternative Market) are
  fictional.
- **Number tags:** figures marked **[prototype]** were measured on the working build; figures marked **[illustrative]**
  come from a stated assumption. Show the tag in small type next to the number.

## Audience and story

| Persona | Who | What they need to hear |
|---|---|---|
| Executive sponsor | Global Markets CFO / Head of FP&A | One number that ties, explained before results; controls an auditor accepts; where cost can come down |
| Domain owner | Business Finance (Sales & Trading), Product Control, Operations cost management | Drivers by desk and venue, one click to the trades, a ranked fix list, a review workflow that fits the close |
| Technical stakeholder | Head of Finance Data / Data Platform | Governance, lineage, security model, how it connects to the GL and existing platforms, how the AI is kept honest |

Arc: **tell** (the outcome) → **show** (four live demo moments) → **tell** (value, proof, next steps).

---

## Slide 1 — Title

- **Headline:** Explain every dollar of trade cost — in minutes, with evidence
- **On-slide content:** Half-year close, APAC Global Markets · Meridian Group (synthetic) · Zhi Han Tan, Databricks
- **Visual:** one large waterfall silhouette (US$5.0M → US$6.2M) in the driver colours, faded behind the title.
- **Speaker notes:** "Today: why trade costs rose 24% in September, what to do about it, and how the explanation becomes
  approved commentary with the evidence attached — on one governed platform. Every number is synthetic and illustrative."

## Slide 2 — The answer in one slide

- **Headline:** +US$1.2M explained to US$10K — and US$340K of it you can act on
- **On-slide content:**
  - Trade costs **US$5.0M → US$6.2M (+24%)**, September vs August [prototype]
  - **75% volume-driven** (revenue rose with it); **28% controllable** (mix + fails) [prototype]
  - Found: **US$85K broker over-billing**, **US$145K** fail cost from one counterparty [prototype]
  - Commentary drafted in **under a minute**, approved under **four-eyes**, every figure traced [prototype]
- **Visual:** four KPI tiles in a row (Explained · Controllable · Recovered · Time to commentary).
- **Speaker notes:** "If you remember one slide: the bars add up, we know which part is good cost and which part is
  controllable, and the narrative is signed off with evidence."

## Slide 3 — Half-year close today

- **Headline:** The number arrives on day one; the explanation takes days
- **On-slide content:**
  - A ledger line with no drivers: volume, mix, rate, fails, FX, timing all blended
  - Broker invoices arrive weeks after month end — the close runs on accruals
  - Spreadsheet bridges leave an unexplained residual nobody can defend
  - Auditors ask how each number in the commentary was produced
- **Visual:** "before" flow — GL, trade feeds, invoices, PDFs of fee schedules → spreadsheets and email → commentary,
  with a clock and a question mark.
- **Speaker notes:** Frame as hypotheses to confirm: "Is this how your close works today? How long does the trade-cost
  flux take, and who signs it?"

## Slide 4 — September, explained to the dollar

- **Headline:** Six drivers add up to the US$1.2M — the residual is US$10K
- **On-slide content:** Bridge (US$K): prior **5,000** · volume **+900** · mix **+190** · rate **+100** · fails **+150** ·
  timing / accrual **−50** · FX **−100** · fixed **0** · unexplained **+10** → current **6,200** [prototype]
- **Visual:** waterfall chart, bars coloured by meaning (volume green, mix and fails coral, rate / FX / timing /
  residual grey); annotate "residual US$10K < threshold US$60K".
- **Demo cue:** AI/BI dashboard, page *Flux* (scene 1), then ask Genie "Why did APAC trade costs go up in September?"
- **Speaker notes:** "Genie reads the governed bridge; it does not recompute it. The residual threshold is the greater
  of US$25K and 5% of the change — we're at US$10K."

## Slide 5 — Good flux vs controllable flux

- **Headline:** 75% of the increase is good cost; 28% is yours to control
- **On-slide content:**
  - **Good: US$900K (75%)** — volume, revenue up US$44.67M → US$53.74M [prototype]
  - **Controllable: US$340K (28%)** — mix US$190K + fails US$150K [prototype]
  - **External / timing / residual: −US$40K** [prototype]
- **Visual:** stacked bar of the change by flux class next to a 13-month cost-vs-revenue line, with the volatility
  spike (PRX Volatility Index ~20 → low 30s in mid-September) marked.
- **Demo cue:** dashboard page *Good vs bad flux* (scene 3).
- **Speaker notes:** For the CFO: cost rose because the desks traded more, and revenue rose faster. The conversation
  is about the US$340K.

## Slide 6 — Three things to act on this month

- **Headline:** From a variance to an owner and an action
- **On-slide content:**
  - **Mix +US$190K:** PRX 50 futures booked in the house account instead of the market-maker account (+US$90K); orders
    routed to the higher-fee venue (+US$100K) → *Desk heads, execution routing* [prototype]
  - **Over-billing US$85K:** Cobalt Securities billed the 3.0 bp tier, not 2.5 bp, on US$1.70bn turnover → *Procurement
    claims it* [prototype]
  - **Fails US$145K:** Kestrel Asset Management, settlement-instruction mismatch after a custodian change → *Operations
    fixes the static data* [prototype]
- **Visual:** three cards, each with the amount, the root cause and the owner.
- **Demo cue:** dashboard pages *Drill to trade*, *Invoice vs expected*, *Fails* (scenes 4–6).
- **Speaker notes:** "One click from a ledger line to the executions behind it. Ops gets a ranked fix list, not just a
  cost number."

## Slide 7 — From number to approved commentary

- **Headline:** The agent drafts, an analyst edits, a second person approves
- **On-slide content:**
  - Draft in **41–52 seconds**; **14–16 figures per draft, all traced** to the governed data [prototype]
  - Every number is a figure chip: source table, filter and version one click away
  - **Four-eyes:** the author cannot approve their own commentary; every action audited
  - Approved history lands in Unity Catalog **35 seconds** after the click [prototype]
- **Visual:** screenshot-style mock of the review app: commentary text with highlighted figure chips, an approval
  panel, an audit trail.
- **Demo cue:** Databricks App *cost-explain-app* (scene 7): Draft commentary → edit → submit → approve the seeded item.
- **Speaker notes:** "The agent may only state numbers the tools returned; anything else is dropped before you see it."

## Slide 8 — Ask in plain language

- **Headline:** Business finance gets answers without a ticket
- **On-slide content:**
  - Genie answers **11 of 11** benchmark questions, including one asked in Traditional Chinese [prototype]
  - "Which brokers billed more than expected in Q2?" → Cobalt **+US$85K**, Dunmore **+US$68K**
  - "What fee changes take effect in the next six months?" → **+US$29.1K** and **+US$11.5K a month** from 1 Jan 2027
  - Each user sees only the desks they are entitled to
- **Visual:** a chat panel with the question, the answer and the generated SQL collapsed underneath.
- **Demo cue:** Genie space (scene 2, follow-up questions).
- **Speaker notes:** "Benchmarked over ten eval runs, tuned one change at a time, from 5/10 to 11/11."

## Slide 9 — Numbers you can sign

- **Headline:** Controls are built in, not bolted on
- **On-slide content:**
  - **56 automated tie-out checks** on every rebuild; any miss fails the build [prototype]
  - Desk heads see only their desks: **12 desks → 1** for a desk-head login [prototype]
  - Lineage from commentary to Gold to the source files and **PDF fee schedules**
  - Fee schedules read from **20 PDFs in 3 languages**, **98.6%** of fields right first time, analyst-approved [prototype]
- **Visual:** lineage chain: commentary → figure → Gold bridge → trades / GL / invoices / fee schedule → landed files and
  PDFs, with a shield icon on the row-filter step.
- **Demo cue:** Catalog Explorer lineage (scene 8).
- **Speaker notes:** For Product Control and audit: "evidence for the control walkthrough, end to end."

## Slide 10 — One platform, one journey

- **Headline:** Six Databricks capabilities, one governed data path
- **On-slide content:** Lakeflow pipeline (ingest + quality) → Unity Catalog (row security, lineage, metric
  definitions) → Lakebase (review and approval store) → Gen AI agent on Model Serving + PDF extraction → Genie →
  Databricks App
- **Visual:** left-to-right architecture: landing files and PDFs → bronze / silver / gold → metric views → three
  consumers (dashboard, Genie, agent) → app → Lakebase → back into Unity Catalog. Label each with the capability name.
- **Speaker notes:** For the technical stakeholder: "One bundle deploys everything, serverless. The app reads with the
  user's own permissions and writes as a service principal, recording who did what."

## Slide 11 — Proof it runs

- **Headline:** Tested end to end, not mocked
- **On-slide content:**

  | Check | Result [prototype] |
  |---|---|
  | Tie-out gate | 56 / 56 passed |
  | Dashboard queries re-run as deployed | 59, 0 failures |
  | Genie benchmarks | 11 / 11 |
  | Agent drafts | every figure resolved, no value mismatches |
  | Approval → Unity Catalog | 35 s |
  | Independent rebuild from raw files | PASS (3.28M executions) |

- **Visual:** the table, with a check mark per row.
- **Speaker notes:** "The data is synthetic, so we designed it backwards from the answer and test that it ties every
  time we rebuild."

## Slide 12 — What it is worth

- **Headline:** Measured on one month; sized for a year with your numbers
- **On-slide content:**

  | Lever | Measured [prototype] | Annual sizing [illustrative] |
  |---|---|---|
  | Billing recoveries | US$85K on one invoice | one finding this size per quarter ≈ **US$340K** |
  | Controllable cost | US$340K in one month | act on a quarter of it each month ≈ **US$1.0M** |
  | Finance time | commentary in < 1 minute | 3 analysts × 2 days × 12 closes ≈ **72 analyst-days** |
  | Audit readiness | 56 checks, full lineage | fewer control-walkthrough findings |

- **Visual:** three large numbers (US$340K · US$1.0M · 72 days) with the assumption written under each.
- **Speaker notes:** "These annual figures are assumptions to replace with yours in discovery — how often invoices are
  wrong, how much controllable flux you act on, how long the close takes today."

## Slide 13 — Path to production

- **Headline:** From this prototype to your close in three steps
- **On-slide content:**
  1. **Discover (2 weeks):** GL, trade, invoice and fee-schedule sources; the four-eyes control; success criteria
  2. **Pilot (4 weeks):** two desk groups on real data — GL through Lakeflow Connect, ABAC with your account groups, an
     APAC-region workspace
  3. **Scale (4 weeks):** all APAC desks, commentary in the close calendar, Lakehouse Sync for review history
- **Visual:** three-step timeline with the success criteria under the pilot: residual under threshold, commentary on
  day one of the close, 100% of figures traced.
- **Speaker notes:** Timeline is indicative; confirm with the customer's close calendar.

## Slide 14 — Next steps

- **Headline:** What we need from you
- **On-slide content:**
  - A 90-minute discovery session with FP&A and Product Control
  - Sample extracts: one month of GL, trades and broker invoices
  - Two pilot desk groups and the success criteria that matter to you
  - A security review contact for the workspace and data access
- **Visual:** four numbered boxes with an owner and a target date placeholder each.
- **Speaker notes:** Close with a date: "Can we book the discovery session for next week?"

---

## Appendix A — Run of show for the 25-minute roleplay

| Minutes | Slides | Live demo |
|---|---|---|
| 0–2 | 1–2 | — Open: who you are, the customer, the business persona and the agenda |
| 2–5 | 3–4 | Dashboard *Flux*; Genie: "Why did APAC trade costs go up in September?" |
| 5–12 | 5–6 | Dashboard *Good vs bad flux*, *Drill to trade*, *Invoice vs expected*, *Fails* |
| 12–17 | 7–8 | App: draft → edit → submit → approve; Genie follow-up questions |
| 17–21 | 9–12 | Lineage, proof, value — answer the technical stakeholder |
| 21–25 | 13–14 | Path to production and the ask; book the next meeting |

Finish inside 25 minutes, with the close and next steps done.

## Appendix B — Likely questions

| Question | Answer |
|---|---|
| How do you stop the bridge drifting? | Constant currency first; FX on every GL line; volume / mix / rate inside groups that share a volume unit; identity `flux = Σ effects` checked on every row by the tie-out gate |
| Can the AI make up a number? | No: it only states figures its tools returned, each as a traceable chip; unknown chips are dropped; an analyst edits and a second person approves |
| Who sees what? | Unity Catalog row filters on the Gold data; dashboard, Genie, agent and app all inherit them; the app reads with the signed-in user's token |
| Where do the fee rates come from? | 20 PDF rate cards (English, Traditional Chinese, Korean) → `ai_parse_document` → `ai_extract` → analyst review → approved fee schedule; 98.6% of fields right first time |
| Does this replace our existing data platform? | No — federate or share; Unity Catalog governs what lands here |
| How does it connect to our GL? | Lakeflow Connect or landed files; a mapping-coverage check (99.76% of GL mapped to a counterparty in the prototype) |
| Data residency? | This build runs in AWS us-west-2; the same bundle redeploys unchanged to Singapore, Sydney or Mumbai |
| What does it cost to run? | Serverless throughout and the Lakebase store autoscales; size it on your volumes in the pilot |
| Isn't this just a dashboard? | The dashboard shows the bridge; the platform also finds the root causes, drafts the commentary, runs the approval and keeps the evidence |
