"""Module dependency graphs: coupling, instability and cycles from module nodes and directed edges."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup

PER_MODULE = ("structure.afferent_coupling", "structure.efferent_coupling", "structure.instability")


@dataclass(frozen=True)
class Graph:
    """Modules and the dependencies between them, sorted; every edge joins two of the modules."""

    modules: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]


def graph(modules: Iterable[str], edges: Iterable[tuple[str, str]]) -> Graph:
    """A graph of the modules; duplicate edges and edges to or from unknown modules are dropped."""
    nodes = set(modules)
    kept = {(source, sink) for source, sink in edges if source in nodes and sink in nodes}
    return Graph(tuple(sorted(nodes)), tuple(sorted(kept)))


def _successors(g: Graph, reverse: bool = False) -> dict[str, list[str]]:
    """Each module's successors (or predecessors when reversed), in sorted order."""
    succ: dict[str, list[str]] = {module: [] for module in g.modules}
    for source, sink in g.edges:
        succ[sink if reverse else source].append(source if reverse else sink)
    return succ


def _postorder(nodes: Iterable[str], succ: Mapping[str, list[str]]) -> list[str]:
    """Depth-first finishing order over all nodes, iterative so deep graphs can't exhaust the stack."""
    seen: set[str] = set()
    order: list[str] = []
    for start in nodes:
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(succ[start]))]
        while stack:
            node, children = stack[-1]
            child = next((c for c in children if c not in seen), None)
            if child is None:
                stack.pop()
                order.append(node)
            else:
                seen.add(child)
                stack.append((child, iter(succ[child])))
    return order


def _reach(start: str, succ: Mapping[str, list[str]], seen: set[str]) -> list[str]:
    """The nodes reachable from start that are not yet seen; marks them seen."""
    found, stack = [], [start]
    seen.add(start)
    while stack:
        node = stack.pop()
        found.append(node)
        for nxt in succ[node]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return found


def components(g: Graph) -> list[tuple[str, ...]]:
    """The strongly connected components (Kosaraju), each sorted, in sorted order."""
    order = _postorder(g.modules, _successors(g))
    pred = _successors(g, reverse=True)
    seen: set[str] = set()
    found = [tuple(sorted(_reach(node, pred, seen))) for node in reversed(order) if node not in seen]
    return sorted(found)


def cycles(g: Graph) -> list[tuple[str, ...]]:
    """Dependency cycles: components with more than one module, or a module that depends on itself."""
    loops = {source for source, sink in g.edges if source == sink}
    return [c for c in components(g) if len(c) > 1 or c[0] in loops]


def _coupling(g: Graph) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """For each module, the other modules that depend on it (Ca) and that it depends on (Ce)."""
    afferent: dict[str, set[str]] = {module: set() for module in g.modules}
    efferent: dict[str, set[str]] = {module: set() for module in g.modules}
    for source, sink in g.edges:
        if source != sink:
            efferent[source].add(sink)
            afferent[sink].add(source)
    return afferent, efferent


def graph_metrics(g: Graph, tool: str, labels: tuple[tuple[str, str], ...] = ()) -> list[Metric]:
    """Ca, Ce and instability per module (self-dependencies excluded), target totals and statistics."""
    afferent, efferent = _coupling(g)
    metrics = []
    for module in g.modules:
        ca, ce = len(afferent[module]), len(efferent[module])
        values = (ca, ce, ce / (ca + ce)) if ca + ce else (ca, ce)
        metrics += [Metric(metric_id, tool, Scope("module", module), float(value), labels=labels)
                    for metric_id, value in zip(PER_MODULE, values, strict=False)]
    found = cycles(g)
    totals = (("structure.modules", len(g.modules)), ("structure.dependencies", len(g.edges)),
              ("structure.cycles", len(found)), ("structure.modules_in_cycles", sum(map(len, found))))
    metrics += [Metric(metric_id, tool, Scope("target"), float(n), labels=labels) for metric_id, n in totals]
    rollups = [rollup(metrics, metric_id, tool) for metric_id in PER_MODULE]
    return metrics + [Metric(m.id, m.tool, m.scope, stats=m.stats, labels=labels) for m in rollups if m]
