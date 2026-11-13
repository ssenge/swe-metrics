"""Citations in documents: `path:line` references to code, the quotes next to them, and whether they hold."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

CITATION = re.compile(r"([\w./-]+\.[A-Za-z]\w*):(\d+)")
SPAN = re.compile(r"`([^`\n]+)`")
ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
FENCE = re.compile(r"^\s*(```|~~~)")
# lines around the cited one in which a quote must stand (a citation names where a statement begins)
NEAR = 15
# a host and port (`example.com:8080`) reads like a citation: the extensions that name a host, not a file
HOSTS = frozenset({"com", "org", "net", "io", "dev", "local", "internal", "test", "example"})


@dataclass(frozen=True)
class Citation:
    """A reference to a line of a file, and the line of the document it stands on."""

    path: str
    line: int
    at: int


@dataclass(frozen=True)
class Quote:
    """A backtick span, and the line of the document it stands on."""

    text: str
    at: int


@dataclass
class Block:
    """What one list item or paragraph of a document cites and quotes."""

    citations: list[Citation] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)


def blocks(text: str) -> list[Block]:
    """The list items and paragraphs of a document that hold a citation, outside fenced code."""
    found: list[Block] = []
    current, fence = Block(), ""
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if marker and (not fence or fence == marker.group(1)):
            fence = "" if fence else marker.group(1)
            continue
        if fence:
            continue
        if not line.strip() or ITEM.match(line) or line.startswith("#"):
            found.append(current)
            current = Block()
            if not line.strip():
                continue
        current.citations += _citations(line, number)
        current.quotes += [Quote(q, number) for q in _quotes(line)]
    return [b for b in [*found, current] if b.citations]


def _citations(line: str, number: int) -> list[Citation]:
    """The citations on a line, without URLs' ports and hosts."""
    return [Citation(m.group(1), int(m.group(2)), number) for m in CITATION.finditer(line)
            if line[m.start() - 1:m.start()] != ":" and m.group(1).rsplit(".", 1)[1].lower() not in HOSTS]


def _quotes(line: str) -> list[str]:
    """The backtick spans of a line that aren't a citation themselves."""
    return [s for s in SPAN.findall(line) if not CITATION.fullmatch(s.strip())]


def resolve(path: str, roots: Sequence[Path]) -> Path | None:
    """The file a cited path names: under the first root that has it, and never outside that root."""
    for root in roots:
        candidate = (root / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root.resolve()):
            return candidate
    return None


def lines_of(path: Path) -> list[str]:
    """The lines of a cited file, whatever its encoding."""
    return path.read_text(errors="ignore").splitlines()


def holds(quote: str, cited: Sequence[str], line: int) -> bool:
    """Whether the quote, whitespace folded, stands within NEAR lines of the cited one."""
    window = " ".join(" ".join(cited[max(line - 1 - NEAR, 0):line + NEAR]).split())
    folded = " ".join(quote.split())
    return bool(folded) and folded in window
