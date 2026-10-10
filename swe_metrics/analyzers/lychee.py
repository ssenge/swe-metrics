"""lychee: links in Markdown and HTML files and the ones that don't resolve, checked offline."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import read_json, run, version

TOOL = "lychee"
SETTINGS = "offline, anchor fragments"  # offline: local links only, so results don't depend on the network
CHECKED = ("success_map", "error_map", "timeout_map", "redirect_map")  # excluded links are not checked
BROKEN = ("error_map", "timeout_map")
DOCUMENTS = ("markdown", "html")


class Lychee:
    """Implements core.analyzer.Analyzer with lychee's JSON report, run outside the target."""

    id = "lychee"
    tool = TOOL
    families: tuple[str, ...] = ("docs",)

    def version(self) -> str | None:
        """lychee's version and its fixed settings."""
        found = version(["lychee", "--version"])
        return f"{found} ({SETTINGS})" if found else None

    def prerequisites(self) -> str:
        """lychee needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Markdown and HTML files of the target."""
        return tuple(p for p in target.files if language(p) in DOCUMENTS)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Check the files' local links and anchors; it runs in scratch so no lychee.toml applies."""
        root = Path(target.root).resolve()
        report = str(Path(scratch) / "lychee.json")
        paths = {str(root / path): path for path in files}
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        run(["lychee", "--offline", "--include-fragments=anchor-only", "--format", "json", "--verbose",
             "--no-progress", "--root-dir", str(root), "--output", report, *paths], cwd=scratch, ok=(0, 2))
        return Measurement(_metrics(read_json(report), paths), (("lychee-json", report),))


def _metrics(report: dict[str, Any], paths: dict[str, str]) -> list[Metric]:
    """Checked and broken links per file (where there are any) and in total."""
    metrics = []
    for metric_id, maps in (("docs.links", CHECKED), ("docs.broken_links", BROKEN)):
        per_file = _per_file(report, maps, paths)
        metrics += [Metric(metric_id, TOOL, Scope("file", path), float(n))
                    for path, n in sorted(per_file.items())]
        metrics.append(Metric(metric_id, TOOL, Scope("target"), float(sum(per_file.values()))))
    return metrics


def _per_file(report: dict[str, Any], maps: tuple[str, ...], paths: dict[str, str]) -> dict[str, int]:
    """Links per input file in the given status maps, keyed by the file's path in the target."""
    counts: dict[str, int] = {}
    for name in maps:
        for source, links in (report.get(name) or {}).items():
            path = paths.get(source, source)
            counts[path] = counts.get(path, 0) + len(links)
    return {path: n for path, n in counts.items() if n}
