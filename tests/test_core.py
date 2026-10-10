"""Tests for the pure core: catalog, statistics, report JSON form and languages."""
import pytest

from swe_metrics.core.catalog import CATALOG, DIRECTIONS, families, family
from swe_metrics.core.report import AnalyzerRun, Metric, Scope, Stats, Subject
from swe_metrics.core.stats import percentile, rollup, summarize
from swe_metrics.core.target import language, languages


def test_catalog_is_consistent():
    """Every metric ID is <family>.<name> with a known direction."""
    for metric_id, definition in CATALOG.items():
        assert metric_id.count(".") == 1 and definition.direction in DIRECTIONS
    assert family("complexity.cyclomatic") == "complexity"
    assert {"size", "complexity"} <= families()


@pytest.mark.parametrize(("share", "expected"), [(0.5, 2), (0.95, 5), (0.0, 1), (1.0, 5)])
def test_percentile_is_nearest_rank(share, expected):
    """Nearest rank: always an observed value."""
    assert percentile([1, 2, 2, 3, 5], share) == expected


def test_summarize_and_rollup():
    """Statistics of the values; no values, no statistics; roll-ups only cover their metric ID."""
    assert summarize([]) is None
    assert summarize([4, 1, 2]) == Stats(3, 7, 7 / 3, 2, 4, 4)
    metrics = [Metric("size.parameters", "t", Scope("function", "a.py", "f", 1), 3.0),
               Metric("size.parameters", "t", Scope("function", "a.py", "g", 5), 1.0),
               Metric("size.files", "t", Scope("target"), 9.0)]
    rolled = rollup(metrics, "size.parameters", "t")
    assert rolled is not None and rolled.stats is not None
    assert rolled.scope == Scope("target") and rolled.stats.max == 3
    assert rollup(metrics, "complexity.cyclomatic", "t") is None


def test_json_forms():
    """Unit and direction come from the catalog; unset fields are left out."""
    metric = Metric("complexity.cyclomatic", "lizard", Scope("function", "a.py", "f", 3), 5.0,
                    labels=(("language", "python"),))
    assert metric.as_dict() == {"id": "complexity.cyclomatic", "tool": "lizard", "unit": "count",
                                "direction": "lower_better",
                                "scope": {"level": "function", "path": "a.py", "symbol": "f", "line": 3},
                                "value": 5.0, "labels": {"language": "python"}}
    rolled = Metric("size.files", "t", Scope("target"), stats=Stats(1, 1, 1, 1, 1, 1)).as_dict()
    assert "value" not in rolled and rolled["stats"]["p95"] == 1
    assert AnalyzerRun("x", "x", "skipped", reason="why").as_dict() == {
        "id": "x", "tool": "x", "status": "skipped", "reason": "why"}
    assert Subject("t", "file", 1).as_dict()["commit"] is None


def test_languages():
    """Languages by file name, most frequent first; unknown kinds are not counted."""
    assert language("src/A.java") == "java" and language("Dockerfile") == "dockerfile"
    assert language("README") is None
    assert languages(["a.py", "b.py", "c.md", "d.unknown"]) == (("python", 2), ("markdown", 1))


def test_version_matches_pyproject():
    """Built-in analyzers report swe-metrics' version; it must equal the package version."""
    import tomllib
    from pathlib import Path

    import swe_metrics

    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert swe_metrics.__version__ == pyproject["project"]["version"]
