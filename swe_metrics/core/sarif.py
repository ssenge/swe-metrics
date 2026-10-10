"""SARIF 2.1.0 findings as data, and finding counts as metrics (per file, per label, and in total)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from swe_metrics.core.report import Metric, Scope

DEFAULT_LEVEL = "warning"  # SARIF 2.1.0 §3.27.10: the level when neither result nor rule sets one


@dataclass(frozen=True)
class Finding:
    """One SARIF result: its rule, level and location. Never carries the matched text."""

    rule: str
    level: str
    path: str
    line: int = 0


def findings(doc: Mapping[str, Any], root: str = "") -> list[Finding]:
    """The results of every run; the level comes from the result, else its rule's default."""
    found = []
    for run in doc.get("runs", []):
        rules = run.get("tool", {}).get("driver", {}).get("rules", [])
        levels = {r["id"]: r.get("defaultConfiguration", {}).get("level", DEFAULT_LEVEL) for r in rules}
        for result in run.get("results", []):
            rule = result.get("ruleId", "")
            level = result.get("level") or levels.get(rule, DEFAULT_LEVEL)
            path, line = _location(result, root)
            found.append(Finding(rule, level, path, line))
    return found


def _location(result: Mapping[str, Any], root: str) -> tuple[str, int]:
    """The relative path and start line of a result's first location."""
    locations = result.get("locations") or [{}]
    physical = locations[0].get("physicalLocation", {})
    uri = physical.get("artifactLocation", {}).get("uri", "").removeprefix("file://")
    prefix = root.rstrip("/") + "/"
    path = uri[len(prefix):] if root and uri.startswith(prefix) else uri
    return path, int(physical.get("region", {}).get("startLine", 0))


def count_metrics(metric_id: str, tool: str, items: Sequence[Finding],
                  label: tuple[str, Callable[[Finding], str]]) -> list[Metric]:
    """Counts per file, per label value (e.g. severity) and in total; a total of 0 when nothing was found."""
    key, label_of = label
    per_file = Counter(f.path for f in items)
    per_label = Counter(label_of(f) for f in items)
    metrics = [Metric(metric_id, tool, Scope("file", path), float(n)) for path, n in sorted(per_file.items())]
    metrics += [Metric(metric_id, tool, Scope("target"), float(n), labels=((key, value),))
                for value, n in sorted(per_label.items())]
    return [*metrics, Metric(metric_id, tool, Scope("target"), float(len(items)))]
