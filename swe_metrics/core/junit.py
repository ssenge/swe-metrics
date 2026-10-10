"""JUnit XML test results: test outcomes and duration per test suite and in total."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from swe_metrics.core.buildreports import parse_xml, tagged
from swe_metrics.core.report import Metric, Scope

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element  # type only: parsing goes through defusedxml

FORMAT = "junit"
OUTCOMES = ("failure", "error", "skipped")  # a test case without one of these child elements passed


@dataclass(frozen=True)
class Suite:
    """The outcomes of one test suite's test cases and the time it took."""

    name: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0

    def __add__(self, other: Suite) -> Suite:
        """Two results of the same suite (e.g. from two files) added up."""
        return replace(self, passed=self.passed + other.passed, failed=self.failed + other.failed,
                       errors=self.errors + other.errors, skipped=self.skipped + other.skipped,
                       duration=self.duration + other.duration)


def parse_junit(data: bytes) -> list[Suite]:
    """The suites of a JUnit XML document (root <testsuites> or <testsuite>) that hold test cases."""
    root = parse_xml(data)
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError(f"not a JUnit XML report: root element <{root.tag}>")
    return [_suite(element) for element in root.iter("testsuite") if element.find("testcase") is not None]


def _suite(element: Element) -> Suite:
    """Outcome counts of a suite's own test cases, and its time (the cases' times if it has none)."""
    counts = dict.fromkeys(OUTCOMES, 0)
    passed, case_time = 0, 0.0
    for case in element.findall("testcase"):
        outcome = next((tag for tag in OUTCOMES if case.find(tag) is not None), "")
        if outcome:
            counts[outcome] += 1
        else:
            passed += 1
        case_time += float(case.get("time") or 0)
    # A suite's own time includes its set-up, but a nesting suite's time also includes its children.
    own_time = element.get("time")
    nested = element.find("testsuite") is not None
    duration = float(own_time) if own_time and not nested else case_time
    return Suite(element.get("name", ""), passed, counts["failure"], counts["error"], counts["skipped"],
                 round(duration, 3))


def junit_metrics(documents: Iterable[bytes]) -> list[Metric]:
    """Outcomes and duration per suite (scope module, path = suite name) and in total."""
    suites: dict[str, Suite] = {}
    for data in documents:
        for suite in parse_junit(data):
            suites[suite.name] = suites[suite.name] + suite if suite.name in suites else suite
    total = sum(suites.values(), Suite(""))
    metrics = [m for name in sorted(suites) for m in _suite_metrics(suites[name], Scope("module", name))]
    return metrics + _suite_metrics(total, Scope("target"))


def _suite_metrics(suite: Suite, scope: Scope) -> list[Metric]:
    """The five test metrics of one suite (or of the total) at the given scope."""
    values = {"passed": suite.passed, "failed": suite.failed, "errors": suite.errors,
              "skipped": suite.skipped, "duration": round(suite.duration, 3)}
    return [tagged(f"tests.{name}", FORMAT, scope, float(value)) for name, value in values.items()]
