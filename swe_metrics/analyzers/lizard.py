"""lizard: lines of code, functions, cyclomatic complexity, function length and parameters (20+ languages)."""
from __future__ import annotations

from pathlib import Path

import lizard
from lizard_ext import version as lizard_version

from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup
from swe_metrics.core.target import Target, language

TOOL = "lizard"
PER_FUNCTION = ("complexity.cyclomatic", "size.function_length", "size.parameters")


class Lizard:
    """Implements core.analyzer.Analyzer with lizard's Python API (no subprocess, same results as its CLI)."""

    id = "lizard"
    tool = TOOL
    families: tuple[str, ...] = ("size", "complexity")

    def version(self) -> str | None:
        """The installed lizard version."""
        return str(lizard_version)

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The files lizard has a language reader for."""
        return tuple(path for path in target.files if lizard.get_reader_for(path))

    def measure(self, target: Target, files: tuple[str, ...]) -> list[Metric]:
        """Per-file and per-function values, then the target-level counts and statistics."""
        metrics = [m for path in files for m in _file_metrics(Path(target.root), path)]
        functions = sum(1 for m in metrics if m.id == "complexity.cyclomatic")
        summary = [Metric("size.files", TOOL, Scope("target"), float(len(files))),
                   Metric("size.functions", TOOL, Scope("target"), float(functions))]
        rollups = [rollup(metrics, metric_id, TOOL) for metric_id in ("size.lines_of_code", *PER_FUNCTION)]
        return metrics + summary + [m for m in rollups if m]


def _file_metrics(root: Path, path: str) -> list[Metric]:
    """Lines of code of one file and the values of each of its functions."""
    info = lizard.analyze_file(str(root / path))
    labels = (("language", language(path) or "unknown"),)
    metrics = [Metric("size.lines_of_code", TOOL, Scope("file", path), float(info.nloc), labels=labels)]
    for fn in info.function_list:
        scope = Scope("function", path, fn.name, fn.start_line)
        values = (fn.cyclomatic_complexity, fn.nloc, fn.parameter_count)
        metrics += [Metric(metric_id, TOOL, scope, float(value), labels=labels)
                    for metric_id, value in zip(PER_FUNCTION, values, strict=True)]
    return metrics
