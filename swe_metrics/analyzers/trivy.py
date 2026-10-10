"""trivy: the packages that manifests and lock files declare, and their known vulnerabilities per severity."""
from __future__ import annotations

import json
import subprocess  # nosec B404
from pathlib import Path, PurePath
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.sarif import Finding, count_metrics
from swe_metrics.core.target import Target
from swe_metrics.tools.process import ToolError, read_json, run

TOOL = "trivy"
MANIFESTS = {"pom.xml", "build.gradle", "build.gradle.kts", "package-lock.json", "yarn.lock",
             "pnpm-lock.yaml", "requirements.txt", "Pipfile.lock", "poetry.lock", "uv.lock", "go.mod",
             "Cargo.lock", "Gemfile.lock", "composer.lock", "packages.lock.json"}


class Trivy:
    """Implements core.analyzer.Analyzer with `trivy fs` (JSON for the metrics, converted to SARIF)."""

    id = "trivy"
    tool = TOOL
    families: tuple[str, ...] = ("dependencies",)

    def version(self) -> str | None:
        """trivy's version and the date of its vulnerability database (results depend on both)."""
        try:
            info = json.loads(run(["trivy", "version", "--format", "json"], "."))
        except (FileNotFoundError, ToolError, ValueError, subprocess.TimeoutExpired):
            return None
        updated = (info.get("VulnerabilityDB") or {}).get("UpdatedAt", "")[:10]
        return f"{info['Version']} (db {updated})" if updated else str(info["Version"])

    def prerequisites(self) -> str:
        """trivy needs nothing beyond itself (it fetches its database on first use)."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """Manifests and lock files trivy reads."""
        return tuple(p for p in target.files if PurePath(p).name in MANIFESTS or p.endswith(".csproj"))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Scan the target, keep the results of its manifests, and convert the report to SARIF."""
        report, sarif = str(Path(scratch) / "trivy.json"), str(Path(scratch) / "trivy.sarif")
        run(["trivy", "fs", "--quiet", "--format", "json", "--list-all-pkgs", "--scanners", "vuln",
             "--output", report, "."], cwd=target.root)
        run(["trivy", "convert", "--format", "sarif", "--output", sarif, report], cwd=target.root)
        wanted = set(files)
        results = [r for r in read_json(report).get("Results") or [] if r.get("Target") in wanted]
        return Measurement(_metrics(results), (("sarif", sarif), ("trivy-json", report)))


def _metrics(results: list[dict[str, Any]]) -> list[Metric]:
    """Packages per manifest and in total; vulnerabilities per manifest, per severity and in total."""
    packages = [(r["Target"], len(r.get("Packages") or [])) for r in results]
    metrics = [Metric("dependencies.packages", TOOL, Scope("file", path), float(n)) for path, n in packages]
    metrics.append(Metric("dependencies.packages", TOOL, Scope("target"), float(sum(n for _, n in packages))))
    vulns = [Finding(v["VulnerabilityID"], v.get("Severity", "UNKNOWN").lower(), r["Target"])
             for r in results for v in r.get("Vulnerabilities") or []]
    by_severity = ("severity", lambda f: f.level)
    return metrics + count_metrics("dependencies.vulnerabilities", TOOL, vulns, by_severity)
