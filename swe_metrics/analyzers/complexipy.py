"""complexipy: cognitive complexity (SonarSource's definition) of every Python function."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

import complexipy

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup
from swe_metrics.core.target import Target, language

TOOL = "complexipy"


class Complexipy:
    """Implements core.analyzer.Analyzer with complexipy's Python API."""

    id = "complexipy"
    tool = TOOL
    families: tuple[str, ...] = ("complexity",)

    def version(self) -> str | None:
        """The installed complexipy version."""
        try:
            return package_version("complexipy")
        except PackageNotFoundError:
            return None

    def prerequisites(self) -> str:
        """complexipy needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Python files of the target."""
        return tuple(path for path in target.files if language(path) == "python")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Cognitive complexity per function, and its target statistics."""
        metrics = []
        for path in files:
            analysis = complexipy.file_complexity(str(Path(target.root) / path))
            metrics += [Metric("complexity.cognitive", TOOL, Scope("function", path, fn.name, fn.line_start),
                               float(fn.complexity), labels=(("language", "python"),))
                        for fn in analysis.functions]
        summary = rollup(metrics, "complexity.cognitive", TOOL)
        return Measurement(metrics + ([summary] if summary else []))
