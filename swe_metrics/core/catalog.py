"""The metric catalog: every metric ID with its unit, its direction and what it measures."""
from __future__ import annotations

from dataclasses import dataclass

DIRECTIONS = ("lower_better", "higher_better", "neutral")


@dataclass(frozen=True)
class MetricDef:
    """What a metric ID means. The direction tells consumers how to read a value, never whether it is good."""

    unit: str
    direction: str
    description: str


CATALOG: dict[str, MetricDef] = {
    "size.files": MetricDef("count", "neutral", "Files measured"),
    "size.functions": MetricDef("count", "neutral", "Functions and methods found"),
    "size.lines_of_code": MetricDef("lines", "neutral", "Lines of code, without blank and comment lines"),
    "size.function_length": MetricDef("lines", "lower_better", "Lines of code of a function"),
    "size.parameters": MetricDef("count", "lower_better", "Parameters of a function"),
    "complexity.cyclomatic": MetricDef("count", "lower_better", "McCabe complexity of a function"),
    "complexity.cognitive": MetricDef("count", "lower_better", "Cognitive complexity of a function"),
    "duplication.percent": MetricDef("percent", "lower_better", "Share of lines inside a code clone"),
    "duplication.duplicated_lines": MetricDef("lines", "lower_better", "Lines inside a code clone"),
    "duplication.clones": MetricDef("count", "lower_better", "Code clones (pairs of duplicated fragments)"),
    "secrets.findings": MetricDef("count", "lower_better", "Secrets found (location and rule only)"),
    "dependencies.packages": MetricDef("count", "neutral", "Packages a manifest or lock file declares"),
    "dependencies.vulnerabilities": MetricDef("count", "lower_better", "Known vulnerabilities of packages"),
    "security.findings": MetricDef("count", "lower_better", "Static analysis findings of the given rules"),
    # docs (M2)
    "docs.lint_findings": MetricDef("count", "lower_better", "Markdown lint findings"),
    "docs.links": MetricDef("count", "neutral", "Links checked"),
    "docs.broken_links": MetricDef("count", "lower_better", "Links that don't resolve"),
    # iac (M2)
    "iac.validation_errors": MetricDef("count", "lower_better", "Errors of the IaC engine's own validation"),
    "iac.lint_findings": MetricDef("count", "lower_better", "IaC lint findings"),
    "iac.misconfigurations": MetricDef("count", "lower_better", "Failed IaC misconfiguration checks"),
    "iac.passed_checks": MetricDef("count", "neutral", "Passed IaC misconfiguration checks"),
    "iac.resources": MetricDef("count", "neutral", "Infrastructure resources declared"),
    # container (M2)
    "container.lint_findings": MetricDef("count", "lower_better", "Dockerfile lint findings"),
    "container.base_images": MetricDef("count", "neutral", "FROM instructions (labels: image, stage)"),
    "container.runtime_major": MetricDef("version", "neutral", "Major runtime version in a base image tag"),
    # architecture_model (M2)
    "architecture_model.errors": MetricDef("count", "lower_better", "Errors when the model is parsed"),
    "architecture_model.elements": MetricDef("count", "neutral", "Elements in the model"),
    "architecture_model.relationships": MetricDef("count", "neutral", "Relationships in the model"),
    "architecture_model.views": MetricDef("count", "neutral", "Views in the model"),
    "architecture_model.view_elements": MetricDef("count", "lower_better", "Elements shown in one view"),
    "architecture_model.view_relationships": MetricDef("count", "lower_better", "Relations in one view"),
    # structure (M3): module dependency graph
    "structure.modules": MetricDef("count", "neutral", "Modules in the dependency graph"),
    "structure.dependencies": MetricDef("count", "neutral", "Dependencies between modules"),
    "structure.afferent_coupling": MetricDef("count", "neutral", "Modules that depend on a module (Ca)"),
    "structure.efferent_coupling": MetricDef("count", "lower_better", "Modules a module depends on (Ce)"),
    "structure.instability": MetricDef("ratio", "neutral", "Ce / (Ca + Ce) of a module"),
    "structure.cycles": MetricDef("count", "lower_better", "Dependency cycles (strongly connected groups)"),
    "structure.modules_in_cycles": MetricDef("count", "lower_better", "Modules that are part of a cycle"),
    # doc_coverage (M3)
    "doc_coverage.percent": MetricDef("percent", "higher_better", "Share of public APIs with a doc comment"),
    "doc_coverage.documented": MetricDef("count", "higher_better", "Public APIs with a doc comment"),
    "doc_coverage.undocumented": MetricDef("count", "lower_better", "Public APIs without a doc comment"),
    # tests, coverage, mutation (M3, tier B: from reports the caller passes)
    "tests.passed": MetricDef("count", "higher_better", "Tests that passed"),
    "tests.failed": MetricDef("count", "lower_better", "Tests that failed"),
    "tests.errors": MetricDef("count", "lower_better", "Tests that could not run to a verdict"),
    "tests.skipped": MetricDef("count", "lower_better", "Tests that were skipped"),
    "tests.duration": MetricDef("seconds", "neutral", "Time the tests took"),
    "coverage.line_percent": MetricDef("percent", "higher_better", "Share of lines executed by the tests"),
    "coverage.branch_percent": MetricDef("percent", "higher_better", "Share of branches the tests took"),
    "coverage.lines_total": MetricDef("lines", "neutral", "Coverable lines"),
    "coverage.lines_covered": MetricDef("lines", "higher_better", "Lines executed by the tests"),
    "mutation.score": MetricDef("percent", "higher_better", "Share of mutants the tests killed"),
    "mutation.killed": MetricDef("count", "higher_better", "Mutants the tests killed"),
    "mutation.survived": MetricDef("count", "lower_better", "Mutants the tests let survive"),
    "mutation.no_coverage": MetricDef("count", "lower_better", "Mutants in code no test runs"),
    # history (M4): from the Git history of a repository target
    "history.commits": MetricDef("count", "neutral", "Commits that changed a file"),
    "history.authors": MetricDef("count", "neutral", "Distinct authors who changed a file"),
    "history.age_days": MetricDef("days", "neutral", "Days since a file last changed"),
    "history.change_coupling": MetricDef("percent", "lower_better", "How often two files change together"),
}


def family(metric_id: str) -> str:
    """The family of a metric ID: the part before the first dot."""
    return metric_id.split(".", 1)[0]


def families() -> set[str]:
    """All metric families in the catalog."""
    return {family(metric_id) for metric_id in CATALOG}
