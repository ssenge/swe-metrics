# AGENTS.md: rules for agents working on swe-metrics

swe-metrics measures software (code, IaC, docs, architecture models) and reports the metrics. Read `docs/implementation-plan.md` first.

## Rules
- **Measure, never judge.** No thresholds, pass/fail, grades or combined scores in the package. Interpretation belongs to the caller.
- **Stateless and read-only.** One input, one report; never modify the input.
- **Consumer-agnostic.** Never import, name or special-case any consumer of swe-metrics.
- **Layers:** `core` is pure (no I/O); analyzers import only `core` and never each other; `cli` is the composition root.
- **Small units:** functions ≤ 50 lines, cognitive complexity ≤ 15, cyclomatic ≤ 10, ≤ 5 parameters; modules ≤ 400 lines.
- **Docstrings:** every module and function has a one-line docstring saying what it is responsible for. Comments explain why, not what.
- **Tests:** every branch of non-trivial logic is tested (pytest). Branch coverage ≥ 85 %.
- **Never weaken the gate** to make a change pass. Stop and ask instead.
- **Before you finish a change, run `scripts/gate.sh`.** It must print `GATE PASSED`.
