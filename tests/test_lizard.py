"""The lizard analyzer against fixtures with hand-computed values (fixtures/*/expected.json)."""
import json

import pytest

from swe_metrics.analyzers.lizard import Lizard
from swe_metrics.runner.discover import discover
from tests.helpers import FIXTURES


def measured(fixture):
    """The lizard metrics of a fixture and its expected values."""
    expected = json.loads((FIXTURES / fixture / "expected.json").read_text())
    target, _ = discover(FIXTURES / fixture)
    analyzer = Lizard()
    return analyzer.measure(target, analyzer.applicable(target)), expected


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
    assert Lizard().version() == "1.24.1"
