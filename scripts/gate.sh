#!/usr/bin/env bash
# swe-metrics quality gate (docs/implementation-plan.md §8). Exit 0 = pass.
# Run from the repo root. Thresholds live in pyproject.toml; the rest is here.
# GATE_BASE: the ref the change-size limit compares against (CI: the PR's base branch).
set -uo pipefail
SRC=(swe_metrics tests)            # code and tests; coverage counts only CODE
CODE=(swe_metrics)
BASE=${GATE_BASE:-HEAD}
MAX_CHANGED_LINES=400
fail=0
run() { echo "== $*"; "$@" || fail=1; }

for tool in ruff mypy complexipy lizard interrogate pytest bandit pip-audit lint-imports gitleaks npx; do
  command -v "$tool" >/dev/null || { echo "missing tool: $tool"; fail=1; }
done

run ruff check "${SRC[@]}"
run mypy "${SRC[@]}"
run complexipy "${SRC[@]}"
run lizard -C 10 -L 50 -w "${SRC[@]}"
run interrogate "${SRC[@]}"
run pytest -q "${CODE[@]/#/--cov=}" --cov-report=term-missing:skip-covered
run bandit -q -r "${SRC[@]}" --severity-level high --exclude '*/test_*.py'
run pip-audit --progress-spinner off .
run gitleaks git --no-banner --redact .
run npx -y jscpd@4.0.5 --silent --threshold 3 --min-lines 5 "${SRC[@]}"
run lint-imports                  # layer contracts in pyproject.toml [tool.importlinter]
run python scripts/self_check.py  # dogfooding: swe-metrics measures itself against the same limits

echo "== module length <= 400 lines"
for f in $(find "${SRC[@]}" -name '*.py'); do
  n=$(wc -l < "$f")
  if [ "$n" -gt 400 ]; then echo "$f: $n lines"; fail=1; fi
done

echo "== changed lines vs $BASE <= $MAX_CHANGED_LINES (code only, tests and test data excluded)"
# Whole-repo diff with rename detection (a moved file counts only its edits), then filtered to code paths.
CODE_RE='(^|[{ ])swe_metrics[/}]'
changed=$( { git diff -M --numstat "$BASE" | awk -F'\t' -v re="$CODE_RE" '$3 ~ re && $3 !~ /(^|\/)tests?[\/_]/'
  git ls-files --others --exclude-standard -- "${CODE[@]}" ':(exclude)**/test_*.py' \
    | while read -r f; do printf '%s\t0\t%s\n' "$(wc -l < "$f")" "$f"; done
} | awk -F'\t' '{ s += $1 + $2 } END { print s + 0 }')     # untracked new files count too
echo "$changed changed lines"
if [ "$changed" -gt "$MAX_CHANGED_LINES" ]; then fail=1; fi

if [ "$fail" -ne 0 ]; then echo "GATE FAILED"; else echo "GATE PASSED"; fi
exit "$fail"
