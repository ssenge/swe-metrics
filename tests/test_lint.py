"""The caller's coding rules: Checkstyle on a recorded report and on the real tool when installed."""
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import checkstyle as module
from swe_metrics.analyzers.checkstyle import Checkstyle
from swe_metrics.core.target import Target
from swe_metrics.tools.process import ToolError
from tests.helpers import FIXTURES, values

JAVA = FIXTURES / "lint_java"
CONFIG = str(JAVA / "checkstyle.xml")
FILES = ("Orders.java", "Clean.java")
WANT = {"Orders.java": 3, "rule": {"MissingJavadocMethod": 1, "NeedBraces": 1, "EmptyBlock": 1},
        "level": {"error": 2, "warning": 1}, "total": 3}


def recorded(argv, cwd, ok=(0,)):
    """A fake checkstyle run: the real report recorded on the fixture, with its paths made the target's."""
    text = (FIXTURES / "recorded" / "checkstyle.xml").read_text().replace("/work", str(Path(cwd).resolve()))
    Path(argv[argv.index("-o") + 1]).write_text(text)
    assert argv[:3] == ["checkstyle", "-c", str(Path(CONFIG).resolve())] and argv[3:5] == ["-f", "xml"]
    return "Checkstyle ends with 2 errors.\n"


def test_violations_per_file_rule_and_severity(tmp_path, monkeypatch):
    """A recorded report gives the counts of the fixture's three checks; the XML is kept as the detail."""
    monkeypatch.setattr(module, "run", recorded)
    analyzer = Checkstyle([CONFIG])
    target = Target(str(JAVA), (*FILES, "checkstyle.xml", "notes.md"))
    assert analyzer.applicable(target) == FILES and analyzer.prerequisites() == ""
    result = analyzer.measure(target, FILES, str(tmp_path))
    assert values(result.metrics, "lint.violations") == WANT
    assert result.details[0][0] == "checkstyle-xml" and Path(result.details[0][1]).exists()


def test_without_a_configuration_or_with_a_missing_one_it_is_skipped(tmp_path):
    """There is no neutral default: the caller's configuration is a prerequisite."""
    assert Checkstyle().prerequisites() == "no Checkstyle rules given (--rules checkstyle=PATH)"
    assert Checkstyle([str(tmp_path / "x.xml")]).prerequisites().startswith("Checkstyle rules not found")


def test_the_version_names_the_configuration(monkeypatch):
    """The tool's version and the configuration's stem and digest: what the report ran."""
    monkeypatch.setattr(module, "version", lambda argv: "14.4.0")
    shown = Checkstyle([CONFIG]).version() or ""
    assert shown.startswith("14.4.0 (rules: checkstyle sha256:") and shown.endswith(")")
    assert Checkstyle().version() == "14.4.0"
    monkeypatch.setattr(module, "version", lambda argv: None)
    assert Checkstyle([CONFIG]).version() is None


def test_no_report_is_a_failure_whatever_the_exit_code(tmp_path, monkeypatch):
    """A config Checkstyle can't read writes no report (exit 255): the analyzer fails with its words."""
    monkeypatch.setattr(module, "run", lambda argv, cwd, ok=(0,): "Could not find config XML file 'x.xml'.\n")
    with pytest.raises(ToolError, match="wrote no report: Could not find config"):
        Checkstyle([CONFIG]).measure(Target(str(JAVA), FILES), FILES, str(tmp_path))


def test_a_file_outside_the_target_keeps_its_name():
    """A reported name that isn't below the root stays as it is."""
    assert module._relative("/elsewhere/A.java", Path("/work")) == "/elsewhere/A.java"


@pytest.mark.skipif(not shutil.which("checkstyle"), reason="checkstyle not installed")
def test_the_real_tool_finds_the_fixtures_violations(tmp_path):
    """The real tool, on the fixture, with a checkstyle config in the target that the analyzer ignores."""
    copy = shutil.copytree(JAVA, tmp_path / "java")
    (copy / "checkstyle_checks.xml").write_text("<broken")
    analyzer = Checkstyle([CONFIG])
    assert analyzer.version()
    (tmp_path / "scratch").mkdir()
    result = analyzer.measure(Target(str(copy), FILES), FILES, str(tmp_path / "scratch"))
    assert values(result.metrics, "lint.violations") == WANT
