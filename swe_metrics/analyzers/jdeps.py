"""jdeps: the package dependency graph of the target's own packages, from classes the caller built."""
from __future__ import annotations

import re
from pathlib import Path

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.graph import graph, graph_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import run, version

TOOL = "jdeps"
LANGUAGES = ("java", "kotlin", "scala")  # jdeps reads bytecode, whatever JVM language produced it
EDGE = re.compile(r"^[ \t]+(\S+)[ \t]+->[ \t]+(\S+)", re.MULTILINE)


class Jdeps:
    """Implements core.analyzer.Analyzer with `jdeps -verbose:package` on the `classes` build report."""

    id = "jdeps"
    tool = TOOL
    families: tuple[str, ...] = ("structure",)

    def __init__(self, classes: tuple[str, ...] = ()) -> None:
        """classes: directories of compiled classes or JARs (`--report classes=PATH`)."""
        self.classes = tuple(str(Path(path).resolve()) for path in classes)

    def version(self) -> str | None:
        """The installed jdeps (JDK) version."""
        return version(["jdeps", "--version"], r"(\d+(?:\.\d+)*)")

    def prerequisites(self) -> str:
        """jdeps needs the compiled classes; swe-metrics never builds a project."""
        if not self.classes:
            return "no classes report given (--report classes=PATH)"
        missing = [path for path in self.classes if not Path(path).exists()]
        return f"classes report not found: {', '.join(missing)}" if missing else ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The JVM source files of the target (the classes come from the report)."""
        return tuple(path for path in target.files if language(path) in LANGUAGES)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Package-level dependencies; the target's own packages are the ones the classes contain."""
        output = run(["jdeps", "-verbose:package", *self.classes], cwd=scratch)
        detail = Path(scratch) / "jdeps.txt"
        detail.write_text(output)
        edges = EDGE.findall(output)
        metrics = graph_metrics(graph({source for source, _ in edges}, edges), TOOL)
        return Measurement(metrics, (("jdeps-txt", str(detail)),))
