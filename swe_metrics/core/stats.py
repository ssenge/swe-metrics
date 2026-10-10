"""Distribution statistics of measured values, and target-level roll-ups of finer-grained metrics."""
from __future__ import annotations

import math
from collections.abc import Sequence

from swe_metrics.core.report import Metric, Scope, Stats


def percentile(ordered: Sequence[float], share: float) -> float:
    """Nearest-rank percentile of sorted values: deterministic and always an observed value."""
    rank = max(1, math.ceil(share * len(ordered)))
    return ordered[rank - 1]


def summarize(values: Sequence[float]) -> Stats | None:
    """count, sum, mean, p50, p95 and max of the values; None when there are none."""
    if not values:
        return None
    ordered = sorted(values)
    total = sum(ordered)
    return Stats(len(ordered), total, total / len(ordered), percentile(ordered, 0.5),
                 percentile(ordered, 0.95), ordered[-1])


def rollup(metrics: Sequence[Metric], metric_id: str, tool: str) -> Metric | None:
    """One target-level metric with the statistics of the metric's per-file or per-function values."""
    values = [m.value for m in metrics if m.id == metric_id and m.value is not None]
    stats = summarize(values)
    return Metric(metric_id, tool, Scope("target"), stats=stats) if stats else None
