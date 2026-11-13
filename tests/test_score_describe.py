"""`swe-metrics score --describe`: a scoring definition's parts as data, for callers that explain scores."""
import json

from swe_metrics.cli.main import main


def test_a_definitions_gates_and_components_are_printed_as_json(capsys):
    assert main(["score", "--describe"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["name"] == "swe-default" and doc["version"]
    assert {"what", "tool", "max", "min", "cap"} <= set(doc["gates"][0])
    cyclomatic = next(c for c in doc["components"] if c["what"] == "complexity.cyclomatic p95")
    assert cyclomatic["good"] == 5 and cyclomatic["bad"] == 10 and cyclomatic["weight"] == 3
    assert any(c["tool"] == "swe-metrics" for c in doc["components"]), "a selector's tool is named"


def test_a_score_needs_a_report_unless_it_describes(capsys):
    assert main(["score"]) != 0
    assert "a report is required" in capsys.readouterr().err
