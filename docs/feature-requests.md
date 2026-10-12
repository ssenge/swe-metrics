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
