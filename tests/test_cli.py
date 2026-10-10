"""Tests for the command line: reports validate against the published schema; usage errors exit 2."""
import json

import jsonschema

from swe_metrics.cli.main import main
from tests.helpers import copy_fixture


def schema(capsys):
    """The schema printed by `swe-metrics schema`."""
    assert main(["schema"]) == 0
    return json.loads(capsys.readouterr().out)


def test_measure_report_is_schema_valid(tmp_path, capsys):
    """A report on stdout and in a file validates against the published schema."""
    report_schema = schema(capsys)
    root = copy_fixture("java_small", tmp_path)
    assert main(["measure", str(root)]) == 0
    report = json.loads(capsys.readouterr().out)
    jsonschema.validate(report, report_schema)
    assert report["analyzers"][0]["status"] == "ran"
    out = tmp_path / "report.json"
    assert main(["measure", str(root), "--only", "complexity", "--out", str(out)]) == 0
    in_file = json.loads(out.read_text())
    jsonschema.validate(in_file, report_schema)
    assert {m["id"].split(".")[0] for m in in_file["metrics"]} == {"complexity"}


def test_usage_errors(tmp_path, capsys):
    """A missing target or an unknown family is a usage error (exit 2)."""
    assert main(["measure", str(tmp_path / "missing")]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert main(["measure", str(tmp_path), "--only", "nonsense"]) == 2
    assert "unknown metric families" in capsys.readouterr().err


def test_tools(capsys):
    """`tools` lists each analyzer with its version and families."""
    assert main(["tools"]) == 0
    assert "lizard" in capsys.readouterr().out
