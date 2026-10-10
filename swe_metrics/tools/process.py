"""Running external tools: fixed argument lists, no shell, a timeout against hung tools."""
from __future__ import annotations

import json
import re
import subprocess  # nosec B404
from collections.abc import Sequence
from pathlib import Path
from typing import Any

TIMEOUT = 1800  # seconds: robustness against a hung tool, reported as a failed analyzer


class ToolError(RuntimeError):
    """A tool exited with an error; the message ends with the tail of its output."""


def run(argv: Sequence[str], cwd: str, ok: Sequence[int] = (0,)) -> str:
    """Run a tool in cwd and return its stdout; ToolError for an exit code not in `ok`."""
    done = subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True,
                          timeout=TIMEOUT, check=False)
    if done.returncode not in ok:
        tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
        raise ToolError(f"{argv[0]} exited with {done.returncode}: {' | '.join(tail)}")
    return done.stdout


def version(argv: Sequence[str], pattern: str = r"(\d+\.\d+\.\d+)") -> str | None:
    """The first version number a tool prints for argv, or None if it isn't installed or fails."""
    try:
        output = run(argv, ".")
    except (FileNotFoundError, ToolError, subprocess.TimeoutExpired):
        return None
    found = re.search(pattern, output)
    return found.group(1) if found else None


def read_json(path: str | Path) -> Any:
    """A JSON file a tool wrote."""
    return json.loads(Path(path).read_text())
