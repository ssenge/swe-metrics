"""git history: commits, authors and age per file, and change coupling between files, from `git log`."""
from __future__ import annotations

import subprocess  # only for TimeoutExpired: git itself runs through tools.process

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.history import LOG_FORMAT, Coupling, coupling_metrics, file_metrics, parse_log
from swe_metrics.core.target import Target
from swe_metrics.tools.process import ToolError, run, version

TOOL = "git"
COUPLING = Coupling()
# Pinned against user configuration that would change the log: root commit's files, merges, signatures.
LOG = ["git", "-c", "log.showRoot=true", "log", "-z", "--no-renames", "--no-merges", "--no-relative",
       "--no-show-signature", "--name-only", f"--format={LOG_FORMAT}", "HEAD", "--"]


class GitHistory:
    """Implements core.analyzer.Analyzer with `git log` over the full history of HEAD.

    Renames are not followed (--no-renames): a file's history is the history of its current path.
    """

    id = "git-history"
    tool = TOOL
    families: tuple[str, ...] = ("history",)

    def version(self) -> str | None:
        """The installed git version with the change-coupling parameters, which change results."""
        found = version(["git", "--version"])
        return f"{found} ({COUPLING.describe()})" if found else None

    def prerequisites(self) -> str:
        """git needs nothing beyond itself."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """Every file, if the target is inside a Git work tree with at least one commit; else none."""
        try:
            inside = run(["git", "rev-parse", "--is-inside-work-tree", "--verify", "HEAD"], cwd=target.root)
        except (FileNotFoundError, ToolError, subprocess.TimeoutExpired):
            return ()
        return target.files if inside.startswith("true") else ()

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Read the whole log once, keep the target's files, then compute per-file values and coupling."""
        prefix = run(["git", "rev-parse", "--show-prefix"], cwd=target.root).strip()
        head_time = int(run(["git", "log", "-1", "--format=%ct", "HEAD"], cwd=target.root).strip())
        commits = parse_log(run(LOG, cwd=target.root), prefix, set(files))
        return Measurement(file_metrics(commits, head_time, TOOL) + coupling_metrics(commits, TOOL, COUPLING))
