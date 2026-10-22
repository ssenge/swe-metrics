"""ShellCheck: shell script lint findings per file, rule and level, with ShellCheck's default checks."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.sarif import Finding, lint_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import run, version

TOOL = "shellcheck"
SETTINGS = "default checks, rc files and SHELLCHECK_OPTS ignored"
FINDINGS = 1  # ShellCheck's exit code when it found something; 2 means a file couldn't be read


class Shellcheck:
    """Implements core.analyzer.Analyzer with ShellCheck's json1 output."""

    id = "shellcheck"
    tool = TOOL
    families: tuple[str, ...] = ("shell",)

    def version(self) -> str | None:
        """ShellCheck's version and its fixed settings (a target's .shellcheckrc would change the results)."""
        found = version(["shellcheck", "--version"])
        return f"{found} ({SETTINGS})" if found else None

    def prerequisites(self) -> str:
        """ShellCheck needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The shell scripts of the target, by file name (see core.target)."""
        return tuple(p for p in target.files if language(p) == "shell")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Lint the scripts; count findings per file, rule (SC code) and level (ShellCheck's own levels)."""
        report = Path(scratch) / "shellcheck.json"
        # --norc: no .shellcheckrc of the target or the user; inline `# shellcheck disable=` stays honored.
        # Sourced files aren't followed (no -x): what they contain depends on paths outside the target.
        env = {k: v for k, v in os.environ.items() if k != "SHELLCHECK_OPTS"}
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        output = run(["shellcheck", "--norc", "--format", "json1", "--", *files], cwd=target.root,
                     ok=(0, FINDINGS), env=env)
        report.write_text(output or '{"comments": []}')
        found = findings(json.loads(report.read_text()), set(files))
        metrics = lint_metrics("shell.lint_findings", TOOL, found)
        return Measurement(metrics, (("shellcheck-json", str(report)),))


def findings(doc: dict[str, Any], wanted: set[str]) -> list[Finding]:
    """The json1 comments as findings in the measured files; the rule is the SC code, e.g. SC2086."""
    return [Finding(f"SC{c['code']}", c["level"], c["file"], int(c.get("line", 0)))
            for c in doc.get("comments", []) if c["file"] in wanted]
