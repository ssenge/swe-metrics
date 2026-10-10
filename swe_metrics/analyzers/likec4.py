"""LikeC4: validation errors, elements, relationships and views of a model, and the size of every view."""
from __future__ import annotations

import json
import os
import shutil
from collections import Counter
from pathlib import Path, PurePath, PurePosixPath
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup
from swe_metrics.core.target import Target
from swe_metrics.tools.process import read_json, run, version

TOOL = "likec4"
SOURCES = (".c4", ".likec4")
# Project configs in JSON; executable configs (likec4.config.ts, ...) are not copied, so never run.
CONFIGS = frozenset({"likec4.config.json", ".likec4.config.json", ".likec4rc"})
PER_VIEW = ("architecture_model.view_elements", "architecture_model.view_relationships")


class Likec4:
    """Implements core.analyzer.Analyzer with `likec4 validate --json` and `likec4 export json` on a copy."""

    id = "likec4"
    tool = TOOL
    families: tuple[str, ...] = ("architecture_model",)

    def version(self) -> str | None:
        """likec4's version and its settings: layout drifts are neither validated nor computed."""
        found = version(["likec4", "--version"])
        return f"{found} (no layout)" if found else None

    def prerequisites(self) -> str:
        """likec4 needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The LikeC4 source files of the target."""
        return tuple(path for path in target.files if path.endswith(SOURCES))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Validate and export the model from a copy of its sources; count errors, elements and views."""
        workspace = Path(scratch) / "workspace"
        projects = _copy(target, files, workspace)
        validation, export = Path(scratch) / "likec4-validate.json", Path(scratch) / "likec4.json"
        validation.write_text(run(["likec4", "validate", "--json", "--no-layout", "."],
                                  cwd=str(workspace), ok=(0, 1)))
        run(["likec4", "export", "json", "--skip-layout", "-o", str(export), "."], cwd=str(workspace))
        exported = read_json(export)
        models = exported if isinstance(exported, list) else [exported]
        errors = read_json(validation).get("errors") or []
        metrics = error_metrics([_relative(e.get("file", ""), workspace) for e in errors])
        details = (("likec4-json", str(export)), ("likec4-validate-json", str(validation)))
        return Measurement(metrics + model_metrics(models, projects), details)


def _copy(target: Target, files: tuple[str, ...], workspace: Path) -> dict[str, str]:
    """Copy the sources and JSON project configs into the workspace; the directory of each named project."""
    projects = {}
    for path in (*files, *(p for p in target.files if PurePath(p).name in CONFIGS)):
        copy = workspace / path
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(target.root) / path, copy)
        if PurePath(path).name in CONFIGS:
            projects[_project_name(copy)] = str(PurePosixPath(path).parent)
    return projects


def _project_name(config: Path) -> str:
    """The `name` a project config declares; empty if it can't be read as JSON."""
    try:
        return str(json.loads(config.read_text()).get("name", ""))
    except (ValueError, AttributeError):
        return ""


def _relative(file: str, workspace: Path) -> str:
    """A path likec4 reports (absolute, symlinks resolved) relative to the workspace."""
    return os.path.relpath(Path(file).resolve(), workspace.resolve()) if file else ""


def error_metrics(paths: list[str]) -> list[Metric]:
    """architecture_model.errors per file and in total (0 when the model is valid)."""
    metric, per_file = "architecture_model.errors", sorted(Counter(p for p in paths if p).items())
    metrics = [Metric(metric, TOOL, Scope("file", path), float(n)) for path, n in per_file]
    return [*metrics, Metric(metric, TOOL, Scope("target"), float(len(paths)))]


def model_metrics(models: list[dict[str, Any]], projects: dict[str, str]) -> list[Metric]:
    """Element, relationship and view totals; elements and relationships per declared view, and statistics."""
    views = [view for model in models for view in _declared_views(model, projects)]
    totals = {"architecture_model.elements": sum(_count(m, "elements") for m in models),
              "architecture_model.relationships": sum(_count(m, "relations") for m in models),
              "architecture_model.views": len(views)}
    metrics = [Metric(metric, TOOL, Scope("target"), float(n)) for metric, n in totals.items()]
    for path, view in views:
        scope = Scope("file", path, symbol=view["id"])
        metrics += [Metric(PER_VIEW[0], TOOL, scope, float(_count(view, "nodes"))),
                    Metric(PER_VIEW[1], TOOL, scope, float(_count(view, "edges")))]
    summaries = [rollup(metrics, metric, TOOL) for metric in PER_VIEW]
    return metrics + [s for s in summaries if s]


def _declared_views(model: dict[str, Any], projects: dict[str, str]) -> list[tuple[str, dict[str, Any]]]:
    """(source path relative to the target, view) of the views a model's sources declare."""
    # likec4 adds a generated `index` view, which has no sourcePath; it is not part of the sources.
    project_dir = projects.get(model.get("projectId", ""), "")
    views = (model.get("views") or {}).values()
    return [(_source(view["sourcePath"], project_dir), view) for view in views if view.get("sourcePath")]


def _count(data: dict[str, Any], key: str) -> int:
    """The number of entries under a key of the exported JSON (absent or null: 0)."""
    return len(data.get(key) or ())


def _source(source_path: str, project_dir: str) -> str:
    """A view's source file relative to the target: likec4 reports it relative to its project."""
    return str(PurePosixPath(project_dir) / source_path) if project_dir not in ("", ".") else source_path
