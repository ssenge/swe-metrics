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

**Status:** partly done (2026-10-23). YAML, JSON and XML are covered and scored by `swe-default@4`; SQL, JSP,
HTML, Makefiles and YAML misconfiguration checks stay open (see *Done and open* at the end).

### Problem

`core/target.py` recognizes more file types than the analyzers read. A change that touches only such files gets
no quality score: every component of `swe-default` is `not_applicable` (shell scripts had this gap until
`swe-default@3` and the `shellcheck` analyzer). Audit of 2026-10-22, by type; gitleaks (`secrets`) and git-history
(`history`) read every file and are left out of the table:

| Type (extensions) | Read by (families) | `swe-default@3` score for a change of only this type | Gap → standard open-source tool |
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
| `yaml` | **done:** `yamllint` 1.38.0 → `yaml.lint_findings`, component in `swe-default@4` | default rules without `line-length` (a style choice of the code base), fixed config |
| `json` | **done:** built-in `wellformed` → `syntax.parse_errors`, component in `swe-default@4` | a parse needs no tool; JSON-with-comments files (`tsconfig*.json`, `.vscode/`, …) are skipped |
| `xml` | **done:** built-in `wellformed` (defusedxml) → `syntax.parse_errors` | well-formedness only, no DTD loaded; xmllint would add a native dependency for the same answer |
| `sql` | open | SQLFluff 4.4.0 installs fine (a 42 MB virtual environment) but is too slow for a measuring tool: about 6 s for a 20 KB file and 63 s for an 85 KB one (superlinear), so a schema dump or a migration history takes minutes per file. Its default skips files over 20 KB "to avoid parser lock" without linting them, which would leave exactly the large scripts a modernization changes unmeasured while reporting them clean. Open until a faster SQL linter or a per-file size policy is decided. |
| `yaml` misconfigurations | open | checkov's Kubernetes and GitHub Actions frameworks: a second, separate decision (which frameworks, how a manifest is recognized) |
| `jsp` | open | PMD needs a Java runtime and a large distribution rather than one pinned binary, for a handful of JSP rules |
| `html` | open | no single standard linter (HTMLHint and html-validate differ in rules); lychee already reads HTML for links; much HTML in the apps measured is server-side templates that a markup linter misreads |
| `make` | open | checkmake isn't a de-facto standard and has only a few style rules; Makefiles rarely change alone in a modernization |
