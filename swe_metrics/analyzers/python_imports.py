"""Python imports (built in): the module dependency graph of the target's own modules, parsed with ast."""
from __future__ import annotations

from pathlib import Path

from swe_metrics import __version__
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.graph import graph, graph_metrics
from swe_metrics.core.python_source import imported_names, module_name, resolve
from swe_metrics.core.target import Target, language

TOOL = "swe-metrics"


class PythonImports:
    """Implements core.analyzer.Analyzer: import statements become edges between the target's modules."""

    id = "python-imports"
    tool = TOOL
    families: tuple[str, ...] = ("structure",)

    def version(self) -> str | None:
        """The swe-metrics version: the analysis is built in."""
        return __version__

    def prerequisites(self) -> str:
        """Nothing beyond the Python standard library."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Python files of the target."""
        return tuple(path for path in target.files if language(path) == "python")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Edges from every import that names a target module; imports of a module's own names are dropped."""
        modules = {path: module_name(path) for path in files}
        known = {name for name, _ in modules.values() if name}
        edges = []
        for path, (name, package) in sorted(modules.items()):
            source = (Path(target.root) / path).read_bytes()
            for imported in imported_names(source, name, package, path):
                found = resolve(imported, known)
                if found and found != name:
                    edges.append((name, found))
        return Measurement(graph_metrics(graph(known, edges), TOOL, (("language", "python"),)))
