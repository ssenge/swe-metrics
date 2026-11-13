"""Structurizr: errors, elements, relationships and views of DSL workspaces, and each view's size."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup
from swe_metrics.core.target import Target
from swe_metrics.tools.files import copy_files
from swe_metrics.tools.process import ToolError, read_json, run, version

TOOL = "structurizr-cli"
SOURCE = ".dsl"
WORKSPACE = re.compile(r"^\s*workspace\b", re.MULTILINE)
SNIFF_BYTES = 50_000
NESTED = ("containers", "components")   # an element holds its containers, a container its components
PER_VIEW = ("architecture_model.view_elements", "architecture_model.view_relationships")


class Structurizr:
    """Implements core.analyzer.Analyzer with `structurizr-cli validate` and `export -format json`."""

    id = "structurizr"
    tool = TOOL
    families: tuple[str, ...] = ("architecture_model",)

    def version(self) -> str | None:
        """structurizr-cli's version (it needs a JRE, which it reports when it is missing)."""
        return version(["structurizr-cli", "version"])

    def prerequisites(self) -> str:
        """structurizr-cli needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Structurizr DSL files of the target."""
        return tuple(p for p in target.files if p.endswith(SOURCE))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Validate and export each workspace from a copy of the DSL files (`!include` needs them all)."""
        workspace = Path(scratch) / "workspace"
        copy_files(target.root, files, workspace)
        invalid: list[str] = []
        exports: list[tuple[str, dict[str, Any]]] = []
        details = []
        for n, path in enumerate(p for p in files if _is_workspace(workspace / p)):
            source = str(workspace / path)
            try:
                run(["structurizr-cli", "validate", "-workspace", source], cwd=str(workspace))
            except ToolError:   # an exit code of 1 says the workspace is invalid
                invalid.append(path)
                continue
            out = Path(scratch) / f"export-{n}"
            out.mkdir()
            run(["structurizr-cli", "export", "-workspace", source, "-format", "json", "-output", str(out)],
                cwd=str(workspace))
            exported = out / f"{Path(path).stem}.json"
            exports.append((path, read_json(exported)))
            details.append(("structurizr-json", str(exported)))
        return Measurement(_metrics(invalid, exports), tuple(details))


def _is_workspace(path: Path) -> bool:
    """Whether a DSL file is a workspace of its own, not a part another one includes."""
    with path.open(errors="ignore") as source:
        return bool(WORKSPACE.search(source.read(SNIFF_BYTES)))


def _walk(element: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """An element and everything nested in it: its containers, and their components."""
    yield element
    for key in NESTED:
        for child in element.get(key) or ():
            yield from _walk(child)


def _metrics(invalid: list[str], exports: list[tuple[str, dict[str, Any]]]) -> list[Metric]:
    """Errors per invalid workspace, the model's totals, and the views and their sizes."""
    target = Scope("target")
    metrics = [Metric("architecture_model.errors", TOOL, Scope("file", p), 1.0) for p in sorted(invalid)]
    models = float(len(invalid) + len(exports))
    metrics += [Metric("architecture_model.errors", TOOL, target, float(len(invalid))),
                Metric("architecture_model.models", TOOL, target, models)]
    elements = relationships = 0
    views: list[tuple[str, str, dict[str, Any]]] = []
    for path, workspace in exports:
        found = _elements(workspace)
        elements += len(found)
        # relationships Structurizr derives from others (implied) are not counted again
        relationships += sum(1 for e in found for r in e.get("relationships") or ()
                             if not r.get("linkedRelationshipId"))
        views += [(path, kind, v) for kind, group in _views(workspace) for v in group]
    metrics += [Metric("architecture_model.elements", TOOL, target, float(elements)),
                Metric("architecture_model.relationships", TOOL, target, float(relationships))]
    return metrics + _view_metrics(views)


def _elements(workspace: dict[str, Any]) -> list[dict[str, Any]]:
    """Every person, software system, container and component of an exported workspace."""
    model = workspace.get("model") or {}
    return [e for key in ("people", "softwareSystems") for top in model.get(key) or () for e in _walk(top)]


def _views(workspace: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """The view lists of an exported workspace by type (`systemContext`, `container`, ...)."""
    return [(kind.removesuffix("Views"), group) for kind, group in (workspace.get("views") or {}).items()
            if isinstance(group, list)]


def _view_metrics(views: list[tuple[str, str, dict[str, Any]]]) -> list[Metric]:
    """Views in total and by type, the elements and relationships of each, and statistics of those."""
    target = Scope("target")
    metrics = [Metric("architecture_model.views", TOOL, target, float(len(views)))]
    for kind in sorted({k for _, k, _ in views}):
        count = float(sum(1 for _, k, _ in views if k == kind))
        metrics.append(Metric("architecture_model.views", TOOL, target, count, labels=(("type", kind),)))
    for path, _, view in views:
        scope = Scope("file", path, symbol=str(view.get("key", "")))
        metrics += [Metric(PER_VIEW[0], TOOL, scope, float(len(view.get("elements") or ()))),
                    Metric(PER_VIEW[1], TOOL, scope, float(len(view.get("relationships") or ())))]
    return metrics + [s for s in (rollup(metrics, m, TOOL) for m in PER_VIEW) if s]
