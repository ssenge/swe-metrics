"""The hadolint analyzer on a recorded report, and on the fixture when hadolint is installed."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import hadolint as module
from swe_metrics.analyzers.hadolint import Hadolint
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES

DOCKER = FIXTURES / "docker_small"
EXPECTED = json.loads((DOCKER / "expected.json").read_text())["hadolint"]


def counts(metrics):
    """Findings per file, per (label, value) at the target, and the total."""
    per_file = {m.scope.path: m.value for m in metrics if m.scope.level == "file"}
    labeled = {m.labels[0]: m.value for m in metrics if m.scope.level == "target" and m.labels}
    total = [m.value for m in metrics if m.scope.level == "target" and not m.labels]
    return per_file, labeled, total


def check(result):
    """The metrics match the fixture's expected values; the SARIF detail is kept."""
    per_file, labeled, total = counts(result.metrics)
    assert per_file == {path: len(rules) for path, rules in EXPECTED.items() if path.endswith("file")}
    rules = {rule: n for path in ("Dockerfile", "web.Dockerfile") for rule, n in EXPECTED[path].items()}
    assert {v: n for (k, v), n in labeled.items() if k == "rule"} == rules
    assert {v: n for (k, v), n in labeled.items() if k == "level"} == EXPECTED["levels"]
    assert total == [EXPECTED["total"]]
    assert result.details[0][0] == "sarif" and Path(result.details[0][1]).exists()


def test_metrics_from_recorded_output(tmp_path, monkeypatch):
    """Recorded JSON output gives counts per file, rule and level; the fixed config is passed."""
    calls = []

    def fake_run(argv, cwd, ok=(0,)):
        calls.append(argv)
        recorded = (FIXTURES / "recorded" / "hadolint.json").read_text()
        return recorded if "json" in argv else "{}"
    monkeypatch.setattr(module, "run", fake_run)
    target = Target(str(DOCKER), ("Dockerfile", "notes.md", "web.Dockerfile"))
    analyzer = Hadolint()
    files = analyzer.applicable(target)
    assert files == ("Dockerfile", "web.Dockerfile") and analyzer.prerequisites() == ""
    check(analyzer.measure(target, files, str(tmp_path)))
    config = calls[0][calls[0].index("--config") + 1]
    assert Path(config).read_text() == module.CONFIG and config.startswith(str(tmp_path))


def test_no_findings_gives_a_zero_total(tmp_path, monkeypatch):
    """Empty output is no findings: only a total of 0."""
    monkeypatch.setattr(module, "run", lambda argv, cwd, ok=(0,): "")
    result = Hadolint().measure(Target(str(tmp_path), ("Dockerfile",)), ("Dockerfile",), str(tmp_path))
    assert [(m.scope.level, m.value) for m in result.metrics] == [("target", 0.0)]


def test_version_records_the_fixed_config(monkeypatch):
    """The version names the fixed configuration; None when hadolint is missing."""
    monkeypatch.setattr(module, "version", lambda argv: "2.15.1")
    assert Hadolint().version() == "2.15.1 (default rules, target config ignored)"
    monkeypatch.setattr(module, "version", lambda argv: None)
    assert Hadolint().version() is None


@pytest.mark.skipif(not shutil.which("hadolint"), reason="hadolint not installed")
def test_real_hadolint_ignores_target_config(tmp_path):
    """The real tool finds every expected finding although the fixture's .hadolint.yaml ignores them."""
    analyzer = Hadolint()
    assert analyzer.version()
    files = ("Dockerfile", "web.Dockerfile")
    check(analyzer.measure(Target(str(DOCKER), files), files, str(tmp_path)))
