"""Quality scores: one number from a report, computed by a scoring definition written in Python.

A definition is any object with `name`, `version` and `score(report, baseline=None) -> dict`. Most are a
`Definition` built from the building blocks below; see `swe_metrics.scoring.default` for the shipped one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from swe_metrics.scoring.blocks import (
    Gate,
    Linear,
    Regression,
    Selector,
    gate,
    linear,
    per_kloc,
    regression,
    select,
)
from swe_metrics.scoring.evaluate import evaluate

__all__ = ["Definition", "Selector", "gate", "linear", "per_kloc", "regression", "select"]


@dataclass(frozen=True)
class Definition:
    """A definition from building blocks; scores compare only under the same name and version."""

    name: str
    version: str
    gates: tuple[Gate, ...] = ()
    components: tuple[Linear, ...] = ()
    regressions: tuple[Regression, ...] = ()

    def score(self, report: dict[str, Any], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
        """The score document for a report (and, for regressions, a baseline report)."""
        parts = (self.gates, self.components, self.regressions)
        return evaluate(self.name, self.version, parts, report, baseline)
