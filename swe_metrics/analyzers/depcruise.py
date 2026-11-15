"""dependency-cruiser: the module (file) dependency graph of the target's JavaScript and TypeScript files."""
from __future__ import annotations

from pathlib import Path, PurePath
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.graph import graph, graph_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import ToolError, read_json, run, version

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
        # imports as written: TypeScript drops an unused import, but it is still a dependency of the source
        argv = ["depcruise", "--no-config", "--ts-pre-compilation-deps", "--output-type", "json",
                "--do-not-follow", "node_modules"]
        output = str(Path(scratch) / "depcruise.json")
        run([*argv, "--output-to", output, *files], cwd=target.root)
        cruise = read_json(output)
        unresolved = _unresolved(cruise)
        if unresolved:  # a graph without these edges would read as "no dependencies, no cycles"
            raise ToolError(unresolved)
        metrics = graph_metrics(graph(files, _edges(cruise)), TOOL)
        return Measurement(metrics, (("depcruise-json", output),))


def _edges(cruise: dict[str, Any]) -> list[tuple[str, str]]:
    """Every resolved dependency as (source, resolved); edges outside the target are dropped later."""
    return [(module["source"], dep["resolved"])
            for module in cruise.get("modules", []) for dep in module.get("dependencies", [])]


def _unresolved(cruise: dict[str, Any]) -> str:
    """Why the graph would be incomplete, or empty: no relative import resolved, or one from a file kind
    dependency-cruiser says it can't read (e.g. TypeScript without a compatible compiler) wasn't."""
    environment = cruise.get("summary", {}).get("environment", {})
    imports = _relative_imports(cruise)
    missed = {suffix for suffix, resolved in imports if not resolved}
    resolved = len(imports) - sum(1 for _, ok in imports if not ok)
    if not missed or (resolved and not missed & _unreadable(environment)):
        return ""
    issues = " ".join(" ".join(i.get("description", "").split()) for i in environment.get("issues", []))
    return f"dependency-cruiser resolved {resolved} of {len(imports)} relative imports" + (
        f": {issues}" if issues else "")


def _relative_imports(cruise: dict[str, Any]) -> list[tuple[str, bool]]:
    """Each relative import ('./x', '../y') as the importing file's extension and whether it resolved."""
    return [(PurePath(module["source"]).suffix, not dep.get("couldNotResolve"))
            for module in cruise.get("modules", []) for dep in module.get("dependencies", [])
            if dep.get("module", "").startswith(".")]


def _unreadable(environment: dict[str, Any]) -> set[str]:
    """The file extensions dependency-cruiser reports it has no reader for (e.g. no compatible compiler)."""
    found = environment.get("extensionsFound", [])
    return {kind["extension"] for kind in found if not kind.get("available")}
