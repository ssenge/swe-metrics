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
         "tsconfig.json", "broken.yaml", "multi.yaml", "data.jsonl", "good.jsonl", "post.md", "fine.md",
         "plain.md")


def test_fixture_parse_errors_per_file_and_language(tmp_path):
    """One error per malformed file, per language and in total; the detail names line and message."""
    analyzer = Wellformed()
    target = Target(str(WELLFORMED), (*FILES, "notes.txt"))
    files = analyzer.applicable(target)
    assert "tsconfig.json" not in files and files == tuple(f for f in FILES if f != "tsconfig.json")
    result = analyzer.measure(target, files, str(tmp_path))
    assert values(result.metrics, "syntax.parse_errors") == {
        "broken.json": 1, "broken.xml": 1, "broken.yaml": 1, "data.jsonl": 1, "post.md": 1,
        "language": EXPECTED["languages"], "total": EXPECTED["total"]}
    kind, path = result.details[0]
    errors = json.loads(Path(path).read_text())
    broken = ("broken.json", "broken.xml", "broken.yaml", "data.jsonl", "post.md")
    assert kind == "wellformed-json" and [(e["path"], e["line"]) for e in errors] == [
        (name, EXPECTED[name]["line"]) for name in broken]
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


@pytest.mark.parametrize(("kind", "text", "line"), [
    ("yaml", "a: 1\n", None),
    ("yaml", "a: 1\n---\nb: &x 2\nc: *x\n", None),
    ("yaml", "", None),
    ("yaml", "a: [1\nb: 2\n", 2),
    ("yaml", "a: *nowhere\n", 1),
    ("yaml", "a: &x 1\nb: *x\n", None),
    ("jsonl", '{"a": 1}\n\n[2]\n', None),
    ("jsonl", '{"a": 1}\nnot json\n', 2),
    ("markdown", "# Title\n", None),
    ("markdown", "---\na: 1\n---\n# T\n", None),
    ("markdown", "---\na: [1\n---\n# T\n", 2),
    ("markdown", "---\nnever closed: [\n", None),
    ("markdown", "", None),
])
def test_parse_error_of_yaml_jsonl_and_front_matter(kind, text, line):
    """YAML (every document), JSON lines and a Markdown file's closed front matter; the line is the file's."""
    failure = parse_error(kind, text.encode())
    assert (failure.line if failure else None) == line


def test_bytes_that_are_not_text_fail_with_their_line():
    """A YAML or JSON lines file that isn't UTF-8 text fails on the line of its first bad byte."""
    assert parse_error("jsonl", b'{"a": 1}\n\xff\n') == ParseFailure(2, "not valid UTF-8")
    failure = parse_error("yaml", b"a: 1\nb: \xff\xfe\n")
    assert failure is not None and failure.line >= 1


def test_a_yaml_alias_bomb_is_not_expanded():
    """Composing (not constructing) the document keeps nested aliases from multiplying."""
    levels = ["a: &a0 [x, x, x, x, x, x, x, x, x]"] + [
        f"b{n}: &a{n} [" + ", ".join([f"*a{n - 1}"] * 9) + "]" for n in range(1, 9)]
    assert parse_error("yaml", "\n".join(levels).encode()) is None
