"""One measurement: run every applicable analyzer on the target and assemble the report."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from swe_metrics.core.analyzer import Analyzer
from swe_metrics.core.catalog import family
from swe_metrics.core.report import AnalyzerRun, Metric, Report
from swe_metrics.core.target import Target
from swe_metrics.runner.discover import discover


def measure(path: Path, analyzers: Sequence[Analyzer], only: tuple[str, ...] = (),
            exclude: tuple[str, ...] = ()) -> Report:
    """Measure a file, directory or repository; `only` limits the metric families."""
    target, subject = discover(path, exclude)
    runs, metrics = [], []
    for analyzer in analyzers:
        run, found = _run(analyzer, target, only)
        runs.append(run)
        metrics += [m for m in found if not only or family(m.id) in only]
    return Report(subject, tuple(runs), tuple(metrics))


def _run(analyzer: Analyzer, target: Target, only: tuple[str, ...]) -> tuple[AnalyzerRun, list[Metric]]:
    """Run one analyzer; a missing tool or a fault is a failed run, never an exception."""
    def status(state: str, reason: str = "", version: str = "") -> AnalyzerRun:
        return AnalyzerRun(analyzer.id, analyzer.tool, state, version, reason)

    if only and not set(analyzer.families) & set(only):
        return status("skipped", "not selected"), []
    version = analyzer.version()
    if version is None:
        return status("failed", f"{analyzer.tool} is not installed"), []
    files = analyzer.applicable(target)
    if not files:
        return status("skipped", "no applicable files", version), []
    try:
        return status("ran", version=version), analyzer.measure(target, files)
    except Exception as exc:  # an analyzer fault must not cost the other analyzers' results
        return status("failed", f"{type(exc).__name__}: {exc}", version), []
