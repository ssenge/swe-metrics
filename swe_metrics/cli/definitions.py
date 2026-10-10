"""Loading a scoring definition: the shipped default (by name or omitted), a file, or `package.module:NAME`.

A definition is the caller's own code and runs in this process, like a test file; load only code you trust.
"""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

DEFAULT = "swe-default"


def load_definition(spec: str | None) -> Any:
    """The definition object; ValueError if it can't be loaded or doesn't look like a definition."""
    if not spec or spec == DEFAULT:
        module, attr = importlib.import_module("swe_metrics.scoring.default"), "DEFINITION"
    elif spec.endswith(".py"):
        module, attr = _from_file(Path(spec)), "DEFINITION"
    else:
        name, _, attr = spec.partition(":")
        module, attr = _import(name), attr or "DEFINITION"
    definition = getattr(module, attr, None)
    if not all(hasattr(definition, field) for field in ("name", "version")) or not callable(
            getattr(definition, "score", None)):
        raise ValueError(f"{spec}: {attr} must have name, version and score(report, baseline)")
    return definition


def _from_file(path: Path) -> ModuleType:
    """A module loaded from a Python file."""
    spec = importlib.util.spec_from_file_location(f"swe_metrics_definition_{path.stem}", path)
    if not path.is_file() or spec is None or spec.loader is None:
        raise ValueError(f"definition file not found: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _import(name: str) -> ModuleType:
    """An importable module, or ValueError."""
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ValueError(f"definition module not importable: {name} ({exc})") from exc
