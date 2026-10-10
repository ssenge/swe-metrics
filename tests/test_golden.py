"""Golden report: the locally installed tools give the recorded results on the fixtures.

Runs only with SWE_METRICS_GOLDEN=1 (it runs every tool; scripts/integration.sh sets it). A tool whose
installed version differs from the recorded one is skipped and named, not failed: a new version may
legitimately measure differently, and the golden file then needs a deliberate update.
Update: SWE_METRICS_GOLDEN=update pytest tests/test_golden.py
"""
import json
import os
import shutil
from collections import defaultdict

import pytest

from swe_metrics.cli.main import Settings, analyzers
from swe_metrics.runner.measure import measure
from tests.helpers import FIXTURES

GOLDEN = FIXTURES.parent / "tests" / "golden" / "fixtures.json"
NETWORK = {"trivy", "terraform"}  # results depend on a vulnerability database or provider downloads
MODE = os.environ.get("SWE_METRICS_GOLDEN", "")


def normalized(report):
    """Per tool: its version and its metrics in a stable order (tools that didn't run are left out)."""
    versions = {a.tool: a.version for a in report.analyzers if a.status == "ran"}
    metrics = defaultdict(list)
    for m in report.metrics:
        if m.tool in versions and m.tool not in NETWORK:
            metrics[m.tool].append(m.as_dict())
    def order(row):
        return json.dumps(row, sort_keys=True)
    return {tool: {"version": versions[tool], "metrics": sorted(rows, key=order)}
            for tool, rows in sorted(metrics.items())}


@pytest.mark.skipif(not MODE, reason="runs only with SWE_METRICS_GOLDEN=1 (scripts/integration.sh)")
def test_fixtures_match_the_golden_report(tmp_path):
    """Every tool at its recorded version gives exactly the recorded metrics."""
    target = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, target)  # a plain directory: no Git history, same on every machine
    report = measure(target, analyzers(Settings(str(target / "sast" / "rules.yaml"))))
    got = normalized(report)
    if MODE == "update":
        GOLDEN.write_text(json.dumps(got, indent=1, sort_keys=True) + "\n")
        pytest.skip(f"golden report written for {len(got)} tools")
    want = json.loads(GOLDEN.read_text())
    installed = {tool: got[tool]["version"] if tool in got else "none" for tool in want}
    differing = {tool: f"installed {installed[tool]}, golden {w['version']}"
                 for tool, w in want.items() if installed[tool] != w["version"]}
    mismatched = [tool for tool, w in want.items()
                  if tool not in differing and got[tool]["metrics"] != w["metrics"]]
    print("skipped (version differs or tool missing):", differing or "none")
    assert not mismatched, f"tools measuring differently at the recorded version: {mismatched}"
    assert len(differing) < len(want), "no tool at its recorded version (scripts/install-tools.sh)"
