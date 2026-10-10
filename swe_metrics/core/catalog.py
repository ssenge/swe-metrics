"""The metric catalog: every metric ID with its unit, its direction and what it measures."""
from __future__ import annotations

from dataclasses import dataclass

DIRECTIONS = ("lower_better", "higher_better", "neutral")


@dataclass(frozen=True)
class MetricDef:
    """What a metric ID means. The direction tells consumers how to read a value, never whether it is good."""

    unit: str
    direction: str
    description: str


CATALOG: dict[str, MetricDef] = {
    "size.files": MetricDef("count", "neutral", "Files measured"),
    "size.functions": MetricDef("count", "neutral", "Functions and methods found"),
    "size.lines_of_code": MetricDef("lines", "neutral", "Lines of code, without blank and comment lines"),
    "size.function_length": MetricDef("lines", "lower_better", "Lines of code of a function"),
    "size.parameters": MetricDef("count", "lower_better", "Parameters of a function"),
    "complexity.cyclomatic": MetricDef("count", "lower_better", "McCabe complexity of a function"),
}


def family(metric_id: str) -> str:
    """The family of a metric ID: the part before the first dot."""
    return metric_id.split(".", 1)[0]


def families() -> set[str]:
    """All metric families in the catalog."""
    return {family(metric_id) for metric_id in CATALOG}
