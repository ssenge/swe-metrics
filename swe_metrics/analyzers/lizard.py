"""lizard: lines of code, functions, cyclomatic complexity, function length and parameters (20+ languages)."""
from __future__ import annotations

import re
from collections.abc import Iterator
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import lizard

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup
from swe_metrics.core.target import Target, language

TOOL = "lizard"
PER_FUNCTION = ("complexity.cyclomatic", "size.function_length", "size.parameters")
# lizard's tokenizer joins "<...?...>" into one generic-type token (Java's <? extends T>), so in
# `a < b ? c > d : e` the ternary's "?" is never counted. A "?" (or "??") between two words is a
# ternary: a wildcard follows "<" or ",", a nullable type precedes ">" or ",".
HIDDEN_CONDITION = re.compile(r"(?<=\w)\s*(\?\??)(?![.?])\s*(?=\w)")


class Lizard:
    """Implements core.analyzer.Analyzer with lizard's Python API (no subprocess, same results as its CLI)."""

    id = "lizard"
    tool = TOOL
    families: tuple[str, ...] = ("size", "complexity")

    def version(self) -> str | None:
        """The installed lizard version (its package metadata: lizard_ext.version has lagged releases)."""
        return package_version("lizard")

    def prerequisites(self) -> str:
        """lizard needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The files lizard has a language reader for."""
        return tuple(path for path in target.files if lizard.get_reader_for(path))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Per-file and per-function values, then the target-level counts and statistics."""
        metrics = [m for path in files for m in _file_metrics(Path(target.root), path)]
        functions = sum(1 for m in metrics if m.id == "complexity.cyclomatic")
        summary = [Metric("size.files", TOOL, Scope("target"), float(len(files))),
                   Metric("size.functions", TOOL, Scope("target"), float(functions))]
        rollups = [rollup(metrics, metric_id, TOOL) for metric_id in ("size.lines_of_code", *PER_FUNCTION)]
        return Measurement(metrics + summary + [m for m in rollups if m])


def hidden_conditions(token: str, conditions: set[str]) -> int:
    """The conditions lizard can't see inside a token it took for generic type arguments."""
    if len(token) < 3 or token[0] != "<" or token[-1] != ">":
        return 0
    return sum(1 for op in HIDDEN_CONDITION.findall(token) if op in conditions)


def _count_hidden_conditions(tokens: Iterator[str], reader: Any) -> Iterator[str]:
    """A lizard token processor: adds the hidden conditions to the function being read."""
    for token in tokens:
        hidden = hidden_conditions(token, reader.conditions)
        if hidden:
            reader.context.add_condition(hidden)
        yield token


ANALYZE = lizard.FileAnalyzer(lizard.get_extensions([_count_hidden_conditions]))


def _file_metrics(root: Path, path: str) -> list[Metric]:
    """Lines of code of one file and the values of each of its functions."""
    info = ANALYZE(str(root / path))
    labels = (("language", language(path) or "unknown"),)
    metrics = [Metric("size.lines_of_code", TOOL, Scope("file", path), float(info.nloc), labels=labels)]
    for fn in info.function_list:
        scope = Scope("function", path, fn.name, fn.start_line)
        values = (fn.cyclomatic_complexity, fn.nloc, fn.parameter_count)
        metrics += [Metric(metric_id, TOOL, scope, float(value), labels=labels)
                    for metric_id, value in zip(PER_FUNCTION, values, strict=True)]
    return metrics
