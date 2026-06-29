#!/usr/bin/env bash
# TAE Finish Sprint — autonomous checkpoint + commit + push
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

MSG="${1:-TAE sprint checkpoint}"
WARN=0

banner() {
  echo ""
  echo "===== $1 ====="
}

warn() {
  echo "WARN: $*"
  WARN=1
}

detect_last_sprint() {
  local session_file="SESSION_START.md"
  local sprint=""

  if [[ ! -f "$session_file" ]]; then
    echo "UNKNOWN"
    return
  fi

  sprint=$(grep -E '^\| \*\*Last completed sprint\*\*' "$session_file" 2>/dev/null \
    | sed -E 's/^\| \*\*Last completed sprint\*\* \| //; s/ \|\s*$//' \
    | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' || true)

  if [[ -z "$sprint" ]]; then
    sprint=$(grep -Ei 'last completed sprint|latest sprint' "$session_file" 2>/dev/null | head -1 \
      | sed -E 's/^[^|]*\| //; s/ \|\s*$//' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' || true)
  fi

  if [[ -z "$sprint" ]]; then
    echo "UNKNOWN"
  else
    echo "$sprint"
  fi
}

journal_status_line() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "$file: MISSING"
    return
  fi
  local lines size
  lines=$(wc -l < "$file" | tr -d ' ')
  size=$(wc -c < "$file" | tr -d ' ')
  echo "$file: present (${lines} lines, ${size} bytes)"
}

banner "TAE FINISH SPRINT"
echo "Project: $PROJECT_DIR"
echo "Time:    $(date '+%Y-%m-%d %H:%M:%S')"
echo "Commit:  $MSG"

banner "CHECKPOINT"
export TAE_FINISH_SPRINT=1
bash tae_checkpoint.sh

banner "JOURNAL CHECK"
if [[ -f PROJECT_BOOK.md ]]; then
  echo "OK: PROJECT_BOOK.md present"
  journal_status_line "PROJECT_BOOK.md"
else
  warn "PROJECT_BOOK.md missing — commit will still proceed"
fi

if [[ -f SESSION_START.md ]]; then
  echo "OK: SESSION_START.md present"
  journal_status_line "SESSION_START.md"
else
  warn "SESSION_START.md missing — commit will still proceed"
fi

LAST_SPRINT="$(detect_last_sprint)"
echo ""
echo "Last completed sprint (detected): $LAST_SPRINT"
if [[ "$LAST_SPRINT" == "UNKNOWN" ]]; then
  warn "Could not detect last completed sprint from SESSION_START.md"
fi

echo ""
echo "PROJECT_BOOK status: $(journal_status_line PROJECT_BOOK.md)"
echo "SESSION_START status: $(journal_status_line SESSION_START.md)"

banner "GIT ADD"
git add -A

banner "GIT COMMIT"
if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "$MSG"
  echo "OK: commit created"
fi

banner "GIT PUSH"
git push
echo "OK: push complete"

banner "FINAL STATUS"
git status

banner "TAE FINISH SPRINT COMPLETE"
if [[ "$WARN" -eq 1 ]]; then
  echo "Completed with warnings — review journal detection above."
else
  echo "All steps completed successfully."
fi
