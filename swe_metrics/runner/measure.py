"""One measurement: run every applicable analyzer on the target and assemble the report."""
from __future__ import annotations

import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from swe_metrics.core.analyzer import Analyzer, Measurement
from swe_metrics.core.catalog import families, family
from swe_metrics.core.report import AnalyzerRun, Detail, Report
from swe_metrics.core.target import Target
from swe_metrics.runner.discover import discover


@dataclass(frozen=True)
class Options:
    """What to measure and where detailed outputs go (None: detailed outputs are discarded). `only` names
    metric families or analyzer ids; a name that is both is the family."""

    only: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    details: Path | None = None
    changed_since: str = ""


DEFAULTS = Options()


def measure(path: Path, analyzers: Sequence[Analyzer], options: Options = DEFAULTS) -> Report:
    """Measure a file, directory or repository with every analyzer, each in its own scratch directory."""
    target, subject = discover(path, options.exclude, options.changed_since)
    runs, metrics, details = [], [], []
    for analyzer in analyzers:
        with tempfile.TemporaryDirectory(prefix=f"swe-metrics-{analyzer.id}-") as scratch:
            run, found = _run(analyzer, target, options.only, scratch)
            details += _keep(analyzer.id, found.details, options.details)
        runs.append(run)
        metrics += [m for m in found.metrics if not options.only or _selects(options.only, analyzer, m.id)]
    return Report(subject, tuple(runs), tuple(metrics), tuple(details))


def _by_id(only: tuple[str, ...], analyzer: Analyzer) -> bool:
    """Whether `only` names the analyzer by its id (a name that is also a metric family is the family)."""
    return analyzer.id in only and analyzer.id not in families()


def _selects(only: tuple[str, ...], analyzer: Analyzer, metric_id: str) -> bool:
    """Whether `only` keeps a metric of the analyzer: its family is named, or the analyzer itself is."""
    return family(metric_id) in only or _by_id(only, analyzer)


def _run(analyzer: Analyzer, target: Target, only: tuple[str, ...],
         scratch: str) -> tuple[AnalyzerRun, Measurement]:
    """Run one analyzer; a missing tool, a missing prerequisite or a fault is a status, never an exception."""
    def status(state: str, reason: str = "", version: str = "") -> AnalyzerRun:
        return AnalyzerRun(analyzer.id, analyzer.tool, state, version, reason, tuple(analyzer.families))

    nothing = Measurement([])
    if only and not set(analyzer.families) & set(only) and not _by_id(only, analyzer):
        return status("skipped", "not selected"), nothing
    version = analyzer.version()
    if version is None:
        return status("failed", f"{analyzer.tool} is not installed"), nothing
    files, missing = analyzer.applicable(target), analyzer.prerequisites()
    if missing or not files:
        return status("skipped", missing or "no applicable files", version), nothing
    try:
        return status("ran", version=version), analyzer.measure(target, files, scratch)
    except Exception as exc:  # an analyzer fault must not cost the other analyzers' results
        return status("failed", f"{type(exc).__name__}: {exc}", version), nothing


def _keep(analyzer: str, outputs: tuple[tuple[str, str], ...], directory: Path | None) -> list[Detail]:
    """Copy an analyzer's detailed outputs out of its scratch directory, named after the analyzer."""
    if directory is None:
        return []
    directory.mkdir(parents=True, exist_ok=True)
    kept = []
    for n, (fmt, source) in enumerate(outputs):
        name = f"{analyzer}{f'-{n}' if n else ''}{Path(source).suffix}"
        shutil.copyfile(source, directory / name)
        kept.append(Detail(analyzer, fmt, name))
    return kept
