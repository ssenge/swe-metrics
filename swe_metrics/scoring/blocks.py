"""Scoring building blocks: which value to read from a report, and the gates, components and regressions."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Selector:
    """A target-level value of a report: a metric, optionally a statistic, labels, tool, or a density."""

    metric: str
    stat: str = ""
    labels: tuple[tuple[str, tuple[str, ...]], ...] = ()
    tool: str = ""
    per_kloc: bool = False

    @property
    def family(self) -> str:
        """The metric family (the part of the ID before the dot)."""
        return self.metric.split(".", 1)[0]

    def describe(self) -> str:
        """A short readable form, e.g. `complexity.cyclomatic p95` or `secrets.findings per kloc`."""
        labels = ",".join(f"{k}={'|'.join(v)}" for k, v in self.labels)
        parts = [self.metric, self.stat, f"[{labels}]" if labels else "", "per kloc" if self.per_kloc else ""]
        return " ".join(part for part in parts if part)


Target = Selector | str


def select(metric: str, stat: str = "", labels: Mapping[str, str | Sequence[str]] | None = None,
           tool: str = "") -> Selector:
    """A selector; `labels` maps a label to one allowed value or several (their rows are summed)."""
    pairs = (labels or {}).items()
    normalized = tuple(sorted((k, (v,) if isinstance(v, str) else tuple(v)) for k, v in pairs))
    return Selector(metric, stat, normalized, tool)


def per_kloc(target: Target) -> Selector:
    """The value per 1,000 lines of code (size.lines_of_code), so targets of different size compare."""
    return replace(_selector(target), per_kloc=True)


def _selector(target: Target) -> Selector:
    """A selector from a selector or a bare metric ID."""
    return target if isinstance(target, Selector) else select(target)


@dataclass(frozen=True)
class Gate:
    """A hard limit; while it fails, the score is capped at `cap`."""

    selector: Selector
    max: float | None
    min: float | None
    cap: float


@dataclass(frozen=True)
class Linear:
    """A weighted component scored 0-100, linear between `bad` (0) and `good` (100), clamped."""

    selector: Selector
    good: float
    bad: float
    weight: float
    required: bool


@dataclass(frozen=True)
class Regression:
    """With a baseline report: worse than the baseline by more than `tolerance` costs `penalty` points."""

    selector: Selector
    tolerance: float
    penalty: float


def gate(target: Target, *, max: float | None = None, min: float | None = None,
         cap: float = 40.0) -> Gate:
    """A gate; exactly one of max and min must be given."""
    if (max is None) == (min is None):
        raise ValueError("a gate needs exactly one of max and min")
    return Gate(_selector(target), max, min, cap)


def linear(target: Target, *, good: float, bad: float, weight: float = 1.0, required: bool = False) -> Linear:
    """A component; `good` may lie above or below `bad`."""
    if good == bad or weight <= 0:
        raise ValueError("a component needs good != bad and a positive weight")
    return Linear(_selector(target), good, bad, weight, required)


def regression(target: Target, *, tolerance: float = 0.0, penalty: float = 10.0) -> Regression:
    """A regression check against the baseline report."""
    return Regression(_selector(target), tolerance, penalty)
