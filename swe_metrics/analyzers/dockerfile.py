"""Dockerfile parser (built in): the base image of every build stage and the runtime versions they state."""
from __future__ import annotations

from pathlib import Path

from swe_metrics import __version__
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.dockerfile import is_dockerfile, runtime, stages
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.target import Target

TOOL = "swe-metrics"


class Dockerfile:
    """Implements core.analyzer.Analyzer by parsing FROM instructions (core.dockerfile)."""

    id = "dockerfile"
    tool = TOOL
    families: tuple[str, ...] = ("container",)

    def version(self) -> str:
        """The swe-metrics version: the parser and its runtime table ship with it."""
        return __version__

    def prerequisites(self) -> str:
        """The parser needs nothing."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Dockerfiles of the target."""
        return tuple(path for path in target.files if is_dockerfile(path))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """One base image per FROM, and the runtime version of every image that states one."""
        metrics: list[Metric] = []
        for path in files:
            metrics += file_metrics(path, (Path(target.root) / path).read_text(errors="replace"))
        return Measurement(metrics)


def file_metrics(path: str, text: str) -> list[Metric]:
    """container.base_images and container.runtime_major for the stages of one Dockerfile."""
    metrics, names = [], set()
    for stage in stages(text):
        scope = Scope("file", path, line=stage.line)
        where = (("stage", stage.name), ("final", str(stage.final).lower()))
        image = (("image", stage.image), *where)
        metrics.append(Metric("container.base_images", TOOL, scope, 1.0, labels=image))
        stated = None if stage.image in names else runtime(stage.image)  # an earlier stage is no base image
        if stated:
            labels = (("runtime", stated.runtime), ("version", stated.version), *where)
            metrics.append(Metric("container.runtime_major", TOOL, scope, float(stated.major), labels=labels))
        names.add(stage.name)
    return metrics
