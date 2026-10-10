"""Graph metrics on hand-made graphs, and the Python import graph of the python_structure fixture."""
import json

import pytest

from swe_metrics.analyzers.python_imports import PythonImports
from swe_metrics.core.graph import components, cycles, graph, graph_metrics
from swe_metrics.core.python_source import imported_names, module_name, resolve
from swe_metrics.core.target import Target
from swe_metrics.runner.discover import discover
from tests.helpers import FIXTURES

EXPECTED = json.loads((FIXTURES / "python_structure" / "expected.json").read_text())["structure"]


def per_module(metrics, metric_id):
    """Module-level values of one metric, by module."""
    return {m.scope.path: m.value for m in metrics if m.id == metric_id and m.scope.level == "module"}


def totals(metrics):
    """Target-level values (or statistics) by metric ID."""
    return {m.id: m.value if m.stats is None else m.stats for m in metrics if m.scope.level == "target"}


def test_graph_drops_duplicates_and_unknown_modules():
    """Edges are deduplicated and kept only between known modules."""
    g = graph(["b", "a"], [("a", "b"), ("a", "b"), ("a", "x"), ("y", "b")])
    assert g.modules == ("a", "b") and g.edges == (("a", "b"),)


def test_components_and_cycles():
    """Two cycles: a three-module ring and a self-loop; a chain into the ring is not a cycle."""
    g = graph("abcdef", [("a", "b"), ("b", "c"), ("c", "a"), ("d", "a"), ("e", "e"), ("f", "d")])
    assert components(g) == [("a", "b", "c"), ("d",), ("e",), ("f",)]
    assert cycles(g) == [("a", "b", "c"), ("e",)]


def test_deep_chain_needs_no_recursion():
    """A long chain is walked iteratively: every module is its own component."""
    names = [f"m{i:05d}" for i in range(5000)]
    g = graph(names, zip(names, names[1:], strict=False))
    assert len(components(g)) == 5000 and cycles(g) == []


def test_graph_metrics_by_hand():
    """a->b, a->c, b->c, c->b, d isolated, e->e: Ca, Ce, instability, totals and statistics."""
    g = graph("abcde", [("a", "b"), ("a", "c"), ("b", "c"), ("c", "b"), ("e", "e")])
    metrics = graph_metrics(g, "t", (("language", "x"),))
    assert per_module(metrics, "structure.afferent_coupling") == {"a": 0, "b": 2, "c": 2, "d": 0, "e": 0}
    assert per_module(metrics, "structure.efferent_coupling") == {"a": 2, "b": 1, "c": 1, "d": 0, "e": 0}
    assert per_module(metrics, "structure.instability") == pytest.approx({"a": 1.0, "b": 1 / 3, "c": 1 / 3})
    found = totals(metrics)
    assert {k: found[k] for k in ("structure.modules", "structure.dependencies", "structure.cycles",
                                  "structure.modules_in_cycles")} == {
        "structure.modules": 5, "structure.dependencies": 5, "structure.cycles": 2,
        "structure.modules_in_cycles": 3}
    assert found["structure.efferent_coupling"].sum == 4 and found["structure.instability"].count == 3
    assert all(m.labels == (("language", "x"),) for m in metrics)


def test_empty_graph_has_totals_but_no_statistics():
    """No modules: zero totals, no statistics."""
    assert totals(graph_metrics(graph([], []), "t")) == {
        "structure.modules": 0, "structure.dependencies": 0, "structure.cycles": 0,
        "structure.modules_in_cycles": 0}


@pytest.mark.parametrize(("path", "expected"), [
    ("pkg/mod.py", ("pkg.mod", False)),
    ("pkg/__init__.py", ("pkg", True)),
    ("src/pkg/a/__init__.py", ("pkg.a", True)),
    ("backend/src/pkg/b.py", ("pkg.b", False)),
    ("src.py", ("src", False)),
])
def test_module_name(path, expected):
    """Dotted names from paths; everything up to a `src` directory is dropped."""
    assert module_name(path) == expected


@pytest.mark.parametrize(("source", "module", "package", "expected"), [
    (b"import a.b, c", "m", False, {"a.b", "c"}),
    (b"from . import x", "p.q", False, {"p.x"}),
    (b"from . import x", "p", True, {"p.x"}),
    (b"from ..r import y", "p.q.m", False, {"p.r.y"}),
    (b"from .. import z", "p.q", True, {"p.z"}),
    (b"from . import x", "top", False, {"x"}),
    (b"from a import *", "m", False, {"a"}),
    (b"def f():\n    from a import b\n", "m", False, {"a.b"}),
])
def test_imported_names(source, module, package, expected):
    """Absolute and relative imports, star imports and function-local imports."""
    assert imported_names(source, module, package) == expected


def test_resolve_takes_the_longest_known_prefix():
    """`a.b.C` resolves to module a.b when a.b exists, else to a; unknown names to None."""
    assert resolve("a.b.C", {"a", "a.b"}) == "a.b"
    assert resolve("a.x", {"a", "a.b"}) == "a"
    assert resolve("json", {"a"}) is None


def test_python_imports_on_fixture():
    """The fixture's import graph: hand-derived coupling, instability and one cycle."""
    target, _ = discover(FIXTURES / "python_structure")
    analyzer = PythonImports()
    files = analyzer.applicable(target)
    assert len(files) == 7 and analyzer.prerequisites() == "" and analyzer.version()
    metrics = analyzer.measure(target, files, "/unused").metrics
    assert per_module(metrics, "structure.afferent_coupling") == EXPECTED["afferent"]
    assert per_module(metrics, "structure.efferent_coupling") == EXPECTED["efferent"]
    assert per_module(metrics, "structure.instability") == EXPECTED["instability"]
    found = totals(metrics)
    assert {k: found[k] for k in EXPECTED["target"]} == EXPECTED["target"]


def test_python_imports_drop_self_imports(tmp_path):
    """A package importing a name from itself is not a dependency (and not a cycle)."""
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "__init__.py").write_text("X = 1\nfrom p import X as Y\n")
    analyzer = PythonImports()
    metrics = analyzer.measure(Target(str(tmp_path), ("p/__init__.py",)), ("p/__init__.py",), "").metrics
    assert totals(metrics)["structure.dependencies"] == 0 and totals(metrics)["structure.cycles"] == 0
