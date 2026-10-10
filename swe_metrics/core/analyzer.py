"""The analyzer interface: one measuring tool behind a uniform protocol."""
from __future__ import annotations

from typing import Protocol

from swe_metrics.core.report import Metric
from swe_metrics.core.target import Target


class Analyzer(Protocol):
    """One tool behind a uniform interface. Implementations live in swe_metrics.analyzers."""

    id: str
    tool: str
    families: tuple[str, ...]

    def version(self) -> str | None:
        """The installed tool version, or None if the tool is not available."""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The files of the target this analyzer can measure."""

    def measure(self, target: Target, files: tuple[str, ...]) -> list[Metric]:
        """Measure the files; raise only for unexpected faults (the runner reports them as failed)."""
