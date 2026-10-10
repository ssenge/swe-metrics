# swe-metrics

Measures software (code, infrastructure as code, documentation, architecture models) and reports the metrics as JSON, with the tools' detailed findings as SARIF. Stateless and read-only; it never judges the values.

```bash
swe-metrics measure <file|directory|repository> [--only FAMILY] [--exclude GLOB] [--changed-since REF]
                    [--report KIND=PATH] [--sast-rules PATH] [--details DIR] [--out FILE]
swe-metrics tools [--json]     # analyzers, their tools and installed versions
swe-metrics schema             # the report JSON Schema
```

All tools at pinned versions: `docker build -f container/Dockerfile -t swe-metrics .`, then
`docker run --rm -v "$PWD:/work:ro" swe-metrics measure /work`.

Plan and design decisions: `docs/implementation-plan.md`. Rules for contributors and agents: `AGENTS.md`.
