"""Cognitive complexity per language against hand-computed values (fixtures/cognitive/expected.json)."""
import json

import pytest

from swe_metrics.analyzers.cognitive import Cognitive
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
