"""dependency-cruiser: the module (file) dependency graph of the target's JavaScript and TypeScript files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.graph import graph, graph_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import read_json, run, version

TOOL = "dependency-cruiser"
LANGUAGES = ("javascript", "typescript")


class Depcruise:
    """Implements core.analyzer.Analyzer with `depcruise --output-type json`, ignoring the target's config."""

    id = "dependency-cruiser"
    tool = TOOL
    families: tuple[str, ...] = ("structure",)

    def version(self) -> str | None:
        """dependency-cruiser's version; a target's config (aliases, rules) is never read."""
        found = version(["depcruise", "--version"])
        return f"{found} (no target config)" if found else None

    def prerequisites(self) -> str:
        """dependency-cruiser needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The JavaScript and TypeScript files of the target."""
        return tuple(path for path in target.files if language(path) in LANGUAGES)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Resolve the files' imports; keep only edges between the files, then the graph metrics."""
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        argv = ["depcruise", "--no-config", "--output-type", "json", "--do-not-follow", "node_modules"]
        output = str(Path(scratch) / "depcruise.json")
        run([*argv, "--output-to", output, *files], cwd=target.root)
        metrics = graph_metrics(graph(files, _edges(read_json(output))), TOOL)
        return Measurement(metrics, (("depcruise-json", output),))


def _edges(cruise: dict[str, Any]) -> list[tuple[str, str]]:
    """Every resolved dependency as (source, resolved); edges outside the target are dropped later."""
    return [(module["source"], dep["resolved"])
            for module in cruise.get("modules", []) for dep in module.get("dependencies", [])]
