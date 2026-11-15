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
from swe_metrics.tools.process import ToolError
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


def test_depcruise_without_a_typescript_compiler(tmp_path, monkeypatch):
    """No relative import resolved (recorded with TypeScript 7, which it can't use): failed, with a reason."""
    def fake_run(argv, cwd, ok=(0,)):
        shutil.copyfile(FIXTURES / "recorded" / "depcruise-ts7.json", argv[argv.index("--output-to") + 1])
        return ""
    monkeypatch.setattr(depcruise_module, "run", fake_run)
    files = ("f1.ts", "f2.ts", "f3.ts")
    with pytest.raises(ToolError, match="resolved 0 of 2 relative imports: .*compatible TypeScript compiler"):
        Depcruise().measure(Target(str(tmp_path), files), files, str(tmp_path))


def cruise(*imports, unreadable=(), issues=()):
    """A dependency-cruiser result: (source, module, resolved) imports, extensions it can't read, issues."""
    modules = [{"source": source, "dependencies": [{"module": module, "couldNotResolve": not resolved}]}
               for source, module, resolved in imports]
    found = [{"extension": ext, "available": False} for ext in unreadable]
    found.append({"extension": ".js", "available": True})
    return {"modules": modules, "summary": {"environment": {"extensionsFound": found,
                                                            "issues": [{"description": i} for i in issues]}}}


@pytest.mark.parametrize(("result", "reason"), [
    (cruise(("a.ts", "lodash", False)), ""),                                      # no relative import
    (cruise(("a.js", "./b", True), ("a.js", "./gone", False)), ""),               # one broken import
    (cruise(("a.ts", "./b", False)), "resolved 0 of 1 relative imports"),         # nothing resolved
    (cruise(("a.js", "./b", True), ("a.ts", "./c", False), unreadable=(".ts",), issues=("no\n  tsc",)),
     "resolved 1 of 2 relative imports: no tsc"),                                 # a file kind it can't read
])
def test_depcruise_unresolved_imports(result, reason):
    """An incomplete graph is named; a missing package or one broken relative import is not."""
    assert depcruise_module._unresolved(result).removeprefix("dependency-cruiser ") == reason


@pytest.mark.skipif(not shutil.which("depcruise"), reason="dependency-cruiser not installed")
def test_depcruise_cycle_or_failure(tmp_path):
    """Two TypeScript files importing each other: the cycle, or a failure when TypeScript can't be read."""
    (tmp_path / "f1.ts").write_text('import { b } from "./f3";\nexport const a = () => b();\n')
    (tmp_path / "f3.ts").write_text('import { a } from "./f1";\nexport const b = () => a();\n')
    files, scratch = ("f1.ts", "f3.ts"), tmp_path / "out"
    scratch.mkdir()
    try:
        metrics = Depcruise().measure(Target(str(tmp_path), files), files, str(scratch)).metrics
    except ToolError as error:
        assert "relative imports" in str(error)
        return
    assert {m.id: m.value for m in metrics if m.scope.level == "target"}["structure.cycles"] == 1


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
