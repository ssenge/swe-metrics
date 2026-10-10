# swe-metrics: implementation plan

**Status:** v0.5, 2026-10-10. M0–M4 are built: 25 analyzers (`swe-metrics tools` lists them), `measure` with `--only`, `--exclude`, `--changed-since`, `--report`, `--sast-rules`, `--details`; `tools [--json]`; `schema`. The gate measures swe-metrics with itself. M5 is built: no container image; `scripts/install-tools.sh` installs the pinned tools locally on macOS and Linux, and the golden report (`scripts/integration.sh`) gives identical results on both.

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
| `docs` | markdown lint findings per rule; links and broken links, checked offline (local links and anchors); readability statistics later | markdownlint, lychee |
| `doc_coverage` | share of public APIs with a doc comment | interrogate (Python), checkstyle Javadoc check (Java) |
| `iac` | validation errors per module, lint findings per rule, failed and passed misconfiguration checks per check, resources; later: resources without tags | terraform validate, tflint, checkov; later trivy config |
| `structure` | module dependency graph; afferent and efferent coupling, instability, cycles | built-in `ast` import parser (Python), jdeps (Java bytecode, needs tier B), dependency-cruiser (JS/TS) |
| `docs` | markdown lint findings, broken links, readability statistics | markdownlint, lychee |
| `doc_coverage` | share of public APIs with a doc comment | built in: Python's `ast`, a small Java lexer |
| `iac` | validation errors, lint findings, misconfiguration findings per severity, resources without tags | terraform validate, tflint, checkov, trivy config |
| `container` | Dockerfile lint findings, base image and its runtime version | hadolint, Dockerfile parser |
| `architecture_model` | model validity, elements, relationships, views, elements per view | LikeC4, Structurizr CLI |
| `history` (Git targets) | commits, distinct authors (counted only) and age in days since HEAD per file; change coupling between files | git log (code-maat method) |

**Tier B: needs a build or test run that the caller performs.** swe-metrics doesn't build projects; build systems are too varied and too slow for a measuring tool. The caller passes the reports with `--report`:
- `tests`: passed, failed, errors, skipped and duration per test suite and in total (`--report junit=`, a file or a directory of `*.xml`);
- `coverage`: line and branch coverage per file and in total (`jacoco`, `cobertura`, `lcov`; coverage.py through `coverage xml`, which writes Cobertura);
- `mutation`: killed, survived and uncovered mutants and the mutation score per file and in total (`pit`, `stryker`). mutmut has no report file format of its own and is not read;
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

## 7. Distribution: local tools, one install script

swe-metrics runs locally and uses the tools installed on the machine. There is no container image. *(M5; the container image built in M2 is removed.)*

- **Python package** `swe-metrics` (Python ≥ 3.12), installed with pip or uv. lizard and complexipy come with it as pinned Python dependencies.
- **External tools** are found on `PATH`. A missing tool is not an error: its analyzer is reported as `failed` with "… is not installed", and every other analyzer still runs.
- **`scripts/install-tools.sh`** installs the external tools on a Unix-like system (macOS and Linux, arm64 and x86_64; on Windows inside WSL):
  - **No root, no package manager.** Everything goes into one user directory, `~/.local/share/swe-metrics/tools` by default (`--prefix` to change it), with links in `~/.local/bin`. The script only prints the `PATH` line to add; it never edits shell profiles. Uninstalling means deleting the directory.
  - **Pinned and verified.** `tools.lock` (repository root) lists each tool's version, platform, SHA-256 and source. The script downloads exactly those files and aborts on any checksum mismatch. Only releases at least two weeks old are pinned.
  - **Kinds of tools:** release binaries (gitleaks, trivy, opengrep, tflint, terraform, hadolint, lychee); Node packages (jscpd, markdownlint-cli2, likec4, dependency-cruiser), installed with a pinned Node into the same directory, so they never depend on the system Node version; Python tools with conflicting dependencies (checkov) in their own virtual environment there.
  - **Not installed:** git (expected on every development machine) and a JDK (needed only for jdeps with `--report classes=PATH`; the script says so if `jdeps` is missing).
  - **Options:** `--only TOOL` (repeatable), `--check` (compare the installed versions with `tools.lock` and install nothing), `--prefix DIR`.
- **Versions:** swe-metrics doesn't require the pinned versions. It uses whatever is on `PATH` and records each tool's version in the report, so two reports are comparable when their versions match. `tools.lock` is the recommended, tested set.
- `swe-metrics tools [--json]` lists every analyzer with its tool and installed version; `swe-metrics schema` prints the report schema.

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
- **Integration tests** run the real, locally installed tools against the fixtures and compare with golden reports (M5). A test whose tool isn't installed is skipped and says so.
- **Schema tests:** every report validates against the published schema.

## 10. Milestones

| Milestone | Content | Done when |
|---|---|---|
| **M0 Skeleton** *(done)* | Package layout, report model and schema, runner, CLI (`measure`, `tools`, `schema`), gate script, one analyzer end to end (lizard: size and complexity) | `swe-metrics measure` on a Python and a Java fixture gives schema-valid reports with the expected values; gate passes |
| **M1 Core code and security** *(done)* | Duplication (jscpd), cognitive complexity for Python (complexipy), secrets (gitleaks), dependencies and vulnerabilities (trivy), SAST (opengrep), SARIF details | Fixture values match; secret matches never appear in output |
| **M2 Docs, IaC, containers, models, self-measurement** *(done)* | markdownlint, lychee, terraform validate, tflint, checkov, hadolint, LikeC4; `--changed-since`; container image with `tools.lock`; dogfooding gate | The gate measures swe-metrics with swe-metrics |
| **M3 Structure and tier B** *(done)* | Coupling, instability and cycles (grimp, dependency-cruiser, jdeps); doc coverage; `--report` for tests, coverage and mutation | Fixture graphs and coupling values match |
| **M4 History** *(done)* | Change frequency, code age, change coupling from Git history | Values match a fixture repository with scripted history |
| **M5 Local tools** *(done)* | Remove the container image (`container/`, `.dockerignore`, references). `tools.lock` at the repository root with entries for macOS and Linux on arm64 and x86_64. `scripts/install-tools.sh` (`--only`, `--check`, `--prefix`). Golden-report integration tests with the local tools. README: install in two commands | On a clean macOS user account and in a Linux shell, `pip install -e .` plus `scripts/install-tools.sh` makes `swe-metrics tools` report every analyzer as installed at the pinned version, and the integration tests pass |

Each milestone is a set of small changes (≤ 400 changed code lines each), every one passing the gate.

## 11. Open questions

0. **Recorded decisions (M1).**
   - Settings that change results are part of the analyzer's version string: trivy's database date, jscpd's minimum tokens and lines.
   - Tools that are Python packages (lizard, complexipy) are pinned dependencies and used through their API; the others are found on `PATH`.
   - opengrep is installed from its signed release binary (signature checked with cosign); `tools.lock` pins the same release.
   - **Merges.** Every analyzer was built on its own branch with a gated commit each (≤ 400 changed lines). The merge commits ran the full gate; only the change-size check doesn't apply to them, because it compares against one parent and so counts the other side's already-gated commits.
   - **M4 history** (`git-history`, tool git): one `git log --no-merges --no-renames` over the full history of HEAD, parsed in `core/history.py`. Renames are not followed: a file's history is that of its current path. Merge commits are left out. Ages count from the HEAD commit's committer date, never the wall clock. Authors are distinct author e-mails (lowercased, after `.mailmap`), counted only and never reported. A subdirectory target keeps its own files, but a commit's size for the bulk-change limit counts all its files, so a pair gets the same coupling whatever the target is. Change coupling follows code-maat: shared commits / mean commits of both files × 100, only with ≥ 2 shared commits and ≥ 2 commits per file, without commits that change > 50 files. These parameters are part of the version string. Files without a commit (untracked) get no history metrics.
   - **M2 containers/models.**
     - Dockerfiles are files named `Dockerfile`, `Dockerfile.*`, `*.Dockerfile` or `Containerfile`.
     - hadolint runs with a fixed, empty configuration (`ignored: []`) from the scratch directory, so a `.hadolint.yaml` in the target or the user's home doesn't change the results. Inline `# hadolint ignore=` pragmas are part of the source and are honored. Levels are hadolint's own (`error`, `warning`, `info`, `style`) and come from its JSON output. A second run writes the SARIF detail, where `info` and `style` both become `note`.
     - The built-in `dockerfile` analyzer parses `FROM` lines itself (`core/dockerfile.py`). It substitutes the defaults of `ARG`s declared before the first `FROM` (`$X`, `${X}`), and it leaves unresolved ones as written. A `FROM` that names an earlier stage counts as a base image but states no runtime.
     - `container.runtime_major` is the first number of the version an image states. The `version` label holds the full stated version (`python:3.12-slim` gives 3 with version `3.12`; `golang:1.23` gives 1 with version `1.23`). The heuristics are one table, `RUNTIME_RULES`. Images that state no version (`node:lts`) get no value.
     - LikeC4 runs `validate --json --no-layout` and `export json --skip-layout` on a copy of the `.c4`/`.likec4` files in the scratch directory. That copy also holds the JSON project configs (`likec4.config.json`, `.likec4.config.json`, `.likec4rc`). Executable configs (`likec4.config.ts` and the like) aren't copied, so target code never runs. Layout drifts aren't validated (the version string says "no layout").
     - LikeC4 counts only views declared in the sources; the `index` view that LikeC4 generates isn't counted. Model elements and relationships are counted, deployment nodes aren't. With several projects the totals add up across them. Per-view values have scope `file` (the view's source file) with `symbol` = view id.
     - Structurizr CLI isn't bound yet (it isn't installed); `architecture_model` is measured for LikeC4 only.
   - **M2 docs/IaC.** Tools that read configuration from the target or write next to it run on a copy in the scratch directory, with swe-metrics' own fixed configuration, so a target can't change what is measured: markdownlint (default rules, inline `markdownlint-disable` comments ignored; a small formatter writes its results as JSON, as markdownlint-cli2 has no machine-readable output of its own), terraform validate (`init -backend=false` per module copy), checkov (a `.checkov.yaml` next to the modules would otherwise skip checks). lychee and tflint only read: lychee runs in the scratch directory (no `lychee.toml` or `.lycheeignore` of the target applies), tflint gets a fixed `--config` (bundled terraform ruleset, recommended preset, local modules).
   - lychee checks offline (local links and anchors only): remote links depend on the network and on time, so they are excluded and not counted as checked. A remote mode can come as an explicit option later.
   - A module is a directory with `.tf` files. terraform validate copies the whole directory, so a module stays complete under `--changed-since`. Provider downloads during `init` need the network; a failed init fails the analyzer, naming the module, rather than reporting the module as valid.
   - A tool that couldn't read part of the input fails the analyzer instead of reporting partial counts: tflint's own errors (e.g. a syntax error) and checkov's parsing errors.
   - Inline suppressions in the target still apply for tflint (`tflint-ignore`) and checkov (`checkov:skip`); neither tool can switch them off. checkov counts them as skipped, which isn't reported.
   - checkov's open-source checks carry no severity, so misconfigurations are counted per check ID (label `check`), not per severity.
   - **M3 build reports.** One analyzer per report kind (`junit`, `jacoco`, `cobertura`, `lcov`, `pit`, `stryker`); it runs no tool: its tool and every metric's `tool` is the report format (plus a `format` label), its version is swe-metrics' own. Parsing is pure (`core/junit.py`, `core/coverage.py`, `core/mutation.py`); XML goes through defusedxml, so entity declarations and external references fail the run. Report paths (Java packages, absolute paths, `SF:` lines, paths relative to a Cobertura `<source>` or Stryker `projectRoot`) map to target files by suffix: a path containing target files picks the longest, a path that is a suffix of target files needs a unique match. Unmatched entries count only in the totals. Several reports of a kind are combined: coverage line by line (a line any report covers is covered; per line the larger branch counts), tests per suite name, mutants added up. `mutation.score` = killed / (killed + survived + no_coverage) × 100, where killed follows each tool's reading: PIT KILLED, TIMED_OUT, MEMORY_ERROR, RUN_ERROR; Stryker Killed, Timeout. PIT NON_VIABLE and Stryker CompileError, RuntimeError, Ignored and Pending are not counted. A test suite's duration is its own `time` (it includes set-up), or the sum of its cases' times when it has none or nests other suites. Percentages are rounded to 2 decimals and omitted when there is nothing to divide by.
   - **M3 structure/doc coverage.**
     - Graph metrics are pure code (`core/graph.py`). Ca and Ce count distinct other modules; instability is left out when both are 0. A cycle is a strongly connected component with more than one module, or a module that depends on itself. Module scopes carry the module's name in `path`: the dotted module (Python), the file (JS/TS), the package (Java).
     - Python imports are parsed with `ast` (built in, `python-imports`) instead of grimp: grimp imports nothing, but needs the package names up front and a `sys.path` set-up. A module's name is its file path in dotted form, minus everything up to the first `src` directory. Every import statement counts, including function-local and `TYPE_CHECKING` ones. A `from X import a` edge goes to `X.a` when that is a module, else to `X`. Imports from outside the target, and a module importing its own names, are dropped. A file that doesn't parse fails the analyzer, with the file named.
     - dependency-cruiser runs with `--no-config` (recorded in its version string), so a target's config can't change the result. As a consequence, path aliases from `tsconfig` or bundlers are not resolved. Only edges between the target's JS/TS files count.
     - jdeps runs as `jdeps -verbose:package` on the `classes` report. The target's own packages are the packages the classes contain; JDK and library packages are dropped. Without the report, the analyzer is skipped.
     - Doc coverage is built in (`doc-coverage`), not interrogate or checkstyle. interrogate's library API isn't documented, and its notion of public depends on its options. checkstyle's MissingJavadoc* checks report only what is missing, so the total of public APIs, which a percentage needs, would still need a parser.
       - Python: public means no leading underscore in the name or in any enclosing module or class. It counts the module, top-level classes and functions, and the methods and nested classes of public classes. A non-empty docstring counts as documented.
       - Java: a lexer drops comments and literals and cuts the code at `{ ; }` outside parentheses. It counts public types, methods and constructors (interface members are implicitly public) inside public types, with a `/** */` before the declaration. `@Override` methods are left out, as in checkstyle's default.
       - The output has per-file values, totals per language (label `language`) and an unlabeled total. A file without public APIs gets counts but no percentage.

1. **Cognitive complexity beyond Python.** No permissive open-source tool covers Java, JS and others the way SonarQube does. Options: implement the published cognitive-complexity rules on top of a parser (tree-sitter), or report the gap. Proposal: report the gap in v1, then decide.
2. **Vulnerability database freshness.** trivy and osv-scanner need a database, which breaks strict reproducibility. Proposal: record the database date in the report (done); later an option to point trivy at a database the caller provides.
3. **Monorepos.** Should `module` scopes come from build files (Maven modules, npm workspaces) or from directories? Proposal: from build files when present, otherwise top-level directories.
4. **Very large repositories.** Is there a need for streaming output or sharding by directory? Proposal: not before a real case needs it.
