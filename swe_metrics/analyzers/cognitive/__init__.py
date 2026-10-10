"""Built-in cognitive complexity (SonarSource's definition) for many languages, on tree-sitter grammars."""
from __future__ import annotations

import importlib
from importlib.metadata import version as package_version
from pathlib import Path, PurePath

from tree_sitter import Language, Parser

import swe_metrics
from swe_metrics.analyzers.cognitive.grammars import GRAMMARS, Grammar
from swe_metrics.analyzers.cognitive.walk import score_functions
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup
from swe_metrics.core.target import Target, language

TOOL = "swe-metrics"


class Cognitive:
    """Implements core.analyzer.Analyzer: cognitive complexity per function, parsed with tree-sitter."""

    id = "cognitive"
    tool = TOOL
    families: tuple[str, ...] = ("complexity",)

    def version(self) -> str:
        """swe-metrics' version and the parser library's (the pinned grammars come with swe-metrics)."""
        return f"{swe_metrics.__version__} (tree-sitter {package_version('tree-sitter')})"

    def prerequisites(self) -> str:
        """The grammars are Python dependencies of swe-metrics."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The files of a language with a grammar."""
        return tuple(path for path in target.files if PurePath(path).suffix.lower() in GRAMMARS)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Per function, then the target statistics."""
        parsers: dict[tuple[str, str], Parser] = {}
        metrics = []
        for path in files:
            grammar = GRAMMARS[PurePath(path).suffix.lower()]
            tree = _parser(grammar, parsers).parse((Path(target.root) / path).read_bytes())
            labels = (("language", language(path) or "unknown"),)
            functions = score_functions(tree.root_node, grammar)
            metrics += [Metric("complexity.cognitive", TOOL, Scope("function", path, f.name, f.line),
                               float(f.complexity), labels=labels) for f in functions]
        summary = rollup(metrics, "complexity.cognitive", TOOL)
        return Measurement(metrics + ([summary] if summary else []))


def _parser(grammar: Grammar, parsers: dict[tuple[str, str], Parser]) -> Parser:
    """The parser of a grammar, created once per measurement."""
    key = (grammar.module, grammar.loader)
    if key not in parsers:
        parsers[key] = Parser(Language(getattr(importlib.import_module(grammar.module), grammar.loader)()))
    return parsers[key]
