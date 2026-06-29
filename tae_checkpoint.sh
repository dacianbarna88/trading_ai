#!/usr/bin/env bash
# TAE Governance Checkpoint — validation gate (commit via tae_finish_sprint.sh)
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

PYTHON="${PYTHON:-python3}"
FAIL=0
STEP=0
FINISH_MODE="${TAE_FINISH_SPRINT:-0}"

banner() {
  echo ""
  echo "===== $1 ====="
}

run_step() {
  STEP=$((STEP + 1))
  echo ""
  echo "--- [$STEP] $1 ---"
}

banner "TAE GOVERNANCE CHECKPOINT"
echo "Project: $PROJECT_DIR"
echo "Time:    $(date '+%Y-%m-%d %H:%M:%S')"
if [[ "$FINISH_MODE" == "1" ]]; then
  echo "Mode:    finish-sprint (autonomous commit follows)"
fi

# 1. Regenerate live advisory if demo exists
run_step "Regenerate tae_live_advisory.json (if demo present)"
if [[ -f tae_live_advisory_demo.py ]]; then
  if "$PYTHON" tae_live_advisory_demo.py; then
    echo "OK: tae_live_advisory_demo.py"
  else
    echo "WARN: tae_live_advisory_demo.py exited non-zero"
    FAIL=1
  fi
else
  echo "SKIP: tae_live_advisory_demo.py not found"
fi

# 2. py_compile core runtime UI
run_step "Compile live_bot.py and dashboard_v2.py"
for f in live_bot.py dashboard_v2.py; do
  if [[ -f "$f" ]]; then
    if "$PYTHON" -m py_compile "$f"; then
      echo "OK: $f"
    else
      echo "FAIL: $f"
      FAIL=1
    fi
  else
    echo "SKIP: $f missing"
  fi
done

# 3. py_compile governance modules
run_step "Compile governance / advisory scripts"
GOV_FILES=(
  research_core/governance/advisory_index.py
  research_core/governance/advisory_index_report.py
  research_core/governance/live_advisory_bridge.py
  research_core/governance/live_advisory_runtime.py
  research_core/governance/shadow_validation_ledger.py
  tae_advisory_index_demo.py
  tae_live_advisory_demo.py
  tae_shadow_validation_report.py
  tae_full_ecosystem_review.py
)

for f in "${GOV_FILES[@]}"; do
  if [[ -f "$f" ]]; then
    if "$PYTHON" -m py_compile "$f"; then
      echo "OK: $f"
    else
      echo "FAIL: $f"
      FAIL=1
    fi
  else
    echo "SKIP: $f missing"
  fi
done

# Optional self-check for runtime loader
if [[ -f research_core/governance/live_advisory_runtime.py ]]; then
  run_step "Live advisory runtime self-check"
  if "$PYTHON" research_core/governance/live_advisory_runtime.py; then
    echo "OK: live_advisory_runtime self-check"
  else
    echo "FAIL: live_advisory_runtime self-check"
    FAIL=1
  fi
fi

if [[ -f research_core/governance/shadow_validation_ledger.py ]]; then
  run_step "Shadow validation ledger self-check"
  if "$PYTHON" research_core/governance/shadow_validation_ledger.py; then
    echo "OK: shadow_validation_ledger self-check"
  else
    echo "FAIL: shadow_validation_ledger self-check"
    FAIL=1
  fi
fi

# Optional full TAE health (recommended, non-fatal)
if [[ -f tae_quick_health_check.py ]]; then
  run_step "Quick health check (recommended)"
  if "$PYTHON" tae_quick_health_check.py >/dev/null 2>&1; then
    echo "OK: tae_quick_health_check.py"
  else
    echo "WARN: tae_quick_health_check.py failed or not ready (review manually)"
  fi
fi

# 4. git status
run_step "Git status"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git status --short
  echo ""
  git diff --stat 2>/dev/null || true
else
  echo "WARN: not a git repository"
fi

# 5. Advisory JSON sanity
run_step "Advisory artifact check"
if [[ -f tae_live_advisory.json ]]; then
  if "$PYTHON" -m json.tool tae_live_advisory.json >/dev/null; then
    ACTION=$("$PYTHON" -c "import json; print(json.load(open('tae_live_advisory.json'))['advisory']['action'])" 2>/dev/null || echo "unknown")
    echo "OK: tae_live_advisory.json valid — action=$ACTION"
  else
    echo "FAIL: tae_live_advisory.json invalid JSON"
    FAIL=1
  fi
else
  echo "WARN: tae_live_advisory.json missing"
fi

banner "CHECKPOINT RESULT"
if [[ "$FAIL" -eq 0 ]]; then
  if [[ "$FINISH_MODE" == "1" ]]; then
    echo "Status: CHECKPOINT PASSED — tae_finish_sprint.sh will commit/push"
  else
    echo "Status: CHECKPOINT PASSED"
  fi
else
  echo "Status: ISSUES DETECTED — fix before commit"
fi

if [[ "$FINISH_MODE" != "1" ]]; then
  banner "NEXT STEP"
  cat <<'EOF'
Finish the sprint with one command:

  ./tae_finish_sprint.sh "TAE Sprint X.N — short description"

That runs this checkpoint, stages changes, commits, and pushes.
Update PROJECT_BOOK.md and SESSION_START.md before running finish sprint.
EOF
fi

exit "$FAIL"
