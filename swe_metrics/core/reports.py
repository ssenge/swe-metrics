"""Build reports the caller passes in (`--report kind=path`): the known kinds and how the option is parsed."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

REPORT_KINDS = {
    "junit": "JUnit XML test results (file or directory of files)",
    "jacoco": "JaCoCo XML coverage report",
    "cobertura": "Cobertura XML coverage report (also coverage.py's `coverage xml`)",
    "lcov": "LCOV coverage trace (lcov.info)",
    "pit": "PIT mutations.xml",
    "stryker": "Stryker mutation-testing JSON report",
    "classes": "Directory of compiled classes or a JAR (Java dependency structure)",
}


def parse_pairs(values: Iterable[str], kinds: Mapping[str, str], option: str,
                noun: str) -> dict[str, tuple[str, ...]]:
    """`kind=path` options grouped by kind; ValueError for a malformed option or an unknown kind."""
    found: dict[str, list[str]] = {}
    for value in values:
        kind, separator, path = value.partition("=")
        if not separator or not path:
            raise ValueError(f"{option} expects kind=path, got '{value}'")
        if kind not in kinds:
            raise ValueError(f"unknown {noun} '{kind}' (known: {sorted(kinds)})")
        found.setdefault(kind, []).append(path)
    return {kind: tuple(paths) for kind, paths in found.items()}


def parse_reports(values: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """`--report kind=path` options grouped by kind."""
    return parse_pairs(values, REPORT_KINDS, "--report", "report kind")
