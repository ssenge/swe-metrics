"""swe-metrics command line: measure a target, list the analyzers, print the report schema."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from swe_metrics.analyzers.buildreports import report_analyzers
from swe_metrics.analyzers.complexipy import Complexipy
from swe_metrics.analyzers.gitleaks import Gitleaks
from swe_metrics.analyzers.jscpd import Jscpd
from swe_metrics.analyzers.lizard import Lizard
from swe_metrics.analyzers.opengrep import Opengrep
from swe_metrics.analyzers.trivy import Trivy
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
    return [Lizard(), Complexipy(), Jscpd(), Gitleaks(), Trivy(), Opengrep(settings.sast_rules),
            *report_analyzers(settings.reports)]


def cmd_measure(args: argparse.Namespace) -> int:
    """Measure the target and write the report as JSON."""
    unknown = set(args.only) - families()
    if unknown:
        known = sorted(families())
        print(f"error: unknown metric families: {sorted(unknown)} (known: {known})", file=sys.stderr)
        return USAGE_ERROR
    try:
        settings = Settings(args.sast_rules, parse_reports(args.report))
        details = Path(args.details) if args.details else None
        options = Options(tuple(args.only), tuple(args.exclude), details, args.changed_since or "")
        report = measure(Path(args.target), analyzers(settings), options)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return USAGE_ERROR
    text = json.dumps(report.as_dict(), indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    """List every analyzer with its tool, families and installed version."""
    for analyzer in analyzers():
        version = analyzer.version() or "not installed"
        print(f"{analyzer.id:<12} {analyzer.tool:<12} {version:<14} {','.join(analyzer.families)}")
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    """Print the report JSON Schema."""
    sys.stdout.write((files("swe_metrics") / "schemas" / "report.schema.json").read_text())
    return 0


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
    sub.add_parser("tools", help="list the analyzers and their tools")
    sub.add_parser("schema", help="print the report JSON Schema")
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point of the `swe-metrics` command."""
    args = parser().parse_args(sys.argv[1:] if argv is None else argv)
    commands = {"measure": cmd_measure, "tools": cmd_tools, "schema": cmd_schema}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
