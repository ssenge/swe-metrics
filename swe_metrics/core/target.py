"""Targets: the files to measure, relative to a root, and the language of each file by its name."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePath

LANGUAGES = {
    ".py": "python", ".java": "java", ".kt": "kotlin", ".scala": "scala", ".js": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".cs": "csharp",
    ".rb": "ruby", ".php": "php", ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".swift": "swift",
    ".rs": "rust", ".tf": "terraform", ".md": "markdown", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".xml": "xml", ".sh": "shell", ".sql": "sql", ".jsp": "jsp", ".html": "html", ".c4": "likec4",
}
SPECIAL_NAMES = {"Dockerfile": "dockerfile", "Makefile": "make"}
CODE_LANGUAGES = frozenset({"python", "java", "kotlin", "scala", "javascript", "typescript", "go", "csharp",
                            "ruby", "php", "c", "cpp", "swift", "rust", "jsp"})


@dataclass(frozen=True)
class Target:
    """The files of one measurement: paths relative to root, in a stable order."""

    root: str
    files: tuple[str, ...]


def language(path: str) -> str | None:
    """The language or file kind of a path, by its file name; None if unknown."""
    pure = PurePath(path)
    return SPECIAL_NAMES.get(pure.name) or LANGUAGES.get(pure.suffix.lower())


def code_files(files: Iterable[str]) -> tuple[str, ...]:
    """The files written in a programming language (not markup, data or docs)."""
    return tuple(path for path in files if language(path) in CODE_LANGUAGES)


def languages(files: Iterable[str]) -> tuple[tuple[str, int], ...]:
    """Files per language, most frequent first; unknown kinds are not counted."""
    counts = Counter(lang for lang in map(language, files) if lang)
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
