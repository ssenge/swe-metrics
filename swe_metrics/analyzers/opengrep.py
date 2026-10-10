"""opengrep: static analysis findings of the rules the caller gives, per file and level."""
from __future__ import annotations

from pathlib import Path

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.sarif import count_metrics, findings
from swe_metrics.core.target import Target, code_files
from swe_metrics.tools.process import read_json, run, version

TOOL = "opengrep"


class Opengrep:
    """Implements core.analyzer.Analyzer with `opengrep scan` and its SARIF report."""

    id = "opengrep"
    tool = TOOL
    families: tuple[str, ...] = ("security",)

    def __init__(self, rules: str | None = None) -> None:
        """rules: a rule file or directory; the results depend on it, so it is the caller's choice."""
        self.rules = str(Path(rules).resolve()) if rules else None

    def version(self) -> str | None:
        """The installed opengrep version."""
        return version(["opengrep", "--version"])

    def prerequisites(self) -> str:
        """opengrep needs rules; without them there is nothing to report."""
        if not self.rules:
            return "no SAST rules given (--sast-rules)"
        return "" if Path(self.rules).exists() else f"SAST rules not found: {self.rules}"

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The code files of the target."""
        return code_files(target.files)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Scan the code files with the rules; count the findings per file and level."""
        sarif = str(Path(scratch) / "opengrep.sarif")
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        argv = ["opengrep", "scan", "--config", str(self.rules), "--sarif", "--output", sarif, "--quiet"]
        run([*argv, *files], cwd=target.root)
        found = findings(read_json(sarif), target.root)
        metrics = count_metrics("security.findings", TOOL, found, ("level", lambda f: f.level))
        return Measurement(metrics, (("sarif", sarif),))
