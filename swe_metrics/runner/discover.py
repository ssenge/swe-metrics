"""File discovery: the files of a file, directory or Git repository target, honoring .gitignore and the
linguist-vendored and linguist-generated attributes of .gitattributes."""
from __future__ import annotations

import os

# git runs with fixed arguments and never through a shell.
import subprocess  # nosec B404
import tempfile
from pathlib import Path

import pathspec

from swe_metrics.core.report import Subject
from swe_metrics.core.target import Target, languages

LINGUIST = ("linguist-vendored", "linguist-generated")  # the attributes GitHub and GitLab honor too


def discover(path: Path, exclude: tuple[str, ...] = (), changed_since: str = "",
             gitattributes: bool = True) -> tuple[Target, Subject]:
    """The target's files (relative, sorted) and its subject; FileNotFoundError if the path doesn't exist.

    exclude: gitignore-style patterns. With gitattributes, files marked vendored or generated are left out.
    With changed_since, only files changed since that Git ref (or untracked) are kept; ValueError if the
    target isn't a Git work tree or the ref is unknown.
    """
    root, files, kind = _listing(path)
    if changed_since:
        files = [f for f in files if f in _changed(root, kind, changed_since)]
    kept, excluded = _kept(root, kind, [f for f in files if (root / f).is_file()], exclude, gitattributes)
    commit = (_git(root, "rev-parse", "HEAD") or "").strip() if kind == "repository" else ""
    subject = Subject(str(path), kind, len(kept), languages(kept), commit, changed_since, excluded)
    return Target(str(root), kept, partial=bool(changed_since)), subject


def _kept(root: Path, kind: str, files: list[str], exclude: tuple[str, ...],
          gitattributes: bool) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...]]:
    """The files no exclude pattern and (if honored) no .gitattributes mark leaves out; counts by reason."""
    by_exclude = set(pathspec.GitIgnoreSpec.from_lines(exclude).match_files(files))
    rest = [f for f in files if f not in by_exclude]
    by_attributes = _marked(root, kind, rest) if gitattributes else set()
    kept = tuple(sorted(f for f in rest if f not in by_attributes))
    return kept, (("gitattributes", len(by_attributes)), ("exclude", len(by_exclude)))


def _listing(path: Path) -> tuple[Path, list[str], str]:
    """The root, the candidate files and the kind (file, directory or Git repository) of a target path."""
    if not path.exists():
        raise FileNotFoundError(f"target does not exist: {path}")
    if path.is_file():
        return path.parent, [path.name], "file"
    tracked = _git(path, "ls-files", "--cached", "--others", "--exclude-standard")
    if tracked is None:
        return path, _walk(path), "directory"
    return path, tracked.splitlines(), "repository"


def _changed(root: Path, kind: str, ref: str) -> set[str]:
    """Files changed since ref plus untracked files, relative to root."""
    if kind != "repository":
        raise ValueError("--changed-since needs a Git repository target")
    diff = _git(root, "diff", "--name-only", "--relative", ref, "--")
    if diff is None:
        raise ValueError(f"unknown Git ref '{ref}'")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard") or ""
    return set(diff.splitlines()) | set(untracked.splitlines())


def _marked(root: Path, kind: str, files: list[str]) -> set[str]:
    """The files Git attributes mark vendored or generated (set or true; false keeps a file in).

    A single file has no attributes. A plain directory is read through an empty repository outside the
    target, so its .gitattributes files mean what they mean to Git. Without git, nothing is marked.
    """
    if kind == "file" or not files:
        return set()
    listing = "\0".join(files)
    check = ("check-attr", "-z", "--stdin", *LINGUIST)
    if kind == "repository":
        return _set_paths(_git(root, *check, stdin=listing) or "")
    with tempfile.TemporaryDirectory(prefix="swe-metrics-attributes-") as scratch:
        if _git(Path(scratch), "init", "-q") is None:
            return set()
        work_tree = (f"--git-dir={Path(scratch) / '.git'}", f"--work-tree={root}")
        return _set_paths(_git(root, *work_tree, *check, stdin=listing) or "")


def _set_paths(output: str) -> set[str]:
    """The paths of `git check-attr -z` output (path, attribute, value triples) with a value set or true."""
    fields = output.split("\0")
    return {fields[i] for i in range(0, len(fields) - 2, 3) if fields[i + 2] in ("set", "true")}


def _walk(root: Path) -> list[str]:
    """All files below root, without hidden directories (e.g. .git, .venv)."""
    found = []
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = [d for d in subdirs if not d.startswith(".")]
        found += [str((Path(directory) / name).relative_to(root)) for name in names]
    return found


def _git(cwd: Path, *args: str, stdin: str | None = None) -> str | None:
    """Output of a git command in cwd, or None if cwd isn't in a Git work tree (or git is missing)."""
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,  # nosec B603 B607
                              check=False, input=stdin)
    except FileNotFoundError:
        return None
    return done.stdout if done.returncode == 0 else None
