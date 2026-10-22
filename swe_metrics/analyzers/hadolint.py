"""hadolint: Dockerfile lint findings per file, rule and level, with a fixed configuration."""
from __future__ import annotations

import json
from pathlib import Path

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.dockerfile import is_dockerfile
from swe_metrics.core.sarif import Finding, lint_metrics
from swe_metrics.core.target import Target
from swe_metrics.tools.process import run, version

TOOL = "hadolint"
CONFIG = "ignored: []\n"  # hadolint's defaults; replaces a .hadolint.yaml in the target or the user's home


class Hadolint:
    """Implements core.analyzer.Analyzer with hadolint's JSON output (metrics) and SARIF output (detail)."""

    id = "hadolint"
    tool = TOOL
    families: tuple[str, ...] = ("container",)

    def version(self) -> str | None:
        """hadolint's version and its fixed configuration (a target's config would change the results)."""
        found = version(["hadolint", "--version"])
        return f"{found} (default rules, target config ignored)" if found else None

    def prerequisites(self) -> str:
        """hadolint needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Dockerfiles of the target."""
        return tuple(path for path in target.files if is_dockerfile(path))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Lint the Dockerfiles; count findings per file, rule and level (hadolint's own levels)."""
        config, sarif = Path(scratch) / "hadolint.yaml", Path(scratch) / "hadolint.sarif"
        config.write_text(CONFIG)
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        argv = ["hadolint", "--no-fail", "--no-color", "--config", str(config)]
        report = json.loads(run([*argv, "--format", "json", *files], cwd=target.root) or "[]")
        sarif.write_text(run([*argv, "--format", "sarif", *files], cwd=target.root))
        found = [Finding(r["code"], r["level"], r["file"], int(r.get("line", 0))) for r in report]
        metrics = lint_metrics("container.lint_findings", TOOL, found)
        return Measurement(metrics, (("sarif", str(sarif)),))
