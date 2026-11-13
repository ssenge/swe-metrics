"""trivy on a recorded report; opengrep with fixture rules (real tool when installed)."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import trivy as trivy_module
from swe_metrics.analyzers.opengrep import Opengrep
from swe_metrics.analyzers.trivy import Trivy
from swe_metrics.core.target import Target
from swe_metrics.tools.files import digest
from tests.helpers import FIXTURES


def fake_trivy(argv, cwd, ok=(0,)):
    """`trivy fs` writes the recorded report; `trivy convert` writes an empty SARIF."""
    output = argv[argv.index("--output") + 1]
    if argv[1] == "fs":
        shutil.copyfile(FIXTURES / "recorded" / "trivy.json", output)
    else:
        Path(output).write_text("{}")
    return ""


def test_trivy_metrics_from_recorded_report(tmp_path, monkeypatch):
    """Packages and vulnerabilities per manifest and severity; manifests outside the target are dropped."""
    monkeypatch.setattr(trivy_module, "run", fake_trivy)
    target = Target(str(tmp_path), ("pom.xml", "src/A.java"))
    analyzer = Trivy()
    assert analyzer.applicable(target) == ("pom.xml",) and analyzer.prerequisites() == ""
    result = analyzer.measure(target, ("pom.xml",), str(tmp_path))
    at_target = {(m.id, tuple(m.labels)): m.value for m in result.metrics if m.scope.level == "target"}
    assert at_target[("dependencies.packages", ())] == 3
    assert at_target[("dependencies.vulnerabilities", ())] == 8
    assert at_target[("dependencies.vulnerabilities", (("severity", "critical"),))] == 2
    assert [fmt for fmt, _ in result.details] == ["sarif", "trivy-json"]


@pytest.mark.parametrize(("output", "expected"), [
    ({"Version": "0.75.0", "VulnerabilityDB": {"UpdatedAt": "2026-10-10T07:01:36Z"}},
     "0.75.0 (db 2026-10-10)"),
    ({"Version": "0.75.0"}, "0.75.0"),
    (None, None),
])
def test_trivy_version_includes_database_date(monkeypatch, output, expected):
    """The database date is part of the version, because results depend on it."""
    def fake_run(argv, cwd, ok=(0,)):
        if output is None:
            raise FileNotFoundError("trivy")
        return json.dumps(output)
    monkeypatch.setattr(trivy_module, "run", fake_run)
    assert Trivy().version() == expected


def test_opengrep_prerequisites(tmp_path):
    """Without rules, or with missing rules, opengrep is skipped with the reason."""
    assert Opengrep().prerequisites() == "no SAST rules given (--sast-rules or --rules opengrep=PATH)"
    assert Opengrep(str(tmp_path / "none.yaml")).prerequisites().startswith("SAST rules not found")
    assert Opengrep(str(FIXTURES / "sast" / "rules.yaml")).prerequisites() == ""
    assert Opengrep().applicable(Target(".", ("a.py", "b.md"))) == ("a.py",)


@pytest.mark.skipif(not shutil.which("opengrep"), reason="opengrep not installed")
def test_opengrep_finds_fixture_rules(tmp_path):
    """One error (eval) and one note (print) in the fixture, counted per level."""
    analyzer = Opengrep(str(FIXTURES / "sast" / "rules.yaml"))
    target = Target(str(FIXTURES / "sast"), ("app.py",))
    result = analyzer.measure(target, ("app.py",), str(tmp_path))
    at_target = {tuple(m.labels): m.value for m in result.metrics if m.scope.level == "target"}
    assert at_target == {(("level", "error"),): 1, (("level", "note"),): 1, (("rules", "rules"),): 2, (): 2}
    shown = analyzer.version() or ""
    assert shown.endswith(")") and "rules: rules sha256:" in shown


@pytest.mark.skipif(not shutil.which("opengrep"), reason="opengrep not installed")
def test_opengrep_scans_every_rule_set_and_labels_each(tmp_path):
    """Two rule sets: each is scanned on its own, counted under its file stem, and kept as a detail."""
    sets = [str(FIXTURES / "sast" / "rules.yaml"), str(FIXTURES / "sast" / "rules-eval.yaml")]
    analyzer = Opengrep(sets)
    result = analyzer.measure(Target(str(FIXTURES / "sast"), ("app.py",)), ("app.py",), str(tmp_path))
    per_set = {m.labels[0][1]: m.value for m in result.metrics if m.labels and m.labels[0][0] == "rules"}
    assert per_set == {"rules": 2, "rules-eval": 1}
    assert [kind for kind, _ in result.details] == ["sarif", "sarif"]
    shown = analyzer.version() or ""
    assert "rules: rules sha256:" in shown and "; rules-eval sha256:" in shown


def test_rule_set_digests_name_what_ran(tmp_path):
    """A file's digest is its content's; a directory's covers its files' names and contents."""
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "a.yaml").write_text("a")
    (tmp_path / "f.yaml").write_text("a")
    before = digest(str(tmp_path / "d"))
    (tmp_path / "d" / "b.yaml").write_text("b")
    assert digest(str(tmp_path / "f.yaml")) == digest(str(tmp_path / "f.yaml")) != before
    assert digest(str(tmp_path / "d")) != before
