"""Coverage reports (JaCoCo XML, Cobertura XML, LCOV): line and branch coverage per file and in total."""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from swe_metrics.core.buildreports import PathIndex, parse_xml, percent, tagged
from swe_metrics.core.report import Metric, Scope

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element  # type only: parsing goes through defusedxml

CONDITIONS = re.compile(r"\((\d+)/(\d+)\)")  # Cobertura's condition-coverage, e.g. "50% (1/2)"
LCOV_LINE = re.compile(r"[A-Z][A-Z0-9_]*:|end_of_record$")


@dataclass
class FileCoverage:
    """One source file's lines (covered or not) and branches per line (covered, total)."""

    names: tuple[str, ...]  # the report's paths for the file, most specific first
    lines: dict[int, bool] = field(default_factory=dict)
    branches: dict[int, tuple[int, int]] = field(default_factory=dict)

    def line(self, number: int, covered: bool) -> None:
        """Record a line; a line any report covers is covered."""
        self.lines[number] = self.lines.get(number, False) or covered

    def branch(self, number: int, covered: int, total: int) -> None:
        """Record the branches of a line; when reports overlap, the larger counts are kept."""
        old_covered, old_total = self.branches.get(number, (0, 0))
        self.branches[number] = (max(old_covered, covered), max(old_total, total))

    def merge(self, other: FileCoverage) -> None:
        """Add another record of the same file (another report, another class of the file)."""
        for number, hit in other.lines.items():
            self.line(number, hit)
        for number, (covered, total) in other.branches.items():
            self.branch(number, covered, total)


def parse_jacoco(data: bytes) -> list[FileCoverage]:
    """JaCoCo XML: the <sourcefile>s of every package; a line with an executed instruction is covered."""
    root = parse_xml(data)
    if root.tag != "report":
        raise ValueError(f"not a JaCoCo XML report: root element <{root.tag}>")
    return [_jacoco_file(package.get("name", "").strip("/"), source)
            for package in root.iter("package") for source in package.findall("sourcefile")]


def _jacoco_file(package: str, source: Element) -> FileCoverage:
    """One <sourcefile>: its path is the package directory plus its name."""
    name = source.get("name", "")
    record = FileCoverage((f"{package}/{name}" if package else name,))
    for line in source.findall("line"):
        number, missed, covered = (int(line.get(key, 0)) for key in ("nr", "mb", "cb"))
        record.line(number, int(line.get("ci", 0)) > 0)
        if missed + covered:
            record.branch(number, covered, missed + covered)
    return record


def parse_cobertura(data: bytes) -> list[FileCoverage]:
    """Cobertura XML (also coverage.py's): the lines of every <class>, named relative to the <source>s."""
    root = parse_xml(data)
    if root.tag != "coverage":
        raise ValueError(f"not a Cobertura XML report: root element <{root.tag}>")
    sources = [s.text.strip().rstrip("/") for s in root.iter("source") if s.text and s.text.strip()]
    found = []
    for cls in root.iter("class"):
        filename = cls.get("filename", "")
        record = FileCoverage((*(f"{source}/{filename}" for source in sources), filename))
        for line in cls.findall("lines/line"):  # not the <method>s' lines: they repeat the class's
            number = int(line.get("number", 0))
            record.line(number, int(line.get("hits", 0)) > 0)
            conditions = CONDITIONS.search(line.get("condition-coverage", ""))
            if line.get("branch") == "true" and conditions:
                record.branch(number, int(conditions.group(1)), int(conditions.group(2)))
        found.append(record)
    return found


def parse_lcov(data: bytes) -> list[FileCoverage]:
    """An LCOV trace: DA (line hits) and BRDA (branch taken) entries of every SF record."""
    found: list[FileCoverage] = []
    record: FileCoverage | None = None
    branches: dict[int, list[int]] = {}  # per line of the current record: taken, total
    for number, key, value in _lcov_entries(data):
        if key == "SF":
            record, branches = FileCoverage((value,)), {}
            found.append(record)
        elif key == "end_of_record":
            record = None
        elif key in ("DA", "BRDA"):
            if record is None:
                raise ValueError(f"LCOV line {number} outside an SF record")
            _lcov_data(record, branches, key, value.split(","))
    return found


def _lcov_entries(data: bytes) -> Iterable[tuple[int, str, str]]:
    """(line number, key, value) of every non-blank line; ValueError for a line that isn't LCOV."""
    for number, text in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
        line = text.strip()
        if line and not LCOV_LINE.match(line):
            raise ValueError(f"not an LCOV trace: line {number}: {line[:40]!r}")
        if line:
            key, _, value = line.partition(":")
            yield number, key, value


def _lcov_data(record: FileCoverage, branches: dict[int, list[int]], key: str, fields: list[str]) -> None:
    """Record a DA (line, hits) or BRDA (line, block, branch, taken or -) entry."""
    number = int(fields[0])
    if key == "DA":
        record.line(number, int(fields[1]) > 0)
        return
    counts = branches.setdefault(number, [0, 0])
    counts[0] += fields[3] != "-" and int(fields[3]) > 0
    counts[1] += 1
    record.branch(number, counts[0], counts[1])


PARSERS = {"jacoco": parse_jacoco, "cobertura": parse_cobertura, "lcov": parse_lcov}


def coverage_metrics(fmt: str, documents: Iterable[bytes], files: Sequence[str]) -> list[Metric]:
    """Coverage per target file and in total; files the target lacks count only in the total."""
    index = PathIndex(files)
    matched: dict[str, FileCoverage] = {}
    unmatched: dict[str, FileCoverage] = {}
    for data in documents:
        for record in PARSERS[fmt](data):
            path = next((p for p in map(index.resolve, record.names) if p), None)
            group, key = (matched, path) if path else (unmatched, record.names[-1])
            group.setdefault(key, FileCoverage(record.names)).merge(record)
    metrics = [m for path in sorted(matched) for m in _metrics(fmt, [matched[path]], Scope("file", path))]
    return metrics + _metrics(fmt, [*matched.values(), *unmatched.values()], Scope("target"))


def _metrics(fmt: str, records: Sequence[FileCoverage], scope: Scope) -> list[Metric]:
    """Line counts, line percent and branch percent of the records together (percents only if defined)."""
    total = sum(len(r.lines) for r in records)
    covered = sum(sum(r.lines.values()) for r in records)
    branches = [counts for r in records for counts in r.branches.values()]
    values = {"coverage.lines_total": float(total), "coverage.lines_covered": float(covered),
              "coverage.line_percent": percent(covered, total),
              "coverage.branch_percent": percent(sum(c for c, _ in branches), sum(t for _, t in branches))}
    return [tagged(metric_id, fmt, scope, value) for metric_id, value in values.items() if value is not None]
