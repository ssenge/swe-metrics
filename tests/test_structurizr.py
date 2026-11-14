"""The Structurizr analyzer on a recorded export, and on the real tool when installed."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import structurizr as module
from swe_metrics.analyzers.structurizr import Structurizr
from swe_metrics.core.target import Target
from swe_metrics.tools.process import ToolError
from tests.helpers import FIXTURES, values

DSL = FIXTURES / "structurizr"
FILES = ("good.dsl", "broken.dsl", "part.dsl", "notes.md")
WANT_ELEMENTS = {"architecture_model.errors": {"broken.dsl": 1, "total": 1},
                 "architecture_model.models": {"total": 2}, "architecture_model.elements": {"total": 4},
                 "architecture_model.relationships": {"total": 2}}


def check(result):
    """The counts the good workspace and the broken one give: the same with the real tool and a recording."""
    for metric_id, want in WANT_ELEMENTS.items():
        assert values(result.metrics, metric_id) == want
    check_views(result)


def check_views(result):
    """The views by type, their sizes, and the statistics of the relationships per view."""
    views = [m for m in result.metrics if m.id == "architecture_model.views"]
    assert {tuple(m.labels): m.value for m in views} == {(): 2.0, (("type", "container"),): 1.0,
                                                          (("type", "systemContext"),): 1.0}
    sizes = {m.scope.symbol: m.value for m in result.metrics
             if m.id == "architecture_model.view_elements" and m.scope.level == "file"}
    assert sizes == {"SystemContext-001": 2.0, "Container-001": 3.0}
    stats = [m.stats for m in result.metrics if m.id == "architecture_model.view_relationships" and m.stats]
    assert stats[0].max == 2.0


def recorded(argv, cwd, ok=(0,)):
    """A fake structurizr-cli: validate fails for broken.dsl; export writes the recording of good.dsl."""
    assert Path(argv[3]).exists() and Path(argv[3]).name != "part.dsl", "an included part is no workspace"
    if argv[1] == "validate":
        if Path(argv[3]).name == "broken.dsl":
            raise ToolError("structurizr-cli exited with 1: The source element \"a\" does not exist")
        return ""
    assert argv[1:3] == ["export", "-workspace"] and argv[4:6] == ["-format", "json"]
    Path(argv[7], "good.json").write_text((FIXTURES / "recorded" / "structurizr-good.json").read_text())
    return ""


def test_recorded_export_gives_the_models_counts(tmp_path, monkeypatch):
    """Only the workspaces are measured; an invalid one is an error of its file and has no model."""
    monkeypatch.setattr(module, "run", recorded)
    analyzer = Structurizr()
    target = Target(str(DSL), FILES)
    assert analyzer.applicable(target) == ("good.dsl", "broken.dsl", "part.dsl")
    assert analyzer.prerequisites() == ""
    result = analyzer.measure(target, analyzer.applicable(target), str(tmp_path))
    check(result)
    assert [kind for kind, _ in result.details] == ["structurizr-json"]


def test_no_valid_workspace_gives_only_errors(tmp_path, monkeypatch):
    """Nothing valid to export: errors and zero totals, no view statistics."""
    monkeypatch.setattr(module, "run", recorded)
    result = Structurizr().measure(Target(str(DSL), ("broken.dsl",)), ("broken.dsl",), str(tmp_path))
    assert values(result.metrics, "architecture_model.elements") == {"total": 0}
    assert values(result.metrics, "architecture_model.errors") == {"broken.dsl": 1, "total": 1}
    assert not [m for m in result.metrics if m.stats]


def test_a_failed_export_fails_the_analyzer(tmp_path, monkeypatch):
    """A valid workspace whose export fails is a tool fault, not an invalid model."""
    def fake(argv, cwd, ok=(0,)):
        if argv[1] == "export":
            raise ToolError("structurizr-cli exited with 1: export failed")
        return ""
    monkeypatch.setattr(module, "run", fake)
    with pytest.raises(ToolError, match="export failed"):
        Structurizr().measure(Target(str(DSL), ("good.dsl",)), ("good.dsl",), str(tmp_path))


def test_the_version_is_the_tools(monkeypatch):
    """The installed structurizr-cli's version, or None."""
    monkeypatch.setattr(module, "version", lambda argv: "2025.11.09")
    assert Structurizr().version() == "2025.11.09"


@pytest.mark.skipif(not shutil.which("structurizr-cli"), reason="structurizr-cli not installed")
def test_the_real_tool_gives_the_same_counts(tmp_path):
    """The real tool on the fixture: the DSL parts it includes are copied along."""
    analyzer = Structurizr()
    assert analyzer.version()
    target = Target(str(DSL), FILES)
    result = analyzer.measure(target, analyzer.applicable(target), str(tmp_path))
    check(result)
    assert json.loads(Path(result.details[0][1]).read_text())["views"]
