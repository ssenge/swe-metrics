"""eslint-rules: violations of the caller's ESLint flat config in JavaScript and TypeScript."""
from __future__ import annotations

import os
import re
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.sarif import Finding, lint_metrics
from swe_metrics.core.target import Target, language
from swe_metrics.tools.files import digest
from swe_metrics.tools.process import read_json, run, version

TOOL = "eslint"
LANGUAGES = ("javascript", "typescript")
LEVELS = {1: "warning", 2: "error"}
# the wrapper config: the caller's rules, and what no rule should read (output, dependencies, declarations)
WRAPPER = """import rules from "./rules.mjs";
export default [
  { ignores: ["**/node_modules/**", "**/dist/**", "**/build/**", "**/coverage/**", "**/cdk.out/**",
              "**/*.d.ts", "**/eslint.config.*"] },
  ...[rules].flat(),
];
"""


class EslintRules:
    """Implements core.analyzer.Analyzer with `eslint --format json` and the caller's flat config."""

    id = "eslint-rules"
    tool = TOOL
    families: tuple[str, ...] = ("lint",)

    def __init__(self, configs: Sequence[str] = (), modules: str | None = None) -> None:
        """configs: ESLint flat configs; modules: the node_modules folder their imports (`typescript-eslint`,
        `@eslint/js`) resolve in, by default the one eslint is installed in."""
        self.configs = [str(Path(c).resolve()) for c in configs]
        self.modules = Path(modules) if modules else _modules_next_to_eslint()

    def version(self) -> str | None:
        """ESLint's version, with each config's name and digest: what the report ran."""
        found = version(["eslint", "--version"])
        if not found or not all(Path(c).is_file() for c in self.configs):
            return found
        shown = "; ".join(f"{Path(c).stem} sha256:{digest(c)[:12]}" for c in self.configs)
        return f"{found} (rules: {shown})" if shown else found

    def prerequisites(self) -> str:
        """ESLint needs a config, and the packages that config imports must be where eslint is."""
        if not self.configs:
            return "no ESLint rules given (--rules eslint=PATH)"
        missing = [c for c in self.configs if not Path(c).is_file()]
        if missing:
            return f"ESLint rules not found: {', '.join(missing)}"
        return "" if self.modules and self.modules.is_dir() else "no node_modules folder next to eslint"

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The JavaScript and TypeScript files of the target."""
        return tuple(p for p in target.files if language(p) in LANGUAGES)

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Lint the files with each config, inline comments and the target's own configs ignored."""
        root = Path(target.root).resolve()
        found: list[Finding] = []
        unparsed: dict[str, int] = {}
        details = []
        for n, config in enumerate(self.configs):
            work = Path(scratch) / f"eslint-{n}"
            work.mkdir()
            (work / "rules.mjs").write_text(Path(config).read_text())
            (work / "eslint.config.mjs").write_text(WRAPPER)
            if self.modules:
                os.symlink(self.modules, work / "node_modules")
            report = work / "eslint.json"
            # ponytail: files on the command line; a file list if a target ever exceeds the argv limit
            run(["eslint", "-c", str(work / "eslint.config.mjs"), "--no-inline-config", "--no-warn-ignored",
                 "--format", "json", "-o", str(report), *files], cwd=target.root, ok=(0, 1))
            more, bad = _findings(read_json(report), root)
            found += more
            unparsed.update(bad)
            details.append(("eslint-json", str(report)))
        metrics = lint_metrics("lint.violations", TOOL, found)
        metrics += [Metric("lint.unparsed_files", TOOL, Scope("file", p), 1.0) for p in sorted(unparsed)]
        metrics.append(Metric("lint.unparsed_files", TOOL, Scope("target"), float(len(unparsed))))
        return Measurement(metrics, tuple(details))


def _findings(report: list[dict[str, Any]], root: Path) -> tuple[list[Finding], dict[str, int]]:
    """The violations of an ESLint JSON report, and the files its parser couldn't read."""
    found: list[Finding] = []
    unparsed: dict[str, int] = {}
    for entry in report:
        path = _relative(str(entry["filePath"]), root)
        for message in entry.get("messages") or []:
            if message.get("fatal"):
                unparsed[path] = unparsed.get(path, 0) + 1
            elif message.get("ruleId"):
                found.append(Finding(message["ruleId"], LEVELS.get(message.get("severity"), "error"), path,
                                     int(message.get("line", 0))))
    return found, unparsed


def _relative(name: str, root: Path) -> str:
    """A reported file name relative to the target's root."""
    try:
        return str(Path(name).resolve().relative_to(root))
    except ValueError:
        return name


def _modules_next_to_eslint() -> Path | None:
    """The node_modules folder eslint is installed in: through the wrapper script `install-tools.sh` writes,
    or the symlink an npm install leaves; None when eslint isn't there."""
    exe = shutil.which("eslint")
    if exe is None:
        return None
    text = Path(exe).read_text(errors="ignore") if Path(exe).stat().st_size < 1000 else ""
    wrapped = re.search(r'exec "([^"]+)"', text)
    real = Path(wrapped.group(1) if wrapped else exe).resolve()
    return next((p for p in real.parents if p.name == "node_modules"), None)
