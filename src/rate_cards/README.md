# Rate-card PDFs

`render.py` turns `src/datagen/config/rate_cards.yaml` into 20 fee-schedule PDFs (17 English, 2 Traditional Chinese,
1 Korean) with issuer-specific layouts. `publish.sh <profile>` renders and uploads them to
`/Volumes/cost_explain/landing/rate_cards/`, and writes `vendor_contracts.csv` and `fail_cost_rule.csv` to
`/Volumes/cost_explain/landing/raw/ref/`. Then run the `ce_fee_extraction` job (see `docs/EXTRACTION.md`).

- Fonts: Latin text uses Helvetica / Times; CJK and Hangul fall back to a Unicode TrueType font
  (default `/Library/Fonts/Arial Unicode.ttf`, change with `--cjk-font`). The font is embedded as a subset, and every
  render checks with `pypdf` that the Chinese / Korean text is extractable.
- Notation deliberately varies by issuer, so the extraction step has real conversions to do: % of value
  (Pearl River, Merlion), bps (Southern Cross Clear, brokers), ₹ per crore (Indus), 港幣 / 新台幣 / 원 amounts, and
  local-language dates.
- `out/pdf/pdf_eval_questions.json`: one grounded question and expected fact per card (for a Knowledge Assistant or
  retrieval eval over the rate cards); uploaded alongside the PDFs and ignored by the extraction job (`*.pdf` only).
- Output: `out/pdf/`, `out/html/` (source HTML), `out/ref/`, `out/render_report.json` (pages, characters and CJK / Hangul
  counts per card). `out/` is git-ignored and fully reproducible.
