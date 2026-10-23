"""The default definition and `swe-metrics score`: built-in and custom definitions, baselines, errors."""

import json

import jsonschema
import pytest

from swe_metrics.cli.main import main
from swe_metrics.scoring.default import DEFINITION, VERSION_2, VERSION_3


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
    assert (DEFINITION.name, DEFINITION.version) == ("swe-default", "4")


def test_shell_scripts_alone_get_a_score():
    """A change of shell scripts only: version 3 scores its lint findings, version 2 had nothing to score."""
    shell_only = {
        "analyzers": [
            {"id": "shellcheck", "tool": "shellcheck", "status": "ran", "families": ["shell"]},
            {"id": "lizard", "tool": "lizard", "status": "skipped", "families": ["size", "complexity"]},
        ],
        "metrics": [row("shell.lint_findings", 4), row("shell.lint_findings", 3, labels={"level": "info"})],
    }
    assert DEFINITION.score(shell_only)["score"] == VERSION_3.score(shell_only)["score"] == 60.0
    assert VERSION_2.score(shell_only)["score"] is None and VERSION_2.version == "2"
    assert VERSION_3.components[:-1] == VERSION_2.components and VERSION_3.gates == VERSION_2.gates


def only(analyzer, family, *metrics):
    """A report of a change that only one analyzer applies to: lizard was skipped."""
    return {"analyzers": [{"id": analyzer, "tool": "t", "status": "ran", "families": [family]},
                          {"id": "lizard", "tool": "lizard", "status": "skipped", "families": ["size"]}],
            "metrics": list(metrics)}


@pytest.mark.parametrize(("report", "score"), [
    (only("yamllint", "yaml", row("yaml.lint_findings", 3),
          row("yaml.lint_findings", 3, labels={"level": "warning"})), 70.0),
    (only("wellformed", "syntax", row("syntax.parse_errors", 0)), 100.0),
    (only("wellformed", "syntax", row("syntax.parse_errors", 1),
          row("syntax.parse_errors", 1, labels={"language": "xml"})), 40.0),
])
def test_yaml_json_and_xml_alone_get_a_score(report, score):
    """A change of YAML, JSON or XML files only: version 4 scores it (a file that doesn't parse fails a gate,
    capping the score at 40), version 3 had nothing to score."""
    assert DEFINITION.score(report)["score"] == score
    assert VERSION_3.score(report)["score"] is None and VERSION_3.version == "3"
    assert DEFINITION.components[:-2] == VERSION_3.components and DEFINITION.gates[:-1] == VERSION_3.gates
    assert DEFINITION.gates[-1].max == 0 and DEFINITION.gates[-1].cap == DEFINITION.gates[1].cap  # as secrets


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
    assert main(["score", report, "--definition", "swe-default"]) == 0  # the default, named explicitly
    assert json.loads(capsys.readouterr().out)["definition"]["name"] == "swe-default"


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
