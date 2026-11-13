# swe-metrics: feature requests

**Status:** open requests, not built. Each request says what is needed, why, and how it fits the principles of
`implementation-plan.md` §2. When a request is accepted, it moves into the implementation plan as a milestone.

## FR-1: Design review for coupling that metrics cannot see

### Problem

Today's analyzers are deterministic: complexity, size, duplication, coverage, the dependency graph (afferent and
efferent coupling, instability, cycles), secrets, vulnerabilities, lint findings. They find structural coupling
between modules. They do not find the most damaging kind of design coupling, because that code scores well on
every metric:

- **Hard-coded variant dispatch instead of an extension point.** Behaviour that differs per tool, vendor,
  format, provider or product is chosen with `if name == "x"` chains, `match` on a type code, or a dictionary from
  string literals to functions, scattered over the code base, instead of one interface with one implementation per
  variant that is registered, not named. Adding a variant means editing many places (shotgun surgery). The
  branches are short, simple and well tested, so complexity, size and duplication stay green.
- **Knowledge in the wrong place.** A component that should only orchestrate knows the internals of the things it
  orchestrates: names, file layouts, command lines, formats.
- **Dependency inversion violated.** High-level policy depends on concrete implementations instead of on an
  abstraction they implement.
- **Open/closed violated.** A new variant cannot be added without changing existing, unrelated code.

Detecting these needs an understanding of the design intent ("is this knowledge in the right place, is this a
fork that should be an extension point?"). No deterministic rule can decide that alone; a language-model judge with
a clear rubric can, if it is grounded in deterministic evidence. This request is for that evidence.

### Request: deterministic evidence in `measure` (new metric family `design`)

New analyzers that only **count and locate**, without judging, so they fit `measure`'s principles (stateless,
reproducible, no interpretation):

| Metric | What it counts | Detail |
|---|---|---|
| `design.literal_dispatch` | Branches that compare an identifier with a string or enum literal to choose behaviour (`if x == "maven"`, `match kind: case "npm"`), and dictionaries from literals to callables or classes | Per site: file, line, the literals, the enclosing function |
| `design.literal_spread` | The same literal used as a dispatch key in more than one module | Per literal: the modules that branch on it (the shotgun-surgery signal) |
| `design.type_switch` | `isinstance` / type-tag chains with three or more arms | Per site, with the types |
| `design.concrete_imports` | Imports of concrete implementation modules from modules that otherwise only orchestrate (a module that imports many sibling implementations of one role) | Per importing module: the implementations it names |

Languages first: Python, Java, TypeScript/JavaScript (the languages with tree-sitter grammars in use).
`direction`: lower is better for all four. The report's per-site detail is what a consumer's judge reads.

### Not requested: the judgement itself

Deciding whether the located sites are a design flaw needs a language-model judge with a rubric (the questions:
variants handled by literal branches in more than one place where registered implementations would remove them;
an orchestrating component that knows its variants' internals; policy depending on concrete implementations; a new
variant that cannot be added without changing existing code). That judge belongs to the consumer, which already
runs language-model judges with rubrics. swe-metrics only supplies the evidence, so it stays deterministic.

### How it fits swe-metrics' principles

- **Deterministic and reproducible.** The analyzers only count and locate; no model runs in swe-metrics.
- **No interpretation.** No thresholds; every value has `direction: lower`, and consumers judge.
- **Consumer-agnostic and stateless,** like every other analyzer.

### Acceptance

- The analyzers find the literal dispatch, its spread, the type switches and the concrete imports in fixtures
  written for them (Python, Java, TypeScript), each with file, line and the literals or types involved.
- They report zero sites on equivalent fixtures that use one interface with registered implementations.
- The golden-report tests cover the new family; `swe-metrics schema` describes the per-site detail.

## FR-2: Analyzers for recognized file types that nothing measures

**Status:** partly done (2026-10-23). YAML, JSON and XML are covered and scored by `swe-default@0.4`; SQL, JSP,
HTML, Makefiles and YAML misconfiguration checks stay open (see *Done and open* at the end).

### Problem

`core/target.py` recognizes more file types than the analyzers read. A change that touches only such files gets
no quality score: every component of `swe-default` is `not_applicable` (shell scripts had this gap until
`swe-default@0.3` and the `shellcheck` analyzer). Audit of 2026-10-22, by type; gitleaks (`secrets`) and git-history
(`history`) read every file and are left out of the table:

| Type (extensions) | Read by (families) | `swe-default@0.3` score for a change of only this type | Gap → standard open-source tool |
|---|---|---|---|
| `sql` (`.sql`) | lizard's PL/SQL reader (`size`, `complexity`) | yes (complexity, function length) | no lint findings, no duplication → **SQLFluff** (`sqlfluff lint --format json`, fixed dialect and config); jscpd also reads SQL, but `code_files` leaves it out |
| `jsp` (`.jsp`) | jscpd (`duplication`), opengrep (`security`, only with rules that match JSP) | only duplication, when jscpd finds enough tokens | no size, complexity or lint findings → **PMD** (its JSP rules, e.g. `NoScriptlets`, `NoInlineJavaScript`, `NoUnsanitizedJSPExpression`; needs a JRE) |
| `html` (`.html`) | lychee (`docs`: links, broken links) | yes (broken links) | no markup lint or validity → **HTMLHint** (`htmlhint --format json`) or **html-validate** |
| `xml` (`.xml`) | trivy, for `pom.xml` only (`dependencies`) | no | no well-formedness or lint → **xmllint** (libxml2, `--noout`) for parse errors |
| `yaml` (`.yaml`, `.yml`) | trivy, for `pnpm-lock.yaml` only (`dependencies`) | no | no lint → **yamllint** (`-f parsable`); Kubernetes manifests and CI files have no misconfiguration checks → **checkov** (already installed; its Kubernetes and GitHub Actions frameworks) |
| `json` (`.json`) | trivy, for lock files only (`dependencies`); likec4 reads its project configs | no | no parse validity → a built-in parse check (no tool needed) |
| `make` (`Makefile`) | none | no | no lint → **checkmake** |
| code languages | lizard, cognitive (all but Scala and Swift), jscpd, opengrep; Python, JS/TS and Java (with a classes report) also structure, Python and Java doc coverage | yes | cognitive complexity for Scala and Swift (no grammar); structure only for Python, Java, JS/TS |

Covered: Python, Java and the other code languages, Terraform (`iac`), Markdown (`docs`), Dockerfiles
(`container`), LikeC4 (`architecture_model`), shell scripts (`shell`); since 2026-10-23 also YAML (`yaml`), JSON
and XML (`syntax`).

### Request

One analyzer per gap, each following the pattern of `hadolint` and `shellcheck` (a linter whose findings become
`<family>.lint_findings` per file, rule and level; fixed configuration, so a config file in the target can't
change the rules; skipped with "no applicable files" when the target has none), the tool pinned in `tools.lock`,
and a component in a new `swe-default` version. Priority by how often the type changes alone in a modernization:
SQL, then YAML (including Kubernetes and CI misconfigurations), HTML/JSP, XML, Makefiles, JSON.

### How it fits swe-metrics' principles

- **Measure, never judge:** the analyzers only count findings; the score definition judges them.
- **Reproducible:** pinned tools with fixed settings in the version string, like every other analyzer.

### Acceptance

- Each analyzer finds the known findings in a fixture written for it, ignoring a config file in the fixture.
- A change of only that file type gets a real score under the new `swe-default` version.

### Done and open (2026-10-23)

| Type | State | Why |
|---|---|---|
| `yaml` | **done:** `yamllint` 1.38.0 → `yaml.lint_findings`, component in `swe-default@0.4` | default rules without `line-length` (a style choice of the code base), fixed config; generated lock files (`pnpm-lock.yaml`, `conda-lock.yml`/`.yaml`) skipped |
| `json` | **done:** built-in `wellformed` → `syntax.parse_errors`, gate (max 0) and component in `swe-default@0.4` | a parse needs no tool; JSON-with-comments files (`tsconfig*.json`, `.vscode/`, …) are skipped |
| `xml` | **done:** built-in `wellformed` (defusedxml) → `syntax.parse_errors` | well-formedness only, no DTD loaded; xmllint would add a native dependency for the same answer |
| `sql` | open | SQLFluff 4.4.0 installs fine (a 42 MB virtual environment) but is too slow for a measuring tool: about 6 s for a 20 KB file and 63 s for an 85 KB one (superlinear), so a schema dump or a migration history takes minutes per file. Its default skips files over 20 KB "to avoid parser lock" without linting them, which would leave exactly the large scripts a modernization changes unmeasured while reporting them clean. Open until a faster SQL linter or a per-file size policy is decided. |
| `yaml` misconfigurations | open | checkov's Kubernetes and GitHub Actions frameworks: a second, separate decision (which frameworks, how a manifest is recognized) |
| `jsp` | open | PMD needs a Java runtime and a large distribution rather than one pinned binary, for a handful of JSP rules |
| `html` | open | no single standard linter (HTMLHint and html-validate differ in rules); lychee already reads HTML for links; much HTML in the apps measured is server-side templates that a markup linter misreads |
| `make` | open | checkmake isn't a de-facto standard and has only a few style rules; Makefiles rarely change alone in a modernization |

## FR-3: Citations and quotes in documents

**Status:** open (2026-11-13).

### Problem

Documents written about code (architecture notes, analyses, reviews, many of them written by agents) back their
claims with citations such as `src/orders/Api.java:120`, often with the deciding statement quoted in backticks.
Nothing measures whether those citations hold: a citation to a file that doesn't exist, to a line past its end,
or a quote that isn't in the cited code reads exactly like a correct one. lychee does this for links; nothing does
it for code citations.

### Request: analyzer `citations`, new family `citations`

For every Markdown file of the target:
- a **citation** is `<path>:<line>` where `<path>` has a file extension (regex `([\w./-]+\.\w+):(\d+)`), outside
  fenced code blocks; it is resolved against the target root and then against each folder given with
  `--cite-root DIR` (repeatable, relative to the target), the first existing file winning;
- a **quote** is a backtick span in the same list item or paragraph as a citation; it **holds** when its text,
  whitespace folded, occurs in the cited file within 15 lines around the cited line (also whitespace folded, so
  a quote may span the code's line breaks).

| Metric | What it counts | direction |
|---|---|---|
| `citations.citations` | citations found | none |
| `citations.broken` | citations whose file doesn't exist under any root, or whose line is past its end | lower_better |
| `citations.quotes` | quotes next to a citation | none |
| `citations.quotes_not_found` | quotes not found near any citation of their item or paragraph | lower_better |

Per file and in total, with each broken citation and each quote not found as a SARIF finding (file, line, the
citation or quote) in the details, so a caller can map them to its own structure.

### How it fits

Measures, never judges: it counts what holds and what doesn't; a caller decides how many may fail. Stateless:
the target and the roots are its only input. No tool needed (built-in, like `wellformed`).

### Acceptance

A fixture with a correct citation and quote, a citation to a missing file, one past the file's end, a quote that
is a paraphrase, a quote spanning two code lines, and a citation inside a fenced block (not counted).

## FR-4: `--only` by analyzer id

**Status:** done (2026-11-13).

`--only` takes metric families. A family can hold several analyzers (`docs`: markdownlint and lychee; `iac`:
terraform, tflint and checkov), so a caller that wants one tool's numbers runs the others too. Request: `--only`
also accepts an analyzer id (`swe-metrics tools`' first column); a value that is both is the family. An unknown
value stays an error that lists families and ids.

## FR-5: checkov beyond Terraform, and its inline skips

**Status:** open (2026-11-13).

checkov runs with `--framework terraform` only. Infrastructure is also CloudFormation (incl. what CDK and SAM
synthesize), Kubernetes manifests, ARM, Bicep and Serverless files, which checkov checks with built-in rules too.
And an inline skip (`#checkov:skip=CKV_AWS_20:reason`) silences a check without anyone seeing it.

Request:
- checkov runs every framework that applies to the target's files (FR-2's YAML misconfiguration item, decided
  here: the frameworks `cloudformation`, `kubernetes`, `arm`, `bicep`, `serverless`, `terraform`; a YAML or JSON
  file is CloudFormation when it has `AWSTemplateFormatVersion` or a resource type starting `AWS::`, Kubernetes
  when it has `apiVersion` and `kind`).
- Metrics: `iac.resources` (scanned), `iac.failed_checks` (per framework, check id and severity label),
  `iac.skipped_checks` (inline skips), `iac.skips_without_reason`, `iac.parse_errors` (files checkov couldn't
  parse). Each skip goes into the details with its check id, file, line and reason, so a caller can compare
  them with its own list of approved exceptions.
- A new `swe-default` version only if the score should change; otherwise the definition stays.

## FR-6: The caller's rule files for more analyzers

**Status:** open (2026-11-13).

`--sast-rules` lets a caller measure against its own opengrep rules (a client's or a team's coding rules). The
same need exists for Java and TypeScript coding rules, and for several rule sets at once.

Request: `--rules KIND=PATH`, repeatable; `--sast-rules PATH` stays as the same as `--rules opengrep=PATH`.
- `opengrep=PATH` (repeatable): every rule set is scanned; besides the totals, `security.findings` gets a label
  `rules` with the set's file stem, so each set's count is visible.
- `checkstyle=PATH` (new analyzer `checkstyle`, family `lint`): a Checkstyle configuration; metric
  `lint.violations` per file, rule and severity. Runs only when given (no default rules: Checkstyle has no
  neutral default).
- `eslint=PATH` (new analyzer `eslint-rules`, family `lint`): an ESLint flat config; it may import
  `typescript-eslint` and `@eslint/js`, which the analyzer provides; inline `eslint-disable` comments are
  ignored (`--no-inline-config`); metrics `lint.violations` and `lint.unparsed_files`.
- Rules come only from the caller, never from the target (a config file in the target is ignored, as everywhere).
- The rule file's path and its sha256 go into the analyzer's version string, so a report says what it measured.

## FR-7: Analyzer `cfn-lint`

**Status:** open (2026-11-13).

CloudFormation templates have a validator, cfn-lint, that finds what checkov doesn't (invalid properties,
wrong references, unsupported resource types). Request: analyzer `cfn-lint` in family `iac` on the
CloudFormation files (recognized as in FR-5), fixed settings (all regions off, the default rules), metrics
`iac.validation_findings` per file, rule and level (error, warning, informational). Pinned in `tools.lock` (pip).

## FR-8: Analyzer `structurizr`

**Status:** open (2026-11-13).

Like `likec4` for Structurizr DSL workspaces (`*.dsl`): `structurizr-cli validate` and an export of the views.
Metrics as `likec4` has them (`architecture_model.models`, `.invalid_models`, views per type, the most elements
and relations in one view); use the same metric ids so a caller reads both the same way. Needs a JRE; pinned.

## FR-9: `wellformed` for YAML, JSON lines and Markdown front matter

**Status:** open (2026-11-13).

`syntax.parse_errors` covers JSON and XML. Two common structured formats are left out: JSON lines (`.jsonl`,
one JSON value per non-empty line: logs, records, datasets) and the YAML front matter of Markdown files (between
a leading `---` line and the next `---` line: docs sites, knowledge bases). Request: `wellformed` parses both, and YAML
files too (every document of a multi-document file; yamllint's findings mix style with syntax, so a caller
can't tell a broken file from an untidy one); each failure is a finding with its file, line and the parser's
message.

## FR-10: The units a coverage report shows untested

**Status:** open (2026-11-13). Check first: if the `coverage` family already reports per file, only the count
is missing.

A coverage percentage hides which units no test reached at all. Request: from each coverage report (jacoco,
cobertura, lcov), `coverage.units_uncovered`: classes (jacoco), files (cobertura, lcov) with no covered line,
counted in total and listed in the details, one per line, so a caller can show or compare the list.

## FR-11: GitLab security reports as build reports

**Status:** open (2026-11-13).

Projects on GitLab run its security scanners in CI (SAST, secret detection, dependency scanning, container
scanning), each writing a report in GitLab's security report schema (`gl-sast-report.json`,
`gl-secret-detection-report.json`, `gl-dependency-scanning-report.json`, `gl-container-scanning-report.json`;
`version` and `vulnerabilities[]` with `severity`, `identifiers`, `location`). They find things the open-source
analyzers here don't (the SAST analyzer runs GitLab's own rule set), and a caller that ran the scan, in CI or
with GitLab's image, wants the numbers in the same report as everything else.

Request: report kind `gitlab-security` for `--report` (repeatable, like `junit`): metric `security.findings` for
SAST reports, `secrets.findings`, `dependencies.vulnerabilities` and `container.vulnerabilities` for the others
(the scan type is the report's `scan.type`), each per file and with labels `severity` (`critical`, `high`,
`medium`, `low`, `info`, `unknown`) and `rule` (the first identifier's value), `tool` the report's
`scan.analyzer.id`. The findings go into a SARIF detail as for every reader. A report of an unknown schema
version is read when its `vulnerabilities[]` has the fields above, else the reader is `failed` with the reason.

Acceptance: a recorded report of each scan type with findings of every severity; a report without findings.

## FR-12: Inline suppression marks

**Status:** open (2026-11-13).

A finding can be silenced in the code instead of fixed: `nosemgrep`, `nosec` (Bandit, gosec), `NOSONAR`,
`eslint-disable…`, `# noqa`, `# type: ignore`, `#checkov:skip=`, `gitleaks:allow`, `@SuppressWarnings`,
`// NOLINT`. Each is legitimate one at a time; their number and growth say whether a code base is fixed or
merely
quiet, and nothing reports them.

Request: analyzer `suppressions`, new family `suppressions`, built in (a comment scan per language, no tool):
metric `suppressions.marks` per file with labels `kind` (the marker) and `has_reason` (`true` when the mark
carries text after its rule id or a reason separator, as each tool's syntax allows). Each mark goes into the
details with file, line, kind, the rule id it names (if any) and its reason text. Measures only: whether a mark is
justified is the caller's decision.

Acceptance: a fixture per language family (Python, JavaScript/TypeScript, Java, Go, Terraform/YAML) with marks
with and without reasons, and look-alikes that aren't marks (in strings, in prose).
