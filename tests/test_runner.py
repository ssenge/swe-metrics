"""Tests for file discovery and for the runner's analyzer statuses."""
import subprocess

import pytest

from swe_metrics.runner.discover import discover
from swe_metrics.runner.measure import Options, measure
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
    (FakeAnalyzer(missing="no rules given"), (), "skipped", "no rules given"),
])
def test_analyzer_statuses(tmp_path, analyzer, only, status, reason):
    """Every outcome of an analyzer is a status in the report, never an exception."""
    report = measure(copy_fixture("python_small", tmp_path), [analyzer], Options(only))
    run = report.analyzers[0]
    assert (run.status, run.reason) == (status, reason)


def test_only_filters_metric_families(tmp_path):
    """--only keeps the metrics of the selected families only."""
    report = measure(copy_fixture("python_small", tmp_path), [FakeAnalyzer(families=("size", "complexity"))],
                     Options(only=("complexity",)))
    assert [m.id for m in report.metrics] == ["complexity.cyclomatic"]
    assert report.details == ()


def test_only_names_an_analyzer_by_its_id_but_a_family_wins(tmp_path):
    """--only fake keeps all of that analyzer's metrics, also those of families nobody named; a name that is
    a family too selects the family."""
    root = copy_fixture("python_small", tmp_path)
    fake = FakeAnalyzer(families=("size", "complexity"))
    by_id = measure(root, [fake], Options(only=("fake",)))
    assert [m.id for m in by_id.metrics] == ["size.files", "complexity.cyclomatic"]
    assert by_id.analyzers[0].status == "ran"
    other = FakeAnalyzer(families=("docs",))
    assert measure(root, [other], Options(only=("size",))).analyzers[0].reason == "not selected"
    named = FakeAnalyzer(families=("docs",))
    named.id = "size"
    assert measure(root, [named], Options(only=("size",))).analyzers[0].reason == "not selected", "the family"


def test_details_are_kept_only_on_request(tmp_path):
    """Detailed outputs are copied out of the scratch directory, named after the analyzer."""
    details = tmp_path / "details"
    report = measure(copy_fixture("python_small", tmp_path), [FakeAnalyzer()], Options(details=details))
    expected = [{"analyzer": "fake", "format": "sarif", "path": "fake.sarif"}]
    assert [d.as_dict() for d in report.details] == expected
    assert (details / "fake.sarif").read_text() == "{}"


def vendored_tree(root):
    """A target with a vendored and a generated file, and a vendored file kept in by `=false`."""
    for name in ("web/vendor/x.js", "web/vendor/keep.js", "gen/y.ts", "src/app.ts"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("export const a = 1;\n")
    (root / ".gitattributes").write_text("web/vendor/** linguist-vendored\ngen/*.ts linguist-generated=true\n"
                                         "web/vendor/keep.js linguist-vendored=false\n")
    return root


@pytest.mark.parametrize("repository", [True, False])
def test_gitattributes_leave_out_vendored_and_generated_files(tmp_path, repository):
    """linguist-vendored and -generated files are left out and counted; =false keeps a file in."""
    root = vendored_tree(tmp_path)
    if repository:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    target, subject = discover(root)
    assert target.files == (".gitattributes", "src/app.ts", "web/vendor/keep.js")
    assert subject.as_dict()["excluded_by"] == {"gitattributes": 2, "exclude": 0}
    assert subject.as_dict()["excluded_files"] == 2
    target, subject = discover(root, exclude=("src/",), gitattributes=False)
    assert {"gen/y.ts", "web/vendor/x.js"} <= set(target.files) and "src/app.ts" not in target.files
    assert dict(subject.excluded_by) == {"gitattributes": 0, "exclude": 1}


def test_gitattributes_without_git(tmp_path, monkeypatch):
    """Without git, a plain directory's attributes can't be read: nothing is left out for them."""
    root = vendored_tree(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    target, subject = discover(root)
    assert "gen/y.ts" in target.files and dict(subject.excluded_by)["gitattributes"] == 0


def test_gitattributes_of_a_single_file(tmp_path):
    """A single file target is measured even when its directory marks it generated."""
    root = vendored_tree(tmp_path)
    assert discover(root / "gen" / "y.ts")[0].files == ("y.ts",)


@pytest.mark.parametrize(("pattern", "path", "excluded"), [
    ("**/dist/**", "dist/a.js", True), ("**/dist/**", "web/dist/a.js", True),
    ("*.min.js", "x/y.min.js", True), ("a/*.ts", "a/b.ts", True), ("a/*.ts", "a/b/c.ts", False),
    ("**/node_modules/**", "node_modules/p/i.js", True), ("vendor/**", "src/vendor/a.js", False),
])
def test_exclude_patterns_are_gitignore_style(tmp_path, pattern, path, excluded):
    """`**/` also matches no directory, `*` stays within one, a pattern without '/' matches at any depth."""
    (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / path).write_text("x\n")
    target, subject = discover(tmp_path, exclude=(pattern,))
    assert (path not in target.files) == excluded
    assert dict(subject.excluded_by)["exclude"] == int(excluded)
