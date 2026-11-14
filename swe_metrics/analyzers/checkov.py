"""checkov: failed and passed misconfiguration checks of every IaC framework per file and check, the inline
skips and whether they give a reason, and resources."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path, PurePath
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.sarif import Finding, count_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.files import copy_directories, copy_files
from swe_metrics.tools.process import ToolError, read_json, run, version

TOOL = "checkov"
SETTINGS = "terraform, cloudformation, kubernetes, arm, bicep and serverless frameworks, built-in checks"
FRAMEWORKS = ("terraform", "cloudformation", "kubernetes", "arm", "bicep", "serverless")
NO_REASON = "No comment provided"   # what checkov records for an inline skip without a comment
SNIFFED = ("yaml", "json", "bicep")
SNIFF_BYTES = 200_000   # a template's markers stand near its top; a bigger file is no template
# what a template or manifest says near its top: CloudFormation, Kubernetes, ARM (checkov picks the framework)
MARKERS = (("AWSTemplateFormatVersion",), ("AWS::",), ("apiVersion", "kind"), ("deploymentTemplate",))


class Checkov:
    """Implements core.analyzer.Analyzer with checkov on a copy of the IaC files, whatever their framework."""

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
        """The Terraform files, and the YAML, JSON and Bicep files that look like a template or manifest."""
        return tuple(p for p in target.files if language(p) == "terraform" or _looks_like_iac(target.root, p))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Check a copy of the files, so a .checkov.yaml in the target can't skip checks."""
        copy, output = Path(scratch) / "modules", Path(scratch) / "out"
        terraform = tuple(p for p in files if language(p) == "terraform")
        if terraform:
            copy_directories(target.root, terraform, copy)
        copy_files(target.root, (p for p in files if p not in terraform), copy)
        run(["checkov", "--directory", str(copy), "--framework", *FRAMEWORKS, "--output", "json",
             "--output", "sarif", "--output-file-path", str(output), "--soft-fail", "--skip-download"],
            cwd=scratch)
        report, sarif = output / "results_json.json", output / "results_sarif.sarif"
        reports = _reports(read_json(report))
        skips = Path(scratch) / "checkov-skips.json"
        skips.write_text(json.dumps(_skips(reports, set(files)), indent=1))
        details = (("sarif", str(sarif)), ("checkov-json", str(report)), ("checkov-skips-json", str(skips)))
        return Measurement(_metrics(reports, set(files)), details)


def _looks_like_iac(root: str, path: str) -> bool:
    """Whether a YAML, JSON or Bicep file is a template or manifest (checkov decides which framework)."""
    if language(path) not in SNIFFED and PurePath(path).suffix != ".bicep":
        return False
    if PurePath(path).name in ("serverless.yml", "serverless.yaml") or PurePath(path).suffix == ".bicep":
        return True
    with (Path(root) / path).open(errors="ignore") as source:
        head = source.read(SNIFF_BYTES)
    return any(all(word in head for word in words) for words in MARKERS)


def _reports(raw: Any) -> list[dict[str, Any]]:
    """checkov's JSON as one report per framework: it writes a list when several frameworks had files."""
    return raw if isinstance(raw, list) else [raw]


def _path(check: dict[str, Any]) -> str:
    """A check's file, relative to the copy."""
    return str(check["file_path"]).lstrip("/")


def _checks(reports: list[dict[str, Any]], kind: str, files: set[str]) -> list[tuple[str, dict[str, Any]]]:
    """The checks of a kind (framework, check) in the measured files."""
    return [(r.get("check_type", ""), c) for r in reports for c in r.get("results", {}).get(kind, [])
            if _path(c) in files]


def _skips(reports: list[dict[str, Any]], files: set[str]) -> list[dict[str, Any]]:
    """Each inline skip with its check, file, line and reason (empty without one), for a caller to compare."""
    return [{"check_id": c["check_id"], "file": _path(c), "line": c["file_line_range"][0],
             "reason": "" if _reason(c) == NO_REASON else _reason(c), "framework": framework}
            for framework, c in _checks(reports, "skipped_checks", files)]


def _reason(check: dict[str, Any]) -> str:
    """The comment of an inline skip, or checkov's placeholder when there is none."""
    return str((check.get("check_result") or {}).get("suppress_comment") or NO_REASON)


def _refuse_unparsed(reports: list[dict[str, Any]]) -> None:
    """Fails when checkov could not parse a file: its findings would be missing, not zero."""
    errors = [p for r in reports for p in r.get("results", {}).get("parsing_errors", [])]
    unparsed = [p.split("/modules/", 1)[-1] for p in errors]
    if unparsed or any(r.get("summary", r).get("parsing_errors") for r in reports):
        raise ToolError(f"checkov could not parse: {', '.join(unparsed)}")


def _metrics(reports: list[dict[str, Any]], files: set[str]) -> list[Metric]:
    """Failed checks per file, check and framework, and in total; skips, passed checks and resources."""
    _refuse_unparsed(reports)
    failed = [(f, Finding(c["check_id"], "failed", _path(c), c["file_line_range"][0]))
              for f, c in _checks(reports, "failed_checks", files)]
    skipped = [(f, Finding(c["check_id"], "skipped", _path(c), c["file_line_range"][0]))
               for f, c in _checks(reports, "skipped_checks", files)]
    bare = [c for _, c in _checks(reports, "skipped_checks", files) if _reason(c) == NO_REASON]
    resources = sum(r.get("summary", r).get("resource_count", 0) for r in reports)
    by_check: tuple[str, Callable[[Finding], str]] = ("check", lambda f: f.rule)
    metrics = count_metrics("iac.misconfigurations", TOOL, [f for _, f in failed], by_check)
    metrics += _by_framework("iac.misconfigurations", failed)
    metrics += count_metrics("iac.skipped_checks", TOOL, [f for _, f in skipped], by_check)
    metrics.append(Metric("iac.skips_without_reason", TOOL, Scope("target"), float(len(bare))))
    passed = len(_checks(reports, "passed_checks", files))
    return [*metrics, Metric("iac.passed_checks", TOOL, Scope("target"), float(passed)),
            Metric("iac.resources", TOOL, Scope("target"), float(resources))]


def _by_framework(metric_id: str, found: list[tuple[str, Finding]]) -> list[Metric]:
    """The count of findings per framework, as target-level metrics labelled with it."""
    by = {f: sum(1 for g, _ in found if g == f) for f in sorted({g for g, _ in found})}
    return [Metric(metric_id, TOOL, Scope("target"), float(n), labels=(("framework", name),))
            for name, n in by.items()]
