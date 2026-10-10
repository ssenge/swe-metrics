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
    "complexity.cognitive": MetricDef("count", "lower_better", "Cognitive complexity of a function"),
    "duplication.percent": MetricDef("percent", "lower_better", "Share of lines inside a code clone"),
    "duplication.duplicated_lines": MetricDef("lines", "lower_better", "Lines inside a code clone"),
    "duplication.clones": MetricDef("count", "lower_better", "Code clones (pairs of duplicated fragments)"),
    "secrets.findings": MetricDef("count", "lower_better", "Secrets found (location and rule only)"),
    "dependencies.packages": MetricDef("count", "neutral", "Packages a manifest or lock file declares"),
    "dependencies.vulnerabilities": MetricDef("count", "lower_better", "Known vulnerabilities of packages"),
    "security.findings": MetricDef("count", "lower_better", "Static analysis findings of the given rules"),
}


def family(metric_id: str) -> str:
    """The family of a metric ID: the part before the first dot."""
    return metric_id.split(".", 1)[0]


def families() -> set[str]:
    """All metric families in the catalog."""
    return {family(metric_id) for metric_id in CATALOG}
