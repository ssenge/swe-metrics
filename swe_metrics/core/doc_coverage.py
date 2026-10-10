"""Doc coverage metrics from per-file flags: documented and undocumented public APIs and their share."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from swe_metrics.core.report import Metric, Scope

Labels = tuple[tuple[str, str], ...]


def _metrics(flags: Sequence[bool], tool: str, scope: Scope, labels: Labels) -> list[Metric]:
    """Documented, undocumented and (when there is any public API) the documented percentage."""
    documented = sum(flags)
    values: list[tuple[str, float]] = [("doc_coverage.documented", documented),
                                       ("doc_coverage.undocumented", len(flags) - documented)]
    if flags:
        values.append(("doc_coverage.percent", round(100 * documented / len(flags), 2)))
    return [Metric(metric_id, tool, scope, float(value), labels=labels) for metric_id, value in values]


def doc_metrics(files: Mapping[str, tuple[str, Sequence[bool]]], tool: str) -> list[Metric]:
    """Per file (by path: language and flags), per language, and in total over all files."""
    metrics: list[Metric] = []
    by_language: dict[str, list[bool]] = {}
    for path, (language, flags) in sorted(files.items()):
        metrics += _metrics(flags, tool, Scope("file", path), (("language", language),))
        by_language.setdefault(language, []).extend(flags)
    for language, flags in sorted(by_language.items()):
        metrics += _metrics(flags, tool, Scope("target"), (("language", language),))
    return metrics + _metrics([f for flags in by_language.values() for f in flags], tool, Scope("target"), ())
