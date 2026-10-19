"""Mutation reports: PIT mutations.xml and Stryker's JSON report, per target file and in total."""
import json

import pytest

from swe_metrics.analyzers.buildreports import Pit, Stryker
from swe_metrics.core.mutation import mutation_metrics
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES

REPORTS = FIXTURES / "reports"
CALC, STRINGS = "src/main/java/com/example/Calc.java", "src/main/java/com/example/util/Strings.java"


def measured(analyzer, files, tmp_path):
    """{(metric id, scope path): value} of the analyzer's metrics on a target with these files."""
    target = Target(str(tmp_path), files)
    metrics = analyzer.measure(target, files, str(tmp_path)).metrics
    assert {m.tool for m in metrics} == {analyzer.id}
    assert all(m.labels == () for m in metrics)
    return {(m.id, m.scope.path): m.value for m in metrics}


def test_pit_per_file_and_total(tmp_path):
    """Timeouts and memory errors count as killed, non-viable mutants not at all; Main.java only in total."""
    values = measured(Pit([str(REPORTS / "mutations.xml")]), (CALC, STRINGS), tmp_path)
    assert values == {
        ("mutation.killed", CALC): 3, ("mutation.survived", CALC): 2, ("mutation.no_coverage", CALC): 1,
        ("mutation.score", CALC): 50.0,
        ("mutation.killed", STRINGS): 2, ("mutation.survived", STRINGS): 0,
        ("mutation.no_coverage", STRINGS): 0, ("mutation.score", STRINGS): 100.0,
        ("mutation.killed", ""): 5, ("mutation.survived", ""): 2, ("mutation.no_coverage", ""): 2,
        ("mutation.score", ""): 55.56}


def test_stryker_per_file_and_total(tmp_path):
    """Timeouts count as killed; compile and runtime errors, ignored and pending mutants are left out."""
    values = measured(Stryker([str(REPORTS / "mutation.json")]), ("src/calc.js", "src/util.js"), tmp_path)
    assert values == {
        ("mutation.killed", "src/calc.js"): 3, ("mutation.survived", "src/calc.js"): 1,
        ("mutation.no_coverage", "src/calc.js"): 1, ("mutation.score", "src/calc.js"): 60.0,
        ("mutation.killed", "src/util.js"): 1, ("mutation.survived", "src/util.js"): 1,
        ("mutation.no_coverage", "src/util.js"): 0, ("mutation.score", "src/util.js"): 50.0,
        ("mutation.killed", ""): 4, ("mutation.survived", ""): 3, ("mutation.no_coverage", ""): 1,
        ("mutation.score", ""): 50.0}


def test_no_mutants_means_no_score():
    """Without counted mutants the counts are 0 and there is no score; a report without projectRoot works."""
    doc = {"files": {"a.js": {"mutants": [{"status": "Ignored"}]}}}
    metrics = mutation_metrics("stryker", [json.dumps(doc).encode()], ("a.js",))
    assert {(m.id, m.value) for m in metrics} == {("mutation.killed", 0), ("mutation.survived", 0),
                                                  ("mutation.no_coverage", 0)}


@pytest.mark.parametrize(("fmt", "data", "error"), [
    ("pit", b"<mutations><mutation>", SyntaxError),
    ("pit", b"<report/>", ValueError),
    ("stryker", b"{not json", ValueError),
    ("stryker", b'{"schemaVersion": "1"}', ValueError),
    ("stryker", b"[]", ValueError),
])
def test_malformed_mutation_reports_raise(fmt, data, error):
    """Malformed or foreign reports raise; the runner reports the analyzer as failed."""
    with pytest.raises(error):
        mutation_metrics(fmt, [data], ("a.js",))
