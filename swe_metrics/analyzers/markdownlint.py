"""markdownlint: Markdown lint findings with the default rules, per file and rule."""
from __future__ import annotations

import json
import re
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric
from swe_metrics.core.sarif import Finding, count_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import ToolError, read_json, run

TOOL = "markdownlint"
SETTINGS = "default rules, inline config ignored"
# markdownlint-cli2 has no JSON output of its own; this formatter writes its results as they are.
FORMATTER = 'module.exports = (o, p) => require("fs").writeFileSync(p.path, JSON.stringify(o.results));\n'


class Markdownlint:
    """Implements core.analyzer.Analyzer with markdownlint-cli2 on a copy of the Markdown files."""

    id = "markdownlint"
    tool = TOOL
    families: tuple[str, ...] = ("docs",)

    def version(self) -> str | None:
        """markdownlint-cli2's version (from its banner) and the fixed rule settings."""
        try:
            banner = run(["markdownlint-cli2", "--help"], ".", ok=(0, 2))
        except (FileNotFoundError, ToolError, subprocess.TimeoutExpired):
            return None
        found = re.search(r"v(\d+\.\d+\.\d+)", banner)
        return f"{found.group(1)} ({SETTINGS})" if found else None

    def prerequisites(self) -> str:
        """markdownlint needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Markdown files of the target."""
        return tuple(p for p in target.files if language(p) == "markdown")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Lint a copy of the files, so configuration files in the target can't change the rules."""
        copy, report = Path(scratch) / "docs", str(Path(scratch) / "markdownlint.json")
        for path in files:
            (copy / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(target.root) / path, copy / path)
        (copy / ".swe-metrics-formatter.cjs").write_text(FORMATTER)
        config = {"config": {"default": True}, "noInlineConfig": True,
                  "outputFormatters": [["./.swe-metrics-formatter.cjs", {"path": report}]]}
        (copy / ".markdownlint-cli2.jsonc").write_text(json.dumps(config))
        # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
        run(["markdownlint-cli2", *(f":{path}" for path in files)], cwd=str(copy), ok=(0, 1))
        return Measurement(_metrics(read_json(report)), (("markdownlint-json", report),))


def _metrics(results: list[dict[str, Any]]) -> list[Metric]:
    """Findings per file, per rule (its MD number) and in total."""
    found = [Finding(r["ruleNames"][0], r.get("severity", "error"), r["fileName"], r["lineNumber"])
             for r in results]
    return count_metrics("docs.lint_findings", TOOL, found, ("rule", lambda f: f.rule))
