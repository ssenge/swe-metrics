"""Tests for SARIF parsing, finding counts and the process helper."""
import sys

import pytest

from swe_metrics.core.sarif import Finding, count_metrics, findings
from swe_metrics.tools.process import ToolError, read_json, run, version
from tests.helpers import FIXTURES

DOC = {"runs": [{"tool": {"driver": {"rules": [{"id": "r1", "defaultConfiguration": {"level": "error"}},
                                               {"id": "r2"}]}},
                 "results": [
                     {"ruleId": "r1", "locations": [{"physicalLocation": {
                         "artifactLocation": {"uri": "file:///repo/src/a.py"}, "region": {"startLine": 4}}}]},
                     {"ruleId": "r2", "level": "note", "locations": [{"physicalLocation": {
                         "artifactLocation": {"uri": "src/b.py"}}}]},
                     {"ruleId": "r3"}]}]}


def test_findings_take_levels_from_result_rule_or_default():
    """Result level first, then the rule's default, then SARIF's default (warning); paths relative to root."""
    assert findings(DOC, "/repo") == [Finding("r1", "error", "src/a.py", 4),
                                      Finding("r2", "note", "src/b.py", 0), Finding("r3", "warning", "", 0)]


def test_count_metrics():
    """Counts per file, per label value, and a total that is 0 when nothing was found."""
    items = [Finding("r1", "error", "a.py"), Finding("r1", "error", "a.py"), Finding("r2", "note", "b.py")]
    metrics = count_metrics("secrets.findings", "t", items, ("rule", lambda f: f.rule))
    rows = [(m.scope.level, m.scope.path, dict(m.labels), m.value) for m in metrics]
    assert rows == [("file", "a.py", {}, 2), ("file", "b.py", {}, 1), ("target", "", {"rule": "r1"}, 2),
                    ("target", "", {"rule": "r2"}, 1), ("target", "", {}, 3)]
    assert [m.value for m in count_metrics("secrets.findings", "t", [], ("rule", str))] == [0]


def test_run_and_version():
    """Output on success; ToolError with the output's tail otherwise; versions found by pattern."""
    assert run([sys.executable, "-c", "print('hi')"], ".") == "hi\n"
    with pytest.raises(ToolError, match="exited with 3: bad"):
        run([sys.executable, "-c", "import sys; print('bad', file=sys.stderr); sys.exit(3)"], ".")
    assert run([sys.executable, "-c", "import sys; sys.exit(1)"], ".", ok=(0, 1)) == ""
    assert version([sys.executable, "-c", "print('tool v1.2.3 (x)')"]) == "1.2.3"
    assert version([sys.executable, "-c", "print('no number')"]) is None
    assert version(["no-such-tool-xyz"]) is None


def test_read_json():
    """A JSON file a tool wrote."""
    assert read_json(FIXTURES / "recorded" / "gitleaks.sarif")["version"] == "2.1.0"


def test_run_tolerates_invalid_utf8():
    """Output that isn't valid UTF-8 is decoded with replacement characters, not an exception."""
    out = run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'caf\\xe9\\n')"], ".")
    assert out == "caf�\n"


def test_run_with_an_environment(monkeypatch):
    """A given environment replaces the inherited one."""
    monkeypatch.setenv("SWE_METRICS_PROBE", "inherited")
    probe = [sys.executable, "-c", "import os; print(os.environ.get('SWE_METRICS_PROBE', 'unset'))"]
    assert run(probe, ".") == "inherited\n"
    assert run(probe, ".", env={"PATH": "/usr/bin:/bin"}) == "unset\n"
