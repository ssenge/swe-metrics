"""The ShellCheck analyzer on a recorded report, and on the fixture when ShellCheck is installed."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import shellcheck as module
from swe_metrics.analyzers.shellcheck import Shellcheck, findings
from swe_metrics.core.target import Target
from swe_metrics.tools.process import ToolError
from tests.helpers import FIXTURES, values

SHELL = FIXTURES / "shell_small"
EXPECTED = json.loads((SHELL / "expected.json").read_text())["shellcheck"]
SCRIPTS = ("clean.sh", "deploy.sh")


def check(result):
    """The metrics match the fixture's expected values; the json1 output is kept as the detail."""
    assert {m.id for m in result.metrics} == {"shell.lint_findings"}
    rules = {rule: n for path in SCRIPTS for rule, n in EXPECTED[path].items()}
    per_file = {path: sum(EXPECTED[path].values()) for path in SCRIPTS}
    want = {**per_file, "rule": rules, "level": EXPECTED["levels"], "total": EXPECTED["total"]}
    assert values(result.metrics, "shell.lint_findings") == want
    assert result.details[0][0] == "shellcheck-json" and Path(result.details[0][1]).exists()


def test_metrics_from_recorded_output(tmp_path, monkeypatch):
    """Recorded json1 output gives counts per file, rule and level; rc files and SHELLCHECK_OPTS are off."""
    calls = []

    def fake_run(argv, cwd, ok=(0,), env=None):
        calls.append((argv, cwd, ok, env))
        return (FIXTURES / "recorded" / "shellcheck.json").read_text()
    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setenv("SHELLCHECK_OPTS", "--exclude=SC2086")
    target = Target(str(SHELL), ("clean.sh", "deploy.sh", "expected.json", "tools/run.bash"))
    analyzer = Shellcheck()
    files = analyzer.applicable(target)
    assert files == ("clean.sh", "deploy.sh", "tools/run.bash") and analyzer.prerequisites() == ""
    check(analyzer.measure(target, SCRIPTS, str(tmp_path)))
    argv, cwd, ok, env = calls[0]
    assert argv[:4] == ["shellcheck", "--norc", "--format", "json1"] and argv[-3:] == ["--", *SCRIPTS]
    assert cwd == str(SHELL) and ok == (0, 1) and "SHELLCHECK_OPTS" not in env and "PATH" in env


def test_no_findings_gives_a_zero_total(tmp_path, monkeypatch):
    """Empty output is no findings: only a total of 0."""
    monkeypatch.setattr(module, "run", lambda argv, cwd, ok=(0,), env=None: "")
    result = Shellcheck().measure(Target(str(tmp_path), ("a.sh",)), ("a.sh",), str(tmp_path))
    assert [(m.scope.level, m.value) for m in result.metrics] == [("target", 0.0)]


def test_findings_keep_only_the_measured_files():
    """A comment on a file that wasn't measured is dropped; a comment without a line gets line 0."""
    doc = {"comments": [{"file": "a.sh", "code": 2086, "level": "info"},
                        {"file": "lib/other.sh", "line": 3, "code": 2148, "level": "error"}]}
    found = [(f.rule, f.level, f.path, f.line) for f in findings(doc, {"a.sh"})]
    assert found == [("SC2086", "info", "a.sh", 0)]


def test_version_records_the_fixed_settings(monkeypatch):
    """The version names the fixed settings; None when ShellCheck is missing."""
    monkeypatch.setattr(module, "version", lambda argv: "0.11.0")
    assert Shellcheck().version() == f"0.11.0 ({module.SETTINGS})"
    monkeypatch.setattr(module, "version", lambda argv: None)
    assert Shellcheck().version() is None


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck not installed")
def test_real_shellcheck_ignores_rc_file_and_environment(tmp_path, monkeypatch):
    """The real tool finds every expected finding although .shellcheckrc and SHELLCHECK_OPTS disable them."""
    monkeypatch.setenv("SHELLCHECK_OPTS", "--exclude=SC2086,SC2006,SC2164,SC2148,SC2115")
    analyzer = Shellcheck()
    assert analyzer.version()
    check(analyzer.measure(Target(str(SHELL), SCRIPTS), SCRIPTS, str(tmp_path)))


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck not installed")
def test_real_shellcheck_fails_on_an_unreadable_file(tmp_path):
    """A script ShellCheck can't read fails the analyzer instead of counting nothing for it."""
    with pytest.raises(ToolError, match="exited with 2"):
        Shellcheck().measure(Target(str(tmp_path), ("gone.sh",)), ("gone.sh",), str(tmp_path))
