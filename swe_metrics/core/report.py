"""The report model: what was measured, which analyzers ran, and the metrics, with its JSON form."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from swe_metrics.core.catalog import CATALOG

SCHEMA = "swe-metrics/report/v1"
LEVELS = ("target", "module", "file", "function")
STATUSES = ("ran", "skipped", "failed")


@dataclass(frozen=True)
class Scope:
    """Where a value applies: the whole target, a module, a file, or a function in a file."""

    level: str
    path: str = ""
    symbol: str = ""
    line: int = 0

    def as_dict(self) -> dict[str, Any]:
        """The JSON form: only the fields that are set."""
        return {key: value for key, value in asdict(self).items() if value}


@dataclass(frozen=True)
class Stats:
    """Distribution statistics of the values a target-level metric summarizes."""

    count: int
    sum: float
    mean: float
    p50: float
    p95: float
    max: float


@dataclass(frozen=True)
class Metric:
    """One measured value (or the statistics of many), tagged with the tool that measured it."""

    id: str
    tool: str
    scope: Scope
    value: float | None = None
    stats: Stats | None = None
    labels: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """The JSON form, with the unit and direction from the catalog."""
        definition = CATALOG[self.id]
        data: dict[str, Any] = {"id": self.id, "tool": self.tool, "unit": definition.unit,
                                "direction": definition.direction, "scope": self.scope.as_dict()}
        if self.value is not None:
            data["value"] = self.value
        if self.stats is not None:
            data["stats"] = asdict(self.stats)
        if self.labels:
            data["labels"] = dict(self.labels)
        return data


@dataclass(frozen=True)
class AnalyzerRun:
    """Whether an analyzer ran, was skipped or failed, with the tool version and the reason."""

    id: str
    tool: str
    status: str
    version: str = ""
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        """The JSON form: only the fields that are set."""
        return {key: value for key, value in asdict(self).items() if value}


@dataclass(frozen=True)
class Detail:
    """A detailed tool output kept next to the report (e.g. SARIF), relative to the details directory."""

    analyzer: str
    format: str
    path: str

    def as_dict(self) -> dict[str, Any]:
        """The JSON form."""
        return asdict(self)


@dataclass(frozen=True)
class Subject:
    """What was measured: the target as given, its kind, the commit, and its files per language."""

    target: str
    kind: str
    files: int
    languages: tuple[tuple[str, int], ...] = ()
    commit: str = ""
    changed_since: str = ""

    def as_dict(self) -> dict[str, Any]:
        """The JSON form."""
        return {"target": self.target, "kind": self.kind, "commit": self.commit or None,
                "changed_since": self.changed_since or None, "files": self.files,
                "languages": dict(self.languages)}


@dataclass(frozen=True)
class Report:
    """The result of one measurement."""

    subject: Subject
    analyzers: tuple[AnalyzerRun, ...]
    metrics: tuple[Metric, ...]
    details: tuple[Detail, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """The JSON form (schema swe-metrics/report/v1)."""
        return {"schema": SCHEMA, "subject": self.subject.as_dict(),
                "analyzers": [a.as_dict() for a in self.analyzers],
                "metrics": [m.as_dict() for m in self.metrics],
                "details": [d.as_dict() for d in self.details]}
