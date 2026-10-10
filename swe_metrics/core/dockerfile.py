"""Dockerfiles as data: which files are Dockerfiles, their build stages, runtime versions of base images."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

# (runtime, image name, version at the start of or inside the tag); the first matching row wins.
RUNTIME_RULES: tuple[tuple[str, str, str], ...] = (
    ("java", r"eclipse-temurin|openjdk|amazoncorretto|sapmachine|azul/zulu-openjdk.*|bellsoft/liberica-.*",
     r"^(\d+(?:\.\d+)*)"),
    ("java", r"ibm-semeru-runtimes", r"^open-(\d+)"),
    ("java", r".+", r"(?:jdk|jre|temurin-|corretto-|openjdk-?)(\d+)"),  # tomcat, maven, gradle, jetty, ...
    ("node", r"node", r"^(\d+(?:\.\d+)*)"),
    ("python", r"python", r"^(\d+(?:\.\d+)*)"),
    ("dotnet", r"dotnet/(?:sdk|aspnet|runtime|runtime-deps)", r"^(\d+(?:\.\d+)*)"),
    ("go", r"golang", r"^(\d+(?:\.\d+)*)"),
)
_ARG = re.compile(r"\$\{(\w+)\}|\$(\w+)")


@dataclass(frozen=True)
class Stage:
    """One FROM instruction: the base image (ARG defaults substituted), the stage name or index, its line."""

    image: str
    name: str
    line: int
    final: bool


@dataclass(frozen=True)
class Runtime:
    """A runtime version an image name or tag states, e.g. java 21 or python 3.12 (major 3)."""

    runtime: str
    version: str

    @property
    def major(self) -> int:
        """The first number of the stated version."""
        return int(self.version.split(".")[0])


def is_dockerfile(path: str) -> bool:
    """Whether a path names a Dockerfile: Dockerfile, Dockerfile.*, *.Dockerfile or Containerfile."""
    name = PurePath(path).name
    return name in ("Dockerfile", "Containerfile") or name.startswith("Dockerfile.") \
        or name.endswith(".Dockerfile")


def stages(text: str) -> list[Stage]:
    """The build stages of a Dockerfile in order; the last one is final."""
    args: dict[str, str] = {}
    found: list[tuple[str, str, int]] = []
    for line, instruction, rest in _instructions(text):
        if instruction == "ARG" and not found:  # only ARGs before the first FROM apply to FROM lines
            name, _, default = rest.partition("=")
            args[name.strip()] = default.strip().strip("\"'")
        elif instruction == "FROM" and (stage := _from(rest, args, len(found))):
            found.append((*stage, line))
    return [Stage(image, name, line, n == len(found) - 1) for n, (image, name, line) in enumerate(found)]


def _from(rest: str, args: dict[str, str], index: int) -> tuple[str, str] | None:
    """The image (ARG defaults substituted) and stage name of a FROM's arguments; None if it has none."""
    words = [w for w in rest.split() if not w.startswith("--")]
    if not words:
        return None
    image = _ARG.sub(lambda m: args.get(m.group(1) or m.group(2)) or m.group(0), words[0])
    named = len(words) > 2 and words[1].upper() == "AS"
    return image, words[2] if named else str(index)


def _instructions(text: str) -> list[tuple[int, str, str]]:
    """(first line, instruction in upper case, arguments) of every instruction, continuations joined."""
    escape = "`" if re.match(r"\s*#\s*escape\s*=\s*`", text) else "\\"
    result: list[tuple[int, str, str]] = []
    pending, start = "", 0
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):  # Docker skips these, even inside a continuation
            continue
        start = start or number
        if stripped.endswith(escape):
            pending += stripped[:-1] + " "
            continue
        instruction, _, rest = (pending + stripped).partition(" ")
        result.append((start, instruction.upper(), rest.strip()))
        pending, start = "", 0
    return result


def runtime(image: str) -> Runtime | None:
    """The runtime version an image states in its name or tag, by the first matching RUNTIME_RULES row."""
    name, tag = _name_and_tag(image)
    for runtime_name, name_pattern, version_pattern in RUNTIME_RULES:
        if re.fullmatch(name_pattern, name) and (found := re.search(version_pattern, tag)):
            return Runtime(runtime_name, found.group(1))
    return None


def _name_and_tag(image: str) -> tuple[str, str]:
    """The repository path without registry and `library/`, and the tag (empty if none)."""
    image = image.split("@", 1)[0]
    parts = image.split("/")
    if len(parts) > 1 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        parts = parts[1:]
    path = "/".join(parts).removeprefix("library/")
    name, _, tag = path.partition(":")
    return name, tag
