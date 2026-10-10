"""Coverage reports: JaCoCo XML, Cobertura XML and LCOV, per target file and in total."""
import pytest

from swe_metrics.analyzers.buildreports import Cobertura, Jacoco, Lcov
from swe_metrics.core.coverage import coverage_metrics
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES

REPORTS = FIXTURES / "reports"
JAVA = ("pom.xml", "src/main/java/com/example/Calc.java", "src/main/java/com/example/util/Strings.java")
CALC, STRINGS = JAVA[1], JAVA[2]


def measured(analyzer, files, tmp_path):
    """{(metric id, scope path): value} of the analyzer's metrics on a target with these files."""
    target = Target(str(tmp_path), files)
    metrics = analyzer.measure(target, files, str(tmp_path)).metrics
    assert {m.tool for m in metrics} == {analyzer.id}
    assert all(m.labels == (("format", analyzer.id),) for m in metrics)
    return {(m.id, m.scope.path): m.value for m in metrics}


def test_jacoco_per_file_and_total(tmp_path):
    """Package paths map to target files; generated Gen.java (not in the target) counts only in the total."""
    values = measured(Jacoco([str(REPORTS / "jacoco.xml")]), JAVA, tmp_path)
    assert values == {
        ("coverage.lines_total", CALC): 6, ("coverage.lines_covered", CALC): 4,
        ("coverage.line_percent", CALC): 66.67, ("coverage.branch_percent", CALC): 50.0,
        ("coverage.lines_total", STRINGS): 2, ("coverage.lines_covered", STRINGS): 2,
        ("coverage.line_percent", STRINGS): 100.0, ("coverage.branch_percent", STRINGS): 100.0,
        ("coverage.lines_total", ""): 10, ("coverage.lines_covered", ""): 7,
        ("coverage.line_percent", ""): 70.0, ("coverage.branch_percent", ""): 62.5}


def test_cobertura_from_coverage_py(tmp_path):
    """Paths relative to the <source> map to src/...; a file without branches has no branch percent."""
    init, calc = "src/app/__init__.py", "src/app/calc.py"
    values = measured(Cobertura([str(REPORTS / "cobertura.xml")]), (init, calc, "README.md"), tmp_path)
    assert values == {
        ("coverage.lines_total", init): 1, ("coverage.lines_covered", init): 1,
        ("coverage.line_percent", init): 100.0,
        ("coverage.lines_total", calc): 8, ("coverage.lines_covered", calc): 6,
        ("coverage.line_percent", calc): 75.0, ("coverage.branch_percent", calc): 50.0,
        ("coverage.lines_total", ""): 9, ("coverage.lines_covered", ""): 7,
        ("coverage.line_percent", ""): 77.78, ("coverage.branch_percent", ""): 50.0}


def test_lcov_per_file_and_total(tmp_path):
    """Absolute and relative SF paths map; untaken (0) and unevaluated (-) branches are not covered."""
    values = measured(Lcov([str(REPORTS / "lcov.info")]), ("src/calc.js", "src/util.js"), tmp_path)
    assert values == {
        ("coverage.lines_total", "src/calc.js"): 5, ("coverage.lines_covered", "src/calc.js"): 4,
        ("coverage.line_percent", "src/calc.js"): 80.0, ("coverage.branch_percent", "src/calc.js"): 50.0,
        ("coverage.lines_total", "src/util.js"): 3, ("coverage.lines_covered", "src/util.js"): 3,
        ("coverage.line_percent", "src/util.js"): 100.0, ("coverage.branch_percent", "src/util.js"): 75.0,
        ("coverage.lines_total", ""): 10, ("coverage.lines_covered", ""): 7,
        ("coverage.line_percent", ""): 70.0, ("coverage.branch_percent", ""): 66.67}


def test_reports_of_the_same_file_are_merged():
    """Classes of one file and repeated records join line by line; method lines don't count twice."""
    cobertura = (b'<coverage><packages><package><classes>'
                 b'<class filename="a.py"><methods><method><lines><line number="9" hits="0"/></lines>'
                 b'</method></methods><lines><line number="1" hits="0"/><line number="2" hits="1"/>'
                 b'</lines></class>'
                 b'<class filename="a.py"><lines><line number="1" hits="2"/><line number="3" hits="0"'
                 b' branch="true" condition-coverage="0% (0/2)"/></lines></class>'
                 b'</classes></package></packages></coverage>')
    values = {(m.id, m.scope.path): m.value for m in coverage_metrics("cobertura", [cobertura], ("a.py",))}
    assert values[("coverage.lines_total", "a.py")] == 3 and values[("coverage.lines_covered", "a.py")] == 2
    assert values[("coverage.branch_percent", "a.py")] == 0.0
    lcov = b"SF:a.js\nDA:1,0\nBRDA:1,0,0,-\nend_of_record\n"
    again = b"SF:a.js\nDA:1,5\nDA:2,0\nBRDA:1,0,0,1\nBRDA:1,0,1,0\nend_of_record\n"
    values = {(m.id, m.scope.path): m.value for m in coverage_metrics("lcov", [lcov, again], ("a.js",))}
    assert values[("coverage.lines_covered", "")] == 1 and values[("coverage.lines_total", "")] == 2
    assert values[("coverage.branch_percent", "a.js")] == 50.0


def test_no_lines_means_no_percent():
    """An empty report gives line counts of 0 and no percentages (nothing was measured)."""
    metrics = coverage_metrics("jacoco", [b"<report name='x'/>"], ("a.java",))
    assert {(m.id, m.value) for m in metrics} == {("coverage.lines_total", 0), ("coverage.lines_covered", 0)}


@pytest.mark.parametrize(("fmt", "data", "error"), [
    ("jacoco", b"<report><package>", SyntaxError),
    ("jacoco", b"<coverage/>", ValueError),
    ("cobertura", b"<report/>", ValueError),
    ("lcov", b'{"not": "lcov"}', ValueError),
    ("lcov", b"DA:1,1\n", ValueError),
    ("lcov", b"SF:a.js\nDA:x,1\n", ValueError),
])
def test_malformed_coverage_reports_raise(fmt, data, error):
    """Malformed or foreign reports raise; the runner reports the analyzer as failed."""
    with pytest.raises(error):
        coverage_metrics(fmt, [data], ("a.js",))


def test_missing_report_file_raises(tmp_path):
    """A report deleted after the prerequisites check raises when read."""
    target = Target(str(tmp_path), ("a.js",))
    with pytest.raises(FileNotFoundError):
        Lcov([str(tmp_path / "lcov.info")]).measure(target, target.files, str(tmp_path))
