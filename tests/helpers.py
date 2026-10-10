"""Shared test helpers: fixture paths and a configurable fake analyzer."""
import shutil
from pathlib import Path

from swe_metrics.core.report import Metric, Scope

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def copy_fixture(name, tmp_path):
    """A copy of a fixture outside this repository, so its kind is `directory`, not `repository`."""
    target = tmp_path / name
    shutil.copytree(FIXTURES / name, target)
    return target


class FakeAnalyzer:
    """An analyzer whose version, applicable files and result are set by the test."""

    def __init__(self, version="1.0", families=("size",), applicable=True, fault=None):
        """fault: an exception that measure raises."""
        self.id, self.tool, self.families = "fake", "fake-tool", families
        self._version, self._applicable, self._fault = version, applicable, fault

    def version(self):
        """The configured version (None: not installed)."""
        return self._version

    def applicable(self, target):
        """All files, or none."""
        return target.files if self._applicable else ()

    def measure(self, target, files):
        """One size and one complexity metric, or the configured fault."""
        if self._fault:
            raise self._fault
        scope = Scope("target")
        return [Metric("size.files", self.tool, scope, float(len(files))),
                Metric("complexity.cyclomatic", self.tool, scope, 1.0)]
