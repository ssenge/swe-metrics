"""scripts/install-tools.sh with a fake curl: one tool's broken download doesn't stop the others."""
import os
import subprocess

from tests.helpers import FIXTURES

SCRIPT = FIXTURES.parent / "scripts" / "install-tools.sh"
FAKE_CURL = """#!/bin/sh
# Fails like curl -f on a URL containing 'broken'; otherwise writes a tool that prints its version.
out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in -o) out=$2; shift 2 ;; -*) shift ;; *) url=$1; shift ;; esac
done
case "$url" in *broken*) exit 22 ;; esac
[ -n "$out" ] && [ "$out" != /dev/null ] && printf '#!/bin/sh\\necho "tool 1.2.3"\\n' > "$out"
exit 0
"""


def run_script(tmp_path, *args):
    """The installer on a two-tool list (the second one's URL is broken), with the fake curl first on PATH."""
    fake = tmp_path / "fake"
    fake.mkdir(exist_ok=True)
    (fake / "curl").write_text(FAKE_CURL)
    (fake / "curl").chmod(0o755)
    listing = tmp_path / "tools.list"
    listing.write_text("good\t-\tany\tbin:good\thttps://example.com/good\n"
                       "bad\t-\tany\tbin:bad\thttps://example.com/broken\n")
    argv = [str(SCRIPT), "--prefix", str(tmp_path / "prefix"), "--bin-dir", str(tmp_path / "bin"),
            "--list", str(listing), *args]
    env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"}
    return subprocess.run(argv, capture_output=True, text=True, env=env, check=False)


def test_a_broken_download_fails_only_its_tool(tmp_path):
    """The other tool installs, the check runs, and the script exits 1 naming the failed tool."""
    done = run_script(tmp_path)
    assert done.returncode == 1
    assert "ok        good 1.2.3" in done.stdout and "MISSING   bad" in done.stdout
    assert "failed to install: bad" in done.stderr
    assert run_script(tmp_path, "--only", "good").returncode == 0


def test_check_urls_names_the_broken_ones(tmp_path):
    """--check-urls resolves every URL and exits 1 naming those that don't resolve."""
    done = run_script(tmp_path, "--check-urls")
    assert done.returncode == 1 and "ok        good any" in done.stdout
    assert "broken download URLs: bad/any" in done.stderr
    assert run_script(tmp_path, "--check-urls", "--only", "good").returncode == 0
