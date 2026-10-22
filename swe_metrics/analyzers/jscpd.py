"""jscpd: code clones, duplicated lines and the duplicated share, per file and for the target."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.target import Target, code_files
from swe_metrics.tools.process import read_json, run, version

TOOL = "jscpd"
MIN_TOKENS, MIN_LINES = 50, 5  # jscpd's defaults, passed explicitly so a target's config can't change them


class Jscpd:
    """Implements core.analyzer.Analyzer with jscpd's JSON report."""

    id = "jscpd"
    tool = TOOL
    families: tuple[str, ...] = ("duplication",)

    def version(self) -> str | None:
        """jscpd's version and its detection settings (results depend on both)."""
        found = version(["jscpd", "--version"])
        return f"{found} (min-tokens {MIN_TOKENS}, min-lines {MIN_LINES})" if found else None

    def prerequisites(self) -> str:
        """jscpd needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The code files jscpd considers: those with at least MIN_LINES lines (it ignores shorter ones)."""
        return tuple(p for p in code_files(target.files) if _lines(Path(target.root) / p) >= MIN_LINES)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Detect clones across the code files; report totals and per-file values."""
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        run(["jscpd", *files, "--reporters", "json", "--output", scratch, "--silent",
             "--min-tokens", str(MIN_TOKENS), "--min-lines", str(MIN_LINES)], cwd=target.root)
        report = Path(scratch) / "jscpd-report.json"
        if not report.exists():  # jscpd skipped every file (format, size), so it wrote no report
            return Measurement([])
        return Measurement(_metrics(read_json(report)), (("jscpd-json", str(report)),))


def _lines(path: Path) -> int:
    """A file's lines as jscpd counts them (its content split at newlines); unreadable: left to jscpd."""
    try:
        return path.read_bytes().count(b"\n") + 1
    except OSError:
        return MIN_LINES  # jscpd then reports the error itself, and the analyzer fails


def _metrics(report: dict[str, Any]) -> list[Metric]:
    """Target totals, then the duplicated lines and share of every file that has a clone."""
    total = report["statistics"]["total"]
    metrics = [Metric("duplication.percent", TOOL, Scope("target"), float(total["percentage"])),
               Metric("duplication.duplicated_lines", TOOL, Scope("target"), float(total["duplicatedLines"])),
               Metric("duplication.clones", TOOL, Scope("target"), float(total["clones"]))]
    for fmt in report["statistics"].get("formats", {}).values():
        for path, source in sorted(fmt.get("sources", {}).items()):
            if source["duplicatedLines"]:
                scope = Scope("file", path)
                lines = float(source["duplicatedLines"])
                metrics += [Metric("duplication.percent", TOOL, scope, float(source["percentage"])),
                            Metric("duplication.duplicated_lines", TOOL, scope, lines)]
    return metrics
