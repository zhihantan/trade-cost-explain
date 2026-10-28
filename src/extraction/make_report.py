"""Regenerate the results section of docs/EXTRACTION.md from the review tables.

Usage: python src/extraction/make_report.py --profile fe-vm-zh-serverless --warehouse <id>
Replaces the block between '<!-- RESULTS -->' and '<!-- /RESULTS -->' (hand-written sections around it are kept).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "EXTRACTION.md"
MARK = "<!-- RESULTS -->"
END = "<!-- /RESULTS -->"


def q(sql: str, profile: str, wh: str) -> list[dict]:
    out = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", "--warehouse", wh, "--profile", profile, sql],
                         check=True, capture_output=True, text=True).stdout
    start = out.find("[")
    return json.loads(out[start:]) if start >= 0 else []


def table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(h for _, h in cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = "".join("| " + " | ".join("" if r.get(k) in (None, "null") else str(r.get(k)) for k, _ in cols) + " |\n" for r in rows)
    return head + body


def pct(x) -> str:
    return "" if x in (None, "null", "") else f"{float(x) * 100:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--warehouse", required=True)
    a = ap.parse_args()
    S = "cost_explain.silver"
    per_lang = q(f"""SELECT source_language, count(*) cards, sum(lines_expected) lines_expected, sum(lines_extracted) lines_extracted,
                         sum(matched_first_time) matched, sum(corrected) corrected, sum(missed) missed, sum(spurious) spurious,
                         round(sum(matched_first_time)/sum(lines_expected),4) acc, round(avg(mean_confidence),3) conf
                  FROM {S}.fee_schedule_extraction_summary GROUP BY source_language ORDER BY source_language""", a.profile, a.warehouse)
    tot = q(f"""SELECT 'all' source_language, count(*) cards, sum(lines_expected) lines_expected, sum(lines_extracted) lines_extracted,
                    sum(matched_first_time) matched, sum(corrected) corrected, sum(missed) missed, sum(spurious) spurious,
                    round(sum(matched_first_time)/sum(lines_expected),4) acc, round(avg(mean_confidence),3) conf
                FROM {S}.fee_schedule_extraction_summary""", a.profile, a.warehouse)
    per_card = q(f"""SELECT card_id, source_language, lines_expected, lines_extracted, matched_first_time, corrected, missed, spurious,
                         first_time_accuracy, mean_confidence FROM {S}.fee_schedule_extraction_summary ORDER BY card_id""", a.profile, a.warehouse)
    fields = q(f"""SELECT r.source_language, f.field, count(*) corrections, round(avg(f.confidence),3) mean_conf
                   FROM {S}.fee_schedule_review r LATERAL VIEW explode(r.field_comparison) t AS f
                   WHERE r.status = 'CORRECTED' AND NOT f.is_match
                   GROUP BY r.source_language, f.field ORDER BY r.source_language, corrections DESC""", a.profile, a.warehouse)
    log = q(f"""SELECT card_id, coalesce(fee_id,'—') fee_id, coalesce(item_ref,'—') item_ref, status,
                       round(extraction_confidence,3) conf, correction_reason
                FROM {S}.fee_schedule_review WHERE status <> 'MATCHED' ORDER BY card_id, item_ref""", a.profile, a.warehouse)
    sep = q(f"""SELECT status, count(*) n, round(avg(extraction_confidence),3) conf, round(avg(min_field_confidence),3) min_conf
                FROM {S}.fee_schedule_review WHERE status IN ('MATCHED','CORRECTED','SPURIOUS') GROUP BY status ORDER BY status""",
            a.profile, a.warehouse)
    cross = q(f"""SELECT count_if(status='MATCHED') matched, count_if(status='CORRECTED') corrected, count_if(status='MISSED') missed,
                         count_if(status='SPURIOUS') spurious, count(*) n
                  FROM {S}.fee_schedule_review WHERE card_id = 'RC03'""", a.profile, a.warehouse)
    field_acc = q(f"""SELECT r.source_language, count(*) fields, count_if(f.is_match) correct,
                          round(count_if(f.is_match) / count(*), 4) field_accuracy
                   FROM {S}.fee_schedule_review r LATERAL VIEW explode(r.field_comparison) t AS f
                   WHERE r.status IN ('MATCHED','CORRECTED')
                   GROUP BY ROLLUP(r.source_language) ORDER BY r.source_language NULLS LAST""", a.profile, a.warehouse)
    counts = q(f"""SELECT (SELECT count(*) FROM {S}.rate_card_parsed) parsed, (SELECT count(*) FROM {S}.fee_schedule_extracted) extracted,
                          (SELECT count(*) FROM {S}.rate_card_answer_key) answer_key, (SELECT count(*) FROM {S}.fee_schedule_review) review,
                          (SELECT count(*) FROM {S}.fee_schedule) fee_schedule, (SELECT count(*) FROM {S}.fail_cost_rule) fail_rules""",
               a.profile, a.warehouse)[0]

    for r in per_lang + tot:
        r["acc"] = pct(r["acc"])
    for r in per_card:
        r["first_time_accuracy"] = pct(r["first_time_accuracy"])
    lang_cols = [("source_language", "Language"), ("cards", "Cards"), ("lines_expected", "Lines expected"),
                 ("lines_extracted", "Extracted"), ("matched", "Matched first time"), ("corrected", "Corrected"),
                 ("missed", "Missed"), ("spurious", "Spurious"), ("acc", "First-time accuracy"), ("conf", "Mean confidence")]
    out = [MARK, "", "## Results (latest run)", ""]
    out.append(f"Tables: `rate_card_parsed` {counts['parsed']} docs · `fee_schedule_extracted` {counts['extracted']} lines · "
               f"`rate_card_answer_key` {counts['answer_key']} · `fee_schedule_review` {counts['review']} · "
               f"`fee_schedule` **{counts['fee_schedule']}** approved lines · `fail_cost_rule` {counts['fail_rules']} rules.")
    out += ["", "### By language", "", table(per_lang + tot, lang_cols)]
    for r in field_acc:
        r["source_language"] = r.get("source_language") or "all"
        r["field_accuracy"] = pct(r["field_accuracy"])
    out += ["Field-level accuracy (each line has 20 compared fields):", "",
            table(field_acc, [("source_language", "Language"), ("fields", "Fields compared"), ("correct", "Correct first time"),
                              ("field_accuracy", "Field accuracy")])]
    out += ["### By card", "", table(per_card, [("card_id", "Card"), ("source_language", "Lang"), ("lines_expected", "Expected"),
                                               ("lines_extracted", "Extracted"), ("matched_first_time", "Matched"),
                                               ("corrected", "Corrected"), ("missed", "Missed"), ("spurious", "Spurious"),
                                               ("first_time_accuracy", "First-time"), ("mean_confidence", "Mean conf.")])]
    if cross:
        c = cross[0]
        out += ["### Cross-language check (RC03 繁中 vs RC02 EN)", "",
                f"The Traditional Chinese edition of the derivatives card produced {c['matched']} lines identical to the English "
                f"edition, {c['corrected']} needing a correction, {c['missed']} missed and {c['spurious']} spurious.", ""]
    out += ["### Fields the analyst had to correct", "", table(fields, [("source_language", "Language"), ("field", "Field"),
                                                                       ("corrections", "Corrections"), ("mean_conf", "Mean field confidence")])]
    out += ["### Does the confidence score help triage?", "", table(sep, [("status", "Status"), ("n", "Lines"), ("conf", "Mean confidence"),
                                                                         ("min_conf", "Mean lowest-field confidence")])]
    out += ["### Correction log", "", table(log, [("card_id", "Card"), ("fee_id", "Fee"), ("item_ref", "Item"), ("status", "Status"),
                                                  ("conf", "Conf."), ("correction_reason", "Reason")])]
    text = DOC.read_text(encoding="utf-8")
    head, rest = text.split(MARK, 1)
    tail = rest.split(END, 1)[1] if END in rest else "\n"
    DOC.write_text(head + "\n".join(out) + "\n" + END + tail, encoding="utf-8")
    print("written", DOC)


if __name__ == "__main__":
    main()
