"""Build reports the caller passes in (`--report kind=path`): the known kinds and how the option is parsed."""
from __future__ import annotations

from collections.abc import Iterable

REPORT_KINDS = {
    "junit": "JUnit XML test results (file or directory of files)",
    "jacoco": "JaCoCo XML coverage report",
    "cobertura": "Cobertura XML coverage report (also coverage.py's `coverage xml`)",
    "lcov": "LCOV coverage trace (lcov.info)",
    "pit": "PIT mutations.xml",
    "stryker": "Stryker mutation-testing JSON report",
    "classes": "Directory of compiled classes or a JAR (Java dependency structure)",
}


def parse_reports(values: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """`kind=path` options grouped by kind; ValueError for a malformed option or an unknown kind."""
    reports: dict[str, list[str]] = {}
    for value in values:
        kind, separator, path = value.partition("=")
        if not separator or not path:
            raise ValueError(f"--report expects kind=path, got '{value}'")
        if kind not in REPORT_KINDS:
            raise ValueError(f"unknown report kind '{kind}' (known: {sorted(REPORT_KINDS)})")
        reports.setdefault(kind, []).append(path)
    return {kind: tuple(paths) for kind, paths in reports.items()}
