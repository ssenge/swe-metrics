"""Static facts of Java source from a small lexer (no compiler): which public APIs have a Javadoc comment.

Heuristic: comments and literals are removed, the code is cut at `{`, `;` and `}` outside parentheses,
and each piece in a type body is classified as a type, a method or constructor, or something else.
Public means the `public` modifier (or an interface member that isn't private) inside public types.
Methods annotated `@Override` are left out: they inherit their documentation.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

TOKEN = re.compile(r'(?P<doc>/\*\*.*?\*/)|(?P<comment>/\*.*?\*/|//[^\n]*)'
                   r'|(?P<text>"""(?:.|\n)*?"""|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\')'
                   r'|(?P<delimiter>[{};])', re.DOTALL)
ANNOTATION = re.compile(r"@(?!interface\b)[\w.]+\s*(?:\([^()]*\))?")
TYPE = re.compile(r"(?:\b(class|interface|enum|record)|@(interface))\s+\w+")
OVERRIDE = re.compile(r"@(?:java\.lang\.)?Override\b")
TOP = ("file", True)  # the enclosing block of top-level types


def _segments(source: str) -> Iterator[tuple[str, str, bool]]:
    """Each piece of code ending at a delimiter outside parentheses, and whether a Javadoc lies in it."""
    code: list[str] = []
    doc, depth, pos = False, 0, 0
    for match in TOKEN.finditer(source):
        chunk = source[pos:match.start()]
        depth = max(0, depth + chunk.count("(") - chunk.count(")"))
        code.append(chunk)
        pos = match.end()
        kind = match.lastgroup
        if kind == "delimiter" and not depth:
            yield " ".join("".join(code).split()), match.group(), doc
            code, doc = [], False
        else:
            doc = doc or kind == "doc"
            code.append(match.group() if kind == "delimiter" else '""' if kind == "text" else " ")


def _declaration(header: str, parent: tuple[str, bool]) -> tuple[str, bool]:
    """What a header in the parent block declares ('type', 'interface', 'method' or ''), and if public."""
    parent_kind = parent[0]
    code = ANNOTATION.sub(" ", header)
    head = code.split("(")[0]  # modifiers, type and name come before any parameter list
    if parent_kind == "other" or "=" in head:
        return "", False
    public = _public(head.split(), parent)
    found = TYPE.search(head)
    if found:
        return ("type" if found.group(1) in ("class", "enum", "record") else "interface"), public
    if "(" in code and parent_kind != "file" and not OVERRIDE.search(header):
        return "method", public
    return "", False


def _public(modifiers: list[str], parent: tuple[str, bool]) -> bool:
    """Public API: declared public (interface members implicitly, unless private) inside a public block."""
    parent_kind, parent_public = parent
    implicit = parent_kind == "interface" and "private" not in modifiers
    return parent_public and ("public" in modifiers or implicit)


def doc_flags(source: str) -> list[bool]:
    """Whether each public type, method and constructor has a Javadoc comment, in source order."""
    stack: list[tuple[str, bool]] = []
    flags = []
    for header, delimiter, doc in _segments(source):
        if delimiter == "}":
            stack = stack[:-1]
            continue
        kind, public = _declaration(header, stack[-1] if stack else TOP)
        if kind and public:
            flags.append(doc)
        if delimiter == "{":
            stack.append((kind if kind in ("type", "interface") else "other", public))
    return flags
