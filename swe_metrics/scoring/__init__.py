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

    def describe(self) -> dict[str, Any]:
        """The definition's parts as data, for a caller that explains the score: each gate's and component's
        selector (readable, with its tool) and its limits."""
        def what(selector: Selector) -> dict[str, str]:
            return {"what": selector.describe(), "tool": selector.tool}
        return {"name": self.name, "version": self.version,
                "gates": [{**what(g.selector), "max": g.max, "min": g.min, "cap": g.cap} for g in self.gates],
                "components": [{**what(c.selector), "good": c.good, "bad": c.bad, "weight": c.weight,
                                "required": c.required} for c in self.components],
                "regressions": [{**what(r.selector), "tolerance": r.tolerance, "penalty": r.penalty}
                                for r in self.regressions]}
