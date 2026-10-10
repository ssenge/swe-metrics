"""Reading a selector's value from a report (JSON form), and why a value is missing when it is."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from swe_metrics.scoring.blocks import Selector, select

Report = dict[str, Any]
OK, NOT_APPLICABLE, UNAVAILABLE = "ok", "not_applicable", "unavailable"


@dataclass(frozen=True)
class Value:
    """A selected value, or why there is none; `direction` is the metric's (for regressions)."""

    status: str
    value: float | None = None
    reason: str = ""
    direction: str = "neutral"


def lookup(report: Report, selector: Selector) -> Value:
    """The selector's value: one statistic, or the sum of the matching rows; densities per 1,000 lines."""
    rows = [m for m in report.get("metrics", []) if _matches(m, selector)]
    values = _numbers(rows, selector.stat)
    if not values and selector.labels:
        values = _zero_if_counted(report, selector)
    if not values:
        return absent(report, selector.family, selector.describe())
    if selector.stat and len(values) > 1:
        raise ValueError(f"{selector.describe()}: several tools report it; name one with tool=")
    direction = rows[0]["direction"] if rows else _direction(report, selector.metric)
    found = Value(OK, sum(values), direction=direction)
    return _density(report, found) if selector.per_kloc else found


def _direction(report: Report, metric: str) -> str:
    """The direction any row of the metric states."""
    return next((m["direction"] for m in report.get("metrics", []) if m["id"] == metric), "neutral")


def _zero_if_counted(report: Report, selector: Selector) -> list[float]:
    """Label rows exist only for labels that occurred: with the metric's total present, the count is 0."""
    total = replace(selector, labels=(), per_kloc=False)
    has_total = any(_matches(m, total) for m in report.get("metrics", []))
    return [0.0] if has_total and not selector.stat else []


def _numbers(rows: list[dict[str, Any]], stat: str) -> list[float]:
    """The numbers of the rows that have one (the statistic, or the value)."""
    found = (_number(row, stat) for row in rows)
    return [number for number in found if number is not None]


def _matches(row: dict[str, Any], selector: Selector) -> bool:
    """A target-level row of the selected metric (and tool and labels)."""
    if row["id"] != selector.metric or row["scope"]["level"] != "target":
        return False
    return (not selector.tool or row["tool"] == selector.tool) and _labels_match(row.get("labels", {}),
                                                                                  selector.labels)


def _number(row: dict[str, Any], stat: str) -> float | None:
    """The row's statistic, or its value when no statistic is selected."""
    found = row.get("stats", {}).get(stat) if stat else row.get("value")
    return None if found is None else float(found)


def _labels_match(labels: dict[str, str], wanted: tuple[tuple[str, tuple[str, ...]], ...]) -> bool:
    """Rows with the wanted labels (any allowed value); without wanted labels, the unlabeled totals."""
    if not wanted:
        return not labels
    return all(labels.get(key) in allowed for key, allowed in wanted)


def _density(report: Report, found: Value) -> Value:
    """The value per 1,000 lines of code."""
    lines = lookup(report, select("size.lines_of_code", stat="sum"))
    if lines.status != OK or not lines.value:
        status = lines.status if lines.status != OK else NOT_APPLICABLE
        return Value(status, reason="no lines of code measured")
    return Value(OK, found.value * 1000 / lines.value if found.value is not None else None,
                 direction=found.direction)


def absent(report: Report, family: str, what: str) -> Value:
    """Why a value is missing: an analyzer of its family failed (unavailable), or none applied."""
    runs = [a for a in report.get("analyzers", []) if family in a.get("families", [])]
    failed = [a for a in runs if a["status"] == "failed"]
    if failed:
        reasons = "; ".join(f"{a['id']}: {a.get('reason', 'failed')}" for a in failed)
        return Value(UNAVAILABLE, reason=f"{what}: {reasons}")
    return Value(NOT_APPLICABLE, reason=f"{what}: not measured for this target")
