"""opengrep: static analysis findings of the rules the caller gives, per file, level and rule set."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.sarif import Finding, count_metrics, findings
from swe_metrics.core.target import Target, code_files
from swe_metrics.tools.files import digest
from swe_metrics.tools.process import read_json, run, version

TOOL = "opengrep"


class Opengrep:
    """Implements core.analyzer.Analyzer with `opengrep scan` and its SARIF report."""

    id = "opengrep"
    tool = TOOL
    families: tuple[str, ...] = ("security",)

    def __init__(self, rules: str | Sequence[str] | None = None) -> None:
        """rules: rule files or directories, each scanned on its own; the results depend on them, so they are
        the caller's choice."""
        given = [rules] if isinstance(rules, str) else list(rules or ())
        self.sets = [str(Path(r).resolve()) for r in given]

    def version(self) -> str | None:
        """The installed opengrep version, with each rule set's name and digest: what the report ran."""
        found = version(["opengrep", "--version"])
        if not found or not self.sets or not all(Path(s).exists() for s in self.sets):
            return found
        return f"{found} (rules: {'; '.join(f'{Path(s).stem} sha256:{digest(s)[:12]}' for s in self.sets)})"

    def prerequisites(self) -> str:
        """opengrep needs rules; without them there is nothing to report."""
        if not self.sets:
            return "no SAST rules given (--sast-rules or --rules opengrep=PATH)"
        missing = [s for s in self.sets if not Path(s).exists()]
        return f"SAST rules not found: {', '.join(missing)}" if missing else ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The code files of the target."""
        return code_files(target.files)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Scan the code files with each rule set; count the findings per file, level and rule set."""
        found: list[Finding] = []
        per_set: list[Metric] = []
        details = []
        for n, rules in enumerate(self.sets):
            sarif = str(Path(scratch) / f"opengrep-{n}.sarif")
            # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
            argv = ["opengrep", "scan", "--config", rules, "--sarif", "--output", sarif, "--quiet"]
            run([*argv, *files], cwd=target.root)
            mine = findings(read_json(sarif), target.root)
            found += mine
            per_set.append(Metric("security.findings", TOOL, Scope("target"), float(len(mine)),
                                  labels=(("rules", Path(rules).stem),)))
            details.append(("sarif", sarif))
        metrics = count_metrics("security.findings", TOOL, found, ("level", lambda f: f.level))
        return Measurement([*metrics, *per_set], tuple(details))
