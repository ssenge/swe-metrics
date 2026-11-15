"""jscpd: code clones, duplicated lines and the duplicated share, per file and for the target.

jscpd 4 lists each file's values in its report; jscpd 5 lists only the clones, so a file's duplicated
lines are the lines its clones cover, and its share is relative to its line count.
"""
from __future__ import annotations

from collections import defaultdict
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
        # absolute paths: jscpd 5 writes relative ones against each scanned path, not the working directory
        run(["jscpd", *files, "--reporters", "json", "--output", scratch, "--silent", "--absolute",
             "--min-tokens", str(MIN_TOKENS), "--min-lines", str(MIN_LINES)], cwd=target.root)
        report = Path(scratch) / "jscpd-report.json"
        if not report.exists():  # jscpd skipped every file (format, size), so it wrote no report
            return Measurement([])
        return Measurement(_metrics(read_json(report), Path(target.root).resolve()),
                           (("jscpd-json", str(report)),))


def _lines(path: Path) -> int:
    """A file's lines as jscpd counts them (its content split at newlines); unreadable: left to jscpd."""
    try:
        return path.read_bytes().count(b"\n") + 1
    except OSError:
        return MIN_LINES  # jscpd then reports the error itself, and the analyzer fails


def _metrics(report: dict[str, Any], root: Path) -> list[Metric]:
    """Target totals, then the duplicated lines and share of every file that has a clone."""
    total = report["statistics"]["total"]
    metrics = [Metric("duplication.percent", TOOL, Scope("target"), float(total["percentage"])),
               Metric("duplication.duplicated_lines", TOOL, Scope("target"), float(total["duplicatedLines"])),
               Metric("duplication.clones", TOOL, Scope("target"), float(total["clones"]))]
    for path, (lines, percent) in sorted(_per_file(report, root).items()):
        if lines:
            scope = Scope("file", path)
            metrics += [Metric("duplication.percent", TOOL, scope, float(percent)),
                        Metric("duplication.duplicated_lines", TOOL, scope, float(lines))]
    return metrics


def _per_file(report: dict[str, Any], root: Path) -> dict[str, tuple[float, float]]:
    """Duplicated lines and share per file: from jscpd 4's per-format sources, else from the clones."""
    listed = {_relative(path, root): (source["duplicatedLines"], source["percentage"])
              for fmt in report["statistics"].get("formats", {}).values()
              if isinstance(fmt.get("sources"), dict)  # jscpd 5: a count of files, not a map
              for path, source in fmt["sources"].items()}
    return listed or _from_clones(report.get("duplicates", []), root)


def _from_clones(clones: list[dict[str, Any]], root: Path) -> dict[str, tuple[float, float]]:
    """Per file, the lines its clones cover (start and end included) and their share of its lines."""
    covered: dict[str, set[int]] = defaultdict(set)
    for clone in clones:
        for side in (clone["firstFile"], clone["secondFile"]):
            covered[_relative(side["name"], root)].update(range(side["start"], side["end"] + 1))
    return {path: (len(lines), round(100 * len(lines) / _line_count(root / path), 2))
            for path, lines in covered.items()}


def _relative(name: str, root: Path) -> str:
    """A path of the report relative to the target root (with --absolute, jscpd writes absolute paths)."""
    path = Path(name)
    return path.relative_to(root).as_posix() if path.is_absolute() else name


def _line_count(path: Path) -> int:
    """A file's line count, at least 1 (also for an unreadable file, which jscpd then reports itself)."""
    try:
        return max(len(path.read_bytes().splitlines()), 1)
    except OSError:
        return 1
