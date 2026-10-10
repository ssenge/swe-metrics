"""checkov: failed and passed Terraform misconfiguration checks per file and check, and resources."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.sarif import Finding, count_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.files import copy_directories
from swe_metrics.tools.process import ToolError, read_json, run, version

TOOL = "checkov"
SETTINGS = "terraform framework, built-in checks"


class Checkov:
    """Implements core.analyzer.Analyzer with `checkov --framework terraform` on a copy of the modules."""

    id = "checkov"
    tool = TOOL
    families: tuple[str, ...] = ("iac",)

    def version(self) -> str | None:
        """checkov's version and its fixed settings."""
        found = version(["checkov", "--version"])
        return f"{found} ({SETTINGS})" if found else None

    def prerequisites(self) -> str:
        """checkov needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Terraform files of the target."""
        return tuple(p for p in target.files if language(p) == "terraform")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Check a copy of the files' modules, so a .checkov.yaml in the target can't skip checks."""
        copy, output = Path(scratch) / "modules", Path(scratch) / "out"
        copy_directories(target.root, files, copy)
        run(["checkov", "--directory", str(copy), "--framework", "terraform", "--output", "json",
             "--output", "sarif", "--output-file-path", str(output), "--soft-fail", "--skip-download"],
            cwd=scratch)
        report, sarif = output / "results_json.json", output / "results_sarif.sarif"
        metrics = _metrics(read_json(report), set(files))
        return Measurement(metrics, (("sarif", str(sarif)), ("checkov-json", str(report))))


def _metrics(report: dict[str, Any], files: set[str]) -> list[Metric]:
    """Failed checks per file, check and in total; passed checks and resources in total."""
    summary = report.get("summary", report)  # without any resources checkov writes only the summary
    if summary.get("parsing_errors"):
        unparsed = [p.split("/modules/", 1)[-1] for p in report["results"]["parsing_errors"]]  # in the copy
        raise ToolError(f"checkov could not parse: {', '.join(unparsed)}")
    results = report.get("results", {})
    failed = [Finding(c["check_id"], "failed", c["file_path"].lstrip("/"), c["file_line_range"][0])
              for c in results.get("failed_checks", [])]
    found = [f for f in failed if f.path in files]
    passed = [c for c in results.get("passed_checks", []) if c["file_path"].lstrip("/") in files]
    metrics = count_metrics("iac.misconfigurations", TOOL, found, ("check", lambda f: f.rule))
    return [*metrics, Metric("iac.passed_checks", TOOL, Scope("target"), float(len(passed))),
            Metric("iac.resources", TOOL, Scope("target"), float(summary.get("resource_count", 0)))]
