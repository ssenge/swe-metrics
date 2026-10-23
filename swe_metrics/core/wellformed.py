"""Well-formedness of data files: whether a JSON or XML document parses, and where it doesn't."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePath
from xml.etree.ElementTree import ParseError  # the error type only: parsing goes through defusedxml

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
    """The first parse error of a `json` or `xml` document, None if well-formed; UnsafeXmlError if refused."""
    return _json_error(data) if kind == "json" else _xml_error(data)


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
