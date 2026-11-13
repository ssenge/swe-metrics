"""checkstyle: violations of the caller's Checkstyle configuration in Java files, per file, rule, severity."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from defusedxml.ElementTree import parse

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.sarif import Finding, lint_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.files import digest
from swe_metrics.tools.process import ToolError, run, version

TOOL = "checkstyle"
EXIT_CODES = tuple(range(256))   # Checkstyle exits with its number of violations: the report file decides


class Checkstyle:
    """Implements core.analyzer.Analyzer with `checkstyle -f xml` and the caller's configuration."""

    id = "checkstyle"
    tool = TOOL
    families: tuple[str, ...] = ("lint",)

    def __init__(self, configs: Sequence[str] = ()) -> None:
        """configs: Checkstyle configurations; there is no neutral default, so without one it is skipped."""
        self.configs = [str(Path(c).resolve()) for c in configs]

    def version(self) -> str | None:
        """Checkstyle's version, with each configuration's name and digest: what the report ran."""
        found = version(["checkstyle", "--version"])
        if not found or not all(Path(c).is_file() for c in self.configs):
            return found
        shown = "; ".join(f"{Path(c).stem} sha256:{digest(c)[:12]}" for c in self.configs)
        return f"{found} (rules: {shown})" if shown else found

    def prerequisites(self) -> str:
        """Checkstyle needs a configuration, and it must exist."""
        if not self.configs:
            return "no Checkstyle rules given (--rules checkstyle=PATH)"
        missing = [c for c in self.configs if not Path(c).is_file()]
        return f"Checkstyle rules not found: {', '.join(missing)}" if missing else ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Java files of the target."""
        return tuple(p for p in target.files if language(p) == "java")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Check the files against each configuration; count violations per file, rule and severity."""
        root = Path(target.root).resolve()
        found: list[Finding] = []
        details = []
        for n, config in enumerate(self.configs):
            report = Path(scratch) / f"checkstyle-{n}.xml"
            # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
            said = run(["checkstyle", "-c", config, "-f", "xml", "-o", str(report), *files], cwd=target.root,
                       ok=EXIT_CODES)
            if not report.is_file():
                raise ToolError(f"checkstyle wrote no report: {' | '.join(said.strip().splitlines()[-3:])}")
            found += _findings(report, root)
            details.append(("checkstyle-xml", str(report)))
        return Measurement(lint_metrics("lint.violations", TOOL, found), tuple(details))


def _findings(report: Path, root: Path) -> list[Finding]:
    """The violations of a Checkstyle XML report: rule (the check's name), severity, file and line."""
    found = []
    top = parse(report).getroot()
    for file in top.iter("file") if top is not None else ():
        path = _relative(file.get("name", ""), root)
        for error in file.iter("error"):
            rule = error.get("source", "").rsplit(".", 1)[-1].removesuffix("Check")
            found.append(Finding(rule, error.get("severity", "error"), path, int(error.get("line", 0))))
    return found


def _relative(name: str, root: Path) -> str:
    """A reported file name relative to the target's root."""
    try:
        return str(Path(name).resolve().relative_to(root))
    except ValueError:
        return name
