"""Inline suppression marks: found in comments of several languages, their rules and reasons read."""
import json
from pathlib import Path

import pytest

from swe_metrics.analyzers.suppressions import Suppressions
from swe_metrics.core.suppressions import find_marks
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES, values

MARKS = FIXTURES / "suppressions"
NAMES = ("App.java", "README.md", "app.js", "app.py", "ci.yaml", "main.go", "main.tf")
# (file, line, kind, rules, reason) of every real mark of the fixture, in file and line order
EXPECTED = [
    ("App.java", 1, "suppress-warnings", ["unchecked"], ""),
    ("App.java", 2, "nosonar", [], "legacy API, replaced in 2025"),
    ("app.js", 1, "eslint-disable", ["no-console"], "the CLI prints its result"),
    ("app.js", 3, "eslint-disable", [], ""),
    ("app.js", 5, "nosemgrep", ["javascript.browser.security.insecure-document-method"], ""),
    ("app.py", 1, "noqa", ["F401"], "unused on purpose, kept for the plugin API"),
    ("app.py", 2, "type-ignore", ["attr-defined"], ""),
    ("app.py", 3, "nosec", ["B603"], "trusted constant command"),
    ("app.py", 5, "nosemgrep", ["python.lang.security.audit.exec-use"], "sandboxed by design"),
    ("app.py", 6, "noqa", [], ""),
    ("ci.yaml", 1, "gitleaks-allow", [], ""),
    ("main.go", 1, "nosec", ["G107"], "the url comes from the signed config"),
    ("main.tf", 2, "checkov-skip", ["CKV_AWS_18"], "the log bucket does not log itself"),
]


def test_the_fixtures_marks_per_file_kind_and_reason(tmp_path):
    """Thirteen marks in six files; strings that read like marks and Markdown prose are not counted."""
    analyzer = Suppressions()
    target = Target(str(MARKS), NAMES)
    files = analyzer.applicable(target)
    assert files == tuple(n for n in NAMES if n != "README.md") and analyzer.prerequisites() == ""
    result = analyzer.measure(target, files, str(tmp_path))
    assert values(result.metrics, "suppressions.marks") == {
        "App.java": 2, "app.js": 3, "app.py": 5, "ci.yaml": 1, "main.go": 1, "main.tf": 1,
        "kind": {"suppress-warnings": 1, "nosonar": 1, "eslint-disable": 2, "nosemgrep": 2, "noqa": 2,
                 "type-ignore": 1, "nosec": 2, "gitleaks-allow": 1, "checkov-skip": 1},
        "has_reason": {"true": 7, "false": 6}, "total": 13}
    kind, path = result.details[0]
    entries = json.loads(Path(path).read_text())
    listed = [(m["path"], m["line"], m["kind"], m["rules"], m["reason"]) for m in entries]
    assert kind == "suppressions-json" and listed == EXPECTED
    assert analyzer.version()


def test_no_marks_gives_a_zero_total(tmp_path):
    """Code without marks is a measured 0."""
    (tmp_path / "a.py").write_text("x = 1\n")
    result = Suppressions().measure(Target(str(tmp_path), ("a.py",)), ("a.py",), str(tmp_path))
    assert [(m.scope.level, m.labels, m.value) for m in result.metrics] == [("target", (), 0.0)]


@pytest.mark.parametrize(("line", "kind", "rules", "reason"), [
    ("x  # noqa: E501, W291 two rules and why", "noqa", ["E501", "W291"], "two rules and why"),
    ("x  # type: ignore", "type-ignore", [], ""),
    ("x  # pylint: disable=missing-docstring,invalid-name", "pylint-disable",
     ["missing-docstring", "invalid-name"], ""),
    ("a=1  # shellcheck disable=SC2086 word splitting is wanted", "shellcheck-disable", ["SC2086"],
     "word splitting is wanted"),
    ("/* eslint-disable no-alert */", "eslint-disable", ["no-alert"], ""),
    ("<!-- nosemgrep: html.rule - generated page -->", "nosemgrep", ["html.rule"], "generated page"),
    ("foo(); // NOLINT(readability-braces) why", "nolint", ["readability-braces"], "why"),
    ("// NOLINTNEXTLINE", "nolint", [], ""),
    ("# nosec because tests only", "nosec", [], "because tests only"),
    ("@SuppressWarnings({\"unchecked\", \"rawtypes\"})", "suppress-warnings", ["unchecked", "rawtypes"], ""),
])
def test_each_kind_names_its_rules_and_its_reason(line, kind, rules, reason):
    """The rule ids come first (comma-separated, id-like), the rest is the reason."""
    [mark] = find_marks(line)
    assert (mark.kind, list(mark.rules), mark.reason) == (kind, rules, reason)


@pytest.mark.parametrize("line", [
    'print("# noqa: E501")',
    "s = '// nosemgrep: a.b'",
    "no mark here, only prose about nosec and noqa",
    "x = nosemantic  # nothing",
    "const re = `// eslint-disable-line`;",
])
def test_look_alikes_are_no_marks(line):
    """A marker in a string, or a word that only starts like one, is not a mark."""
    assert find_marks(line) == []
