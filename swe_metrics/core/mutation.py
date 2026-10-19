"""Mutation testing reports (PIT mutations.xml, Stryker JSON): outcomes and score per file and in total."""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from swe_metrics.core.buildreports import PathIndex, parse_xml, percent, tagged
from swe_metrics.core.report import Metric, Scope

KILLED, SURVIVED, NO_COVERAGE = "killed", "survived", "no_coverage"
# Each tool's own reading of its statuses: a timeout (and, for PIT, a memory or run error) means the tests
# detected the mutant. Mutants that never ran or could not be built (PIT NON_VIABLE, Stryker CompileError,
# RuntimeError, Ignored, Pending) are left out, as the tools leave them out of their scores.
PIT_STATUSES = {"KILLED": KILLED, "TIMED_OUT": KILLED, "MEMORY_ERROR": KILLED, "RUN_ERROR": KILLED,
                "SURVIVED": SURVIVED, "NO_COVERAGE": NO_COVERAGE}
STRYKER_STATUSES = {"Killed": KILLED, "Timeout": KILLED, "Survived": SURVIVED, "NoCoverage": NO_COVERAGE}

Mutant = tuple[tuple[str, ...], str]  # (the report's paths of its file, most specific first; outcome)


def parse_pit(data: bytes) -> list[Mutant]:
    """PIT's mutations.xml: the file is the mutated class's package directory plus its source file."""
    root = parse_xml(data)
    if root.tag != "mutations":
        raise ValueError(f"not a PIT mutations report: root element <{root.tag}>")
    found: list[Mutant] = []
    for mutation in root.iter("mutation"):
        outcome = PIT_STATUSES.get(mutation.get("status", ""))
        package, _, _ = (mutation.findtext("mutatedClass") or "").rpartition(".")
        source = mutation.findtext("sourceFile") or ""
        if outcome:
            found.append(((f"{package.replace('.', '/')}/{source}" if package else source,), outcome))
    return found


def parse_stryker(data: bytes) -> list[Mutant]:
    """Stryker's mutation-testing report (JSON): files keyed by path, relative to projectRoot or absolute."""
    doc: Any = json.loads(data)
    if not isinstance(doc, dict) or not isinstance(doc.get("files"), dict):
        raise ValueError("not a mutation-testing report: no 'files' object")
    root = str(doc.get("projectRoot") or "").rstrip("/")
    found: list[Mutant] = []
    for path, entry in doc["files"].items():
        names = (f"{root}/{path}", path) if root and not path.startswith("/") else (path,)
        for mutant in entry.get("mutants", []):
            outcome = STRYKER_STATUSES.get(mutant.get("status", ""))
            if outcome:
                found.append((names, outcome))
    return found


PARSERS = {"pit": parse_pit, "stryker": parse_stryker}


def mutation_metrics(fmt: str, documents: Iterable[bytes], files: Sequence[str],
                     partial: bool = False) -> list[Metric]:
    """Mutant outcomes and score per target file and in total; files the target lacks count only in total, and
    not at all when the target is `partial` (its changes)."""
    index = PathIndex(files)
    per_file: dict[str, Counter[str]] = {}
    total: Counter[str] = Counter()
    for data in documents:
        for names, outcome in PARSERS[fmt](data):
            path = next((p for p in map(index.resolve, names) if p), None)
            total[outcome] += bool(path) or not partial
            if path:
                per_file.setdefault(path, Counter())[outcome] += 1
    metrics = [m for path in sorted(per_file) for m in _metrics(fmt, per_file[path], Scope("file", path))]
    return metrics + _metrics(fmt, total, Scope("target"))


def _metrics(fmt: str, counts: Counter[str], scope: Scope) -> list[Metric]:
    """The outcome counts and the score killed / (killed + survived + no_coverage), when there are mutants."""
    score = percent(counts[KILLED], counts[KILLED] + counts[SURVIVED] + counts[NO_COVERAGE])
    metrics = [tagged(f"mutation.{outcome}", fmt, scope, float(counts[outcome]))
               for outcome in (KILLED, SURVIVED, NO_COVERAGE)]
    return metrics + ([tagged("mutation.score", fmt, scope, score)] if score is not None else [])
