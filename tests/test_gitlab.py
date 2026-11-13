"""GitLab security reports as build reports: the four scan kinds, severities, rules, secrets never copied."""
import json
from pathlib import Path

import pytest

from swe_metrics.analyzers.buildreports import GitlabSecurity
from swe_metrics.core.gitlab import gitlab_metrics, parse
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES, values

GITLAB = FIXTURES / "gitlab"
SAST, SECRETS, DEPENDENCIES, CONTAINER = (
    GITLAB / "gl-sast-report.json", GITLAB / "gl-secret-detection-report.json",
    GITLAB / "gl-dependency-scanning-report.json", GITLAB / "gl-container-scanning-report.json")


FILES = ("src/server.js", "src/config.js", "package-lock.json")


def measured(*reports, files=FILES, partial=False, tmp=None):
    """The analyzer on these reports and a target with these files."""
    analyzer = GitlabSecurity([str(r) for r in reports])
    assert analyzer.prerequisites() == "" and analyzer.applicable(Target(".", files)) == files
    return analyzer.measure(Target(str(GITLAB), files, partial=partial), files, str(tmp))


def by_tool(result, metric_id, tool):
    """The values of a metric of one analyzer, keyed as helpers.values keys them."""
    return values([m for m in result.metrics if m.tool == tool], metric_id)


def test_a_sast_report_gives_findings_per_file_rule_and_severity(tmp_path):
    """The real report of GitLab's analyzer: one High SSRF and two Medium regular-expression findings."""
    result = measured(SAST, tmp=tmp_path)
    assert by_tool(result, "security.findings", "semgrep") == {
        "src/server.js": 3, "rule": {"nodejs_scan.javascript-ssrf-rule-node_ssrf": 1,
                                     "eslint.detect-non-literal-regexp": 1,
                                     "nodejs_scan.javascript-dos-rule-regex_dos": 1},
        "severity": {"high": 1, "medium": 2}, "total": 3}


def test_the_other_scan_kinds_use_their_own_metrics(tmp_path):
    """Secrets, dependencies and container images: each under its metric, the analyzer's id as the tool."""
    result = measured(SECRETS, DEPENDENCIES, CONTAINER, tmp=tmp_path)
    assert by_tool(result, "secrets.findings", "secrets") == {
        "src/config.js": 1, "rule": {"aws-access-token": 1}, "severity": {"critical": 1}, "total": 1}
    assert by_tool(result, "dependencies.vulnerabilities", "gemnasium") == {
        "package-lock.json": 2, "rule": {"CVE-2021-44906": 1, "CVE-2022-25883": 1},
        "severity": {"high": 1, "medium": 1}, "total": 2}
    image = "registry.example/orders:1.0"
    assert by_tool(result, "container.vulnerabilities", "trivy") == {
        image: 1, "rule": {"CVE-2024-0001": 1}, "severity": {"unknown": 1}, "total": 1}


def test_a_secrets_text_never_reaches_the_detail(tmp_path):
    """The SARIF detail carries rule, level and place only, never the report's raw text of a secret."""
    result = measured(SECRETS, SAST, tmp=tmp_path)
    kind, path = result.details[0]
    text = Path(path).read_text()
    assert kind == "sarif" and "REDACTED-IN-FIXTURE" not in text and "aws-access-token" in text
    levels = {r["ruleId"]: r["level"] for r in json.loads(text)["runs"][0]["results"]}
    assert levels["aws-access-token"] == "error" and levels["eslint.detect-non-literal-regexp"] == "warning"


def test_a_partial_target_keeps_the_findings_of_its_files(tmp_path):
    """A target of changes: findings in other files (and an image's) are no part of it, but a scan that found
    nothing in its files is still a measured 0."""
    result = measured(SAST, SECRETS, CONTAINER, files=("src/config.js",), partial=True, tmp=tmp_path)
    assert by_tool(result, "security.findings", "semgrep") == {"total": 0}
    assert by_tool(result, "secrets.findings", "secrets")["total"] == 1
    assert by_tool(result, "container.vulnerabilities", "trivy") == {"total": 0}


def test_a_report_without_findings_gives_a_zero_total():
    """A report of a scan that found nothing is a measured 0, not a missing value."""
    report = json.dumps({"scan": {"type": "sast", "analyzer": {"id": "semgrep"}}, "vulnerabilities": []})
    metrics = gitlab_metrics([parse(report.encode())])
    assert [(m.id, m.tool, m.scope.level, m.value) for m in metrics] == [
        ("security.findings", "semgrep", "target", 0.0)]


@pytest.mark.parametrize("document", [
    b'{"scan": {"type": "coverage_fuzzing"}, "vulnerabilities": []}',
    b'{"scan": {"type": "sast"}}',
    b'[]',
])
def test_a_report_this_reader_does_not_understand_is_refused(document):
    """Unknown scan kinds and documents without a findings list are ValueErrors (the analyzer fails)."""
    with pytest.raises(ValueError, match="not a GitLab security report"):
        parse(document)


def test_missing_reports_are_a_prerequisite(tmp_path):
    """Without a report, or with a missing one, the analyzer is skipped with the reason."""
    given = GitlabSecurity().prerequisites()
    assert given == "no gitlab-security report given (--report gitlab-security=PATH)"
    assert GitlabSecurity([str(tmp_path / "x.json")]).prerequisites().startswith("report not found")
