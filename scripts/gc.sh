#!/usr/bin/env bash
# Gated commit: stage everything and commit only if scripts/gate.sh passes. Usage: scripts/gc.sh "message"
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
if PATH=$PWD/.venv/bin:$HOME/.local/bin:$PATH scripts/gate.sh > .gate.log 2>&1; then
  git add -A && git commit -q -F - <<MSG && git log --oneline -1
$1
MSG
else
  grep -E "^[A-Z]+[0-9]{3} |error:|warning:|FAILED|broken|changed lines" .gate.log | head -20
  echo "GATE FAILED - not committed (full log: .gate.log)"; exit 1
fi
