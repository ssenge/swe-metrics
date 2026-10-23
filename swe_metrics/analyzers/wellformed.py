"""Well-formedness (built in): JSON and XML files that don't parse, per file and language."""
from __future__ import annotations

import json
from pathlib import Path

from swe_metrics import __version__
from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.sarif import Finding, count_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.core.wellformed import UnsafeXmlError, is_jsonc, parse_error

TOOL = "swe-metrics"
KINDS = ("json", "xml")


class Wellformed:
    """Implements core.analyzer.Analyzer by parsing each file (core.wellformed); no tool needed."""

    id = "wellformed"
    tool = TOOL
    families: tuple[str, ...] = ("syntax",)

    def version(self) -> str:
        """The swe-metrics version: the parsers are Python's json and defusedxml, which ship with it."""
        return __version__

    def prerequisites(self) -> str:
        """The parsers need nothing."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The JSON and XML files, without the JSON files their tools read with comments (core.wellformed)."""
        return tuple(p for p in target.files if language(p) in KINDS and not is_jsonc(p))

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """One parse error per file that doesn't parse; the errors with line and message as the detail."""
        found, errors = [], []
        for path in files:
            kind = language(path) or ""
            try:
                failure = parse_error(kind, (Path(target.root) / path).read_bytes())
            except UnsafeXmlError as exc:  # unsafe to parse: not counted as well-formed or malformed
                raise UnsafeXmlError(f"{path} was not parsed: it declares entities ({exc})") from exc
            if failure:
                found.append(Finding(kind, "error", path, failure.line))  # rule: the file's language
                errors.append({"path": path, "line": failure.line, "message": failure.message})
        detail = Path(scratch) / "wellformed.json"
        detail.write_text(json.dumps(errors, indent=1))
        metrics = count_metrics("syntax.parse_errors", TOOL, found, ("language", lambda f: f.rule))
        return Measurement(metrics, (("wellformed-json", str(detail)),))
