#!/usr/bin/env bash
# One-time per workspace: create the demo catalog (Default Storage accounts reject the catalogs API without a location).
# Usage: scripts/bootstrap_catalog.sh <profile> <warehouse_id> [catalog] [managed_location]
set -euo pipefail
PROFILE="${1:?profile}"; WAREHOUSE="${2:?warehouse id}"; CATALOG="${3:-cost_explain}"; LOCATION="${4:-}"
LOC_CLAUSE=""; [[ -n "$LOCATION" ]] && LOC_CLAUSE="MANAGED LOCATION '${LOCATION}'"
databricks experimental aitools tools query --warehouse "$WAREHOUSE" --profile "$PROFILE" \
  "CREATE CATALOG IF NOT EXISTS ${CATALOG} ${LOC_CLAUSE} COMMENT 'Trade Cost Explain demo — Meridian Group APAC Global Markets (synthetic). All figures illustrative.'"
