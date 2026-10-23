"""The built-in well-formedness check of JSON and XML files, on the fixture and on single documents."""
import json
from pathlib import Path

import pytest

from swe_metrics import __version__
from swe_metrics.analyzers.wellformed import Wellformed
from swe_metrics.core.target import Target
from swe_metrics.core.wellformed import ParseFailure, UnsafeXmlError, is_jsonc, parse_error
from tests.helpers import FIXTURES, values

WELLFORMED = FIXTURES / "wellformed"
EXPECTED = json.loads((WELLFORMED / "expected.json").read_text())["wellformed"]
FILES = ("broken.json", "broken.xml", "expected.json", "mapping.xml", "package.json", "pom.xml",
         "tsconfig.json")


def test_fixture_parse_errors_per_file_and_language(tmp_path):
    """One error per malformed file, per language and in total; the detail names line and message."""
    analyzer = Wellformed()
    target = Target(str(WELLFORMED), (*FILES, "notes.md", "ci.yml"))
    files = analyzer.applicable(target)
    assert "tsconfig.json" not in files and files == tuple(f for f in FILES if f != "tsconfig.json")
    result = analyzer.measure(target, files, str(tmp_path))
    assert values(result.metrics, "syntax.parse_errors") == {
        "broken.json": 1, "broken.xml": 1, "language": EXPECTED["languages"], "total": EXPECTED["total"]}
    kind, path = result.details[0]
    errors = json.loads(Path(path).read_text())
    assert kind == "wellformed-json" and [(e["path"], e["line"]) for e in errors] == [
        ("broken.json", EXPECTED["broken.json"]["line"]), ("broken.xml", EXPECTED["broken.xml"]["line"])]
    assert analyzer.version() == __version__ and analyzer.prerequisites() == ""


def test_well_formed_files_give_a_zero_total(tmp_path):
    """Nothing malformed: only a total of 0."""
    (tmp_path / "a.json").write_text("[]")
    result = Wellformed().measure(Target(str(tmp_path), ("a.json",)), ("a.json",), str(tmp_path))
    assert [(m.scope.level, m.value) for m in result.metrics] == [("target", 0.0)]


def test_an_entity_declaration_fails_the_analyzer(tmp_path):
    """XML that declares entities is refused, naming the file, rather than counted either way."""
    (tmp_path / "bomb.xml").write_text('<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')
    with pytest.raises(UnsafeXmlError, match="bomb.xml was not parsed"):
        Wellformed().measure(Target(str(tmp_path), ("bomb.xml",)), ("bomb.xml",), str(tmp_path))


@pytest.mark.parametrize(("kind", "data", "want"), [
    ("json", b'{"a": 1}', None),
    ("json", b"\xef\xbb\xbf[1]", None),
    ("json", b"", ParseFailure(1, "Expecting value")),
    ("json", b'{"a": 1}\n{"b": 2}', ParseFailure(2, "Extra data")),
    ("json", b'{\n"a": "\xff"}', ParseFailure(2, "not valid UTF-8")),
    ("xml", b"<a/>", None),
    ("xml", b"", ParseFailure(1, "no element found: line 1, column 0")),
    ("xml", b"<a>\n<b></a>", ParseFailure(2, "mismatched tag: line 2, column 5")),
    ("xml", b'<?xml version="1.0" encoding="no-such"?><a/>', ParseFailure(1, "unknown encoding: no-such")),
])
def test_parse_error(kind, data, want):
    """The first error's line and message, or None for a well-formed document."""
    assert parse_error(kind, data) == want


def test_external_entities_are_refused():
    """An external entity is never resolved."""
    with pytest.raises(UnsafeXmlError):
        parse_error("xml", b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><x>&a;</x>')


@pytest.mark.parametrize(("path", "jsonc"), [
    ("tsconfig.json", True), ("web/tsconfig.app.json", True), ("jsconfig.json", True),
    (".devcontainer/devcontainer.json", True), (".vscode/settings.json", True), (".eslintrc.json", True),
    ("package.json", False), ("config/vscode.json", False), ("my-tsconfig.json", False),
])
def test_is_jsonc(path, jsonc):
    """Only the files their tools read with comments are JSONC."""
    assert is_jsonc(path) is jsonc
