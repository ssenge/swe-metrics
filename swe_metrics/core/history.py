"""Git history as data: commits parsed from `git log` output, per-file history metrics and change coupling."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from itertools import combinations

from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.stats import rollup

RECORD = "\x1e"  # starts every commit in LOG_FORMAT; -z ends header and paths with NUL
LOG_FORMAT = "%x1e%aE%x00%ct"  # author e-mail (after .mailmap) and committer time, nothing else
SECONDS_PER_DAY = 86400
PER_FILE = ("history.commits", "history.authors", "history.age_days")


@dataclass(frozen=True)
class Coupling:
    """Change-coupling parameters (code-maat's min-shared-revs, min-revs and max-changeset-size)."""

    min_shared: int = 2
    min_revs: int = 2
    max_changeset: int = 50

    def describe(self) -> str:
        """The parameters as they appear in the analyzer's version string."""
        return (f"coupling: min-shared {self.min_shared}, min-revs {self.min_revs}, "
                f"max-changeset {self.max_changeset}")


@dataclass(frozen=True)
class Commit:
    """One commit as far as it concerns the target. The author is only ever counted, never reported."""

    author: str
    time: int
    files: tuple[str, ...]
    size: int


def parse_log(text: str, prefix: str, wanted: Collection[str]) -> list[Commit]:
    """Commits from `git log -z --name-only --format=LOG_FORMAT` output, with paths relative to the target.

    prefix is the target's directory inside the repository (git rev-parse --show-prefix); only paths in
    wanted are kept, and commits that change none of them are dropped. size counts every path the commit
    changed, also outside the target, so a bulk change is recognized whatever the target is.
    """
    commits = []
    for record in text.split(RECORD)[1:]:
        author, time, *paths = record.split("\0")
        changed = [path.removeprefix("\n") for path in paths if path]
        files = tuple(sorted({p.removeprefix(prefix) for p in changed if p.startswith(prefix)} & set(wanted)))
        if files:
            commits.append(Commit(author.lower(), int(time), files, len(changed)))
    return commits


def file_metrics(commits: Sequence[Commit], head_time: int, tool: str) -> list[Metric]:
    """Commits, distinct authors and days since the last change per file, plus target statistics.

    The age counts from the HEAD commit's committer time, so the same commit always gives the same value.
    """
    counts: Counter[str] = Counter()
    authors: defaultdict[str, set[str]] = defaultdict(set)
    last: dict[str, int] = {}
    for commit in commits:
        for path in commit.files:
            counts[path] += 1
            authors[path].add(commit.author)
            last[path] = max(last.get(path, commit.time), commit.time)
    metrics = []
    for path in sorted(counts):
        age = max(0, head_time - last[path]) // SECONDS_PER_DAY
        values = (counts[path], len(authors[path]), age)
        metrics += [Metric(metric_id, tool, Scope("file", path), float(value))
                    for metric_id, value in zip(PER_FILE, values, strict=True)]
    rollups = [rollup(metrics, metric_id, tool) for metric_id in PER_FILE]
    return metrics + [m for m in rollups if m]


def coupling_metrics(commits: Sequence[Commit], tool: str, params: Coupling) -> list[Metric]:
    """Change coupling per file pair: shared commits / mean commits of both files x 100 (code-maat's degree).

    Bulk commits (more than max_changeset files) count neither as shared nor towards a file's commits.
    Each unordered pair appears once, under the lexicographically smaller path.
    """
    regular = [c for c in commits if c.size <= params.max_changeset]
    revs = Counter(path for c in regular for path in c.files)
    shared = Counter(pair for c in regular for pair in combinations(c.files, 2))
    metrics = []
    for (first, second), together in sorted(shared.items()):
        if together < params.min_shared or min(revs[first], revs[second]) < params.min_revs:
            continue
        degree = together / ((revs[first] + revs[second]) / 2) * 100
        metrics.append(Metric("history.change_coupling", tool, Scope("file", first), round(degree, 2),
                              labels=(("with", second),)))
    return metrics
