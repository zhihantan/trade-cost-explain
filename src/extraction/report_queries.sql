-- Queries behind docs/EXTRACTION.md (run on the cost-explain-wh warehouse).

-- 1. Accuracy per card
SELECT card_id, doc_file, source_language, lines_expected, lines_extracted, matched_first_time, corrected, missed, spurious,
       first_time_accuracy, mean_confidence
FROM cost_explain.silver.fee_schedule_extraction_summary
ORDER BY card_id;

-- 2. Accuracy per language
SELECT source_language,
       count(*) AS cards,
       sum(lines_expected) AS lines_expected,
       sum(lines_extracted) AS lines_extracted,
       sum(matched_first_time) AS matched_first_time,
       sum(corrected) AS corrected,
       sum(missed) AS missed,
       sum(spurious) AS spurious,
       round(sum(matched_first_time) / sum(lines_expected), 4) AS first_time_accuracy,
       round(avg(mean_confidence), 3) AS mean_confidence
FROM cost_explain.silver.fee_schedule_extraction_summary
GROUP BY source_language
ORDER BY source_language;

-- 3. Which fields needed correction, by language
SELECT r.source_language, f.field, count(*) AS corrections,
       round(avg(f.confidence), 3) AS mean_field_confidence
FROM cost_explain.silver.fee_schedule_review r
LATERAL VIEW explode(r.field_comparison) t AS f
WHERE r.status = 'CORRECTED' AND NOT f.is_match
GROUP BY r.source_language, f.field
ORDER BY r.source_language, corrections DESC;

-- 4. Correction log (what the analyst changed)
SELECT card_id, fee_id, item_ref, status, round(extraction_confidence, 3) AS confidence, correction_reason
FROM cost_explain.silver.fee_schedule_review
WHERE status <> 'MATCHED'
ORDER BY card_id, item_ref;

-- 5. Does confidence separate good from bad lines?
SELECT status, count(*) AS lines, round(avg(extraction_confidence), 3) AS mean_conf, round(avg(min_field_confidence), 3) AS mean_min_field_conf
FROM cost_explain.silver.fee_schedule_review
WHERE status IN ('MATCHED', 'CORRECTED', 'SPURIOUS')
GROUP BY status;
