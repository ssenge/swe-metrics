"""The analyzer interface: one measuring tool behind a uniform protocol."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from swe_metrics.core.report import Metric
from swe_metrics.core.target import Target


@dataclass(frozen=True)
class Measurement:
    """An analyzer's result: its metrics and detailed outputs as (format, path in the scratch directory)."""

    metrics: list[Metric]
    details: tuple[tuple[str, str], ...] = field(default=())


class Analyzer(Protocol):
    """One tool behind a uniform interface. Implementations live in swe_metrics.analyzers."""

    id: str
    tool: str
    families: tuple[str, ...]

    def version(self) -> str | None:
        """The installed tool version, or None if the tool is not available."""

    def prerequisites(self) -> str:
        """Why the analyzer can't run although its tool is installed (e.g. no rules); empty if it can."""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The files of the target this analyzer can measure."""

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Measure the files, writing tool outputs only below scratch; raise only for unexpected faults."""
