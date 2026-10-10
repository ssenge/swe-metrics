"""markdownlint and lychee on recorded outputs, and on the docs fixture when the tools are installed."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import lychee as lychee_module
from swe_metrics.analyzers import markdownlint as markdownlint_module
from swe_metrics.analyzers.lychee import Lychee
from swe_metrics.analyzers.markdownlint import Markdownlint
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES, values

DOCS = FIXTURES / "docs"
EXPECTED = json.loads((DOCS / "expected.json").read_text())
FILES = ("README.md", "guide/setup.md")


def recorded_markdownlint(argv, cwd, ok=(0,)):
    """Write the recorded results where the generated configuration tells the formatter to."""
    config = json.loads((Path(cwd) / ".markdownlint-cli2.jsonc").read_text())
    assert config["config"] == {"default": True} and config["noInlineConfig"] is True
    assert argv[1:] == [":README.md", ":guide/setup.md"]
    shutil.copyfile(FIXTURES / "recorded" / "markdownlint.json", config["outputFormatters"][0][1]["path"])
    return ""


def test_markdownlint_counts_per_file_and_rule(tmp_path, monkeypatch):
    """Recorded findings counted per file, per rule and in total; the target is linted on a copy."""
    monkeypatch.setattr(markdownlint_module, "run", recorded_markdownlint)
    target = Target(str(DOCS), (*FILES, "expected.json"))
    analyzer = Markdownlint()
    assert analyzer.applicable(target) == FILES and analyzer.prerequisites() == ""
    result = analyzer.measure(target, FILES, str(tmp_path))
    assert values(result.metrics, "docs.lint_findings") == EXPECTED["docs.lint_findings"]
    assert (tmp_path / "docs" / "guide" / "setup.md").exists()
    assert [fmt for fmt, _ in result.details] == ["markdownlint-json"]


@pytest.mark.parametrize(("banner", "expected"), [
    ("markdownlint-cli2 v0.23.3 (markdownlint v0.41.1)\n", "0.23.3 (default rules, inline config ignored)"),
    ("no version here", None),
    (FileNotFoundError("markdownlint-cli2"), None),
])
def test_markdownlint_version_from_banner(monkeypatch, banner, expected):
    """The version comes from the help banner, with the fixed rule settings."""
    def fake_run(argv, cwd, ok=(0,)):
        if isinstance(banner, Exception):
            raise banner
        return banner
    monkeypatch.setattr(markdownlint_module, "run", fake_run)
    assert Markdownlint().version() == expected


def recorded_lychee(argv, cwd, ok=(0,)):
    """Write the recorded report (made with the docs fixture copied to /work/docs) to --output."""
    assert "--offline" in argv and ok == (0, 2)
    shutil.copyfile(FIXTURES / "recorded" / "lychee.json", argv[argv.index("--output") + 1])
    return ""


def test_lychee_counts_links_per_file(tmp_path, monkeypatch):
    """Checked links exclude remote ones (offline); broken links per file and in total."""
    monkeypatch.setattr(lychee_module, "run", recorded_lychee)
    target = Target("/work/docs", (*FILES, "page.html", "expected.json"))
    analyzer = Lychee()
    assert analyzer.applicable(target) == (*FILES, "page.html") and analyzer.prerequisites() == ""
    result = analyzer.measure(target, FILES, str(tmp_path))
    assert values(result.metrics, "docs.links") == EXPECTED["docs.links"]
    assert values(result.metrics, "docs.broken_links") == EXPECTED["docs.broken_links"]
    assert [fmt for fmt, _ in result.details] == ["lychee-json"]


def test_lychee_version_records_offline(monkeypatch):
    """The version string says that links were checked offline."""
    monkeypatch.setattr(lychee_module, "version", lambda argv: "0.24.2")
    assert Lychee().version() == "0.24.2 (offline, anchor fragments)"
    monkeypatch.setattr(lychee_module, "version", lambda argv: None)
    assert Lychee().version() is None


@pytest.mark.skipif(not shutil.which("markdownlint-cli2"), reason="markdownlint-cli2 not installed")
def test_markdownlint_real_tool_ignores_target_config(tmp_path):
    """A config in the target that disables every rule doesn't change what is measured."""
    docs = shutil.copytree(DOCS, tmp_path / "docs")
    (docs / ".markdownlint.json").write_text('{"default": false}')
    (tmp_path / "scratch").mkdir()
    analyzer = Markdownlint()
    assert analyzer.version()
    result = analyzer.measure(Target(str(docs), FILES), FILES, str(tmp_path / "scratch"))
    assert values(result.metrics, "docs.lint_findings") == EXPECTED["docs.lint_findings"]


@pytest.mark.skipif(not shutil.which("lychee"), reason="lychee not installed")
def test_lychee_real_tool_on_fixture(tmp_path):
    """The real tool finds the fixture's links and its one broken link, without the network."""
    analyzer = Lychee()
    assert analyzer.version()
    result = analyzer.measure(Target(str(DOCS), FILES), FILES, str(tmp_path))
    assert values(result.metrics, "docs.links") == EXPECTED["docs.links"]
    assert values(result.metrics, "docs.broken_links") == EXPECTED["docs.broken_links"]
