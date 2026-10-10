"""Copies of target files in scratch, for tools that write next to their input or read config there."""
from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path, PurePath


def copy_files(root: str, paths: Iterable[str], destination: Path) -> None:
    """Copy files given relative to root to the same relative paths below destination."""
    for path in paths:
        (destination / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(root) / path, destination / path)


def copy_directories(root: str, paths: Iterable[str], destination: Path) -> list[str]:
    """Copy every file directly in the directories of the given files; the directories, sorted ("." is root).

    A whole directory, because a Terraform module needs all its files, also those a filter (e.g.
    --changed-since) left out.
    """
    directories = sorted({str(PurePath(path).parent) for path in paths})
    for directory in directories:
        files = [p for p in Path(root, directory).iterdir() if p.is_file()]
        copy_files(root, (str(PurePath(directory) / p.name) for p in files), destination)
    return directories
