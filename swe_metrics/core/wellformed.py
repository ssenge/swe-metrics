"""Well-formedness of data files: whether a JSON, XML, YAML, JSON lines or Markdown front matter document
parses, and where it doesn't."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePath
from xml.etree.ElementTree import ParseError  # the error type only: parsing goes through defusedxml

import yaml
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

# Files their tools read as JSON with comments (JSONC); strict JSON would count every comment as an error.
JSONC_NAMES = ("tsconfig*.json", "jsconfig*.json", "devcontainer.json", ".devcontainer.json",
               ".eslintrc.json")
JSONC_DIRS = (".vscode",)


class UnsafeXmlError(ValueError):
    """An XML document that declares entities or references external ones: not parsed, for safety."""


@dataclass(frozen=True)
class ParseFailure:
    """Where a document stopped parsing: the line (1-based) and the parser's message."""

    line: int
    message: str


def is_jsonc(path: str) -> bool:
    """Whether a .json file is one its tools read as JSON with comments."""
    pure = PurePath(path)
    return any(pure.match(name) for name in JSONC_NAMES) or any(d in pure.parts[:-1] for d in JSONC_DIRS)


def parse_error(kind: str, data: bytes) -> ParseFailure | None:
    """The first parse error of a document of this kind (`json`, `xml`, `yaml`, `jsonl`, or `markdown` for
    its front matter), None if well-formed; UnsafeXmlError if refused."""
    checks = {"json": _json_error, "xml": _xml_error, "yaml": _yaml_error, "jsonl": _jsonl_error,
              "markdown": _front_matter_error}
    return checks[kind](data)


def _yaml_error(data: bytes, first_line: int = 1) -> ParseFailure | None:
    """The first syntax error of a YAML stream (every document), or None. The documents are composed, not
    constructed, so no alias can expand and no tag runs code; the first line is where the text starts."""
    try:
        for _ in yaml.compose_all(data, Loader=yaml.SafeLoader):
            pass
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = (mark.line + 1 if mark else 1) + first_line - 1
        return ParseFailure(line, " ".join(str(getattr(exc, "problem", None) or exc).split()))
    return None


def _jsonl_error(data: bytes) -> ParseFailure | None:
    """The first line of a JSON lines file that isn't a JSON value (blank lines are allowed), or None."""
    try:
        lines = data.decode().splitlines()
    except UnicodeDecodeError as exc:
        return ParseFailure(data[:exc.start].count(b"\n") + 1, "not valid UTF-8")
    for number, line in enumerate(lines, 1):
        if line.strip():
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                return ParseFailure(number, exc.msg)
    return None


def _front_matter_error(data: bytes) -> ParseFailure | None:
    """The first syntax error of a Markdown file's YAML front matter (between a leading `---` line and the
    next `---` line), or None; a file without a closed front matter has none."""
    lines = data.decode(errors="replace").splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None
    end = next((n for n, line in enumerate(lines[1:], 1) if line.rstrip() in ("---", "...")), None)
    if end is None:
        return None
    return _yaml_error("\n".join(lines[1:end]).encode(), first_line=2)


def _json_error(data: bytes) -> ParseFailure | None:
    """The first error of a JSON document (RFC 8259: UTF-8, one value), or None."""
    try:
        json.loads(data)
    except json.JSONDecodeError as exc:
        return ParseFailure(exc.lineno, exc.msg)
    except UnicodeDecodeError as exc:
        return ParseFailure(data[:exc.start].count(b"\n") + 1, "not valid UTF-8")
    return None


def _xml_error(data: bytes) -> ParseFailure | None:
    """The first error of an XML document, or None; entity declarations and external references refused."""
    try:
        fromstring(data)
    except ParseError as exc:
        return ParseFailure(exc.position[0], str(exc))
    except LookupError as exc:  # an encoding declaration Python doesn't know
        return ParseFailure(1, str(exc))
    except DefusedXmlException as exc:
        raise UnsafeXmlError(str(exc)) from exc
    return None
