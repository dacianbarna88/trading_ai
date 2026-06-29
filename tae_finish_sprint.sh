#!/bin/bash
set -e

MSG="${1:-TAE sprint checkpoint}"

echo "===== TAE FINISH SPRINT ====="

bash tae_checkpoint.sh

echo ""
echo "===== GIT ADD ====="
git add -A

echo ""
echo "===== GIT COMMIT ====="
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "$MSG"
fi

echo ""
echo "===== GIT PUSH ====="
git push

echo ""
echo "===== FINAL STATUS ====="
git status
