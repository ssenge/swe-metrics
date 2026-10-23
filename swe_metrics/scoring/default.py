"""The default scoring definition `swe-default@4`: hard limits as gates, weighted quality components.

Where the thresholds come from:
- Cyclomatic complexity 10 per function: McCabe, "A Complexity Measure" (IEEE TSE, 1976), and NIST
  SP 500-235 (1996), which recommends 10 as the limit.
- Cognitive complexity 15 per function: the default threshold of SonarSource's rule S3776, which
  implements its "Cognitive Complexity" white paper. Measured by swe-metrics' own analyzer for every
  supported language (tool "swe-metrics"); complexipy's Python-only values stay in the report.
- Duplicated lines 3 % and coverage 80 %: the conditions on new code in SonarQube's built-in quality
  gate "Sonar way".
- Mutation score 80 (good) and 60 (bad): Stryker's default `thresholds` (high 80, low 60).
- Doc coverage 80 %: interrogate's default `fail-under`.
- Lint findings (IaC, Dockerfiles, shell scripts, YAML) and JSON and XML files that don't parse: 0 (good)
  and 10 (bad), as absolute counts: lint rules are written to report nothing on clean code. Shell, YAML
  and parse findings aren't per kloc: no analyzer counts those lines, so a density would leave a change
  of only such files without a score.
- No critical or high vulnerabilities, no secrets, no error-level SAST findings, no failing tests: the
  usual release blockers; here they are gates, so no weighted improvement elsewhere can hide them.
Any change to a threshold, weight or part means a new version: scores compare only under one version.
Earlier versions stay importable for comparisons (`--definition swe_metrics.scoring.default:VERSION_3`).
"""
from __future__ import annotations

from dataclasses import replace

from swe_metrics.scoring import Definition, gate, linear, per_kloc, regression, select

P95 = "p95"
VERSION_2 = Definition(
    name="swe-default",
    version="2",  # 2: cognitive complexity from the multi-language analyzer (1: complexipy, Python only)
    gates=(
        gate(select("dependencies.vulnerabilities", labels={"severity": ["critical", "high"]}), max=0),
        gate("secrets.findings", max=0),
        gate(select("security.findings", labels={"level": "error"}), max=0),
        gate("tests.failed", max=0),
        gate("tests.errors", max=0),
        gate("iac.validation_errors", max=0),
        gate("architecture_model.errors", max=0, cap=60),
    ),
    components=(
        linear(select("complexity.cyclomatic", stat=P95), good=5, bad=10, weight=3),
        linear(select("complexity.cyclomatic", stat="max"), good=10, bad=25, weight=1),
        linear(select("complexity.cognitive", stat=P95, tool="swe-metrics"), good=5, bad=15, weight=3),
        linear(select("size.function_length", stat=P95), good=20, bad=60, weight=1),
        linear("duplication.percent", good=3, bad=10, weight=2),
        linear("coverage.line_percent", good=80, bad=40, weight=3),
        linear("mutation.score", good=80, bad=60, weight=2),
        linear("doc_coverage.percent", good=80, bad=30, weight=1),
        linear("structure.modules_in_cycles", good=0, bad=10, weight=2),
        linear(select("dependencies.vulnerabilities", labels={"severity": "medium"}), good=0, bad=20,
               weight=1),
        linear(per_kloc(select("security.findings", labels={"level": "warning"})), good=0, bad=5, weight=1),
        linear("iac.misconfigurations", good=0, bad=20, weight=1),
        linear("iac.lint_findings", good=0, bad=10, weight=1),
        linear("container.lint_findings", good=0, bad=10, weight=1),
        linear("docs.broken_links", good=0, bad=10, weight=1),
    ),
    regressions=(
        regression(select("complexity.cyclomatic", stat=P95), tolerance=0.5),
        regression(select("complexity.cognitive", stat=P95, tool="swe-metrics"), tolerance=0.5),
        regression("duplication.percent", tolerance=0.5),
        regression("coverage.line_percent", tolerance=1),
        regression("mutation.score", tolerance=2),
        regression("doc_coverage.percent", tolerance=2),
        regression("structure.modules_in_cycles"),
        regression("dependencies.vulnerabilities"),
    ),
)
VERSION_3 = replace(
    VERSION_2,
    version="3",  # 3: shell script lint findings (2 left changes of shell scripts only without a score)
    components=(*VERSION_2.components, linear("shell.lint_findings", good=0, bad=10, weight=1)),
)
DEFINITION = replace(
    VERSION_3,
    version="4",  # 4: YAML lint findings, JSON and XML parse errors (3 left such changes without a score)
    components=(*VERSION_3.components, linear("yaml.lint_findings", good=0, bad=10, weight=1),
                linear("syntax.parse_errors", good=0, bad=10, weight=1)),
)
