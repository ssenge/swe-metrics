"""cfn-lint: validation findings of CloudFormation templates (invalid properties, references, types)."""
from __future__ import annotations

import os
from pathlib import Path

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.iac import is_cloudformation
from swe_metrics.core.sarif import Finding, lint_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.files import copy_files
from swe_metrics.tools.process import read_json, run, version

TOOL = "cfn-lint"
SETTINGS = "default rules, target config ignored"
SNIFF_BYTES = 200_000   # a template's marks stand near its top
# cfn-lint exits with a bitmask of what it found (2 errors, 4 warnings, 8 informational); 1 is a failure
FINDING_EXITS = (0, 2, 4, 6, 8, 10, 12, 14)


class CfnLint:
    """Implements core.analyzer.Analyzer with `cfn-lint --format json` on a copy of the templates."""

    id = "cfn-lint"
    tool = TOOL
    families: tuple[str, ...] = ("iac",)

    def version(self) -> str | None:
        """cfn-lint's version and its fixed settings (a .cfnlintrc in the target would change the results)."""
        found = version(["cfn-lint", "--version"])
        return f"{found} ({SETTINGS})" if found else None

    def prerequisites(self) -> str:
        """cfn-lint needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The YAML and JSON files that are CloudFormation templates."""
        data = (p for p in target.files if language(p) in ("yaml", "json"))
        return tuple(p for p in data if _is_template(target.root, p))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Validate a copy of the templates, in a folder and a home of their own so no config file applies."""
        copy, report = Path(scratch) / "templates", Path(scratch) / "cfn-lint.json"
        copy_files(target.root, files, copy)
        env = {**os.environ, "HOME": scratch}
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        output = run(["cfn-lint", "--format", "json", *files], cwd=str(copy), ok=FINDING_EXITS, env=env)
        report.write_text(output or "[]")
        found = [Finding(f["Rule"]["Id"], str(f["Level"]).lower(), f["Filename"],
                         int(f["Location"]["Start"]["LineNumber"])) for f in read_json(report)]
        metrics = lint_metrics("iac.validation_findings", TOOL, found)
        return Measurement(metrics, (("cfn-lint-json", str(report)),))


def _is_template(root: str, path: str) -> bool:
    """Whether a YAML or JSON file of the target is a CloudFormation template."""
    with (Path(root) / path).open(errors="ignore") as source:
        return is_cloudformation(source.read(SNIFF_BYTES))
