"""gitleaks: secrets in the files of the target, counted per file and rule; the matches stay redacted."""
from __future__ import annotations

from pathlib import Path

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.sarif import count_metrics, findings
from swe_metrics.core.target import Target
from swe_metrics.tools.process import read_json, run, version

TOOL = "gitleaks"


class Gitleaks:
    """Implements core.analyzer.Analyzer with `gitleaks dir` and its SARIF report (redacted)."""

    id = "gitleaks"
    tool = TOOL
    families: tuple[str, ...] = ("secrets",)

    def version(self) -> str | None:
        """The installed gitleaks version."""
        return version(["gitleaks", "version"])

    def prerequisites(self) -> str:
        """gitleaks needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """Every file can contain a secret."""
        return target.files

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Scan the target directory, then keep only findings in the target's files."""
        sarif = str(Path(scratch) / "gitleaks.sarif")
        # ponytail: scans the whole root and filters afterwards; per-file scanning if large ignored trees hurt
        run(["gitleaks", "dir", ".", "--no-banner", "--redact", "--report-format", "sarif",
             "--report-path", sarif, "--exit-code", "0"], cwd=target.root)
        wanted = set(files)
        found = [f for f in findings(read_json(sarif), target.root) if f.path in wanted]
        metrics = count_metrics("secrets.findings", TOOL, found, ("rule", lambda f: f.rule))
        return Measurement(metrics, (("sarif", sarif),))
