#!/usr/bin/env bash
# Re-render the 20 rate-card PDFs from src/datagen/config/rate_cards.yaml and upload them (plus the ref CSVs).
# Usage: src/rate_cards/publish.sh <profile> [catalog]
# Safe to re-run after any YAML change: PDFs and CSVs are overwritten in place.
set -euo pipefail
PROFILE="${1:?profile}"; CATALOG="${2:-cost_explain}"
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
if [[ ! -x "$HERE/.venv/bin/python" ]]; then
  uv venv -q --python 3.12 "$HERE/.venv"
  uv pip install -q --python "$HERE/.venv/bin/python" plutoprint pyyaml pypdf
fi
"$HERE/.venv/bin/python" "$HERE/render.py" --yaml "$REPO/src/datagen/config/rate_cards.yaml" --out "$HERE/out"
databricks fs cp -r --overwrite "$HERE/out/pdf" "dbfs:/Volumes/$CATALOG/landing/rate_cards" --profile "$PROFILE"
databricks fs mkdir "dbfs:/Volumes/$CATALOG/landing/raw/ref" --profile "$PROFILE"
for f in vendor_contracts.csv fail_cost_rule.csv; do
  databricks fs cp --overwrite "$HERE/out/ref/$f" "dbfs:/Volumes/$CATALOG/landing/raw/ref/$f" --profile "$PROFILE"
done
echo "Uploaded $(ls "$HERE/out/pdf" | wc -l | tr -d ' ') PDFs to /Volumes/$CATALOG/landing/rate_cards — now run job ce_fee_extraction."
