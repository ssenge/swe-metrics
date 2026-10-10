"""Doc coverage (built in): public Python and Java APIs with and without a docstring or Javadoc comment."""
from __future__ import annotations

from pathlib import Path

from swe_metrics import __version__
from swe_metrics.core import java_source, python_source
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.doc_coverage import doc_metrics
from swe_metrics.core.target import Target, language

TOOL = "swe-metrics"
LANGUAGES = ("python", "java")


class DocCoverage:
    """Implements core.analyzer.Analyzer by parsing the sources statically (Python's ast, a Java lexer)."""

    id = "doc-coverage"
    tool = TOOL
    families: tuple[str, ...] = ("doc_coverage",)

    def version(self) -> str | None:
        """The swe-metrics version: the analysis is built in."""
        return __version__

    def prerequisites(self) -> str:
        """Nothing beyond the Python standard library."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Python and Java files of the target."""
        return tuple(path for path in target.files if language(path) in LANGUAGES)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Documented and undocumented public APIs per file, per language and in total."""
        flags = {}
        for path in files:
            source = (Path(target.root) / path).read_bytes()
            if language(path) == "python":
                module = python_source.module_name(path)[0]
                flags[path] = ("python", python_source.doc_flags(source, module, path))
            else:
                flags[path] = ("java", java_source.doc_flags(source.decode("utf-8", errors="replace")))
        return Measurement(doc_metrics(flags, TOOL))
