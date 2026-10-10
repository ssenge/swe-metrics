"""Tests for scoring: selecting values, gates, components, regressions and missing data."""

import pytest

from swe_metrics.scoring import Definition, gate, linear, per_kloc, regression, select
from swe_metrics.scoring.values import NOT_APPLICABLE, OK, UNAVAILABLE, lookup


def metric(metric_id, value=None, **extra):
    """A target-level metric row in report JSON form; extra: stats, labels, tool, direction."""
    row = {"id": metric_id, "tool": extra.get("tool", "t"), "unit": "count",
           "direction": extra.get("direction", "lower_better"), "scope": {"level": "target"}}
    if value is not None:
        row["value"] = value
    for key in ("stats", "labels"):
        if extra.get(key):
            row[key] = extra[key]
    return row


REPORT = {
    "analyzers": [
        {"id": "lizard", "tool": "lizard", "status": "ran", "families": ["size", "complexity"]},
        {"id": "trivy", "tool": "trivy", "status": "ran", "families": ["dependencies"]},
        {
            "id": "gitleaks",
            "tool": "gitleaks",
            "status": "failed",
            "reason": "not installed",
            "families": ["secrets"],
        },
        {"id": "tflint", "tool": "tflint", "status": "skipped", "families": ["iac"]},
    ],
    "metrics": [
        metric("complexity.cyclomatic", stats={"p95": 6, "max": 12}),
        metric("size.lines_of_code", stats={"sum": 2000}, direction="neutral"),
        metric("dependencies.vulnerabilities", 3),
        metric("dependencies.vulnerabilities", 1, labels={"severity": "critical"}),
        metric("dependencies.vulnerabilities", 2, labels={"severity": "low"}),
        metric("doc_coverage.percent", 70, direction="higher_better"),
    ],
}


def test_lookup_rows_labels_stats_and_densities():
    """Unlabeled totals by default, labeled rows summed, statistics, densities per 1,000 lines."""
    assert lookup(REPORT, select("dependencies.vulnerabilities")).value == 3
    labeled = select("dependencies.vulnerabilities", labels={"severity": ["critical", "high"]})
    assert lookup(REPORT, labeled).value == 1
    assert lookup(REPORT, select("complexity.cyclomatic", stat="p95")).value == 6
    assert lookup(REPORT, per_kloc("dependencies.vulnerabilities")).value == 1.5
    assert labeled.describe() == "dependencies.vulnerabilities [severity=critical|high]"


def test_missing_values_say_why():
    """A failed analyzer makes its family unavailable; a skipped one makes it not applicable."""
    assert lookup(REPORT, select("secrets.findings")).status == UNAVAILABLE
    assert "gitleaks: not installed" in lookup(REPORT, select("secrets.findings")).reason
    assert lookup(REPORT, select("iac.lint_findings")).status == NOT_APPLICABLE
    no_lines = {"analyzers": [], "metrics": [metric("secrets.findings", 2)]}
    assert lookup(no_lines, per_kloc("secrets.findings")).status == NOT_APPLICABLE
    assert lookup(REPORT, select("dependencies.vulnerabilities")).status == OK


def test_ambiguous_statistic_needs_a_tool():
    """Two tools reporting the same statistic is a definition error unless one tool is named."""
    report = {
        "analyzers": [],
        "metrics": [
            metric("complexity.cyclomatic", stats={"p95": 1}, tool="a"),
            metric("complexity.cyclomatic", stats={"p95": 2}, tool="b"),
        ],
    }
    with pytest.raises(ValueError, match="several tools"):
        lookup(report, select("complexity.cyclomatic", stat="p95"))
    assert lookup(report, select("complexity.cyclomatic", stat="p95", tool="b")).value == 2


def test_score_from_components_and_gates():
    """Weighted mean of sub-scores; failed gates cap; not applicable parts drop; unavailable gates fail."""
    definition = Definition(
        "test",
        "1",
        gates=(
            gate("dependencies.vulnerabilities", max=5),
            gate(select("dependencies.vulnerabilities", labels={"severity": "critical"}), max=0, cap=30),
        ),
        components=(
            linear(select("complexity.cyclomatic", stat="p95"), good=4, bad=10, weight=3),
            linear("doc_coverage.percent", good=80, bad=20, weight=1),
            linear("iac.lint_findings", good=0, bad=10, weight=5),
        ),
    )
    result = definition.score(REPORT)
    # p95 6 -> (6-10)/(4-10)*100 = 66.67; doc 70 -> (70-20)/60*100 = 83.33
    # (66.67*3 + 83.33)/4 = 70.83, capped at 30 by the failed critical-vulnerability gate
    assert [c.get("subscore") for c in result["components"]] == [66.67, 83.33, None]
    assert [g["passed"] for g in result["gates"]] == [True, False]
    assert result["score"] == 30.0
    assert result["definition"] == {"name": "test", "version": "1"}
    assert any("iac.lint_findings" in note for note in result["notes"])
    assert (
        Definition(
            "t",
            "1",
            gates=(gate("secrets.findings", max=0),),
            components=(linear("doc_coverage.percent", good=80, bad=20),),
        ).score(REPORT)["score"]
        == 40.0
    )
    no_gate_failure = Definition("t", "1", components=(linear("doc_coverage.percent", good=80, bad=20),))
    assert no_gate_failure.score(REPORT)["score"] == 83.33


def test_incomplete_scores_are_null():
    """A required component that is unavailable, or no measurable component at all, gives no score."""
    required = Definition(
        "t",
        "1",
        components=(
            linear("secrets.findings", good=0, bad=5, required=True),
            linear("doc_coverage.percent", good=80, bad=20),
        ),
    )
    assert required.score(REPORT)["score"] is None
    nothing = Definition("t", "1", components=(linear("iac.lint_findings", good=0, bad=5),))
    assert nothing.score(REPORT)["score"] is None


def test_regressions_against_a_baseline():
    """Worse beyond the tolerance in the metric's direction costs the penalty; better or neutral doesn't."""
    baseline = {
        "analyzers": REPORT["analyzers"],
        "metrics": [
            metric("complexity.cyclomatic", stats={"p95": 4, "max": 12}),
            metric("doc_coverage.percent", 75, direction="higher_better"),
            metric("size.lines_of_code", stats={"sum": 1000}, direction="neutral"),
        ],
    }
    definition = Definition(
        "t",
        "1",
        components=(linear("doc_coverage.percent", good=80, bad=20),),
        regressions=(
            regression(select("complexity.cyclomatic", stat="p95"), tolerance=1),
            regression("doc_coverage.percent", tolerance=10),
            regression(select("size.lines_of_code", stat="sum")),
            regression("dependencies.vulnerabilities", penalty=5),
        ),
    )
    result = definition.score(REPORT, baseline)
    assert [r["worse"] for r in result["regressions"]] == [True, False, False, False]
    assert result["score"] == 73.33  # 83.33 - 10
    assert definition.score(REPORT)["regressions"] == []


@pytest.mark.parametrize(
    "build",
    [
        lambda: gate("x"),
        lambda: gate("x", max=1, min=0),
        lambda: linear("x", good=1, bad=1),
        lambda: linear("x", good=1, bad=0, weight=0),
    ],
)
def test_invalid_building_blocks(build):
    """A gate needs exactly one limit; a component needs distinct anchors and a positive weight."""
    with pytest.raises(ValueError):
        build()
