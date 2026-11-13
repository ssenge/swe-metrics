"""Every metric an analyzer emits is in the catalog: a report can't be written without it."""
import re
from pathlib import Path

from swe_metrics.core.catalog import CATALOG, families

SOURCE = Path(__file__).resolve().parents[1] / "swe_metrics"
FILE_SUFFIXES = {"sarif", "json", "txt", "xml"}   # detail file names read like metric ids
METRIC_ID = re.compile(r"""["']([a-z_]+\.[a-z_]+)["']""")


def test_every_metric_id_the_code_names_is_in_the_catalog():
    """A metric id written as a string in an analyzer or a core module (`family.name`, a known family) must be
    in CATALOG: `Metric.as_dict` looks it up, so a missing one fails only when a real report is written."""
    named: dict[str, str] = {}
    for folder in ("analyzers", "core"):
        for path in sorted((SOURCE / folder).glob("*.py")):
            for found in METRIC_ID.findall(path.read_text()):
                family, name = found.split(".")
                if family in families() and name not in FILE_SUFFIXES and path.name != "catalog.py":
                    named.setdefault(found, path.name)
    missing = {metric: where for metric, where in named.items() if metric not in CATALOG}
    assert not missing, f"not in the catalog: {missing}"
