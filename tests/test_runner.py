"""Tests for file discovery and for the runner's analyzer statuses."""
import subprocess

import pytest

from swe_metrics.runner.discover import discover
from swe_metrics.runner.measure import measure
from tests.helpers import FakeAnalyzer, copy_fixture


def test_discover_file_directory_and_repository(tmp_path):
    """A file, a plain directory (hidden directories skipped) and a Git work tree (.gitignore honored)."""
    root = copy_fixture("python_small", tmp_path)
    (root / ".hidden").mkdir()
    (root / ".hidden" / "x.py").write_text("x = 1\n")
    target, subject = discover(root / "calc.py")
    assert (target.files, subject.kind) == (("calc.py",), "file")
    target, subject = discover(root, exclude=("*.json",))
    assert (target.files, subject.kind, subject.commit) == (("calc.py", "notes.md"), "directory", "")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text("notes.md\n")
    target, subject = discover(root)
    assert subject.kind == "repository" and "notes.md" not in target.files and ".gitignore" in target.files
    with pytest.raises(FileNotFoundError):
        discover(root / "missing")


def test_discover_without_git(tmp_path, monkeypatch):
    """Without git on the PATH, a directory is walked like a plain directory."""
    root = copy_fixture("python_small", tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert discover(root)[1].kind == "directory"


@pytest.mark.parametrize(("analyzer", "only", "status", "reason"), [
    (FakeAnalyzer(), (), "ran", ""),
    (FakeAnalyzer(families=("docs",)), ("size",), "skipped", "not selected"),
    (FakeAnalyzer(version=None), (), "failed", "fake-tool is not installed"),
    (FakeAnalyzer(applicable=False), (), "skipped", "no applicable files"),
    (FakeAnalyzer(fault=RuntimeError("boom")), (), "failed", "RuntimeError: boom"),
])
def test_analyzer_statuses(tmp_path, analyzer, only, status, reason):
    """Every outcome of an analyzer is a status in the report, never an exception."""
    report = measure(copy_fixture("python_small", tmp_path), [analyzer], only)
    run = report.analyzers[0]
    assert (run.status, run.reason) == (status, reason)


def test_only_filters_metric_families(tmp_path):
    """--only keeps the metrics of the selected families only."""
    report = measure(copy_fixture("python_small", tmp_path), [FakeAnalyzer(families=("size", "complexity"))],
                     only=("complexity",))
    assert [m.id for m in report.metrics] == ["complexity.cyclomatic"]
