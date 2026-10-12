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
a clear rubric can, if it is grounded in deterministic evidence.

### Request, part 1: deterministic evidence in `measure` (new metric family `design`)

New analyzers that only **count and locate**, without judging, so they fit `measure`'s principles (stateless,
reproducible, no interpretation):

| Metric | What it counts | Detail |
|---|---|---|
| `design.literal_dispatch` | Branches that compare an identifier with a string or enum literal to choose behaviour (`if x == "maven"`, `match kind: case "npm"`), and dictionaries from literals to callables or classes | Per site: file, line, the literals, the enclosing function |
| `design.literal_spread` | The same literal used as a dispatch key in more than one module | Per literal: the modules that branch on it (the shotgun-surgery signal) |
| `design.type_switch` | `isinstance` / type-tag chains with three or more arms | Per site, with the types |
| `design.concrete_imports` | Imports of concrete implementation modules from modules that otherwise only orchestrate (a module that imports many sibling implementations of one role) | Per importing module: the implementations it names |

Languages first: Python, Java, TypeScript/JavaScript (the languages with tree-sitter grammars in use).
`direction`: lower is better for all four. The report's per-site detail is what part 2 feeds to the reviewer.

### Request, part 2: `swe-metrics review` (a new command, separate from `measure`)

`swe-metrics review REPORT --target PATH --rubric FILE | package.module:NAME --model PROVIDER:MODEL [--samples N] [--out FILE]`

A **review definition** (like a scoring definition, §12) is versioned Python code with `name`, `version`, the
rubric (the questions, each with a pass/fail criterion and a severity) and the evidence it needs. The command:

1. reads the deterministic evidence from the report (part 1, plus the dependency graph and coupling metrics);
2. gives the model only the evidence sites and the code around them, never the whole repository;
3. asks the rubric's questions per site and per module;
4. returns findings in the report's finding format (rule, location, severity, message), each with the evidence
   it was based on and the model's rationale.

**Rubric of the shipped definition `design-default@1`:**
- Is a set of variants (tools, vendors, formats, providers, product types) handled by literal branches in more than
  one place, where one interface with registered implementations would remove the branches?
- Does an orchestrating component know internals of the variants it orchestrates (names, paths, command lines,
  formats)?
- Does high-level policy depend on concrete implementations instead of an abstraction?
- Can a new variant be added without changing existing code (open/closed)?

### How it stays honest with swe-metrics' principles

- **`measure` stays deterministic.** Part 1 only counts and locates; the language model never runs in `measure`.
- **Judgement is explicit and separate**, like `score`: a named, versioned review definition, replaceable by the
  caller. Every finding names the definition and its version.
- **Non-determinism is declared, not hidden.** The output records the model, its version and the sampling settings.
  With `--samples N`, the model is asked N times and only findings that a majority of samples report are kept;
  the agreement ratio is recorded per finding. The schema marks the output as `deterministic: false`.
- **Consumer-agnostic and stateless.** The caller chooses the provider and model and supplies the credentials;
  swe-metrics stores nothing between calls and knows no consumer.
- **Data handling.** Only the evidence sites and their surrounding code leave the machine, and only to the provider
  the caller names. A `--dry-run` prints exactly what would be sent.
- **Fail closed.** A model error, an unparsable answer or a sample disagreement below the threshold is reported as
  an error of the review, never as "no findings".

### Acceptance

- Part 1 finds the literal dispatch, its spread and the type switches in fixtures written for it (Python, Java,
  TypeScript), with zero findings on equivalent fixtures that use an interface with registered implementations.
- Part 2 reports the coupling in the "hard-coded variants" fixture and nothing in the "registered implementations"
  fixture, with ≥ 0.8 agreement over 5 samples, for at least one model of two different providers.
- `swe-metrics schema` describes the review output; the golden-report tests stay deterministic because they never
  call `review`.
