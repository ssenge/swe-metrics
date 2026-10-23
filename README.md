# swe-metrics

Measures software (code, infrastructure as code, documentation, architecture models) and reports the metrics as JSON, with the tools' detailed findings as SARIF. Stateless and read-only; it never judges the values. It runs locally and uses the tools installed on the machine.

## Install (macOS, Linux; Windows via WSL)

```bash
pip install -e .              # swe-metrics with lizard and complexipy (Python ≥ 3.12)
scripts/install-tools.sh      # every external tool, pinned in tools.lock, into ~/.local/share/swe-metrics/tools
export PATH="$HOME/.local/bin:$PATH"
swe-metrics tools             # every analyzer with its installed version
```

`install-tools.sh` needs `curl`, `tar`, `unzip`, `python3` with `venv`, and on Linux `xz`:
- Debian/Ubuntu: `sudo apt-get install -y curl unzip xz-utils python3-venv`
- Amazon Linux / Fedora: `sudo dnf install -y curl unzip xz python3`

It never needs root, verifies every download against `tools.lock`, and only prints the `PATH` line. `--check` compares the installed versions with the lock; `--only TOOL` installs one tool. git is expected on the machine; a JDK is needed only for Java class files (`--report classes=PATH`). Without a tool, its analyzer is reported as not installed and the others still run.

## Use

```bash
swe-metrics measure <file|directory|repository> [--only FAMILY] [--exclude GLOB] [--changed-since REF]
                    [--report KIND=PATH] [--sast-rules PATH] [--details DIR] [--out FILE]
swe-metrics tools [--json]     # analyzers, their tools and installed versions
swe-metrics schema             # the report JSON Schema
```

## Score

```bash
swe-metrics score report.json [--baseline earlier.json] [--definition my_scoring.py | package.module:NAME]
```

One quality score (0–100) from a report, with its breakdown. The shipped definition `swe-default@4` (`swe_metrics/scoring/default.py`) has gates for hard limits (critical or high vulnerabilities, secrets, error-level SAST findings, failing tests, invalid IaC): while one fails, the score stays at most 40. The rest is a weighted mean of quality components, each scored 0–100 between a "bad" and a "good" threshold, with the sources of the thresholds cited in the code. With `--baseline`, a metric that got worse costs points. A tool that failed or isn't installed makes its gates fail; parts that don't apply to the target are left out. Every score names its definition and version; consumers that check it configure name `swe-default`, version `4`. Earlier versions stay available for comparisons: `--definition swe_metrics.scoring.default:VERSION_3` (without the YAML lint and JSON/XML parse error components) and `:VERSION_2` (also without the shell script component).

Your own definition is Python:

```python
from swe_metrics.scoring import Definition, gate, linear, per_kloc, select

DEFINITION = Definition("team-a", "1",
    gates=(gate("secrets.findings", max=0),),
    components=(linear(select("complexity.cognitive", stat="p95"), good=5, bad=15, weight=2),
                linear(per_kloc("docs.lint_findings"), good=0, bad=20)))
```

Plan and design decisions: `docs/implementation-plan.md`. Rules for contributors and agents: `AGENTS.md`.
