# Design — Trade Cost Explain app

A full redesign of `cost-explain-app` (2026-10-23): a new shell, every screen rebuilt, and **five themes to vet**.
All five share one layout and one component set; a theme changes only role tokens (colour, type, shape, density).
They take their cue from a restrained financial-services house style — black, white and a single red, hairline
rules, calm space — without using any real company's name or logo.

## Switch and vet

- **In the app:** sidebar footer → theme button → pick one of five (each shows a preview swatch). The choice is
  saved per browser.
- **By link:** add `?theme=<key>` to any app URL — e.g. `…databricksapps.com/?theme=washi` or
  `…/commentary?theme=kon`. Handy for side-by-side vetting; the choice is saved too.
- Keys: `marunouchi` (default) · `otemachi` · `washi` · `kon` · `sumi`.
- Screenshots of every theme are in [`docs/design/`](design/) (Flux overview in all five; review, approvals, audit,
  register and the picker in one theme each).

## The five themes

| | Theme | Mood | Surfaces | Accent / primary action | Type | Shape · density | Best for |
|---|---|---|---|---|---|---|---|
| 1 | **Marunouchi** — corporate light | Glass-tower precision | White cards on cool grey; white sidebar | Signal red, red primary button | System sans | 10 px radius · standard | Default; client-facing reviews |
| 2 | **Otemachi Night** — trading-floor dark | Multi-monitor desk | Near-black, panels one step up | Red signals, inverted (white) primary | System sans, uppercase labels | 6 px · compact | Long sessions, dark rooms, dense data |
| 3 | **Washi** — warm paper, editorial | Board pack on washi paper | Warm paper tones, sumi-ink text | Vermilion signals, sumi-ink primary | Serif headings, sans numbers | 4 px · airy | CFO / board narrative, the review screen |
| 4 | **Kon** — executive indigo | Private-banking polish | White cards on pale blue-grey; deep indigo sidebar | Red signal, indigo primary | System sans | 14 px · soft elevation | Executive audiences, projector |
| 5 | **Sumi** — monochrome, high contrast | Ink painting, restraint | Pure white, hard black rules | Black; colour only in data | Heavy display weight, uppercase labels | 2 px · crisp | Accessibility, print, sceptical audiences |

### Chart colours per theme (validated)

Cost increase / decrease are a diverging pair (warm vs cool), totals neutral. Every pair was run through the
dataviz `validate_palette.js` six checks on its own chart surface — lightness band, chroma floor, colour-vision
separation (target ΔE ≥ 8), normal-vision floor (≥ 15) and contrast (≥ 3:1). All pass:

| Theme | Increase | Decrease | Total | CVD ΔE (worst) | Normal ΔE |
|---|---|---|---|---|---|
| Marunouchi | `#c8102e` | `#2a78d6` | `#4b5563` | 26.1 | 33.4 |
| Otemachi Night | `#f04a5a` | `#3987e5` | `#9aa3ae` | 21.0 | 32.3 |
| Washi | `#c53d1f` vermilion | `#2f5aa8` indigo | `#5a534a` sumi | 21.1 | 29.6 |
| Kon | `#d0021b` | `#2f6fd1` | `#3d4a63` | 27.8 | 34.5 |
| Sumi | `#c4001a` | `#1f4e9c` | `#1a1a1a` | 20.4 | 32.1 |

### Contrast audit

An automated audit parses every theme block in `frontend/src/styles.css` and checks 74 text/surface pairs per theme
(370 in total) — body, secondary and muted text on every surface, sidebar text, active nav, badges, status pills,
primary buttons, chart marks and focus rings, with translucent tints blended over their real background.
**All pass WCAG AA; the weakest text pairing is 5.16 : 1** (threshold 4.5 : 1).

## Principles

1. **Numbers first, chrome last.** Data is the loudest thing on screen; furniture is hairlines and muted labels.
2. **One screen, one question.** Overview: *why did costs move?* Review: *is this commentary right?* Approvals:
   *what needs my sign-off?* Audit: *who did what, when?*
3. **Every number is traceable.** Provenance (table, pipeline update, row filters) is in the filter bar, not a
   footnote; every commentary figure is a chip that opens its source.
4. **Calm precision.** Strict grid, generous space, one accent — used for state (active, focus, selection), not
   decoration.
5. **Accessible by construction.** AA contrast in every theme, CVD-safe chart pairs, status always label + dot,
   visible focus rings, reduced-motion respected, and a table view for every chart.
6. **Fast-feeling.** Skeletons only on first load; refetches keep the previous view dimmed; a cold warehouse is
   explained after 4 s instead of leaving a blank page.

## Layout

- **Sidebar** (fixed): brand mark (two rising bars — a bridge in miniature) · *Analysis*: Flux overview ·
  *Close*: Commentary, Approvals (live count badge), Audit trail · footer: live data status, theme picker, user menu
  (roles; *Reset demo* for approvers). Collapses to icons below 1180 px.
- **Sticky page header**: breadcrumb, title (+ status pill), one-line context, and the page's actions — always in
  reach while scrolling.
- **Cards** on the page plane; one filter row scopes everything below it.

## Screens

**Flux overview** — filter bar (comparison, headline slice, business / desk) with a provenance row (`live ·
cost_explain.gold.cost_flux_bridge · pipeline update … · row filters apply`); KPI strip (prior, current with
constant-currency, change with a delta pill, volume-driven share); the **bridge** (thin columns with rounded
data-ends, connectors carrying each running total, value labels in ink, tooltip with each effect's share of the
change); **Explain the change** (Good / Controllable / External summary, every effect with a diverging bar and share —
select one to see its top contributors for the current breakdown, linked to the chart and table); **Breakdown**
table (seven breakdowns, sticky first column, inline flux bars, totals pinned, selected-effect column highlighted,
CSV export).

**Commentary** — register with status tabs and live counts, status pill, readable comparison label, avatar.

**Commentary review** — the draft as a document (serif heading in Washi), red bullet markers, figure chips;
Preview / Edit toggle in the document header; Save / Submit / Approve / Reject in the sticky page header; rail with
**Figures** (compact rows: label, value, source and snapshot; select for filter, snapshot id, lineage link, Ask
Genie), **History** (timeline) and **Ask Genie** tabs.

**Approvals** — one card per item: status, comparison, slice, version, title, a three-line excerpt, author and
submitted time; Review / Approve / Reject with the four-eyes reason shown when a decision is blocked.

**Audit trail** — colour-coded action pills (created, drafted, edited, submitted, approved, rejected), avatar,
status transition, note, commentary and request id; pick a commentary to see its versions, the text at each version
and the figure snapshot it cited.

## Changing a theme

The token sets live in `frontend/src/styles.css` (one `:root[data-theme="…"]` block per theme); the picker's
names, descriptions and swatches live in `frontend/src/themes.ts` — keep the two in step. To match a brand guide,
change `--accent`, `--primary` and `--viz-up` in one block, then re-run the palette validator and the contrast audit.
