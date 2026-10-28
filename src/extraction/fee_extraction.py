"""Fee-schedule extraction job: rate-card PDFs → approved cost_explain.silver.fee_schedule.

Steps (one job task each; run with --step):
  parse    ai_parse_document over /Volumes/<catalog>/landing/rate_cards → silver.rate_card_parsed
  extract  ai_extract v2.1 (JSON schema, confidence scores) → silver.fee_schedule_extracted
  review   canonical answer key + simulated analyst review → silver.rate_card_answer_key, silver.fee_schedule_review,
           silver.fee_schedule_extraction_summary
  publish  approved schedule (canonical values; the review is the control) → silver.fee_schedule, silver.fail_cost_rule
  guard    fail the run if the approved schedule does not match the canonical line count / integrity rules

Determinism: approved rates always equal the canonical YAML even if extraction is imperfect. The analyst review is
simulated from the canonical cards (the analyst's knowledge) and is disclosed as such in docs/EXTRACTION.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone


def _src_dir(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    try:
        return os.path.dirname(os.path.abspath(__file__))  # type: ignore[name-defined]
    except NameError:
        return os.getcwd()


ARGS = argparse.ArgumentParser()
ARGS.add_argument("--step", required=True, choices=["parse", "extract", "review", "publish", "guard", "all"])
ARGS.add_argument("--catalog", default="cost_explain")
ARGS.add_argument("--rate_cards_yaml", required=True)
ARGS.add_argument("--rate_card_path", default=None, help="defaults to /Volumes/<catalog>/landing/rate_cards/")
ARGS.add_argument("--analyst", default="ava.chen@meridian-demo.example")
ARGS.add_argument("--src_dir", default=None)
args, _ = ARGS.parse_known_args()

sys.path.insert(0, _src_dir(args.src_dir))
import canonical  # noqa: E402
import prompting  # noqa: E402
import review_logic  # noqa: E402

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import types as T  # noqa: E402

spark = SparkSession.builder.getOrCreate()
CAT = args.catalog
SILVER = f"{CAT}.silver"
RATE_CARD_PATH = args.rate_card_path or f"/Volumes/{CAT}/landing/rate_cards/"
DOC = canonical.load_yaml(args.rate_cards_yaml)
CARDS = canonical.cards(DOC)


def sql_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


# ─────────────────────────────── parse ───────────────────────────────
def step_parse() -> None:
    cards_df = spark.createDataFrame(
        [(c["card_id"], c["doc_file"], c["language"], c["issuer"], c["title"], bool(c["is_cross_language_copy"]), c.get("same_as"))
         for c in CARDS],
        "card_id STRING, doc_file STRING, language STRING, issuer STRING, title STRING, is_cross_language_copy BOOLEAN, same_as STRING")
    cards_df.createOrReplaceTempView("ce_cards")
    spark.sql(f"""
        CREATE OR REPLACE TABLE {SILVER}.rate_card_parsed
        COMMENT 'Rate-card PDFs parsed with ai_parse_document (v2.0). One row per document.'
        AS
        WITH files AS (
          SELECT path, content, length AS file_bytes, modificationTime AS file_modified_at,
                 regexp_extract(path, '([^/]+)$', 1) AS doc_file
          FROM read_files({sql_str(RATE_CARD_PATH)}, format => 'binaryFile', pathGlobFilter => '*.pdf')
        ),
        parsed AS (
          SELECT f.*, ai_parse_document(f.content, map('version', '2.0', 'descriptionElementTypes', '')) AS parsed
          FROM files f
        )
        SELECT c.card_id, p.doc_file, p.path, c.language, c.issuer, c.title, c.is_cross_language_copy, c.same_as,
               p.file_bytes, p.file_modified_at, p.parsed,
               concat_ws('\\n', transform(cast(p.parsed:document:elements AS ARRAY<VARIANT>),
                                          e -> e:content::STRING)) AS text_blocks,
               size(cast(p.parsed:document:pages AS ARRAY<VARIANT>)) AS n_pages,
               size(cast(p.parsed:document:elements AS ARRAY<VARIANT>)) AS n_elements,
               size(filter(cast(p.parsed:document:elements AS ARRAY<VARIANT>), e -> e:type::STRING = 'table')) AS n_tables,
               nullif(p.parsed:error_status::STRING, '[]') AS parse_error,
               CASE WHEN p.parsed IS NULL THEN 'ERROR'
                    WHEN size(cast(p.parsed:document:elements AS ARRAY<VARIANT>)) = 0 THEN 'EMPTY'
                    WHEN nullif(nullif(p.parsed:error_status::STRING, '[]'), '') IS NOT NULL THEN 'PARTIAL'
                    ELSE 'OK' END AS parse_status,
               current_timestamp() AS parsed_at
        FROM parsed p LEFT JOIN ce_cards c ON c.doc_file = p.doc_file
    """)
    n = spark.table(f"{SILVER}.rate_card_parsed").count()
    print(f"[parse] documents parsed: {n}")
    unknown = spark.sql(f"SELECT doc_file FROM {SILVER}.rate_card_parsed WHERE card_id IS NULL").collect()
    if unknown:
        print(f"[parse] WARNING: files with no card in the YAML: {[r.doc_file for r in unknown]}")


# ─────────────────────────────── extract ───────────────────────────────
KEY_FIELDS = ["vendor_id", "product_family", "cost_type", "fee_basis", "capacity", "side", "rate", "currency",
              "effective_from", "effective_to"]
ALL_FIELDS = [f for f in prompting.extraction_schema()["fee_lines"]["items"]["properties"].keys()]


def step_extract() -> None:
    schema = json.dumps(prompting.extraction_schema(), ensure_ascii=False)
    instr = prompting.instructions()
    num = {"rate", "tier_min", "tier_max", "floor_per_trade", "cap_per_trade", "gst_rate"}
    boo = {"is_pass_through", "is_discount_or_waiver"}
    cols = []
    for f in ALL_FIELDS:
        if f in num:
            cols.append(f"try_cast(l:{f}:value::STRING AS DOUBLE) AS {f}")
        elif f in boo:
            cols.append(f"try_cast(l:{f}:value::STRING AS BOOLEAN) AS {f}")
        elif f in ("effective_from", "effective_to"):
            cols.append(f"try_cast(l:{f}:value::STRING AS DATE) AS {f}")
        else:
            cols.append(f"l:{f}:value::STRING AS {f}")
    conf_map = ", ".join(f"'{f}', l:{f}:confidence_score::DOUBLE" for f in ALL_FIELDS if f not in ("evidence", "item_ref"))
    key_conf = ", ".join(f"l:{f}:confidence_score::DOUBLE" for f in KEY_FIELDS)
    spark.sql(f"""
        CREATE OR REPLACE TABLE {SILVER}.fee_schedule_extracted
        COMMENT 'Fee lines extracted from parsed rate cards with ai_extract v2.1 (per-field confidence scores). Unreviewed.'
        AS
        WITH x AS (
          SELECT /*+ REPARTITION(20) */ card_id, doc_file, language,
                 ai_extract(parsed, {sql_str(schema)},
                            map('version', '2.1', 'enableConfidenceScores', 'true', 'instructions', {sql_str(instr)})) AS res
          FROM {SILVER}.rate_card_parsed
          WHERE parse_status IN ('OK', 'PARTIAL') AND card_id IS NOT NULL
        ),
        lines AS (
          SELECT card_id, doc_file, language, res:error_message::STRING AS extraction_error, pos AS line_index, l
          FROM x LATERAL VIEW OUTER posexplode(cast(res:response:fee_lines AS ARRAY<VARIANT>)) t AS pos, l
        )
        SELECT card_id, doc_file, language AS source_language, line_index, {", ".join(cols)},
               map({conf_map}) AS field_confidence,
               aggregate(filter(array({key_conf}), c -> c IS NOT NULL), 0D, (acc, c) -> acc + c)
                 / greatest(size(filter(array({key_conf}), c -> c IS NOT NULL)), 1) AS extraction_confidence,
               array_min(filter(array({key_conf}), c -> c IS NOT NULL)) AS min_field_confidence,
               'ai_extract v2.1' AS extraction_method, extraction_error, current_timestamp() AS extracted_at
        FROM lines
        WHERE l IS NOT NULL OR extraction_error IS NOT NULL
    """)
    stats = spark.sql(f"""SELECT count(*) n, count(DISTINCT card_id) cards, round(avg(extraction_confidence), 3) conf,
                                 sum(CASE WHEN extraction_error IS NOT NULL THEN 1 ELSE 0 END) errs
                          FROM {SILVER}.fee_schedule_extracted""").collect()[0]
    print(f"[extract] lines={stats.n} cards={stats.cards} mean_confidence={stats.conf} errors={stats.errs}")


# ─────────────────────────────── review ───────────────────────────────
def step_review() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ak = canonical.answer_key(DOC)
    ak_schema = T.StructType([
        T.StructField("card_id", T.StringType()), T.StructField("fee_id", T.StringType()), T.StructField("vendor_id", T.StringType()),
        T.StructField("cost_type", T.StringType()), T.StructField("fee_basis", T.StringType()), T.StructField("product_family", T.StringType()),
        T.StructField("capacity", T.StringType()), T.StructField("side", T.StringType()), T.StructField("rate", T.DoubleType()),
        T.StructField("currency", T.StringType()), T.StructField("tier_basis", T.StringType()), T.StructField("tier_min", T.DoubleType()),
        T.StructField("tier_max", T.DoubleType()), T.StructField("tier_type", T.StringType()), T.StructField("floor_per_trade", T.DoubleType()),
        T.StructField("cap_per_trade", T.DoubleType()), T.StructField("is_pass_through", T.BooleanType()),
        T.StructField("is_discount_or_waiver", T.BooleanType()), T.StructField("gst_rate", T.DoubleType()),
        T.StructField("gst_recoverable_pct", T.DoubleType()), T.StructField("effective_from", T.StringType()),
        T.StructField("effective_to", T.StringType()), T.StructField("legal_entity", T.StringType()),
        T.StructField("description", T.StringType()), T.StructField("description_local", T.StringType()),
        T.StructField("source_doc", T.StringType()), T.StructField("source_language", T.StringType()),
        T.StructField("is_cross_language_copy", T.BooleanType()), T.StructField("same_as", T.StringType()),
    ])
    rows = [tuple(r.get(f.name) for f in ak_schema.fields) for r in ak]
    (spark.createDataFrame(rows, ak_schema)
        .selectExpr("*", "to_date(effective_from) AS effective_from_d", "to_date(effective_to) AS effective_to_d")
        .drop("effective_from", "effective_to")
        .withColumnRenamed("effective_from_d", "effective_from").withColumnRenamed("effective_to_d", "effective_to")
        .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{SILVER}.rate_card_answer_key"))
    spark.sql(f"COMMENT ON TABLE {SILVER}.rate_card_answer_key IS 'Canonical fee lines per rate-card document (analyst answer key; RC03 = Traditional Chinese edition of RC02).'")

    ext_rows = [r.asDict(recursive=True) for r in spark.table(f"{SILVER}.fee_schedule_extracted").collect()]
    by_card_ext: dict[str, list] = {}
    for r in ext_rows:
        if r.get("line_index") is None:
            continue
        by_card_ext.setdefault(r["card_id"], []).append(r)
    by_card_can: dict[str, list] = {}
    for r in ak:
        by_card_can.setdefault(r["card_id"], []).append(r)

    copies = {c["card_id"] for c in CARDS if c["is_cross_language_copy"]}
    out = []
    for card_id, can_lines in by_card_can.items():
        out += review_logic.review_card(card_id, can_lines, by_card_ext.get(card_id, []), analyst=args.analyst,
                                        reviewed_at=now, is_cross_language_copy=card_id in copies)
    for card_id in sorted(set(by_card_ext) - set(by_card_can)):  # documents with no canonical card
        out += review_logic.review_card(card_id, [], by_card_ext[card_id], analyst=args.analyst, reviewed_at=now)

    comp_t = T.ArrayType(T.StructType([T.StructField("field", T.StringType()), T.StructField("canonical_value", T.StringType()),
                                       T.StructField("extracted_value", T.StringType()), T.StructField("is_match", T.BooleanType()),
                                       T.StructField("confidence", T.DoubleType())]))
    rv_schema = T.StructType([
        T.StructField("card_id", T.StringType()), T.StructField("fee_id", T.StringType()), T.StructField("source_language", T.StringType()),
        T.StructField("is_cross_language_copy", T.BooleanType()), T.StructField("line_index", T.IntegerType()),
        T.StructField("item_ref", T.StringType()), T.StructField("status", T.StringType()), T.StructField("match_score", T.DoubleType()),
        T.StructField("mismatched_fields", T.ArrayType(T.StringType())), T.StructField("field_comparison", comp_t),
        T.StructField("extraction_confidence", T.DoubleType()), T.StructField("min_field_confidence", T.DoubleType()),
        T.StructField("evidence", T.StringType()), T.StructField("corrected_by", T.StringType()),
        T.StructField("correction_reason", T.StringType()), T.StructField("reviewed_at", T.TimestampType()),
        T.StructField("analyst", T.StringType()),
    ])
    rv = spark.createDataFrame([tuple(r.get(f.name) for f in rv_schema.fields) for r in out], rv_schema)
    rv.createOrReplaceTempView("ce_fee_schedule_review_new")
    # Rows built in Python carry no lineage: read the confidence from fee_schedule_extracted in SQL (1:1 on card_id +
    # line_index; missed lines have none) so Unity Catalog records the extracted → review edge.
    cols = ", ".join("coalesce(e.extraction_confidence, v.extraction_confidence) AS extraction_confidence"
                     if f.name == "extraction_confidence" else f"v.{f.name}" for f in rv_schema.fields)
    spark.sql(f"""
        CREATE OR REPLACE TABLE {SILVER}.fee_schedule_review AS
        SELECT {cols} FROM ce_fee_schedule_review_new v
        LEFT JOIN {SILVER}.fee_schedule_extracted e ON e.card_id = v.card_id AND e.line_index = v.line_index
    """)
    spark.sql(f"COMMENT ON TABLE {SILVER}.fee_schedule_review IS 'Analyst review of extracted fee lines vs the source documents (simulated reviewer: {args.analyst}). status MATCHED / CORRECTED / MISSED / SPURIOUS with field-level comparison.'")

    spark.sql(f"""
        CREATE OR REPLACE TABLE {SILVER}.fee_schedule_extraction_summary
        COMMENT 'Extraction accuracy per rate card (expected vs extracted vs matched first time).'
        AS
        SELECT r.card_id, p.doc_file, r.source_language, any_value(p.issuer) AS issuer,
               count_if(r.status <> 'SPURIOUS') AS lines_expected,
               count_if(r.status IN ('MATCHED','CORRECTED','SPURIOUS')) AS lines_extracted,
               count_if(r.status = 'MATCHED') AS matched_first_time,
               count_if(r.status = 'CORRECTED') AS corrected,
               count_if(r.status = 'MISSED') AS missed,
               count_if(r.status = 'SPURIOUS') AS spurious,
               round(count_if(r.status = 'MATCHED') / nullif(count_if(r.status <> 'SPURIOUS'), 0), 4) AS first_time_accuracy,
               round(avg(r.extraction_confidence), 4) AS mean_confidence,
               max(r.reviewed_at) AS reviewed_at
        FROM {SILVER}.fee_schedule_review r LEFT JOIN {SILVER}.rate_card_parsed p USING (card_id)
        GROUP BY r.card_id, p.doc_file, r.source_language
    """)
    s = spark.sql(f"""SELECT source_language, sum(lines_expected) e, sum(matched_first_time) m, sum(corrected) c, sum(missed) x,
                             sum(spurious) sp, round(avg(mean_confidence),3) conf
                      FROM {SILVER}.fee_schedule_extraction_summary GROUP BY source_language ORDER BY source_language""").collect()
    for r in s:
        print(f"[review] {r.source_language}: expected={r.e} matched={r.m} corrected={r.c} missed={r.x} spurious={r.sp} conf={r.conf}")


# ─────────────────────────────── publish ───────────────────────────────
def step_publish() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [dict(ln, approved_by=args.analyst, approved_at=now) for ln in canonical.approved_lines(DOC)]
    sch = T.StructType([
        T.StructField("fee_id", T.StringType(), False), T.StructField("card_id", T.StringType()), T.StructField("vendor_id", T.StringType()),
        T.StructField("cost_type", T.StringType()), T.StructField("fee_basis", T.StringType()), T.StructField("product_family", T.StringType()),
        T.StructField("capacity", T.StringType()), T.StructField("side", T.StringType()), T.StructField("rate", T.DoubleType()),
        T.StructField("currency", T.StringType()), T.StructField("tier_basis", T.StringType()), T.StructField("tier_min", T.DoubleType()),
        T.StructField("tier_max", T.DoubleType()), T.StructField("tier_type", T.StringType()), T.StructField("floor_per_trade", T.DoubleType()),
        T.StructField("cap_per_trade", T.DoubleType()), T.StructField("is_pass_through", T.BooleanType()),
        T.StructField("is_discount_or_waiver", T.BooleanType()), T.StructField("gst_rate", T.DoubleType()),
        T.StructField("gst_recoverable_pct", T.DoubleType()), T.StructField("effective_from", T.StringType()),
        T.StructField("effective_to", T.StringType()), T.StructField("legal_entity", T.StringType()),
        T.StructField("description", T.StringType()), T.StructField("source_doc", T.StringType()),
        T.StructField("source_language", T.StringType()), T.StructField("approved_by", T.StringType()),
        T.StructField("approved_at", T.TimestampType()),
    ])
    df = spark.createDataFrame([tuple(r.get(f.name) for f in sch.fields) for r in rows], sch)
    df.createOrReplaceTempView("ce_fee_schedule_new")
    # Review metadata is joined in SQL rather than looked up in Python, so Unity Catalog records the
    # review → fee_schedule edge (completing PDFs → parsed → extracted → review → fee_schedule → Gold).
    contract = f"n.source_doc = '{canonical.CONTRACT_REGISTER_DOC}'"
    derived = {
        "effective_from": "to_date(n.effective_from)", "effective_to": "to_date(n.effective_to)",
        "extraction_confidence": f"CASE WHEN {contract} THEN NULL ELSE r.extraction_confidence END",
        "extraction_status": f"CASE WHEN {contract} THEN 'STRUCTURED_SOURCE' WHEN r.fee_id IS NULL THEN 'NOT_REVIEWED' "
                             "ELSE r.status END",
        "approved_at": f"CASE WHEN {contract} OR r.fee_id IS NULL THEN n.approved_at ELSE r.reviewed_at END",
    }
    select = ", ".join(f"{derived.get(c, 'n.' + c)} AS {c}" for c in canonical.FEE_SCHEDULE_COLUMNS)
    spark.sql(f"""
        CREATE OR REPLACE TABLE {SILVER}.fee_schedule
        COMMENT 'Analyst-approved fee schedule (exchange, clearing, settlement, levies, taxes, brokerage, fixed). Source of truth for expected cost. Rates equal the source documents; extraction metadata from the AI extraction + analyst review.'
        AS SELECT {select}
        FROM ce_fee_schedule_new n
        LEFT JOIN (SELECT card_id, fee_id, status, extraction_confidence, reviewed_at
                   FROM {SILVER}.fee_schedule_review WHERE fee_id IS NOT NULL) r
          ON r.card_id = n.card_id AND r.fee_id = n.fee_id
        ORDER BY n.vendor_id, n.product_family, n.cost_type, n.fee_id
    """)
    assert spark.table(f"{SILVER}.fee_schedule").columns == canonical.FEE_SCHEDULE_COLUMNS, "column contract drift"

    fr = canonical.fail_cost_rules(DOC)
    fr_schema = ("market STRING, vendor_id STRING, rule_type STRING, pct_per_day DOUBLE, min_per_day DOUBLE, max_per_day DOUBLE, "
                 "currency STRING, buy_in_after_days INT, invoiced STRING, source_doc STRING, confirmed BOOLEAN")
    spark.createDataFrame([tuple(r.values()) for r in fr], fr_schema).write.mode("overwrite").option("overwriteSchema", "true") \
        .saveAsTable(f"{SILVER}.fail_cost_rule")
    spark.sql(f"COMMENT ON TABLE {SILVER}.fail_cost_rule IS 'Per-market settlement-fail cost rules (per-day fee with min/max, close-out, buy-in timing). Only AU is from a published-style schedule; others illustrative — confirm with client Operations.'")
    print(f"[publish] fee_schedule rows={len(rows)} fail_cost_rule rows={len(fr)}")


# ─────────────────────────────── guard ───────────────────────────────
def step_guard() -> None:
    expected = len(canonical.approved_lines(DOC))
    expected_rules = len(canonical.fail_cost_rules(DOC))
    r = spark.sql(f"""
        SELECT count(*) AS n, count(DISTINCT fee_id) AS n_ids, count_if(rate IS NULL) AS null_rates,
               count_if(approved_by IS NULL) AS unapproved,
               count_if(effective_to IS NOT NULL AND effective_to < effective_from) AS bad_dates
        FROM {SILVER}.fee_schedule""").collect()[0]
    n_rules = spark.table(f"{SILVER}.fail_cost_rule").count()
    problems = []
    if r.n != expected:
        problems.append(f"fee_schedule rows {r.n} != canonical {expected}")
    if r.n_ids != r.n:
        problems.append("duplicate fee_id")
    if r.null_rates or r.unapproved or r.bad_dates:
        problems.append(f"null_rates={r.null_rates} unapproved={r.unapproved} bad_dates={r.bad_dates}")
    if n_rules != expected_rules:
        problems.append(f"fail_cost_rule rows {n_rules} != canonical {expected_rules}")
    if problems:
        raise RuntimeError("Fee schedule guard failed: " + "; ".join(problems))
    print(f"[guard] OK — fee_schedule={r.n} lines, fail_cost_rule={n_rules} rules")


STEPS = {"parse": step_parse, "extract": step_extract, "review": step_review, "publish": step_publish, "guard": step_guard}
if args.step == "all":
    for name in ("parse", "extract", "review", "publish", "guard"):
        STEPS[name]()
else:
    STEPS[args.step]()
