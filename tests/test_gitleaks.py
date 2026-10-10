"""The gitleaks analyzer on a recorded report, and on a real secret when gitleaks is installed."""
import random
import shutil
import string
from pathlib import Path

import pytest

from swe_metrics.analyzers import gitleaks as module
from swe_metrics.analyzers.gitleaks import Gitleaks
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES


def recorded(monkeypatch):
    """Make the gitleaks run write the recorded report to its --report-path."""
    def fake_run(argv, cwd, ok=(0,)):
        shutil.copyfile(FIXTURES / "recorded" / "gitleaks.sarif", argv[argv.index("--report-path") + 1])
        return ""
    monkeypatch.setattr(module, "run", fake_run)


def test_counts_only_findings_in_target_files(tmp_path, monkeypatch):
    """Findings outside the target's files (e.g. an ignored .venv) are dropped; counts per file and rule."""
    recorded(monkeypatch)
    target = Target(str(tmp_path), ("app/settings.py", "config.py"))
    result = Gitleaks().measure(target, target.files, str(tmp_path))
    totals = {tuple(m.labels): m.value for m in result.metrics if m.scope.level == "target"}
    assert totals == {(("rule", "aws-access-token"),): 1, (("rule", "github-pat"),): 1, (): 2}
    assert result.details[0][0] == "sarif"
    assert Gitleaks().applicable(target) == target.files and Gitleaks().prerequisites() == ""


@pytest.mark.skipif(not shutil.which("gitleaks"), reason="gitleaks not installed")
def test_real_secret_is_found_but_never_copied(tmp_path):
    """A generated token is found despite a target allowlist; neither metrics nor SARIF contain it."""
    token = "ghp_" + "".join(random.choices(string.ascii_letters + string.digits, k=36))
    (tmp_path / "config.py").write_text(f'TOKEN = "{token}"\n')
    # a target config that allowlists everything must not change the result
    (tmp_path / ".gitleaks.toml").write_text('[allowlist]\npaths = [\'\'\'.*\'\'\']\n')
    analyzer = Gitleaks()
    assert analyzer.version()
    result = analyzer.measure(Target(str(tmp_path), ("config.py",)), ("config.py",), str(tmp_path))
    assert [m.value for m in result.metrics if m.scope.level == "file"] == [1]
    assert token not in repr(result.metrics) and token not in Path(result.details[0][1]).read_text()
