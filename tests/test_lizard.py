"""The lizard analyzer against fixtures with hand-computed values (fixtures/*/expected.json)."""
import json
from importlib.metadata import version as package_version

import pytest

from swe_metrics.analyzers.cognitive import Cognitive
from swe_metrics.analyzers.lizard import ANALYZE, Lizard, hidden_conditions
from swe_metrics.runner.discover import discover
from tests.helpers import FIXTURES


def measured(fixture):
    """The lizard metrics of a fixture and its expected values."""
    expected = json.loads((FIXTURES / fixture / "expected.json").read_text())
    target, _ = discover(FIXTURES / fixture)
    analyzer = Lizard()
    return analyzer.measure(target, analyzer.applicable(target), "/unused").metrics, expected


@pytest.mark.parametrize("fixture", ["python_small", "java_small"])
def test_function_values(fixture):
    """Every function's values equal the hand-computed ones."""
    metrics, expected = measured(fixture)
    for symbol, values in expected["functions"].items():
        for metric_id, value in values.items():
            found = [m.value for m in metrics if m.id == metric_id and m.scope.symbol == symbol]
            assert found == [value], (symbol, metric_id)


@pytest.mark.parametrize("fixture", ["python_small", "java_small"])
def test_target_values(fixture):
    """Target counts and statistics equal the hand-computed ones."""
    metrics, expected = measured(fixture)
    at_target = {m.id: m for m in metrics if m.scope.level == "target"}
    for metric_id, value in expected["target"].items():
        metric = at_target[metric_id]
        got = {k: getattr(metric.stats, k) for k in value} if isinstance(value, dict) else metric.value
        assert got == value, metric_id


def test_applicable_and_version():
    """Only files lizard can read are measured; the version is lizard's."""
    target, _ = discover(FIXTURES / "python_small")
    assert Lizard().applicable(target) == ("calc.py",)
    assert Lizard().version() == package_version("lizard")


TS_FIXTURE = FIXTURES / "lizard_ts"
TS_EXPECTED = json.loads((TS_FIXTURE / "expected.json").read_text())


@pytest.mark.parametrize("name", sorted(k for k in TS_EXPECTED if not k.startswith("_")))
def test_typescript_functions(name):
    """TypeScript and TSX: every function once, with its own range and cyclomatic complexity."""
    found = [[f.name, f.start_line, f.end_line, f.cyclomatic_complexity]
             for f in ANALYZE(str(TS_FIXTURE / name)).function_list]
    assert sorted(found, key=lambda row: (row[1], row[0])) == TS_EXPECTED[name]


def test_cognitive_functions_have_a_lizard_entry():
    """Every function the cognitive analyzer finds starts a lizard function too (none swallowed)."""
    target, _ = discover(TS_FIXTURE)
    def starts(analyzer):
        metrics = analyzer.measure(target, analyzer.applicable(target), "/unused").metrics
        return {(m.scope.path, m.scope.line) for m in metrics if m.scope.level == "function"}
    cognitive = starts(Cognitive())
    assert len(cognitive) >= 20 and cognitive <= starts(Lizard())


@pytest.mark.parametrize(("token", "hidden"), [
    ("< b ? c >", 1), ("< b ?? c >", 1), ("< b ?\n c >", 1),    # ternaries and ?? lizard took for types
    ("<? extends T>", 0), ("<K, ? super V>", 0), ("<int?>", 0), ("<int?, string>", 0),  # wildcards, nullables
    ("< b?.c >", 0), ("<T>", 0), ("<>", 0), ("?", 0), ("< b ? c", 0),
])
def test_hidden_conditions(token, hidden):
    """Only a '?' between two words inside a joined '<...>' token is a hidden condition."""
    assert hidden_conditions(token, {"?", "??", "&&"}) == hidden


def test_hidden_conditions_only_count_the_language_conditions():
    """A '??' counts only where the language reader counts it."""
    assert hidden_conditions("< b ?? c >", {"?"}) == 0
