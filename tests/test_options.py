"""Tests for --changed-since (Git targets) and --report (build reports by kind)."""
import subprocess

import pytest

from swe_metrics.cli.main import main
from swe_metrics.core.reports import parse_reports
from swe_metrics.runner.discover import discover
from tests.helpers import copy_fixture


def git(root, *args):
    """Run git in root with a fixed identity."""
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=root,
                   check=True, capture_output=True)


def test_parse_reports():
    """kind=path options grouped by kind; malformed options and unknown kinds are errors."""
    assert parse_reports(["junit=a.xml", "junit=b", "jacoco=c.xml"]) == {"junit": ("a.xml", "b"),
                                                                        "jacoco": ("c.xml",)}
    with pytest.raises(ValueError, match="expects kind=path"):
        parse_reports(["junit"])
    with pytest.raises(ValueError, match="unknown report kind"):
        parse_reports(["nunit=x"])


def test_changed_since_keeps_changed_and_untracked_files(tmp_path):
    """Only files changed since the ref, plus new untracked files, are measured."""
    root = copy_fixture("python_small", tmp_path)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    (root / "calc.py").write_text("def f():\n    return 1\n")
    (root / "new.py").write_text("x = 1\n")
    target, subject = discover(root, changed_since="HEAD")
    assert target.files == ("calc.py", "new.py") and subject.changed_since == "HEAD"
    with pytest.raises(ValueError, match="unknown Git ref"):
        discover(root, changed_since="no-such-ref")


def test_changed_since_needs_a_repository(tmp_path, capsys):
    """A plain directory can't be measured with --changed-since; bad --report options are usage errors."""
    root = copy_fixture("python_small", tmp_path)
    with pytest.raises(ValueError, match="needs a Git repository"):
        discover(root, changed_since="HEAD")
    assert main(["measure", str(root), "--changed-since", "HEAD"]) == 2
    assert "needs a Git repository" in capsys.readouterr().err
    assert main(["measure", str(root), "--report", "bogus"]) == 2
    assert "expects kind=path" in capsys.readouterr().err
