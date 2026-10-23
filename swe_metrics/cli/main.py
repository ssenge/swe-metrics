"""swe-metrics command line: measure a target, score a report, list the analyzers, print the schemas."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

from swe_metrics.analyzers.buildreports import report_analyzers
from swe_metrics.analyzers.checkov import Checkov
from swe_metrics.analyzers.cognitive import Cognitive
from swe_metrics.analyzers.complexipy import Complexipy
from swe_metrics.analyzers.depcruise import Depcruise
from swe_metrics.analyzers.doc_coverage import DocCoverage
from swe_metrics.analyzers.dockerfile import Dockerfile
from swe_metrics.analyzers.git_history import GitHistory
from swe_metrics.analyzers.gitleaks import Gitleaks
from swe_metrics.analyzers.hadolint import Hadolint
from swe_metrics.analyzers.jdeps import Jdeps
from swe_metrics.analyzers.jscpd import Jscpd
from swe_metrics.analyzers.likec4 import Likec4
from swe_metrics.analyzers.lizard import Lizard
from swe_metrics.analyzers.lychee import Lychee
from swe_metrics.analyzers.markdownlint import Markdownlint
from swe_metrics.analyzers.opengrep import Opengrep
from swe_metrics.analyzers.python_imports import PythonImports
from swe_metrics.analyzers.shellcheck import Shellcheck
from swe_metrics.analyzers.terraform import Terraform
from swe_metrics.analyzers.tflint import Tflint
from swe_metrics.analyzers.trivy import Trivy
from swe_metrics.analyzers.wellformed import Wellformed
from swe_metrics.analyzers.yamllint import Yamllint
from swe_metrics.cli.definitions import load_definition
from swe_metrics.core.analyzer import Analyzer
from swe_metrics.core.catalog import families
from swe_metrics.core.reports import REPORT_KINDS, parse_reports
from swe_metrics.runner.measure import Options, measure

USAGE_ERROR = 2  # argparse's own exit code for usage errors; 1 means an internal failure


@dataclass(frozen=True)
class Settings:
    """Caller choices that analyzers need: SAST rules and build reports by kind."""

    sast_rules: str | None = None
    reports: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


NO_SETTINGS = Settings()


def analyzers(settings: Settings = NO_SETTINGS) -> list[Analyzer]:
    """Every analyzer, in report order."""
    return [Lizard(), Cognitive(), Complexipy(), Jscpd(), Gitleaks(), Trivy(), Opengrep(settings.sast_rules),
            Markdownlint(), Lychee(), Terraform(), Tflint(), Checkov(), Hadolint(), Dockerfile(), Likec4(),
            Shellcheck(), Yamllint(), Wellformed(), PythonImports(), Depcruise(),
            Jdeps(settings.reports.get("classes", ())), DocCoverage(), GitHistory(),
            *report_analyzers(settings.reports)]


def _inputs(args: argparse.Namespace) -> tuple[Settings, Options]:
    """Validated settings and options; ValueError for any input the measurement can't use."""
    unknown = set(args.only) - families()
    if unknown:
        raise ValueError(f"unknown metric families: {sorted(unknown)} (known: {sorted(families())})")
    details = Path(args.details) if args.details else None
    if details:
        try:  # before measuring: a run must not fail at the end on an unusable output directory
            details.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"--details directory can't be created: {exc}") from exc
    settings = Settings(args.sast_rules, parse_reports(args.report))
    return settings, Options(tuple(args.only), tuple(args.exclude), details, args.changed_since or "")


def cmd_measure(args: argparse.Namespace) -> int:
    """Measure the target and write the report as JSON."""
    try:
        settings, options = _inputs(args)
        report = measure(Path(args.target), analyzers(settings), options)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return USAGE_ERROR
    return _write(json.dumps(report.as_dict(), indent=2) + "\n", args.out)


def _write(text: str, out: str | None) -> int:
    """Write a JSON document to the file or stdout; exit code 1 if the file can't be written."""
    if not out:
        sys.stdout.write(text)
        return 0
    try:
        Path(out).write_text(text)
    except OSError as exc:
        print(f"error: can't write {out}: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    """List every analyzer with its tool, families and installed version (as a table or JSON)."""
    rows: list[dict[str, Any]] = [{"id": a.id, "tool": a.tool, "version": a.version(),
                                   "families": list(a.families)} for a in analyzers()]
    if args.json:
        sys.stdout.write(json.dumps(rows, indent=2) + "\n")
        return 0
    for row in rows:
        version = row["version"] or "not installed"
        print(f"{row['id']:<12} {row['tool']:<12} {version:<14} {','.join(row['families'])}")
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    """Print the JSON Schema of the report or of the score."""
    sys.stdout.write((files("swe_metrics") / "schemas" / f"{args.document}.schema.json").read_text())
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    """Score a report with a scoring definition (default: swe-default) and write the score as JSON."""
    try:
        definition = load_definition(args.definition)
        report = json.loads(Path(args.report).read_text())
        baseline = json.loads(Path(args.baseline).read_text()) if args.baseline else None
        result = definition.score(report, baseline)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return USAGE_ERROR
    if not isinstance(result, dict) or "score" not in result:
        print("error: the definition's score() must return a score document", file=sys.stderr)
        return 1
    return _write(json.dumps(result, indent=2) + "\n", args.out)


def parser() -> argparse.ArgumentParser:
    """The argument parser with all subcommands."""
    p = argparse.ArgumentParser(prog="swe-metrics", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    m = sub.add_parser("measure", help="measure a file, directory or repository")
    m.add_argument("target")
    m.add_argument("--only", action="append", default=[], help="metric family; repeatable (default: all)")
    m.add_argument("--exclude", action="append", default=[], help="glob of paths to leave out; repeatable")
    m.add_argument("--out", help="write the report to this file (default: stdout)")
    m.add_argument("--details", help="keep the tools' detailed outputs (e.g. SARIF) in this directory")
    m.add_argument("--sast-rules", help="rule file or directory for static analysis (opengrep)")
    m.add_argument("--changed-since", help="Git targets: measure only files changed since this ref")
    m.add_argument("--report", action="append", default=[], metavar="KIND=PATH",
                   help=f"build report to read; repeatable. Kinds: {', '.join(sorted(REPORT_KINDS))}")
    tools = sub.add_parser("tools", help="list the analyzers and their tools")
    tools.add_argument("--json", action="store_true", help="print JSON instead of a table")
    schema = sub.add_parser("schema", help="print the JSON Schema of the report or the score")
    schema.add_argument("document", nargs="?", choices=["report", "score"], default="report")
    score = sub.add_parser("score", help="one quality score from a report, by a scoring definition")
    score.add_argument("report", help="a report written by `swe-metrics measure`")
    score.add_argument("--baseline", help="an earlier report; worse values cost points (regressions)")
    score.add_argument("--definition", help="swe-default (default), FILE.py or package.module:NAME")
    score.add_argument("--out", help="write the score to this file (default: stdout)")
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point of the `swe-metrics` command."""
    args = parser().parse_args(sys.argv[1:] if argv is None else argv)
    commands = {"measure": cmd_measure, "tools": cmd_tools, "schema": cmd_schema, "score": cmd_score}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
