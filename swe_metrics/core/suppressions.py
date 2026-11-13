"""Inline suppression marks: comments and annotations that silence a checker instead of fixing a finding."""
from __future__ import annotations

import re
from dataclasses import dataclass

# kind -> the pattern of the mark; `rest` is what follows the marker (rule ids, then a reason).
KINDS = {
    "nosemgrep": r"(?:#|//|/\*|<!--)\s*nosem(?:grep)?\b(?::(?P<rest>.*))?",
    "nosec": r"(?:#|//)\s*#?nosec\b(?P<rest>.*)",
    "nosonar": r"(?:#|//|/\*)\s*NOSONAR\b(?P<rest>.*)",
    "eslint-disable": r"(?://|/\*)\s*eslint-disable(?:-next-line|-line)?\b(?P<rest>.*)",
    "noqa": r"#\s*noqa\b(?::(?P<rest>.*))?",
    "type-ignore": r"#\s*type:\s*ignore\b(?P<rest>.*)",
    "pylint-disable": r"#\s*pylint:\s*disable=(?P<rest>.*)",
    "checkov-skip": r"#\s*checkov:skip=(?P<rest>.*)",
    "shellcheck-disable": r"#\s*shellcheck\s+disable=(?P<rest>.*)",
    "gitleaks-allow": r"(?:#|//)\s*gitleaks:allow\b(?P<rest>.*)",
    "nolint": r"//\s*NOLINT(?:NEXTLINE)?\b(?P<rest>.*)",
    "suppress-warnings": r"^\s*@Suppress(?:Warnings)?\((?P<rest>.*)\)",
}
PATTERNS = {kind: re.compile(pattern) for kind, pattern in KINDS.items()}
# a rule id has a digit or one of ._-/@ (so a reason's first plain word isn't taken for one); ids are
# separated by commas, the first space after the last one starts the reason
ID = r"[\w.$/@-]*[\d._/@-][\w.$/@-]*"
RULES = re.compile(rf"\s*(?P<ids>{ID}(?:\s*,\s*{ID})*)(?P<reason>.*)$")
CLOSERS = ("*/", "-->")
SEPARATORS = " \t-—:;#,"


@dataclass(frozen=True)
class Mark:
    """One mark: its kind, its line, the rule ids it names and the reason it gives (empty when absent)."""

    kind: str
    line: int
    rules: tuple[str, ...]
    reason: str


def find_marks(text: str) -> list[Mark]:
    """The marks in a source text: in comments only, not in strings (an odd number of quotes before it)."""
    marks = []
    for number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in PATTERNS.items():
            found = pattern.search(line)
            if found and not _in_string(line[:found.start()]):
                rest = found.group("rest") or ""
                if kind == "suppress-warnings":   # quoted categories, and no slot for a reason
                    rules, reason = tuple(re.findall(r"[\"']([^\"']+)[\"']", rest)), ""
                else:
                    rules, reason = _rules_and_reason(rest)
                marks.append(Mark(kind, number, rules, reason))
    return marks


def _in_string(before: str) -> bool:
    """Whether the text before a would-be comment leaves a string open (a quote count that is odd)."""
    return any(before.count(q) % 2 for q in ("\"", "'", "`"))


def _rules_and_reason(rest: str) -> tuple[tuple[str, ...], str]:
    """The rule ids and the reason after a marker; a bracketed list (`ignore[code]`, `NOLINT(x)`) is ids."""
    rest = rest.strip()
    for closer in CLOSERS:
        rest = rest.removesuffix(closer).strip()
    for opening, closing in ("[]", "()"):
        if rest.startswith(opening) and closing in rest:
            rest = rest[1:].replace(closing, " ", 1)
    named = RULES.match(rest)
    if not named:
        return (), rest.strip(SEPARATORS)
    return tuple(re.split(r"\s*,\s*", named.group("ids"))), named.group("reason").strip(SEPARATORS)
