"""The default definition and `swe-metrics score`: built-in and custom definitions, baselines, errors."""

import json

import jsonschema
import pytest

from swe_metrics.cli.main import main
from swe_metrics.scoring.default import DEFINITION


def row(metric_id, value=None, stats=None, labels=None):
    """A target-level metric row (lower is better)."""
    data = {
        "id": metric_id,
        "tool": "t",
        "unit": "count",
        "direction": "lower_better",
        "scope": {"level": "target"},
    }
    data.update({k: v for k, v in (("value", value), ("stats", stats), ("labels", labels)) if v is not None})
    return data


IDEAL = {
    "analyzers": [{"id": "x", "tool": "t", "status": "ran", "families": ["complexity", "dependencies"]}],
    "metrics": [
        row("complexity.cyclomatic", stats={"p95": 3, "max": 8}),
        {**row("complexity.cognitive", stats={"p95": 3}), "tool": "swe-metrics"},
        row("duplication.percent", 1),
        row("dependencies.vulnerabilities", 0),
    ],
}


def write(tmp_path, name, data):
    """A JSON file in tmp_path."""
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return str(path)


def test_default_definition_rewards_and_gates():
    """An ideal report scores 100; one critical vulnerability caps it at 40; it names itself."""
    assert DEFINITION.score(IDEAL)["score"] == 100.0
    vulnerable = {
        **IDEAL,
        "metrics": [
            *IDEAL["metrics"][:3],
            row("dependencies.vulnerabilities", 1),
            row("dependencies.vulnerabilities", 1, labels={"severity": "critical"}),
        ],
    }
    assert DEFINITION.score(vulnerable)["score"] == 40.0
    assert (DEFINITION.name, DEFINITION.version) == ("swe-default", "2")


def test_score_command_with_baseline_and_schema(tmp_path, capsys):
    """The score validates against its schema; a worse report than the baseline costs points."""
    assert main(["schema", "score"]) == 0
    schema = json.loads(capsys.readouterr().out)
    worse = {
        **IDEAL,
        "metrics": [row("complexity.cyclomatic", stats={"p95": 4, "max": 8}), *IDEAL["metrics"][1:]],
    }
    out = tmp_path / "score.json"
    assert (
        main(
            [
                "score",
                write(tmp_path, "r.json", worse),
                "--baseline",
                write(tmp_path, "b.json", IDEAL),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    result = json.loads(out.read_text())
    jsonschema.validate(result, schema)
    assert result["score"] == 90.0 and result["regressions"][0]["worse"]


def test_custom_definitions_from_file_and_module(tmp_path, capsys):
    """A definition file's DEFINITION, or package.module:NAME, replaces the default."""
    custom = tmp_path / "mine.py"
    custom.write_text(
        "from swe_metrics.scoring import Definition, linear\n"
        "DEFINITION = Definition('mine', '7', components=(linear('duplication.percent', good=0,"
        " bad=2),))\n"
    )
    report = write(tmp_path, "r.json", IDEAL)
    assert main(["score", report, "--definition", str(custom)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert (result["definition"], result["score"]) == ({"name": "mine", "version": "7"}, 50.0)
    assert main(["score", report, "--definition", "swe_metrics.scoring.default:DEFINITION"]) == 0
    assert json.loads(capsys.readouterr().out)["score"] == 100.0


@pytest.mark.parametrize(
    ("definition", "message"),
    [
        ("missing.py", "definition file not found"),
        ("no.such.module", "not importable"),
        ("swe_metrics.scoring.default:P95", "must have name, version and score"),
    ],
)
def test_bad_definitions_are_usage_errors(tmp_path, capsys, definition, message):
    """A definition that can't be loaded, or isn't one, is a usage error."""
    assert main(["score", write(tmp_path, "r.json", IDEAL), "--definition", definition]) == 2
    assert message in capsys.readouterr().err


def test_bad_inputs(tmp_path, capsys):
    """A missing report is a usage error; a definition that returns no score document exits 1."""
    assert main(["score", str(tmp_path / "none.json")]) == 2
    broken = tmp_path / "broken.py"
    broken.write_text(
        "class D:\n    name, version = 'b', '1'\n    def score(self, r, b=None):\n        return 3\n"
        "DEFINITION = D()\n"
    )
    assert main(["score", write(tmp_path, "r.json", IDEAL), "--definition", str(broken)]) == 1
    assert "score document" in capsys.readouterr().err
