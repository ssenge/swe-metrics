"""The caller's coding rules: Checkstyle and ESLint on recorded reports, and on the real tools."""
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import checkstyle as module
from swe_metrics.analyzers import eslint_rules as eslint_module
from swe_metrics.analyzers.checkstyle import Checkstyle
from swe_metrics.analyzers.eslint_rules import EslintRules
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


# --- ESLint -----------------------------------------------------------------------------------------------

TS = FIXTURES / "lint_ts"
TS_FILES = ("src/order.ts", "src/broken.ts")


def recorded_eslint(argv, cwd, ok=(0,)):
    """A fake eslint run: the real report recorded on the fixture, its paths made the target's."""
    text = (FIXTURES / "recorded" / "eslint.json").read_text().replace("/work", str(Path(cwd).resolve()))
    Path(argv[argv.index("-o") + 1]).write_text(text)
    work = Path(argv[argv.index("-c") + 1]).parent
    assert (work / "rules.mjs").read_text() == (TS / "rules.mjs").read_text(), "the caller's own rules"
    assert (work / "node_modules").is_symlink() and "--no-inline-config" in argv and ok == (0, 1)
    return ""


def test_eslint_violations_and_unparsed_files(tmp_path, monkeypatch):
    """A recorded report: the inline disable in the code is ignored, so both findings count; a file the parser
    can't read is counted as unparsed, not as a violation."""
    monkeypatch.setattr(eslint_module, "run", recorded_eslint)
    modules = tmp_path / "modules"
    modules.mkdir()
    analyzer = EslintRules([str(TS / "rules.mjs")], modules=str(modules))
    target = Target(str(TS), (*TS_FILES, "rules.mjs", "notes.md"))
    assert analyzer.applicable(target) == TS_FILES and analyzer.prerequisites() == ""
    (tmp_path / "scratch").mkdir()
    result = analyzer.measure(target, TS_FILES, str(tmp_path / "scratch"))
    assert values(result.metrics, "lint.violations") == {
        "src/order.ts": 2, "rule": {"@typescript-eslint/no-explicit-any": 1, "prefer-const": 1},
        "level": {"error": 2}, "total": 2}
    assert values(result.metrics, "lint.unparsed_files") == {"src/broken.ts": 1, "total": 1}
    assert result.details[0][0] == "eslint-json"


def test_eslint_prerequisites_and_version(tmp_path, monkeypatch):
    """A config and the packages beside eslint are needed; the version names the config."""
    assert EslintRules().prerequisites() == "no ESLint rules given (--rules eslint=PATH)"
    assert EslintRules([str(tmp_path / "x.mjs")]).prerequisites().startswith("ESLint rules not found")
    rules = str(TS / "rules.mjs")
    lacking = EslintRules([rules], modules=str(tmp_path / "none")).prerequisites()
    assert lacking == "no node_modules folder next to eslint"
    monkeypatch.setattr(eslint_module, "version", lambda argv: "9.39.1")
    shown = EslintRules([rules], modules=str(tmp_path)).version() or ""
    assert shown.startswith("9.39.1 (rules: rules sha256:")
    assert EslintRules(modules=str(tmp_path)).version() == "9.39.1"


def test_the_packages_are_found_through_a_wrapper_or_a_symlink(tmp_path, monkeypatch):
    """install-tools.sh writes a wrapper that execs the npm bin; an npm install leaves a symlink to it."""
    lib = tmp_path / "npm/lib/node_modules/eslint/bin"
    lib.mkdir(parents=True)
    (lib / "eslint.js").write_text("#!/usr/bin/env node\n")
    (tmp_path / "npm/bin").mkdir()
    (tmp_path / "npm/bin/eslint").symlink_to("../lib/node_modules/eslint/bin/eslint.js")
    wrapper = tmp_path / "wrapper"
    wrapper.write_text(f'#!/bin/sh\nPATH="x:$PATH" exec "{tmp_path}/npm/bin/eslint" "$@"\n')
    want = (tmp_path / "npm/lib/node_modules").resolve()
    for exe in (wrapper, tmp_path / "npm/bin/eslint"):
        monkeypatch.setattr("shutil.which", lambda name, exe=exe: str(exe))
        assert eslint_module._modules_next_to_eslint() == want
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert eslint_module._modules_next_to_eslint() is None


@pytest.mark.skipif(not shutil.which("eslint"), reason="eslint not installed")
def test_eslint_real_tool_when_its_packages_are_there(tmp_path):
    """The real tool: the fixture's config imports typescript-eslint, which must sit beside eslint."""
    analyzer = EslintRules([str(TS / "rules.mjs")])
    if not analyzer.modules or not (analyzer.modules / "typescript-eslint").is_dir():
        pytest.skip("typescript-eslint is not installed next to eslint")
    (tmp_path / "scratch").mkdir()
    result = analyzer.measure(Target(str(TS), TS_FILES), TS_FILES, str(tmp_path / "scratch"))
    assert values(result.metrics, "lint.violations")["total"] == 2
    assert values(result.metrics, "lint.unparsed_files")["total"] == 1
