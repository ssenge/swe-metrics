"""Citations (built in): `path:line` references in Markdown that don't resolve, and quotes not there."""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from swe_metrics import __version__
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.citations import NEAR, Block, blocks, holds, lines_of, resolve
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.target import Target, language

TOOL = "swe-metrics"
COUNTS = ("citations", "broken", "quotes", "quotes_not_found")


class Citations:
    """Implements core.analyzer.Analyzer by resolving each citation against the target and the cite roots."""

    id = "citations"
    tool = TOOL
    families: tuple[str, ...] = ("citations",)

    def __init__(self, cite_roots: Sequence[str] = ()) -> None:
        """Folders, relative to the target, searched after it for the files a document cites."""
        self.cite_roots = tuple(cite_roots)

    def version(self) -> str:
        """The swe-metrics version: the check is built in; the window a quote must stand in is part of it."""
        return f"{__version__} (a quote within {NEAR} lines of its citation)"

    def prerequisites(self) -> str:
        """Nothing is needed."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Markdown files of the target."""
        return tuple(p for p in target.files if language(p) == "markdown")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Count citations and quotes per file and in total; each broken citation and missing quote is a SARIF
        finding."""
        root = Path(target.root)
        roots = [root, *(root / r for r in self.cite_roots)]
        counts: dict[str, Counter[str]] = {name: Counter() for name in COUNTS}
        results: list[dict[str, object]] = []
        for path in files:
            for block in blocks((root / path).read_text(errors="ignore")):
                self._block(block, path, roots, counts, results)
        detail = Path(scratch) / "citations.sarif"
        detail.write_text(json.dumps(_sarif(results), indent=1))
        return Measurement(_metrics(counts), (("sarif", str(detail)),))

    @staticmethod
    def _block(block: Block, path: str, roots: list[Path], counts: dict[str, Counter[str]],
               results: list[dict[str, object]]) -> None:
        """Check one list item or paragraph: each citation resolves, each quote stands near one of them."""
        cited = []
        for c in block.citations:
            counts["citations"][path] += 1
            file = resolve(c.path, roots)
            lines = lines_of(file) if file else []
            if 1 <= c.line <= len(lines):
                cited.append((lines, c.line))
            else:
                counts["broken"][path] += 1
                results.append(_result("citation-broken", path, c.at, f"{c.path}:{c.line}"))
        for q in block.quotes:
            counts["quotes"][path] += 1
            if not any(holds(q.text, lines, line) for lines, line in cited):
                counts["quotes_not_found"][path] += 1
                results.append(_result("quote-not-found", path, q.at, q.text))


def _result(rule: str, path: str, line: int, text: str) -> dict[str, object]:
    """One SARIF result: the rule, the document and line, and the citation or quote."""
    return {"ruleId": rule, "level": "error", "message": {"text": text},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": path},
                                                "region": {"startLine": line}}}]}


def _sarif(results: list[dict[str, object]]) -> dict[str, object]:
    """The results as a SARIF 2.1.0 document."""
    return {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "swe-metrics citations"}},
                                          "results": results}]}


def _metrics(counts: dict[str, Counter[str]]) -> list[Metric]:
    """Each count per file (where there is one) and in total."""
    metrics = []
    for name in COUNTS:
        per_file = counts[name]
        metrics += [Metric(f"citations.{name}", TOOL, Scope("file", path), float(n))
                    for path, n in sorted(per_file.items())]
        metrics.append(Metric(f"citations.{name}", TOOL, Scope("target"), float(sum(per_file.values()))))
    return metrics
