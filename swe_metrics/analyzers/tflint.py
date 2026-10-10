"""tflint: Terraform lint findings of the bundled ruleset's recommended preset, per file and rule."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.sarif import count_metrics, findings
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import ToolError, read_json, run, version

TOOL = "tflint"
# Fixed configuration, so a .tflint.hcl in the target can't change the rules.
CONFIG = """config {
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
"""


class Tflint:
    """Implements core.analyzer.Analyzer with `tflint --recursive` and its SARIF report."""

    id = "tflint"
    tool = TOOL
    families: tuple[str, ...] = ("iac",)

    def version(self) -> str | None:
        """tflint's version, its bundled terraform ruleset and the preset (results depend on all three)."""
        found = version(["tflint", "--version"])
        ruleset = version(["tflint", "--version"], r"ruleset\.terraform \(([^)]+)\)")
        return f"{found} (ruleset terraform {ruleset}, recommended preset)" if found and ruleset else None

    def prerequisites(self) -> str:
        """tflint needs nothing beyond itself and its bundled ruleset."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Terraform files of the target."""
        return tuple(p for p in target.files if language(p) == "terraform")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Lint every module of the target with the fixed configuration; keep findings in the files."""
        config, sarif = Path(scratch) / "tflint.hcl", Path(scratch) / "tflint.sarif"
        config.write_text(CONFIG)
        output = run(["tflint", "--recursive", "--force", "--no-color", "--format", "sarif",
                      "--config", str(config)], cwd=target.root, ok=(0, 1))
        sarif.write_text(output)
        doc = read_json(sarif)
        _raise_errors(doc)
        wanted = set(files)
        lint = {"runs": [r for r in doc.get("runs", []) if _driver(r) == "tflint"]}
        found = [f for f in findings(lint, target.root) if f.path in wanted]
        metrics = count_metrics("iac.lint_findings", TOOL, found, ("rule", lambda f: f.rule))
        return Measurement(metrics, (("sarif", str(sarif)),))


def _driver(run_: dict[str, Any]) -> str:
    """The tool name of a SARIF run: tflint reports its findings and its own errors as separate runs."""
    return str(run_.get("tool", {}).get("driver", {}).get("name", ""))


def _raise_errors(doc: dict[str, Any]) -> None:
    """ToolError if tflint couldn't lint a module (e.g. a syntax error); its findings would be partial."""
    errors = [result.get("message", {}).get("text", "").split("\n")[0]
              for run_ in doc.get("runs", []) if _driver(run_) == "tflint-errors"
              for result in run_.get("results", [])]
    if errors:
        raise ToolError(f"tflint failed: {' | '.join(errors)}")
