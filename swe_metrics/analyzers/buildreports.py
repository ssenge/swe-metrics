"""Build reports the caller passes in (--report kind=path): tests, coverage and mutation, read, not run."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import swe_metrics
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.coverage import coverage_metrics
from swe_metrics.core.junit import junit_metrics
from swe_metrics.core.report import Metric
from swe_metrics.core.target import Target


class BuildReport:
    """Implements core.analyzer.Analyzer for one report kind: reads the given files, runs no tool."""

    id = ""
    families: tuple[str, ...] = ()
    directory_glob = ""  # the report files inside a directory path; empty: only files are accepted

    def __init__(self, paths: Sequence[str] = ()) -> None:
        """paths: the report files (or directories) given for this kind."""
        self.paths = tuple(paths)
        self.tool = self.id  # the report format measured; swe-metrics itself only reads it

    def version(self) -> str | None:
        """swe-metrics' own version: the parsing is built in."""
        return swe_metrics.__version__

    def prerequisites(self) -> str:
        """A report must be given and exist."""
        if not self.paths:
            return f"no {self.id} report given (--report {self.id}=PATH)"
        missing = [path for path in self.paths if not Path(path).exists()]
        return f"report not found: {', '.join(missing)}" if missing else ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """All files: the metrics describe the target, the report is only their source."""
        return target.files

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Read every report file and turn its contents into metrics."""
        return Measurement(self.metrics([path.read_bytes() for path in self._files()], files))

    def metrics(self, documents: list[bytes], files: tuple[str, ...]) -> list[Metric]:
        """The metrics of the report contents; each kind implements it."""
        raise NotImplementedError

    def _files(self) -> list[Path]:
        """The given report files, with a directory expanded to its report files in name order."""
        found: list[Path] = []
        for given in map(Path, self.paths):
            if given.is_dir() and self.directory_glob:
                found += sorted(given.glob(self.directory_glob))
            else:
                found.append(given)
        return found


class Junit(BuildReport):
    """JUnit XML test results: a file or a directory of *.xml files."""

    id = "junit"
    families = ("tests",)
    directory_glob = "*.xml"

    def metrics(self, documents: list[bytes], files: tuple[str, ...]) -> list[Metric]:
        """Test outcomes and duration per suite and in total."""
        return junit_metrics(documents)


class Coverage(BuildReport):
    """A coverage report; the report kind is the format."""

    families = ("coverage",)

    def metrics(self, documents: list[bytes], files: tuple[str, ...]) -> list[Metric]:
        """Line and branch coverage per target file and in total."""
        return coverage_metrics(self.id, documents, files)


class Jacoco(Coverage):
    """JaCoCo XML coverage (jacoco.xml)."""

    id = "jacoco"


class Cobertura(Coverage):
    """Cobertura XML coverage (also coverage.py's `coverage xml`)."""

    id = "cobertura"


class Lcov(Coverage):
    """LCOV coverage trace (lcov.info)."""

    id = "lcov"


KINDS: tuple[type[BuildReport], ...] = (Junit, Jacoco, Cobertura, Lcov)


def report_analyzers(reports: Mapping[str, tuple[str, ...]]) -> list[BuildReport]:
    """One analyzer per report kind, each with the report paths given for its kind (maybe none)."""
    return [kind(reports.get(kind.id, ())) for kind in KINDS]
