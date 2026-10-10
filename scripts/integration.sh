#!/usr/bin/env bash
# Integration check with the real, locally installed tools: the golden report on the fixtures.
# Usage: scripts/integration.sh            (compare)
#        scripts/integration.sh --update   (re-record after a deliberate tool update)
set -euo pipefail
cd "$(dirname "$0")/.."
export SWE_METRICS_GOLDEN=1
[ "${1:-}" = "--update" ] && export SWE_METRICS_GOLDEN=update
exec python -m pytest -q -s tests/test_golden.py
