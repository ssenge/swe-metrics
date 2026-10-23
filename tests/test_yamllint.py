"""The yamllint analyzer on a recorded report, and on the fixture when yamllint is installed."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import yamllint as module
from swe_metrics.analyzers.yamllint import Yamllint, findings
from swe_metrics.core.target import Target
from swe_metrics.tools.process import ToolError
from tests.helpers import FIXTURES, values

YAML = FIXTURES / "yaml_small"
EXPECTED = json.loads((YAML / "expected.json").read_text())["yamllint"]
FILES = ("broken.yaml", "ci.yml", "config.yaml", "deployment.yaml")
WITH_FINDINGS = ("broken.yaml", "ci.yml", "deployment.yaml")


def check(result):
    """The metrics match the fixture's expected values; the parsable output is kept as the detail."""
    assert {m.id for m in result.metrics} == {"yaml.lint_findings"}
    rules: dict[str, int] = {}
    for path in WITH_FINDINGS:
        for rule, n in EXPECTED[path].items():
            rules[rule] = rules.get(rule, 0) + n
    per_file = {path: sum(EXPECTED[path].values()) for path in WITH_FINDINGS}
    want = {**per_file, "rule": rules, "level": EXPECTED["levels"], "total": EXPECTED["total"]}
    assert values(result.metrics, "yaml.lint_findings") == want
    assert result.details[0][0] == "yamllint-parsable" and Path(result.details[0][1]).exists()


def test_metrics_from_recorded_output(tmp_path, monkeypatch):
    """Recorded parsable output gives counts per file, rule and level; the config is fixed in argv."""
    calls = []

    def fake_run(argv, cwd, ok=(0,), env=None):
        calls.append((argv, cwd, ok))
        return (FIXTURES / "recorded" / "yamllint.txt").read_text()
    monkeypatch.setattr(module, "run", fake_run)
    target = Target(str(YAML), (*FILES, "expected.json", "k8s/service.yml", "notes.md"))
    analyzer = Yamllint()
    assert analyzer.applicable(target) == (*FILES, "k8s/service.yml") and analyzer.prerequisites() == ""
    check(analyzer.measure(target, FILES, str(tmp_path)))
    argv, cwd, ok = calls[0]
    assert argv[:5] == ["yamllint", "--format", "parsable", "--config-data", module.CONFIG]
    assert argv[5:] == ["--", *FILES] and cwd == str(YAML) and ok == (0, 1)


def test_no_findings_gives_a_zero_total(tmp_path, monkeypatch):
    """Empty output is no findings: only a total of 0."""
    monkeypatch.setattr(module, "run", lambda argv, cwd, ok=(0,), env=None: "")
    result = Yamllint().measure(Target(str(tmp_path), ("a.yaml",)), ("a.yaml",), str(tmp_path))
    assert [(m.scope.level, m.value) for m in result.metrics] == [("target", 0.0)]


def test_findings_keep_only_measured_files_and_finding_lines():
    """A line on a file that wasn't measured, and a line that isn't a finding, are dropped."""
    output = ("a.yaml:3:7: [error] trailing spaces (trailing-spaces)\n"
              "other.yaml:1:1: [warning] missing document start \"---\" (document-start)\n"
              "not a finding\n")
    found = [(f.rule, f.level, f.path, f.line) for f in findings(output, {"a.yaml"})]
    assert found == [("trailing-spaces", "error", "a.yaml", 3)]


def test_version_records_the_fixed_settings(monkeypatch):
    """The version names the fixed settings; None when yamllint is missing."""
    monkeypatch.setattr(module, "version", lambda argv: "1.38.0")
    assert Yamllint().version() == f"1.38.0 ({module.SETTINGS})"
    monkeypatch.setattr(module, "version", lambda argv: None)
    assert Yamllint().version() is None


@pytest.mark.skipif(not shutil.which("yamllint"), reason="yamllint not installed")
def test_real_yamllint_ignores_the_targets_config(tmp_path, monkeypatch):
    """The real tool finds every expected finding although .yamllint and YAMLLINT_CONFIG_FILE ignore them."""
    monkeypatch.setenv("YAMLLINT_CONFIG_FILE", str(YAML / ".yamllint"))
    analyzer = Yamllint()
    assert analyzer.version()
    check(analyzer.measure(Target(str(YAML), FILES), FILES, str(tmp_path)))


@pytest.mark.skipif(not shutil.which("yamllint"), reason="yamllint not installed")
def test_real_yamllint_fails_on_an_unreadable_file(tmp_path):
    """A file yamllint can't read fails the analyzer instead of counting nothing for it."""
    with pytest.raises(ToolError, match="exited with 255"):
        Yamllint().measure(Target(str(tmp_path), ("gone.yaml",)), ("gone.yaml",), str(tmp_path))
