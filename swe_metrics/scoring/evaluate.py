"""Turning a report into a score with a definition's gates, components and regressions."""
from __future__ import annotations

from typing import Any

from swe_metrics.scoring.blocks import Gate, Linear, Regression
from swe_metrics.scoring.values import OK, UNAVAILABLE, Report, lookup

SCHEMA = "swe-metrics/score/v1"
Row = dict[str, Any]


Parts = tuple[tuple[Gate, ...], tuple[Linear, ...], tuple[Regression, ...]]


def evaluate(name: str, version: str, parts: Parts, report: Report, baseline: Report | None = None) -> Row:
    """The score document: the score (or null if incomplete), every gate, component, regression and note."""
    gates, components, regressions = parts
    notes: list[str] = []
    gate_rows = [_gate(g, report, notes) for g in gates]
    component_rows = [_component(c, report, notes) for c in components]
    regression_rows = [_regression(r, report, baseline, notes) for r in regressions] if baseline else []
    score = _score(gate_rows, component_rows, regression_rows, notes)
    return {"schema": SCHEMA, "definition": {"name": name, "version": version}, "score": score,
            "gates": gate_rows, "components": component_rows, "regressions": regression_rows, "notes": notes}


def _gate(g: Gate, report: Report, notes: list[str]) -> Row:
    """A gate passes when its value is within the limit or not applicable; unavailable fails (fail closed)."""
    found = lookup(report, g.selector)
    if found.status != OK:
        notes.append(f"gate {found.reason}")
    value = found.value
    within = value is not None and (g.max is None or value <= g.max) and (g.min is None or value >= g.min)
    passed = within if found.status == OK else found.status != UNAVAILABLE
    return {"metric": g.selector.describe(), "status": found.status, "value": value, "max": g.max,
            "min": g.min, "cap": g.cap, "passed": passed}


def _component(c: Linear, report: Report, notes: list[str]) -> Row:
    """A sub-score from 0 to 100, linear between bad and good, clamped."""
    found = lookup(report, c.selector)
    row: Row = {"metric": c.selector.describe(), "status": found.status, "value": found.value,
                "good": c.good, "bad": c.bad, "weight": c.weight, "required": c.required}
    if found.status != OK or found.value is None:
        notes.append(f"component {found.reason}")
        return row
    row["subscore"] = round(min(100.0, max(0.0, 100 * (found.value - c.bad) / (c.good - c.bad))), 2)
    return row


def _regression(r: Regression, report: Report, baseline: Report | None, notes: list[str]) -> Row:
    """Worse than the baseline by more than the tolerance, in the metric's direction, costs the penalty."""
    now, before = lookup(report, r.selector), lookup(baseline or {}, r.selector)
    row: Row = {"metric": r.selector.describe(), "value": now.value, "baseline": before.value,
                "tolerance": r.tolerance, "penalty": r.penalty, "worse": False}
    if now.value is None or before.value is None:
        notes.append(f"regression {r.selector.describe()}: no value in both reports")
        return row
    delta = now.value - before.value
    row["worse"] = (delta > r.tolerance if now.direction == "lower_better"
                    else -delta > r.tolerance if now.direction == "higher_better" else False)
    return row


def _score(gates: list[Row], components: list[Row], regressions: list[Row], notes: list[str]) -> float | None:
    """Weighted mean of the scored components, minus penalties, at least 0, capped by failed gates."""
    weighted = _weighted(components, notes)
    if weighted is None:
        return None
    value = max(0.0, weighted - sum(float(r["penalty"]) for r in regressions if r["worse"]))
    caps = [float(g["cap"]) for g in gates if not g["passed"]]
    return round(min([value, *caps]), 2)


def _weighted(components: list[Row], notes: list[str]) -> float | None:
    """The weighted mean of the scored components (and each one's contribution); None if incomplete."""
    if any(c["status"] == UNAVAILABLE and c["required"] for c in components):
        notes.append("score incomplete: a required component is unavailable")
        return None
    used = [c for c in components if "subscore" in c]
    if not used:
        notes.append("score incomplete: no component could be measured")
        return None
    total = sum(c["weight"] for c in used)
    for c in used:
        c["contribution"] = round(c["subscore"] * c["weight"] / total, 2)
    return float(sum(c["subscore"] * c["weight"] for c in used) / total)
