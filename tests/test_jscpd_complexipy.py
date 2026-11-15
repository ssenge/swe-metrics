"""jscpd on a recorded report and on a real clone; complexipy against hand-computed cognitive complexity."""
import json
import shutil
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

import pytest

from swe_metrics.analyzers import complexipy as complexipy_module
from swe_metrics.analyzers import jscpd as jscpd_module
from swe_metrics.analyzers.complexipy import Complexipy
from swe_metrics.analyzers.jscpd import Jscpd
from swe_metrics.core.target import Target
from swe_metrics.runner.discover import discover
from swe_metrics.runner.measure import measure
from swe_metrics.tools.process import ToolError
from tests.helpers import FIXTURES

EXPECTED = json.loads((FIXTURES / "dup_java" / "expected.json").read_text())


def targets(metrics):
    """Target-level values by metric ID."""
    return {m.id: m.value for m in metrics if m.scope.level == "target"}


@pytest.mark.parametrize(("major", "recorded", "per_file"), [
    ("4", "jscpd-report.json", (17, 94.44)),   # per file as jscpd 4 lists it
    ("5", "jscpd5-report.json", (18, 94.74)),  # lines 2-19 of 19, from the clone (jscpd 5 lists no files)
])
def test_jscpd_metrics_from_recorded_report(tmp_path, monkeypatch, major, recorded, per_file):
    """Totals and per-file values from each major version's report; the settings are part of the version."""
    root = tmp_path / "target"
    shutil.copytree(FIXTURES / "dup_java", root / "j")
    def fake_run(argv, cwd, ok=(0,)):  # the jscpd 5 report was recorded with --absolute below /target
        text = (FIXTURES / "recorded" / recorded).read_text().replace("/target/", f"{root.resolve()}/")
        (tmp_path / "jscpd-report.json").write_text(text)
        return ""
    monkeypatch.setattr(jscpd_module, "run", fake_run)
    monkeypatch.setattr(jscpd_module, "version", lambda argv: f"{major}.0.0")
    analyzer = Jscpd()
    metrics = analyzer.measure(Target(str(root), ("j/A.java",)), ("j/A.java",), str(tmp_path)).metrics
    assert targets(metrics) == pytest.approx(EXPECTED[major], abs=0.01)
    files = {(m.scope.path, m.id): m.value for m in metrics if m.scope.level == "file"}
    assert files == {(path, metric_id): value for path in ("j/A.java", "j/B.java") for metric_id, value
                     in zip(("duplication.duplicated_lines", "duplication.percent"), per_file, strict=True)}
    assert analyzer.version() == f"{major}.0.0 (min-tokens 50, min-lines 5)"
    assert analyzer.prerequisites() == ""
    monkeypatch.setattr(jscpd_module, "version", lambda argv: None)
    assert analyzer.version() is None


def test_jscpd_file_without_lines(tmp_path):
    """A clone in a file that can't be read is counted against one line rather than failing."""
    clone = {"firstFile": {"name": "a.js", "start": 1, "end": 1},
             "secondFile": {"name": "b.js", "start": 1, "end": 1}}
    assert jscpd_module._from_clones([clone], tmp_path) == {"a.js": (1, 100.0), "b.js": (1, 100.0)}


@pytest.mark.skipif(not shutil.which("jscpd"), reason="jscpd not installed")
def test_jscpd_finds_the_fixture_clone(tmp_path):
    """The real tool finds the one clone in dup_java with the hand-computed numbers of its major version."""
    target, _ = discover(FIXTURES / "dup_java")
    analyzer = Jscpd()
    found = targets(analyzer.measure(target, analyzer.applicable(target), str(tmp_path)).metrics)
    major = (analyzer.version() or "").split(".")[0]
    assert found == pytest.approx(EXPECTED[major], abs=0.01)


def test_complexipy_cognitive_complexity():
    """Per-function cognitive complexity equals the hand-computed values; only Python files apply."""
    expected = json.loads((FIXTURES / "python_small" / "expected.json").read_text())["cognitive"]
    target, _ = discover(FIXTURES / "python_small")
    analyzer = Complexipy()
    assert analyzer.applicable(target) == ("calc.py",) and analyzer.prerequisites() == ""
    metrics = analyzer.measure(target, ("calc.py",), "/unused").metrics
    by_function = {m.scope.symbol: m.value for m in metrics if m.scope.level == "function"}
    assert by_function == {k: v for k, v in expected.items() if not k.startswith("_")}
    assert targets(metrics)["complexity.cognitive"] is None  # target level carries statistics, not a value
    assert analyzer.version() == package_version("complexipy")


def test_complexipy_not_installed(monkeypatch):
    """A missing package means no version."""
    def missing(name):
        raise PackageNotFoundError(name)
    monkeypatch.setattr(complexipy_module, "package_version", missing)
    assert Complexipy().version() is None


TINY = FIXTURES / "dup_tiny"  # tiny.py: 2 lines and short.py: 4 lines as jscpd counts them; edge.py: 5


def test_jscpd_applies_only_to_files_it_considers(tmp_path):
    """Files under jscpd's minimum lines are left out; an unreadable file is left to jscpd to report."""
    target = Target(str(TINY), ("edge.py", "notes.md", "short.py", "tiny.py"))
    assert Jscpd().applicable(target) == ("edge.py",)
    assert Jscpd().applicable(Target(str(tmp_path), ("gone.py",))) == ("gone.py",)


def test_jscpd_without_a_report_measured_nothing(tmp_path, monkeypatch):
    """jscpd ran but skipped every file, so it wrote no report: no metrics and no detail, not a failure."""
    monkeypatch.setattr(jscpd_module, "run", lambda argv, cwd, ok=(0,): "")
    result = Jscpd().measure(Target(str(TINY), ("edge.py",)), ("edge.py",), str(tmp_path))
    assert result.metrics == [] and result.details == ()


def test_jscpd_errors_still_fail(tmp_path, monkeypatch):
    """A jscpd that exits with an error still fails the analyzer."""
    def broken(argv, cwd, ok=(0,)):
        raise ToolError("jscpd exited with 1: boom")
    monkeypatch.setattr(jscpd_module, "run", broken)
    with pytest.raises(ToolError):
        Jscpd().measure(Target(str(TINY), ("edge.py",)), ("edge.py",), str(tmp_path))


@pytest.mark.skipif(not shutil.which("jscpd"), reason="jscpd not installed")
def test_real_jscpd_on_tiny_and_edge_files(tmp_path):
    """Only tiny files: skipped as not applicable; a file at the line limit: measured, 0 % duplication."""
    tiny = tmp_path / "tiny"
    tiny.mkdir()
    shutil.copy(TINY / "tiny.py", tiny)
    run = measure(tiny, [Jscpd()]).analyzers[0]
    assert (run.status, run.reason) == ("skipped", "no applicable files")
    edge = Jscpd().measure(Target(str(TINY), ("edge.py",)), ("edge.py",), str(tmp_path / "scratch"))
    assert targets(edge.metrics)["duplication.percent"] == 0.0
