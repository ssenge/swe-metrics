"""Suppressions (built in): marks in the code that silence a checker, by file, kind and if they say why."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from swe_metrics import __version__
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.suppressions import Mark, find_marks
from swe_metrics.core.target import CODE_LANGUAGES, Target, language

TOOL = "swe-metrics"
LANGUAGES = CODE_LANGUAGES | {"shell", "terraform", "yaml", "dockerfile"}   # where comments can carry marks
LIMIT = 1_000_000   # bytes: a bigger file is no source worth reading for marks


class Suppressions:
    """Implements core.analyzer.Analyzer by scanning the comments of code, shell, Terraform and YAML files."""

    id = "suppressions"
    tool = TOOL
    families: tuple[str, ...] = ("suppressions",)

    def version(self) -> str:
        """The swe-metrics version: the scan is built in."""
        return __version__

    def prerequisites(self) -> str:
        """Nothing is needed."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The files in a language whose comments can carry a mark (Markdown prose never does)."""
        return tuple(p for p in target.files if language(p) in LANGUAGES)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Count the marks per file, kind and `has_reason`; every mark is listed in the detail."""
        found: list[tuple[str, Mark]] = []
        for path in files:
            file = Path(target.root) / path
            if file.stat().st_size <= LIMIT:
                found += [(path, mark) for mark in find_marks(file.read_text(errors="ignore"))]
        detail = Path(scratch) / "suppressions.json"
        detail.write_text(json.dumps([{"path": p, "line": m.line, "kind": m.kind, "rules": list(m.rules),
                                       "reason": m.reason} for p, m in found], indent=1))
        return Measurement(_metrics(found), (("suppressions-json", str(detail)),))


def _metrics(found: list[tuple[str, Mark]]) -> list[Metric]:
    """Marks per file, per kind, per `has_reason` (`true` or `false`) and in total (0 when there are none)."""
    metric = "suppressions.marks"
    per_file = sorted(Counter(p for p, _ in found).items())
    metrics = [Metric(metric, TOOL, Scope("file", path), float(n)) for path, n in per_file]
    for key, label in (("kind", lambda m: m.kind), ("has_reason", lambda m: str(bool(m.reason)).lower())):
        counts = Counter(label(m) for _, m in found)
        metrics += [Metric(metric, TOOL, Scope("target"), float(n), labels=((key, value),))
                    for value, n in sorted(counts.items())]
    return [*metrics, Metric(metric, TOOL, Scope("target"), float(len(found)))]
