#!/usr/bin/env bash
# TAE Full Ecosystem Review — unified daily observability command (no commit/push)
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

PYTHON="${PYTHON:-python3}"
JSON_OUT="tae_full_ecosystem_review.json"
FAIL=0

echo ""
echo "===== TAE FULL ECOSYSTEM REVIEW ====="
echo "Project: $PROJECT_DIR"
echo "Time:    $(date '+%Y-%m-%d %H:%M:%S')"
echo "Mode:    OBSERVABILITY | FINANCIAL_ANALYSIS | NO_EXECUTION"
echo ""

if ! "$PYTHON" tae_full_ecosystem_review.py; then
  echo "ERROR: tae_full_ecosystem_review.py failed"
  exit 1
fi

echo "--- JSON validation ---"
if ! "$PYTHON" -m json.tool "$JSON_OUT" > /dev/null; then
  echo "ERROR: invalid JSON in $JSON_OUT"
  FAIL=1
else
  echo "OK: $JSON_OUT valid JSON"
fi

echo ""
echo "===== REVIEW COMPLETE ====="
if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi
exit 0
