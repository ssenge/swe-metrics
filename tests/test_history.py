"""The git-history analyzer: log parsing, per-file values and change coupling, on scripted repositories."""
import json
import os
import subprocess

import pytest

from swe_metrics.analyzers import git_history as module
from swe_metrics.analyzers.git_history import GitHistory
from swe_metrics.cli.main import main
from swe_metrics.core.history import Commit, Coupling, coupling_metrics, file_metrics, parse_log
from swe_metrics.core.target import Target
from swe_metrics.runner.discover import discover

ALICE = ("Alice Example", "alice@example.com")
ALICE_UPPER = ("Alice Example", "ALICE@Example.com")  # same author: e-mails are compared lowercased
BOB = ("Bob Builder", "bob@example.com")


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch):
    """Keep the user's and the system's Git configuration out of the tests."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(root, *args, env=None):
    """Run git in root."""
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, env=env)


def commit(root, day, who, changes):
    """Write the files (None deletes one) and commit them as `who` on 2024-01-<day> at noon UTC."""
    for path, text in changes.items():
        file = root / path
        if text is None:
            file.unlink()
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)
    date = f"2024-01-{day:02d}T12:00:00+00:00"
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    git(root, "add", "-A")
    git(root, "-c", f"user.name={who[0]}", "-c", f"user.email={who[1]}", "commit", "-q", "-m", "c", env=env)


@pytest.fixture
def repo(tmp_path):
    """A repository with five commits by two authors, a rename and an untracked file."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    commit(root, 1, ALICE, {"app/a.py": "1", "app/b.py": "1", "docs/readme.md": "1"})
    commit(root, 3, BOB, {"app/a.py": "2", "app/b.py": "2"})
    commit(root, 5, ALICE_UPPER, {"app/a.py": "3", "app/c.py": "1"})
    commit(root, 11, BOB, {"app/a.py": "4", "app/c.py": "2"})
    commit(root, 12, BOB, {"docs/readme.md": None, "docs/guide.md": "1"})  # a rename
    (root / "app" / "new.py").write_text("untracked")
    return root


def measured(root):
    """The analyzer's metrics for a target, by (metric id, path, other path)."""
    target, _ = discover(root)
    analyzer = GitHistory()
    files = analyzer.applicable(target)
    assert files == target.files
    metrics = analyzer.measure(target, files, str(root)).metrics
    return {(m.id, m.scope.path, dict(m.labels).get("with", "")): m for m in metrics}


def per_file(metrics, path):
    """(commits, authors, age in days) of one file."""
    return tuple(metrics[(f"history.{name}", path, "")].value for name in ("commits", "authors", "age_days"))


def test_values_of_a_scripted_repository(repo):
    """Hand-computed values; ages count from HEAD (Jan 12); a renamed file starts a new history."""
    metrics = measured(repo)
    assert per_file(metrics, "app/a.py") == (4, 2, 1)
    assert per_file(metrics, "app/b.py") == (2, 2, 9)
    assert per_file(metrics, "app/c.py") == (2, 2, 1)
    assert per_file(metrics, "docs/guide.md") == (1, 1, 0)
    assert not any(path in ("app/new.py", "docs/readme.md") for _, path, _ in metrics)
    commits = metrics[("history.commits", "", "")]
    assert commits.scope.level == "target" and (commits.stats.count, commits.stats.sum) == (4, 9)
    coupling = {key[1:]: m.value for key, m in metrics.items() if key[0] == "history.change_coupling"}
    assert coupling == {("app/a.py", "app/b.py"): 66.67, ("app/a.py", "app/c.py"): 66.67}


def test_subdirectory_target_uses_paths_relative_to_it(repo):
    """A subdirectory of the repository: only its files, relative to it, with the same values."""
    metrics = measured(repo / "app")
    assert per_file(metrics, "a.py") == (4, 2, 1) and per_file(metrics, "b.py") == (2, 2, 9)
    assert {m.scope.path for m in metrics.values() if m.scope.path} == {"a.py", "b.py", "c.py"}
    assert metrics[("history.change_coupling", "a.py", "c.py")].value == 66.67


def test_report_holds_no_names_or_e_mail_addresses(repo, tmp_path):
    """Authors are counted only: no name, e-mail address or part of one appears in the report."""
    out = tmp_path / "report.json"
    assert main(["measure", str(repo), "--only", "history", "--out", str(out)]) == 0
    text = out.read_text().lower()
    for word in ("alice", "bob", "builder", "example", "@"):
        assert word not in text
    run = next(a for a in json.loads(text)["analyzers"] if a["id"] == "git-history")
    assert run["status"] == "ran" and run["version"].endswith(
        "(coupling: min-shared 2, min-revs 2, max-changeset 50)")


def test_not_applicable_outside_a_repository_or_without_commits(tmp_path, monkeypatch):
    """A plain directory, a repository without commits and a missing git give no applicable files."""
    (tmp_path / "x.py").write_text("x = 1\n")
    target = Target(str(tmp_path), ("x.py",))
    analyzer = GitHistory()
    assert analyzer.applicable(target) == () and analyzer.prerequisites() == ""
    git(tmp_path, "init", "-q")
    assert analyzer.applicable(target) == ()

    def missing(argv, cwd, ok=(0,)):
        raise FileNotFoundError(argv[0])
    monkeypatch.setattr(module, "run", missing)
    assert analyzer.applicable(target) == ()
    monkeypatch.setattr(module, "version", lambda argv: None)
    assert analyzer.version() is None


def test_applicable_only_inside_the_work_tree(tmp_path, monkeypatch):
    """Inside the .git directory, git answers `false`: not applicable."""
    monkeypatch.setattr(module, "run", lambda argv, cwd, ok=(0,): "false\nabc\n")
    assert GitHistory().applicable(Target(str(tmp_path), ("x",))) == ()


def test_parse_log_keeps_target_files_and_counts_whole_commits():
    """Paths are mapped to the target, other commits dropped; size counts all paths of a commit."""
    log = ("\x1eA@X.com\x00100\x00\nsub/b\x00sub/a\x00top\x00"
           "\x1eb@x.com\x00200\x00"
           "\x1ec@x.com\x00300\x00\nother\x00")
    assert parse_log(log, "sub/", {"a", "b"}) == [Commit("a@x.com", 100, ("a", "b"), 3)]
    assert parse_log(log, "", {"top"}) == [Commit("a@x.com", 100, ("top",), 3)]


def test_age_never_negative_and_rollups_need_files():
    """A commit dated after HEAD gives age 0; no commits give no metrics at all."""
    metrics = file_metrics([Commit("a", 5 * 86400, ("f",), 1)], 86400, "git")
    assert [m.value for m in metrics if m.id == "history.age_days" and m.scope.level == "file"] == [0]
    assert file_metrics([], 0, "git") == []


def test_coupling_leaves_out_bulk_commits_and_rare_files():
    """Bulk commits don't count; pairs need min_shared commits together and files min_revs commits."""
    small = [Commit("a", 0, ("x", "y"), 2), Commit("a", 0, ("x", "y", "z"), 3)]
    assert [(m.scope.path, m.labels, m.value) for m in coupling_metrics(small, "git", Coupling())] == [
        ("x", (("with", "y"),), 100.0)]
    assert coupling_metrics(small, "git", Coupling(max_changeset=2)) == []
    rare = Coupling(min_shared=1, min_revs=3)
    assert coupling_metrics([*small, Commit("a", 0, ("x",), 1)], "git", rare) == []
    assert Coupling().describe() == "coupling: min-shared 2, min-revs 2, max-changeset 50"
