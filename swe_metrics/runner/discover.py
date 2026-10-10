"""File discovery: the files of a file, directory or Git repository target, honoring .gitignore."""
from __future__ import annotations

import fnmatch
import os

# git runs with fixed arguments and never through a shell.
import subprocess  # nosec B404
from pathlib import Path

from swe_metrics.core.report import Subject
from swe_metrics.core.target import Target, languages


def discover(path: Path, exclude: tuple[str, ...] = ()) -> tuple[Target, Subject]:
    """The target's files (relative, sorted) and its subject; FileNotFoundError if the path doesn't exist."""
    if not path.exists():
        raise FileNotFoundError(f"target does not exist: {path}")
    if path.is_file():
        root, files, kind = path.parent, [path.name], "file"
    else:
        tracked = _git(path, "ls-files", "--cached", "--others", "--exclude-standard")
        root, kind = path, "repository" if tracked is not None else "directory"
        files = tracked.splitlines() if tracked is not None else _walk(path)
    kept = tuple(sorted(f for f in files if not _excluded(f, exclude) and (root / f).is_file()))
    commit = (_git(root, "rev-parse", "HEAD") or "").strip() if kind == "repository" else ""
    subject = Subject(str(path), kind, len(kept), languages(kept), commit)
    return Target(str(root), kept), subject


def _excluded(path: str, patterns: tuple[str, ...]) -> bool:
    """Whether a relative path matches one of the exclude globs."""
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _walk(root: Path) -> list[str]:
    """All files below root, without hidden directories (e.g. .git, .venv)."""
    found = []
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = [d for d in subdirs if not d.startswith(".")]
        found += [str((Path(directory) / name).relative_to(root)) for name in names]
    return found


def _git(cwd: Path, *args: str) -> str | None:
    """Output of a git command in cwd, or None if cwd isn't in a Git work tree (or git is missing)."""
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,  # nosec B603 B607
                              check=False)
    except FileNotFoundError:
        return None
    return done.stdout if done.returncode == 0 else None
