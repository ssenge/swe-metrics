"""JUnit XML reports, the shared build-report analyzer behavior, and path mapping."""
import pytest
from defusedxml import EntitiesForbidden

from swe_metrics.analyzers.buildreports import BuildReport, Junit, report_analyzers
from swe_metrics.cli.main import Settings, analyzers, main
from swe_metrics.core.buildreports import PathIndex, percent
from swe_metrics.core.junit import junit_metrics
from swe_metrics.core.target import Target
from swe_metrics.runner.measure import measure
from tests.helpers import FIXTURES

JUNIT = FIXTURES / "reports" / "junit"
BOMB = b'<!DOCTYPE t [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><testsuite name="x">&b;</testsuite>'


def values(metrics, level="target"):
    """{(metric id, scope path): value} of the metrics at one scope level."""
    return {(m.id, m.scope.path): m.value for m in metrics if m.scope.level == level}


def test_junit_directory_per_suite_and_total(tmp_path):
    """Surefire (1 failed, 1 skipped) and pytest (1 error) files; other files in the directory are ignored."""
    target = Target(str(tmp_path), ("a.py",))
    result = Junit([str(JUNIT)]).measure(target, target.files, str(tmp_path))
    total = values(result.metrics)
    assert total == {("tests.passed", ""): 4, ("tests.failed", ""): 1, ("tests.errors", ""): 1,
                     ("tests.skipped", ""): 1, ("tests.duration", ""): 1.465}
    suites = values(result.metrics, "module")
    assert suites[("tests.failed", "com.example.CalcTest")] == 1
    assert suites[("tests.duration", "com.example.CalcTest")] == 0.215
    assert suites[("tests.errors", "pytest")] == 1 and suites[("tests.passed", "pytest")] == 2
    assert {m.tool for m in result.metrics} == {"junit"}
    assert all(m.labels == (("format", "junit"),) for m in result.metrics)


def test_junit_nested_suites_missing_times_and_repeated_suites():
    """Nesting suites use their cases' times; a suite seen twice is added up."""
    nested = (b'<testsuite name="outer" time="9"><testcase name="a" time="0.5"/>'
              b'<testsuite name="inner"><testcase name="b"/><testcase name="c" time="0.25">'
              b'<error/></testcase></testsuite></testsuite>')
    again = b'<testsuites><testsuite name="inner" time="1"><testcase name="d"/></testsuite></testsuites>'
    metrics = junit_metrics([nested, again])
    suites = values(metrics, "module")
    assert suites[("tests.duration", "outer")] == 0.5
    assert suites[("tests.duration", "inner")] == 1.25
    assert suites[("tests.passed", "inner")] == 2 and suites[("tests.errors", "inner")] == 1
    assert values(metrics)[("tests.passed", "")] == 3


@pytest.mark.parametrize(("data", "error"), [
    (b"<testsuite><testcase>", SyntaxError),            # malformed XML (ParseError)
    (b"<report/>", ValueError),                          # well-formed, but not JUnit
    (BOMB, EntitiesForbidden),                           # entity expansion is rejected
])
def test_junit_rejects_bad_documents(data, error):
    """Malformed, foreign and entity-expanding documents raise; the runner reports a failed run."""
    with pytest.raises(error):
        junit_metrics([data])


def test_build_report_prerequisites_and_version(tmp_path):
    """A report must be given and exist; the version is swe-metrics' own; every target file applies."""
    assert Junit().prerequisites() == "no junit report given (--report junit=PATH)"
    assert Junit([str(tmp_path / "none.xml")]).prerequisites() == f"report not found: {tmp_path / 'none.xml'}"
    analyzer = Junit([str(JUNIT)])
    assert analyzer.prerequisites() == "" and analyzer.tool == "junit"
    assert analyzer.version() and analyzer.applicable(Target(".", ("a", "b"))) == ("a", "b")
    with pytest.raises(NotImplementedError):
        BuildReport().metrics([], ())
    assert [a.id for a in report_analyzers({"junit": ("x",)})][0] == "junit"


def test_report_analyzers_registered_and_failures_reported(tmp_path):
    """The CLI passes --report paths to the analyzers; a broken report is a failed run, not a crash."""
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuite>")
    junit = next(a for a in analyzers(Settings(reports={"junit": (str(broken),)})) if a.id == "junit")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    report = measure(tmp_path / "src", [junit])
    assert report.analyzers[0].status == "failed" and "ParseError" in report.analyzers[0].reason
    out = tmp_path / "report.json"
    assert main(["measure", str(tmp_path / "src"), "--only", "tests", "--report", f"junit={JUNIT}",
                 "--out", str(out)]) == 0
    assert '"tests.passed"' in out.read_text()


def test_path_index_maps_report_paths_to_target_files():
    """Absolute paths pick the longest contained file; package paths need a unique match."""
    index = PathIndex(["a.py", "src/a.py", "m1/com/x/Foo.java", "m2/com/x/Foo.java", "src/com/y/Bar.java"])
    assert index.resolve("/ci/proj/src/a.py") == "src/a.py"
    assert index.resolve("file://C:\\proj\\a.py") == "a.py"
    assert index.resolve("./src/a.py") == "src/a.py"
    assert index.resolve("com/y/Bar.java") == "src/com/y/Bar.java"
    assert index.resolve("com/x/Foo.java") is None
    assert index.resolve("b.py") is None and index.resolve("b/a.py") == "a.py"
    assert percent(1, 3) == 33.33 and percent(1, 0) is None
