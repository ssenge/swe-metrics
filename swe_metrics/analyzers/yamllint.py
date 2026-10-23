"""yamllint: YAML lint findings per file, rule and level, with yamllint's default rules but line length."""
from __future__ import annotations

import re
from pathlib import Path, PurePath

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.sarif import Finding, lint_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import run, version

TOOL = "yamllint"
# Line length is a style choice of the code base, not a quality signal; every other rule is the default.
CONFIG = "{extends: default, rules: {line-length: disable}}"
SETTINGS = "default rules without line-length, target config ignored, lock files skipped"
FINDINGS = 1  # yamllint's exit code when it found an error; a file it can't read exits with another code
# Lock files that package managers generate and rewrite on every dependency update; nobody edits them.
LOCK_FILES = frozenset({"pnpm-lock.yaml", "conda-lock.yml", "conda-lock.yaml"})
LINE = re.compile(r"^(?P<path>.+):(?P<line>\d+):\d+: \[(?P<level>\w+)\] .* \((?P<rule>[\w-]+)\)$")


class Yamllint:
    """Implements core.analyzer.Analyzer with yamllint's parsable output."""

    id = "yamllint"
    tool = TOOL
    families: tuple[str, ...] = ("yaml",)

    def version(self) -> str | None:
        """yamllint's version and its fixed settings (a target's .yamllint would change the results)."""
        found = version(["yamllint", "--version"])
        return f"{found} ({SETTINGS})" if found else None

    def prerequisites(self) -> str:
        """yamllint needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The YAML files of the target, by file name (see core.target), without generated lock files."""
        return tuple(p for p in target.files if language(p) == "yaml" and PurePath(p).name not in LOCK_FILES)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Lint the files; count findings per file, rule and level (yamllint's own: error, warning)."""
        report = Path(scratch) / "yamllint.txt"
        # -d replaces every other config: a .yamllint in the target, the user's, YAMLLINT_CONFIG_FILE.
        # Inline `# yamllint disable` comments are part of the source and stay honored.
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        output = run(["yamllint", "--format", "parsable", "--config-data", CONFIG, "--", *files],
                     cwd=target.root, ok=(0, FINDINGS))
        report.write_text(output)
        metrics = lint_metrics("yaml.lint_findings", TOOL, findings(output, set(files)))
        return Measurement(metrics, (("yamllint-parsable", str(report)),))


def findings(output: str, wanted: set[str]) -> list[Finding]:
    """The parsable lines as findings in the measured files; syntax errors have the rule `syntax`."""
    found = []
    for line in output.splitlines():
        match = LINE.match(line)
        if match and match["path"] in wanted:
            found.append(Finding(match["rule"], match["level"], match["path"], int(match["line"])))
    return found
