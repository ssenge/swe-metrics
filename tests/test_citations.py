"""Citations in documents: what the parser reads, and the analyzer's counts with and without a cite root."""
import json
from pathlib import Path

from swe_metrics.analyzers.citations import Citations
from swe_metrics.cli.main import main
from swe_metrics.core.citations import blocks, holds, resolve
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES, values

CITATIONS = FIXTURES / "citations"


def measured(tmp_path, roots=()):
    """The analyzer on the fixture's one document."""
    target = Target(str(CITATIONS), ("notes.md", "src/Api.java"))
    analyzer = Citations(roots)
    assert analyzer.applicable(target) == ("notes.md",) and analyzer.prerequisites() == ""
    return analyzer.measure(target, ("notes.md",), str(tmp_path))


def test_counts_without_a_cite_root(tmp_path):
    """Six citations (a URL, a host and port, a version and a fenced one aren't), three of them broken."""
    result = measured(tmp_path)
    assert values(result.metrics, "citations.citations")["total"] == 7
    assert values(result.metrics, "citations.broken")["total"] == 4, "gone, past the end, legacy, outside"
    assert values(result.metrics, "citations.quotes")["total"] == 6
    assert values(result.metrics, "citations.quotes_not_found")["total"] == 4


def test_a_cite_root_resolves_what_the_target_lacks(tmp_path):
    """`Old.vb:2` is in the legacy folder, and its quote spans two lines of it."""
    result = measured(tmp_path, ("legacy",))
    assert values(result.metrics, "citations.broken")["total"] == 3
    assert values(result.metrics, "citations.quotes_not_found")["total"] == 3
    assert values(result.metrics, "citations.broken")["notes.md"] == 3


def test_every_broken_citation_and_missing_quote_is_a_finding(tmp_path):
    """SARIF results with the rule, the document line and the text."""
    kind, path = measured(tmp_path, ("legacy",)).details[0]
    results = json.loads(Path(path).read_text())["runs"][0]["results"]
    found = [(r["ruleId"], r["locations"][0]["physicalLocation"]["region"]["startLine"], r["message"]["text"])
             for r in results]
    assert kind == "sarif" and found == [
        ("citation-broken", 5, "src/Gone.java:10"), ("quote-not-found", 5, "x"),
        ("citation-broken", 6, "src/Api.java:99"), ("quote-not-found", 6, "return store.load(id);"),
        ("quote-not-found", 7, "fetches the order"), ("citation-broken", 9, "../outside.txt:1")]


def test_a_document_without_citations_gives_zero_totals(tmp_path):
    """Nothing cited: totals of 0 and no findings."""
    (tmp_path / "a.md").write_text("# Title\n\nSome `code` here.\n")
    result = Citations().measure(Target(str(tmp_path), ("a.md",)), ("a.md",), str(tmp_path))
    assert {m.value for m in result.metrics} == {0.0}


def test_blocks_split_at_items_paragraphs_and_fences():
    """A quote belongs to the citation of its own item or paragraph, and fenced code is skipped."""
    text = "- a `x.py:1` and `foo`\n- b `bar`\n\npara `y.py:2`\n`baz`\n```\nz.py:3 `q`\n```\n"
    found = blocks(text)
    assert [[c.path for c in b.citations] for b in found] == [["x.py"], ["y.py"]]
    assert [[q.text for q in b.quotes] for b in found] == [["foo"], ["baz"]]


def test_hosts_urls_and_versions_are_no_citations():
    """The text before the colon must be a file name with an extension that isn't a host's."""
    text = "see http://localhost:8080/a and example.com:80 and 1.2:3 and a.org:9 but `real.py:4`\n"
    assert [c.path for b in blocks(text) for c in b.citations] == ["real.py"]


def test_a_quote_stands_within_fifteen_lines_whitespace_folded():
    """The window is the cited line and fifteen lines each side; indents and line breaks don't matter."""
    lines = ["pad"] * 40
    lines[19], lines[20] = "  if (a &&", "      b) {"
    assert holds("if (a && b) {", lines, 20) and holds("if (a && b) {", lines, 35), "15 lines after it"
    assert not holds("if (a && b) {", lines, 36), "16 lines after it"
    assert not holds("   ", lines, 20), "an empty quote holds nowhere"


def test_a_cited_path_stays_inside_its_root(tmp_path):
    """`..` can't reach a file outside the root; the first root that has the file wins."""
    (tmp_path / "root").mkdir()
    (tmp_path / "outside.txt").write_text("secret\n")
    (tmp_path / "root/a.txt").write_text("a\n")
    other = tmp_path / "other"
    other.mkdir()
    (other / "a.txt").write_text("b\n")
    assert resolve("../outside.txt", [tmp_path / "root"]) is None
    assert resolve("a.txt", [tmp_path / "root", other]) == (tmp_path / "root/a.txt").resolve()
    assert resolve("a.txt", [tmp_path / "missing", other]) == (other / "a.txt").resolve()


def test_the_cli_takes_cite_roots(tmp_path, capsys):
    """--cite-root is repeatable and relative to the target; --only names the analyzer."""
    out = tmp_path / "report.json"
    argv = ["measure", str(CITATIONS), "--only", "citations", "--cite-root", "legacy", "--out", str(out)]
    assert main(argv) == 0
    report = json.loads(out.read_text())
    broken = [m for m in report["metrics"] if m["id"] == "citations.broken"]
    assert [m["value"] for m in broken if m["scope"]["level"] == "target"] == [3]
