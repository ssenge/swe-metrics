"""Shared parts of build-report parsing: safe XML, report paths mapped to target files, tagged metrics."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from defusedxml.ElementTree import fromstring

from swe_metrics.core.report import Metric, Scope

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element  # type only: parsing goes through defusedxml


def parse_xml(data: bytes) -> Element:
    """The root element of an untrusted XML report; entity declarations and external references raise."""
    return fromstring(data)


def tagged(metric_id: str, fmt: str, scope: Scope, value: float) -> Metric:
    """A metric measured by reading a report: the tool is the report format, also given as a label."""
    return Metric(metric_id, fmt, scope, value, labels=(("format", fmt),))


def percent(part: float, whole: float) -> float | None:
    """part as a percentage of whole, rounded to 2 decimals; None when whole is 0 (nothing to measure)."""
    return round(100.0 * part / whole, 2) if whole else None


def _normalized(path: str) -> str:
    """A report path with forward slashes, without a file:// scheme or a leading ./."""
    path = path.replace("\\", "/").removeprefix("file://")
    while path.startswith("./"):
        path = path[2:]
    return path


class PathIndex:
    """Maps the paths a report names (absolute, package-relative, ...) to the target's files by suffix."""

    def __init__(self, files: Iterable[str]) -> None:
        """Index the target's files by their file name."""
        self._by_name: dict[str, list[str]] = {}
        for path in files:
            self._by_name.setdefault(path.rsplit("/", 1)[-1], []).append(path)

    def resolve(self, report_path: str) -> str | None:
        """The target file the report path names; None when no file or several files match."""
        path = _normalized(report_path)
        candidates = self._by_name.get(path.rsplit("/", 1)[-1], [])
        # The report path contains a target file (e.g. an absolute path): the longest such file is meant.
        inside = [c for c in candidates if path == c or path.endswith("/" + c)]
        if inside:
            return max(inside, key=len)
        # The report path is a suffix of target files (e.g. a package path): only a unique match counts.
        around = [c for c in candidates if c.endswith("/" + path)]
        return around[0] if len(around) == 1 else None
