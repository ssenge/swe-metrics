"""Doc coverage of the Python and Java fixtures against hand-counted values; the Java lexer's edge cases."""
import json

import pytest

from swe_metrics.analyzers.doc_coverage import DocCoverage
from swe_metrics.core.java_source import doc_flags as java_flags
from swe_metrics.core.python_source import doc_flags as python_flags
from swe_metrics.core.target import Target
from swe_metrics.runner.discover import discover
from tests.helpers import FIXTURES


def measured(fixture, language):
    """Per-file (documented, undocumented), the language totals and percent, and the unlabeled total."""
    target, _ = discover(FIXTURES / fixture)
    analyzer = DocCoverage()
    metrics = analyzer.measure(target, analyzer.applicable(target), "/unused").metrics
    def pick(level, labels, metric_id, path=""):
        key = (level, path, metric_id, labels)
        found = [m.value for m in metrics if (m.scope.level, m.scope.path, m.id, m.labels) == key]
        return found[0] if found else None
    lang = (("language", language),)
    files = {path: [pick("file", lang, f"doc_coverage.{k}", path) for k in ("documented", "undocumented")]
             for path in {m.scope.path for m in metrics if m.scope.level == "file"}}
    total = [pick("target", lang, f"doc_coverage.{k}") for k in ("documented", "undocumented")]
    unlabeled = [pick("target", (), f"doc_coverage.{k}") for k in ("documented", "undocumented", "percent")]
    return files, total, pick("target", lang, "doc_coverage.percent"), unlabeled


@pytest.mark.parametrize(("fixture", "language"),
                         [("python_structure", "python"), ("java_structure", "java")])
def test_fixture_doc_coverage(fixture, language):
    """Hand-counted documented and undocumented public APIs per file and in total."""
    expected = json.loads((FIXTURES / fixture / "expected.json").read_text())["doc_coverage"]
    files, total, percent, unlabeled = measured(fixture, language)
    assert files == expected["files"] and total == expected["total"] and percent == expected["percent"]
    assert unlabeled == [*expected["total"], expected["percent"]]


def test_file_without_public_api_has_no_percent():
    """A private module has counts of 0 and no percentage (never a made-up 0 % or 100 %)."""
    target = Target(str(FIXTURES / "python_structure"), ("src/shop/_version.py",))
    ids = {m.id for m in DocCoverage().measure(target, target.files, "").metrics if m.scope.level == "file"}
    assert ids == {"doc_coverage.documented", "doc_coverage.undocumented"}


def test_doc_coverage_contract():
    """Built in, always available, applies to Python and Java files."""
    analyzer = DocCoverage()
    assert analyzer.version() and analyzer.prerequisites() == ""
    assert analyzer.applicable(Target(".", ("a.py", "B.java", "c.js"))) == ("a.py", "B.java")


def test_python_private_parts():
    """Private classes hide their methods; private modules count nothing; nested functions don't count."""
    source = b'"""M."""\nclass A:\n    """A."""\n    class B:\n        def m(self): pass\n' \
             b'class _C:\n    def m(self): pass\ndef f():\n    def g(): pass\n'
    assert python_flags(source, "pkg.mod") == [True, True, False, False, False]
    assert python_flags(source, "pkg._impl.mod") == []


@pytest.mark.parametrize(("source", "expected"), [
    ("/** D. */ public class A { public A() {} }", [True, False]),
    ("public interface I { /** D. */ void a(); private void b() {} default void c() {} }",
     [False, True, False]),
    ("public @interface Ann { String value() default \"}\"; }", [False, False]),
    ("public record R(int x) { /** D. */ public int twice() { return 2 * x; } }", [False, True]),
    ("public class A { @SuppressWarnings({\"a\", \"b\"}) /** D. */ public void m() {} }", [False, True]),
    ("public class A { @Override public String toString() { return \"\"; } }", [False]),
    ("public class A { public static final Runnable R = () -> { int x; }; public void m() {} }",
     [False, False]),
    ("public class A { String s = \"\"\"\n { ; }\n\"\"\"; char c = '{'; public void m() {} }",
     [False, False]),
    ("class P { public void m() {} public class N {} }", []),
    ("public class A { private static class P { public void m() {} } public <T> T id(T t) { return t; } }",
     [False, False]),
    ("public class A { void m() { new Object() { public void x() {} }; } }", [False]),
    ("public enum E { X(\"a\"), Y(\"b\"); /** D. */ public String s() { return \"\"; } }", [False, True]),
    ("/**/ public class A {}", [False]),
    ("}} public class A {}", [False]),
])
def test_java_lexer_cases(source, expected):
    """Interfaces, annotations, records, lambdas, literals, text blocks, nested and anonymous types."""
    assert java_flags(source) == expected
