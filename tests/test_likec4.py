"""The LikeC4 analyzer on recorded outputs, and on the fixture model when likec4 is installed."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import likec4 as module
from swe_metrics.analyzers.likec4 import Likec4
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES

MODEL = FIXTURES / "likec4_small"
RECORDED = FIXTURES / "recorded"
EXPECTED = json.loads((MODEL / "expected.json").read_text())


def fake_likec4(monkeypatch, exported, validation="likec4-validate.json"):
    """Make `validate` print a recorded result (paths in its cwd) and `export` write `exported`."""
    calls = []

    def fake_run(argv, cwd, ok=(0,)):
        calls.append((argv, cwd))
        if argv[1] == "validate":
            return (RECORDED / validation).read_text().replace("{workspace}", cwd)
        Path(argv[argv.index("-o") + 1]).write_text(json.dumps(exported))
        return ""
    monkeypatch.setattr(module, "run", fake_run)
    return calls


def values(metrics, level):
    """{(metric id, path, symbol): value} of the plain values at one scope level."""
    return {(m.id, m.scope.path, m.scope.symbol): m.value for m in metrics
            if m.scope.level == level and m.value is not None}


def check_model(metrics, prefix=""):
    """Totals and per-view values of the fixture model match the hand-counted expected values."""
    at_target = values(metrics, "target")
    for name in ("elements", "relationships", "views"):
        assert at_target[(f"architecture_model.{name}", "", "")] == EXPECTED[name]
    per_view = {(metric.split(".")[1].removeprefix("view_"), path, view): n
                for (metric, path, view), n in values(metrics, "file").items() if view}
    assert per_view == {(name, f"{prefix}model.c4", view): n
                        for view, counts in EXPECTED["per_view"].items() for name, n in counts.items()}
    stats = {m.id: m.stats for m in metrics if m.stats}
    elements = stats["architecture_model.view_elements"]
    assert (elements.count, elements.sum, elements.p50, elements.max) == (2, 9, 3, 6)


def test_recorded_outputs(tmp_path, monkeypatch):
    """Errors per file from `validate`; totals, per-view sizes and statistics from the export of a copy."""
    calls = fake_likec4(monkeypatch, json.loads((RECORDED / "likec4.json").read_text()))
    target = Target(str(MODEL), ("expected.json", "model.c4"))
    analyzer = Likec4()
    assert analyzer.applicable(target) == ("model.c4",) and analyzer.prerequisites() == ""
    scratch = tmp_path / "scratch"
    result = analyzer.measure(target, ("model.c4",), str(scratch))
    assert {cwd for _, cwd in calls} == {str(scratch / "workspace")}
    assert (scratch / "workspace" / "model.c4").read_text() == (MODEL / "model.c4").read_text()
    check_model(result.metrics)
    errors = {m.scope.path: m.value for m in result.metrics if m.id == "architecture_model.errors"}
    assert errors == {"broken.c4": 5, "": 5}
    assert [fmt for fmt, _ in result.details] == ["likec4-json", "likec4-validate-json"]


def test_projects_map_views_to_their_directory(tmp_path, monkeypatch):
    """With project configs, view paths are relative to the target and totals add up over projects."""
    model = json.loads((RECORDED / "likec4.json").read_text())
    for project in ("alpha", "beta"):
        (tmp_path / project).mkdir()
        shutil.copyfile(MODEL / "model.c4", tmp_path / project / "model.c4")
        (tmp_path / project / "likec4.config.json").write_text(json.dumps({"name": project}))
    (tmp_path / ".likec4rc").write_text("not json")
    fake_likec4(monkeypatch, [{**model, "projectId": "alpha"}, {**model, "projectId": "beta"}])
    files = ("alpha/model.c4", "beta/model.c4")
    configs = (".likec4rc", "alpha/likec4.config.json", "beta/likec4.config.json")
    target = Target(str(tmp_path), (*configs, *files))
    result = Likec4().measure(target, files, str(tmp_path / "scratch"))
    at_target = values(result.metrics, "target")
    assert at_target[("architecture_model.views", "", "")] == 4
    assert at_target[("architecture_model.errors", "", "")] == 5
    assert {path for (_, path, view) in values(result.metrics, "file") if view} == set(files)


def test_version_records_the_settings(monkeypatch):
    """The version says that layout is not validated; None when likec4 is missing."""
    monkeypatch.setattr(module, "version", lambda argv: "1.59.4")
    assert Likec4().version() == "1.59.4 (no layout)"
    monkeypatch.setattr(module, "version", lambda argv: None)
    assert Likec4().version() is None


@pytest.mark.skipif(not shutil.which("likec4"), reason="likec4 not installed")
def test_real_likec4_on_fixture(tmp_path):
    """The real tool counts the fixture model as hand-counted, with no errors, and leaves it untouched."""
    before = sorted(p.name for p in MODEL.iterdir())
    analyzer = Likec4()
    assert analyzer.version()
    result = analyzer.measure(Target(str(MODEL), ("model.c4",)), ("model.c4",), str(tmp_path))
    check_model(result.metrics)
    assert [m.value for m in result.metrics if m.id == "architecture_model.errors"] == [EXPECTED["errors"]]
    assert sorted(p.name for p in MODEL.iterdir()) == before
