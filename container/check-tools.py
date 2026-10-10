"""Image build check: every analyzer finds its tool, at the version tools.lock pins.

Usage: check-tools.py <tools.lock>   (exit 1 on any mismatch; runs as the image build's last step)
"""
from __future__ import annotations

import json
import subprocess  # nosec B404
import sys
from pathlib import Path


def pinned(lock: Path) -> dict[str, str]:
    """Tool name -> pinned version, from the lock file."""
    rows = [line.split("\t") for line in lock.read_text().splitlines() if line and not line.startswith("#")]
    return {row[0]: row[1] for row in rows}


def main(lock: str) -> int:
    """Compare `swe-metrics tools --json` with the lock; built-in analyzers have no pinned tool."""
    versions = pinned(Path(lock))
    done = subprocess.run(["swe-metrics", "tools", "--json"], capture_output=True, text=True, check=True)  # nosec
    problems = []
    for analyzer in json.loads(done.stdout):
        tool, found = analyzer["tool"], analyzer["version"]
        if found is None:
            problems.append(f"{analyzer['id']}: {tool} not installed")
        elif tool in versions and not found.startswith(versions[tool]):
            problems.append(f"{analyzer['id']}: {tool} {found}, lock pins {versions[tool]}")
    print("\n".join(problems) or f"all analyzers find their tools ({len(versions)} pinned)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
