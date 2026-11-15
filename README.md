# swe-metrics

Measures software (code, infrastructure as code, documentation, architecture models) and reports the metrics as JSON, with the tools' detailed findings as SARIF. Stateless and read-only; it never judges the values. It runs locally and uses the tools installed on the machine.

## Install (macOS, Linux; Windows via WSL)

```bash
pip install -e .              # swe-metrics with lizard and complexipy (Python ≥ 3.12)
scripts/install-tools.sh      # every external tool, at its latest release (tools.list), into ~/.local/share/swe-metrics/tools
export PATH="$HOME/.local/bin:$PATH"
swe-metrics tools             # every analyzer with its installed version
```

`install-tools.sh` needs `curl`, `tar`, `unzip`, `python3` with `venv`, and on Linux `xz`:
- Debian/Ubuntu: `sudo apt-get install -y curl unzip xz-utils python3-venv`
- Amazon Linux / Fedora: `sudo dnf install -y curl unzip xz python3`

It never needs root, always installs the latest release, and only prints the `PATH` line. `--check` lists the installed versions; `--only TOOL` installs one tool; `--check-urls` resolves every platform's download URL. A tool that fails to install doesn't stop the others; the script then exits 1 and names it. Checkstyle (for `--rules checkstyle=`) and structurizr-cli are not in `tools.list`: they must be on the PATH, with a JDK. git is expected on the machine; a JDK is needed only for Java class files (`--report classes=PATH`). Without a tool, its analyzer is reported as not installed and the others still run.

## Use

```bash
swe-metrics measure <file|directory|repository> [--only FAMILY|ANALYZER] [--cite-root DIR] [--rules KIND=PATH] [--exclude PATTERN] [--changed-since REF]
                    [--no-gitattributes] [--report KIND=PATH] [--sast-rules PATH] [--details DIR] [--out FILE]
swe-metrics tools [--json]     # analyzers, their tools and installed versions
swe-metrics schema             # the report JSON Schema
```

What is left out: files `.gitignore` ignores; files `.gitattributes` marks `linguist-vendored` or `linguist-generated` (the attributes GitHub and GitLab use; `=false` keeps a file in; read with Git, for a plain directory too; `--no-gitattributes` measures them); and `--exclude` patterns, written as in `.gitignore`: `*` stays within a directory, `**/` also matches no directory (`**/dist/**` covers `dist/` and `web/dist/`), and a pattern without `/` matches at any depth (`*.min.js`). Since 0.6, `a/*.ts` no longer matches `a/b/c.ts`. The report's `subject` counts what was left out: `excluded_files`, and `excluded_by` (`gitattributes`, `exclude`).

## Score

```bash
swe-metrics score report.json [--baseline earlier.json] [--definition my_scoring.py | package.module:NAME]
swe-metrics score --describe [--definition …]      # the definition's gates and components as JSON, no report needed
```

One quality score (0–100) from a report, with its breakdown. The shipped definition `swe-default@0.4` (`swe_metrics/scoring/default.py`) has gates for hard limits (critical or high vulnerabilities, secrets, error-level SAST findings, failing tests, invalid IaC, JSON or XML files that don't parse): while one fails, the score stays at most 40. The rest is a weighted mean of quality components, each scored 0–100 between a "bad" and a "good" threshold, with the sources of the thresholds cited in the code. With `--baseline`, a metric that got worse costs points. A tool that failed or isn't installed makes its gates fail; parts that don't apply to the target are left out. Every score names its definition and version; consumers that check it configure name `swe-default`, version `0.4`: the definition is versioned with the release (0.x), so swe-metrics 0.4 ships `swe-default@0.4`. Earlier versions stay available for comparisons: `--definition swe_metrics.scoring.default:VERSION_0_3` (without the YAML lint and JSON/XML parse error components) and `:VERSION_0_2` (also without the shell script component).

Your own definition is Python:

```python
from swe_metrics.scoring import Definition, gate, linear, per_kloc, select

DEFINITION = Definition("team-a", "1",
    gates=(gate("secrets.findings", max=0),),
    components=(linear(select("complexity.cognitive", stat="p95"), good=5, bad=15, weight=2),
                linear(per_kloc("docs.lint_findings"), good=0, bad=20)))
```

Plan and design decisions: `docs/implementation-plan.md`. Rules for contributors and agents: `AGENTS.md`.
