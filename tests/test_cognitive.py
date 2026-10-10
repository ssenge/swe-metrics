"""Cognitive complexity per language against hand-computed values (fixtures/cognitive/expected.json)."""
import json

import pytest
import tree_sitter_java
from tree_sitter import Language, Parser

from swe_metrics.analyzers.cognitive import Cognitive
from swe_metrics.analyzers.cognitive.grammars import JAVA
from swe_metrics.analyzers.cognitive.walk import score_functions
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES

ROOT = FIXTURES / "cognitive"
EXPECTED = json.loads((ROOT / "expected.json").read_text())
FILES = tuple(name for name in EXPECTED if not name.startswith("_"))


def scores(files):
    """Per file, per function: the measured cognitive complexity."""
    found: dict[str, dict[str, float | None]] = {}
    for metric in Cognitive().measure(Target(str(ROOT), files), files, "/unused").metrics:
        if metric.scope.level == "function":
            found.setdefault(metric.scope.path, {})[metric.scope.symbol] = metric.value
    return found


@pytest.mark.parametrize("name", FILES)
def test_hand_computed_values(name):
    """Every function's score equals the hand-computed one (Java includes the white paper's examples)."""
    assert scores((name,))[name] == EXPECTED[name]


def test_analyzer_contract():
    """Applies to files with a grammar; target statistics; a version naming the parser library."""
    analyzer = Cognitive()
    assert analyzer.applicable(Target(str(ROOT), ("a.java", "b.md", "c.tsx"))) == ("a.java", "c.tsx")
    assert analyzer.applicable(Target(str(ROOT), ("d.h", "e.HPP", "f.cc", "g.rb", "h.rs", "i.c"))) == (
        "d.h", "e.HPP", "f.cc", "g.rb", "h.rs", "i.c")
    metrics = analyzer.measure(Target(str(ROOT), FILES), FILES, "/unused").metrics
    rollup = [m for m in metrics if m.scope.level == "target"]
    assert rollup[0].stats is not None and rollup[0].stats.max == 9
    assert "tree-sitter" in analyzer.version() and analyzer.prerequisites() == ""


@pytest.mark.parametrize(("name", "source"), [
    ("plain.kt", "fun f(x: Int) { val y = foo@ x + 1; for (i in 0..x) { break } }"),
    ("plain.php", "<?php function f($x) { foreach ($x as $y) { break; } }"),
])
def test_only_jumps_to_a_label_count(name, source, tmp_path):
    """A Kotlin label on a plain expression and a PHP break without a level add nothing; the loop is 1."""
    (tmp_path / name).write_text(source)
    metrics = Cognitive().measure(Target(str(tmp_path), (name,)), (name,), "/unused").metrics
    assert [m.value for m in metrics if m.scope.level == "function"] == [1.0]


def java_scores(source):
    """(name, score) of every method in a Java source, in order."""
    tree = Parser(Language(tree_sitter_java.language())).parse(source.encode())
    return [(f.name, f.complexity) for f in score_functions(tree.root_node, JAVA)]


def test_overloads_and_super_are_not_recursion():
    """A same-named call is recursion only if the argument count picks this overload; super never is."""
    source = """class O {
      String name(Class<?> c) { return name(c.getName()); }
      String name(String s) { return s.isEmpty() ? "" : name(s.substring(1)); }
      int sum(int a) { return sum(a, 0); }
      int sum(int a, int b) { return a > 0 ? sum(a - 1, b + 1) : b; }
      int v(int n) { return super.v(n); }
      int fact(int n) { return n < 2 ? 1 : n * fact(n - 1); }
    }"""
    # name/1 twice: ambiguous without types, not counted; sum(a, 0) calls the other overload; sum/2 recurses
    assert java_scores(source) == [("name", 0), ("name", 1), ("sum", 0), ("sum", 2), ("v", 0), ("fact", 2)]


def test_loop_headers_are_nested_but_if_conditions_are_not():
    """A ternary in a loop header is inside the loop (+2); in an if condition it is at the if's level (+1)."""
    source = """class H {
      int loop(int n) { while ((n > 0 ? 1 : 2) > 1) { n--; } return n; }
      int cond(int n) { if ((n > 0 ? 1 : 2) > 1) { n--; } return n; }
    }"""
    assert java_scores(source) == [("loop", 3), ("cond", 2)]
