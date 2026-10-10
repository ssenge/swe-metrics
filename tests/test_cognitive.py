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
    assert analyzer.applicable(Target(str(ROOT), ("d.h", "e.HPP", "f.cc", "g.rb", "h.rs", "i.c"))) == (
        "d.h", "e.HPP", "f.cc", "g.rb", "h.rs", "i.c")
    metrics = analyzer.measure(Target(str(ROOT), FILES), FILES, "/unused").metrics
    rollup = [m for m in metrics if m.scope.level == "target"]
    assert rollup[0].stats is not None and rollup[0].stats.max == 9
    assert "tree-sitter" in analyzer.version() and analyzer.prerequisites() == ""
