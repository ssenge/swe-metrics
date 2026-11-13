"""Rule files the caller gives (`--rules kind=path`): the known kinds and how the option is parsed."""
from __future__ import annotations

from collections.abc import Iterable

from swe_metrics.core.reports import parse_pairs

RULE_KINDS = {
    "opengrep": "opengrep rule file or directory, repeatable (same as --sast-rules)",
    "checkstyle": "Checkstyle configuration (Java coding rules)",
    "eslint": "ESLint flat config (JavaScript and TypeScript coding rules)",
}


def parse_rules(values: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """`--rules kind=path` options grouped by kind; ValueError for a malformed option or an unknown kind."""
    return parse_pairs(values, RULE_KINDS, "--rules", "rule kind")
