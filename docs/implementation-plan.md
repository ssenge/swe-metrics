# swe-metrics: implementation plan

**Status:** v0.3, 2026-10-10. M0 and M1 are built: lizard, complexipy, jscpd, gitleaks, trivy and opengrep; `measure` (with `--details`, `--sast-rules`), `tools`, `schema`.

## 1. Purpose

swe-metrics measures software. It takes an input and returns the metrics for it:
- a single file;
- a directory;
- a whole Git repository;
- source code, infrastructure as code, documentation, or an architecture description.

Where the underlying tools produce detailed analysis, it returns that too: findings with locations, per-function values, dependency graphs.

It is a **measuring instrument, not a judge.** It never decides whether a value is good or bad. Thresholds, verdicts, ratchets against earlier values, trends, and the combination of several tools into one opinion all belong to the consumers that call it: loop harnesses, CI pipelines, dashboards, review tools.

## 2. Principles

1. **Stateless.** One call, one input, one report. No database, no history, no cache that changes results. Anything a consumer wants to compare, it compares itself, using the per-file and per-function values in the report.
2. **No interpretation.** No thresholds, no pass/fail, no scores that mix metrics, no "quality grade". A value carries its unit and its direction (lower is better, higher is better, or neutral), so consumers can interpret it without guessing.
3. **Consumer-agnostic.** swe-metrics knows nothing about any consumer: no imports, no config formats, no names. Consumers adapt to its report format, never the other way round.
4. **Reproducible.** The same input with the same tool versions gives the same report. The report records every tool's version, and the date of any vulnerability database used.
5. **Read-only.** swe-metrics never modifies its input. Tools that write next to the sources run on a temporary copy.
6. **Honest about coverage.** For every analyzer, the report says whether it ran, was skipped as not applicable (e.g. no Terraform files), or failed, and why. A missing metric is never silently reported as zero.
7. **Tool-tagged values.** When two tools measure the same thing (e.g. complexity from two analyzers), the report lists both values, each tagged with its tool. swe-metrics never merges them.
8. **Exit codes.**
   - **0:** measurement succeeded, whatever the findings.
   - **1:** internal failure.
   - **2:** usage error (the argparse convention), e.g. a missing target or an unknown metric family.
   - A failed analyzer does not change the exit code; it is reported in the report.

## 3. Input

```text
swe-metrics measure <target> [options]
```

| Option | Meaning |
|---|---|
| `<target>` | A file, a directory or a Git repository (local path) |
| `--only <families>` | Measure only these metric families (default: all that apply) |
| `--exclude <glob>` | Leave paths out (e.g. `vendor/**`); `.gitignore` is honored by default |
| `--changed-since <ref>` | Git targets: measure only files changed since this ref (scope for "new code" metrics) |
| `--report <kind>=<path>` | Results of a build the caller ran: test results, coverage, mutation (see §5, tier B) |
| `--out <file>` | Write the report there (default: stdout) |
| `--details <dir>` | Write the tools' detailed outputs there (SARIF, raw reports, graphs) |

Languages and file kinds are detected automatically. A hint (`--kind code|iac|docs|architecture`) is only needed for a single file whose kind isn't clear from its name.

## 4. Output: the report

One JSON document, schema `swe-metrics/report/v1` (published as JSON Schema, versioned).

```json
{
  "schema": "swe-metrics/report/v1",
  "subject": { "target": "…", "kind": "repository", "commit": "…", "changed_since": null,
               "languages": {"java": 2306, "xml": 410}, "files": 57 },
  "analyzers": [
    { "id": "lizard", "tool": "lizard", "version": "1.17.10", "status": "ran" },
    { "id": "tflint", "tool": "tflint", "version": "0.53.0", "status": "skipped",
      "reason": "no Terraform files" }
  ],
  "metrics": [
    { "id": "complexity.cyclomatic", "tool": "lizard", "unit": "count", "direction": "lower_better",
      "scope": {"level": "function", "path": "src/…/ClaimService.java", "symbol": "registerClaim", "line": 120},
      "value": 26 },
    { "id": "complexity.cyclomatic", "tool": "lizard", "unit": "count", "direction": "lower_better",
      "scope": {"level": "target"}, "stats": {"count": 214, "mean": 2.1, "p50": 1, "p95": 5, "max": 26} }
  ],
  "details": [ { "analyzer": "trivy", "format": "sarif", "path": "details/trivy.sarif" } ]
}
```

- **Metric IDs** are stable and tool-neutral, `<family>.<metric>` (catalog in §5). The `tool` field says who measured it.
- **Scopes:** `target`, `module`, `file`, `function`. Target-level entries carry distribution statistics (`count`, `sum`, `mean`, `p50`, `p95`, `max`) so consumers don't have to recompute them. They are statistics, not judgments.
- **Findings** (vulnerabilities, secrets, lint and SAST results) go into SARIF 2.1.0 files under `details/`. The report counts them per file, per label and in total as metrics, e.g. `dependencies.vulnerabilities` with scope target and a `severity` label. Every detail file a measurement kept is listed in the report's `details` array.
- **Secrets are never copied** into the report or the details. Secret findings carry the location and rule only, with the match redacted.

## 5. Metric catalog (first version)

**Tier A: measured from the input alone.**

| Family | Metrics | Tools (first binding) |
|---|---|---|
| `size` | lines of code, comment lines, files, functions per language | lizard, tokei |
| `complexity` | cyclomatic per function; cognitive per function | lizard (cyclomatic, all languages); complexipy (cognitive, Python). A gap for cognitive complexity in other languages is reported as "not measured". |
| `duplication` | duplicated lines and %, clone pairs | jscpd |
| `dependencies` | direct and transitive dependencies; known vulnerabilities per severity; licenses | trivy (SBOM and vulnerabilities), osv-scanner |
| `secrets` | secret findings per rule | gitleaks |
| `security` | static analysis findings per level, for rules the caller gives (`--sast-rules`); without rules the analyzer is skipped, because the findings depend entirely on the rule set | opengrep |
| `structure` | module dependency graph; afferent and efferent coupling, instability, cycles | grimp (Python), jdeps (Java bytecode, needs tier B), dependency-cruiser (JS/TS) |
| `docs` | markdown lint findings, broken links, readability statistics | markdownlint, lychee |
| `doc_coverage` | share of public APIs with a doc comment | interrogate (Python), checkstyle Javadoc check (Java) |
| `iac` | validation errors, lint findings, misconfiguration findings per severity, resources without tags | terraform validate, tflint, checkov, trivy config |
| `container` | Dockerfile lint findings, base image and its runtime version | hadolint, Dockerfile parser |
| `architecture_model` | model validity, elements, relationships, views, elements per view | LikeC4, Structurizr CLI |
| `history` (Git targets) | commits, distinct authors (counted only) and age in days since HEAD per file; change coupling between files | git log (code-maat method) |

**Tier B: needs a build or test run that the caller performs.** swe-metrics doesn't build projects; build systems are too varied and too slow for a measuring tool. The caller passes the reports with `--report`:
- `tests`: passed, failed, skipped (JUnit XML);
- `coverage`: line and branch coverage per file (JaCoCo, Cobertura, lcov, coverage.py);
- `mutation`: mutation score per file (PIT, Stryker, mutmut);
- `structure` for compiled languages: class files for jdeps.

**Later (not in v1):**
- cloud-readiness rules (Konveyor kantra), which are heavy and rule-set-dependent;
- readability models;
- LLM-based analyses. They are not deterministic, so if they come, they come as an explicitly opt-in family with the model recorded.

## 6. Architecture

```text
swe_metrics/
  core/        pure: report model, metric catalog, statistics (percentiles), schema; no I/O
  analyzers/   one module per tool: applies(target) -> bool, run(target, workdir) -> raw, parse(raw) -> metrics
  runner/      detects languages and kinds, picks applicable analyzers, runs them (in parallel), assembles the report
  cli/         argument parsing, output; the only entry point
  schemas/     report JSON Schema
```

- **Analyzer protocol.** Each analyzer declares its families and metric IDs, the file kinds it applies to, the tool it needs and how to get its version. A missing tool means status `failed`, reason "tool not installed". The other analyzers still run.
- **Layer rules (enforced by import-linter):**
  - `core` imports nothing from the other packages and does no I/O;
  - analyzers import only `core`, never each other;
  - `runner` imports `core` and the analyzer registry;
  - `cli` is the composition root.
- **Tool timeouts** are robustness measures (a hung tool), set per analyzer and reported when hit.
- **Python API:** `swe_metrics.measure(target, **options) -> Report`, the same as the CLI.

## 7. Distribution

- **Python package** `swe-metrics` (Python ≥ 3.12), installable with pip/uv; tools are found on `PATH`.
- **Container image** with every tier-A tool installed at pinned versions. This is the recommended way to run it, because installing a dozen tools in matching versions is the hardest part of using them. A `tools.lock` file lists the pinned versions; the image build checks them.
- `swe-metrics tools` lists every analyzer with its tool, the installed version and whether it is available.
- `swe-metrics schema` prints the report schema.

## 8. Quality bar: swe-metrics measures itself

swe-metrics must meet the same standard it helps others enforce. Its gate (`scripts/gate.sh`) must pass before any change counts as done:
- ruff and mypy (strict);
- cognitive complexity ≤ 15 per function, cyclomatic ≤ 10, function length ≤ 50 lines, ≤ 5 parameters, module length ≤ 400 lines;
- docstring coverage ≥ 90 %;
- branch coverage ≥ 85 %;
- duplication ≤ 3 %;
- bandit, pip-audit, gitleaks;
- import-linter layer contracts;
- ≤ 400 changed code lines per commit.

**Dogfooding** *(in place)*. The gate runs `scripts/self_check.py`: it measures the package with `swe-metrics measure` (size, complexity, duplication, secrets) and compares the report with the same limits as the gate's own tools. The limits live in that script, outside the package, true to principle 2. An analyzer that fails, or a metric that is missing, fails the check (fail closed). The gate keeps calling the tools directly as well, so a regression in swe-metrics can't hide a regression in its own code.

## 9. Testing

- **Fixtures with known values:** a tiny project per language and file kind (Python, Java, JavaScript/TypeScript, Terraform, Markdown, C4 model, Dockerfile), each with expected metric values written down in the fixture.
- **Unit tests** parse recorded tool outputs. They are fast and need no tools installed.
- **Integration tests** run the real tools in the container image against the fixtures and compare with golden reports. They are skipped unless enabled.
- **Schema tests:** every report validates against the published schema.

## 10. Milestones

| Milestone | Content | Done when |
|---|---|---|
| **M0 Skeleton** *(done)* | Package layout, report model and schema, runner, CLI (`measure`, `tools`, `schema`), gate script, one analyzer end to end (lizard: size and complexity) | `swe-metrics measure` on a Python and a Java fixture gives schema-valid reports with the expected values; gate passes |
| **M1 Core code and security** *(done)* | Duplication (jscpd), cognitive complexity for Python (complexipy), secrets (gitleaks), dependencies and vulnerabilities (trivy), SAST (opengrep), SARIF details | Fixture values match; secret matches never appear in output |
| **M2 Docs, IaC, containers, models, self-measurement** | markdownlint, lychee, terraform validate, tflint, checkov, hadolint, LikeC4; `--changed-since`; container image with `tools.lock`; dogfooding gate | The gate measures swe-metrics with swe-metrics |
| **M3 Structure and tier B** | Coupling, instability and cycles (grimp, dependency-cruiser, jdeps); doc coverage; `--report` for tests, coverage and mutation | Fixture graphs and coupling values match |
| **M4 History** | Change frequency, code age, change coupling from Git history | Values match a fixture repository with scripted history |

Each milestone is a set of small changes (≤ 400 changed code lines each), every one passing the gate.

## 11. Open questions

0. **Recorded decisions (M1).**
   - Settings that change results are part of the analyzer's version string: trivy's database date, jscpd's minimum tokens and lines.
   - Tools that are Python packages (lizard, complexipy) are pinned dependencies and used through their API; the others are found on `PATH`.
   - opengrep is installed from its signed release binary (signature checked with cosign) until the container image (M2) pins it.
   - **M4 history** (`git-history`, tool git): one `git log --no-merges --no-renames` over the full history of HEAD, parsed in `core/history.py`. Renames are not followed: a file's history is that of its current path. Merge commits are left out. Ages count from the HEAD commit's committer date, never the wall clock. Authors are distinct author e-mails (lowercased, after `.mailmap`), counted only and never reported. A subdirectory target keeps its own files, but a commit's size for the bulk-change limit counts all its files, so a pair gets the same coupling whatever the target is. Change coupling follows code-maat: shared commits / mean commits of both files × 100, only with ≥ 2 shared commits and ≥ 2 commits per file, without commits that change > 50 files. These parameters are part of the version string. Files without a commit (untracked) get no history metrics.
   - **M2 containers/models.**
     - Dockerfiles are files named `Dockerfile`, `Dockerfile.*`, `*.Dockerfile` or `Containerfile`.
     - hadolint runs with a fixed, empty configuration (`ignored: []`) from the scratch directory, so a `.hadolint.yaml` in the target or the user's home doesn't change the results. Inline `# hadolint ignore=` pragmas are part of the source and are honored. Levels are hadolint's own (`error`, `warning`, `info`, `style`) and come from its JSON output. A second run writes the SARIF detail, where `info` and `style` both become `note`.
     - The built-in `dockerfile` analyzer parses `FROM` lines itself (`core/dockerfile.py`). It substitutes the defaults of `ARG`s declared before the first `FROM` (`$X`, `${X}`), and it leaves unresolved ones as written. A `FROM` that names an earlier stage counts as a base image but states no runtime.
     - `container.runtime_major` is the first number of the version an image states. The `version` label holds the full stated version (`python:3.12-slim` gives 3 with version `3.12`; `golang:1.23` gives 1 with version `1.23`). The heuristics are one table, `RUNTIME_RULES`. Images that state no version (`node:lts`) get no value.
     - LikeC4 runs `validate --json --no-layout` and `export json --skip-layout` on a copy of the `.c4`/`.likec4` files in the scratch directory. That copy also holds the JSON project configs (`likec4.config.json`, `.likec4.config.json`, `.likec4rc`). Executable configs (`likec4.config.ts` and the like) aren't copied, so target code never runs. Layout drifts aren't validated (the version string says "no layout").
     - LikeC4 counts only views declared in the sources; the `index` view that LikeC4 generates isn't counted. Model elements and relationships are counted, deployment nodes aren't. With several projects the totals add up across them. Per-view values have scope `file` (the view's source file) with `symbol` = view id.
     - Structurizr CLI isn't bound yet (it isn't installed); `architecture_model` is measured for LikeC4 only.

1. **Cognitive complexity beyond Python.** No permissive open-source tool covers Java, JS and others the way SonarQube does. Options: implement the published cognitive-complexity rules on top of a parser (tree-sitter), or report the gap. Proposal: report the gap in v1, then decide.
2. **Vulnerability database freshness.** trivy and osv-scanner need a database, which breaks strict reproducibility. Proposal: record the database date in the report; offer an offline mode with a database snapshot inside the container image.
3. **Monorepos.** Should `module` scopes come from build files (Maven modules, npm workspaces) or from directories? Proposal: from build files when present, otherwise top-level directories.
4. **Very large repositories.** Is there a need for streaming output or sharding by directory? Proposal: not before a real case needs it.
