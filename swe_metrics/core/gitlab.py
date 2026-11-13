"""GitLab security reports (gl-sast-report.json and its siblings): findings per severity and rule."""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from swe_metrics.core.report import Metric
from swe_metrics.core.sarif import Finding, count_metrics

# scan type -> the metric its findings count under: the report says which kind of scanner wrote it
SCANS = {
    "sast": "security.findings",
    "secret_detection": "secrets.findings",
    "dependency_scanning": "dependencies.vulnerabilities",
    "container_scanning": "container.vulnerabilities",
}
SARIF_LEVELS = {"critical": "error", "high": "error", "medium": "warning", "low": "note", "info": "note"}


@dataclass(frozen=True)
class Scan:
    """One report: the metric its findings count under, the analyzer that found them, and the findings
    (their level is the severity, lower case)."""

    metric: str
    tool: str
    findings: tuple[Finding, ...]


def parse(data: bytes) -> Scan:
    """The findings of a GitLab security report; ValueError if it isn't one this reader understands. Only the
    rule, severity and location are kept: a secret's text never leaves the report."""
    report = json.loads(data)
    scan = (report.get("scan") or {}) if isinstance(report, dict) else {}
    kind = scan.get("type")
    if kind not in SCANS or not isinstance(report.get("vulnerabilities"), list):
        raise ValueError(f"not a GitLab security report (scan type {kind!r}, known: {sorted(SCANS)})")
    tool = str((scan.get("analyzer") or {}).get("id") or "gitlab")
    return Scan(SCANS[kind], tool, tuple(_finding(v) for v in report["vulnerabilities"]))


def _finding(vulnerability: dict[str, Any]) -> Finding:
    """One vulnerability: its first identifier as the rule, its severity, and its file (else its image)."""
    severity = str(vulnerability.get("severity") or "unknown").lower()
    identifiers = vulnerability.get("identifiers") or [{}]
    rule = str(identifiers[0].get("value") or vulnerability.get("name") or "")
    where = vulnerability.get("location") or {}
    return Finding(rule, severity, str(where.get("file") or where.get("image") or ""),
                   int(where.get("start_line") or 0))


def only_in(scan: Scan, files: Sequence[str]) -> Scan:
    """The scan's findings in these files (a partial target's own); an image's or a dependency's are not."""
    return Scan(scan.metric, scan.tool, tuple(f for f in scan.findings if f.path in files))


def gitlab_metrics(scans: Sequence[Scan]) -> list[Metric]:
    """Per scan kind and analyzer: counts per file, per rule, per severity and in total; a scan that found
    nothing gives a total of 0."""
    metrics: list[Metric] = []
    for metric, tool in sorted({(s.metric, s.tool) for s in scans}):
        mine = [f for s in scans if (s.metric, s.tool) == (metric, tool) for f in s.findings]
        by_rule = count_metrics(metric, tool, mine, ("rule", lambda f: f.rule))
        by_severity = count_metrics(metric, tool, mine, ("severity", lambda f: f.level))
        metrics += by_rule[:-1] + [m for m in by_severity if m.labels] + by_rule[-1:]
    return metrics


def gitlab_sarif(scans: Sequence[Scan]) -> dict[str, Any]:
    """The findings as a SARIF 2.1.0 document: rule, level and place, no text of the finding."""
    results = [{"ruleId": f.rule, "level": SARIF_LEVELS.get(f.level, "warning"),
                "message": {"text": f"{f.level} finding of {s.tool}"},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": f.path},
                                                    "region": {"startLine": max(f.line, 1)}}}]}
               for s in scans for f in s.findings]
    driver = {"name": "gitlab-security"}
    return {"version": "2.1.0", "runs": [{"tool": {"driver": driver}, "results": results}]}
