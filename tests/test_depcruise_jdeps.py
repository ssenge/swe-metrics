"""dependency-cruiser and jdeps on recorded outputs, and on the fixtures when the tools are installed."""
import json
import shutil
import subprocess

import pytest

from swe_metrics.analyzers import depcruise as depcruise_module
from swe_metrics.analyzers import jdeps as jdeps_module
from swe_metrics.analyzers.depcruise import Depcruise
from swe_metrics.analyzers.jdeps import Jdeps
from swe_metrics.core.target import Target
from swe_metrics.runner.discover import discover
from tests.helpers import FIXTURES

JS = json.loads((FIXTURES / "js_structure" / "expected.json").read_text())
JAVA = json.loads((FIXTURES / "java_structure" / "expected.json").read_text())["structure"]


def check_graph(metrics, expected):
    """Per-module Ca, Ce, instability and the target totals equal the hand-derived values."""
    def per_module(metric_id):
        return {m.scope.path: m.value for m in metrics if m.id == metric_id and m.scope.level == "module"}
    assert per_module("structure.afferent_coupling") == expected["afferent"]
    assert per_module("structure.efferent_coupling") == expected["efferent"]
    assert per_module("structure.instability") == pytest.approx(expected["instability"])
    totals = {m.id: m.value for m in metrics if m.scope.level == "target" and m.value is not None}
    assert {k: totals[k] for k in expected["target"]} == expected["target"]


def js_target():
    """The js_structure fixture as a target."""
    return discover(FIXTURES / "js_structure")[0]


def test_depcruise_on_recorded_output(tmp_path, monkeypatch):
    """Only edges between target files count; fs and lodash are dropped; the JSON is kept as a detail."""
    def fake_run(argv, cwd, ok=(0,)):
        assert "--no-config" in argv
        shutil.copyfile(FIXTURES / "recorded" / "depcruise.json", argv[argv.index("--output-to") + 1])
        return ""
    monkeypatch.setattr(depcruise_module, "run", fake_run)
    monkeypatch.setattr(depcruise_module, "version", lambda argv: "18.4.0")
    analyzer, target = Depcruise(), js_target()
    files = analyzer.applicable(target)
    assert files == ("src/a.js", "src/b.js", "src/index.js", "src/t.ts") and analyzer.prerequisites() == ""
    result = analyzer.measure(target, files, str(tmp_path))
    check_graph(result.metrics, JS)
    assert [fmt for fmt, _ in result.details] == ["depcruise-json"]
    assert analyzer.version() == "18.4.0 (no target config)"
    monkeypatch.setattr(depcruise_module, "version", lambda argv: None)
    assert analyzer.version() is None


@pytest.mark.skipif(not shutil.which("depcruise"), reason="dependency-cruiser not installed")
def test_depcruise_on_fixture(tmp_path):
    """The real tool gives the hand-derived graph."""
    analyzer, target = Depcruise(), js_target()
    check_graph(analyzer.measure(target, analyzer.applicable(target), str(tmp_path)).metrics, JS)


def test_jdeps_prerequisites(tmp_path):
    """Without a classes report jdeps is skipped; a missing path is named."""
    assert Jdeps().prerequisites() == "no classes report given (--report classes=PATH)"
    assert Jdeps((str(tmp_path / "none"),)).prerequisites().startswith("classes report not found")
    assert Jdeps((str(tmp_path),)).prerequisites() == ""
    assert Jdeps().applicable(Target(".", ("A.java", "b.kt", "c.py"))) == ("A.java", "b.kt")


def test_jdeps_on_recorded_output(tmp_path, monkeypatch):
    """Own packages are those the classes contain; JDK packages are dropped."""
    recorded = (FIXTURES / "recorded" / "jdeps-package.txt").read_text()
    monkeypatch.setattr(jdeps_module, "run", lambda argv, cwd, ok=(0,): recorded)
    result = Jdeps((str(tmp_path),)).measure(Target(".", ()), (), str(tmp_path))
    check_graph(result.metrics, JAVA)
    assert [fmt for fmt, _ in result.details] == ["jdeps-txt"]


def compile_fixture(tmp_path):
    """The java_structure sources compiled into tmp_path/classes."""
    sources = sorted(str(p) for p in (FIXTURES / "java_structure").rglob("*.java"))
    subprocess.run(["javac", "-d", str(tmp_path / "classes"), *sources], check=True, capture_output=True)
    return str(tmp_path / "classes")


@pytest.mark.skipif(not (shutil.which("javac") and shutil.which("jdeps")), reason="JDK not installed")
def test_jdeps_on_compiled_fixture(tmp_path):
    """The real tool on freshly compiled classes gives the hand-derived package graph."""
    analyzer = Jdeps((compile_fixture(tmp_path),))
    assert analyzer.version()
    check_graph(analyzer.measure(Target(".", ()), (), str(tmp_path)).metrics, JAVA)
