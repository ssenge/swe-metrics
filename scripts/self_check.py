"""Dogfooding: measure swe-metrics with swe-metrics and compare against the gate's limits.

The limits live here, in the gate, not in the package: swe-metrics measures, the caller judges.
Usage: python scripts/self_check.py   (exit 0 = within all limits)
"""
from __future__ import annotations

import json
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# (metric ID, statistic or "value", labels, maximum). Same limits as the gate's own tools.
LIMITS = [
    ("complexity.cyclomatic", "max", {}, 10),
    ("complexity.cognitive", "max", {}, 15),
    ("size.function_length", "max", {}, 50),
    ("size.parameters", "max", {}, 5),
    ("duplication.percent", "value", {}, 3),
    ("secrets.findings", "value", {}, 0),
]


def measure() -> dict:
    """The report of swe-metrics on its own package code (tests and fixtures excluded)."""
    argv = [sys.executable, "-m", "swe_metrics.cli.main", "measure", str(ROOT),
            "--only", "size", "--only", "complexity", "--only", "duplication", "--only", "secrets",
            "--exclude", "tests/*", "--exclude", "fixtures/*", "--exclude", "scripts/*"]
    done = subprocess.run(argv, capture_output=True, text=True, check=True)  # nosec B603
    report: dict = json.loads(done.stdout)
    return report


def violations(report: dict) -> list[str]:
    """Every limit the report exceeds, and every analyzer that didn't run (missing values fail closed)."""
    problems = [f"analyzer {a['id']}: {a['status']} ({a.get('reason', '')})"
                for a in report["analyzers"] if a["status"] == "failed"]
    for metric_id, stat, labels, limit in LIMITS:
        found = [m for m in report["metrics"] if m["id"] == metric_id and m["scope"]["level"] == "target"
                 and m.get("labels", {}) == labels]
        if not found:
            problems.append(f"{metric_id}: not measured")
            continue
        value = found[0]["value"] if stat == "value" else found[0]["stats"][stat]
        if value > limit:
            problems.append(f"{metric_id} {stat} = {value} > {limit}")
    return problems


def main() -> int:
    """Print the result; exit 1 on any violation."""
    problems = violations(measure())
    print("\n".join(problems) if problems else "self-measurement within limits")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
