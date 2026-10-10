"""terraform validate: the errors of Terraform's own validation, per module directory."""
from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePath
from typing import Any

from swe_metrics.core.analyzer import Measurement
from swe_metrics.core.report import Metric, Scope
from swe_metrics.core.target import Target, language
from swe_metrics.tools.process import ToolError, run, version

TOOL = "terraform"


class Terraform:
    """Implements core.analyzer.Analyzer with `terraform validate -json` on a copy of each module."""

    id = "terraform"
    tool = TOOL
    families: tuple[str, ...] = ("iac",)

    def version(self) -> str | None:
        """The installed Terraform version."""
        return version(["terraform", "version"])

    def prerequisites(self) -> str:
        """terraform needs nothing beyond itself (init fetches providers, which needs the network)."""
        return ""

    def applicable(self, target: Target) -> tuple[str, ...]:
        """The Terraform files of the target."""
        return tuple(p for p in target.files if language(p) == "terraform")

    def measure(self, target: Target, files: tuple[str, ...], scratch: str) -> Measurement:
        """Copy every module directory, then init and validate each copy; a failed init raises."""
        copy, modules = Path(scratch) / "modules", module_dirs(files)
        for module in modules:
            # the whole directory: a module needs all its files, also those --changed-since left out
            (copy / module).mkdir(parents=True, exist_ok=True)
            for source in Path(target.root, module).iterdir():
                if source.is_file():
                    shutil.copyfile(source, copy / module / source.name)
        results = {module: _validate(str(copy / module), module) for module in modules}
        report = Path(scratch) / "terraform-validate.json"
        report.write_text(json.dumps(results, indent=2))
        return Measurement(_metrics(results), (("terraform-validate-json", str(report)),))


def module_dirs(files: tuple[str, ...]) -> list[str]:
    """The directories that hold Terraform files, sorted; "." is the target's root."""
    return sorted({str(PurePath(path).parent) for path in files})


def _validate(directory: str, module: str) -> Any:
    """`terraform validate -json` of one module copy after a local init without a backend."""
    try:
        run(["terraform", "init", "-backend=false", "-input=false", "-no-color"], cwd=directory)
    except ToolError as exc:
        raise ToolError(f"terraform init failed in module {module}: {exc}") from exc
    return json.loads(run(["terraform", "validate", "-json", "-no-color"], cwd=directory, ok=(0, 1)))


def _metrics(results: dict[str, Any]) -> list[Metric]:
    """Validation errors per module and in total."""
    counts = {module: int(result.get("error_count", 0)) for module, result in results.items()}
    metrics = [Metric("iac.validation_errors", TOOL, Scope("module", module), float(n))
               for module, n in counts.items()]
    return [*metrics, Metric("iac.validation_errors", TOOL, Scope("target"), float(sum(counts.values())))]
