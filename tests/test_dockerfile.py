"""The Dockerfile parser (core.dockerfile), its runtime table, and the built-in dockerfile analyzer."""
import json

import pytest

from swe_metrics import __version__
from swe_metrics.analyzers.dockerfile import Dockerfile
from swe_metrics.core.dockerfile import is_dockerfile, runtime, stages
from swe_metrics.core.target import Target
from tests.helpers import FIXTURES

DOCKER = FIXTURES / "docker_small"


@pytest.mark.parametrize(("path", "expected"), [
    ("Dockerfile", True), ("app/Dockerfile.prod", True), ("web.Dockerfile", True), ("Containerfile", True),
    ("Dockerfile.md", True), ("docker-compose.yml", False), ("dockerfile.txt", False),
    ("MyDockerfile", False),
])
def test_is_dockerfile(path, expected):
    """Dockerfile, Dockerfile.*, *.Dockerfile and Containerfile, by file name only."""
    assert is_dockerfile(path) is expected


@pytest.mark.parametrize(("image", "expected"), [
    ("eclipse-temurin:21-jre", ("java", "21", 21)),
    ("tomcat:11.0-jdk21-temurin", ("java", "21", 21)),
    ("amazoncorretto:17", ("java", "17", 17)),
    ("maven:3.9-eclipse-temurin-21", ("java", "21", 21)),
    ("maven:3.9.9-amazoncorretto-17-debian", ("java", "17", 17)),
    ("gradle:8.10-jdk17", ("java", "17", 17)),
    ("openjdk:11.0.2-jre-slim", ("java", "11.0.2", 11)),
    ("ibm-semeru-runtimes:open-17-jre", ("java", "17", 17)),
    ("docker.io/library/eclipse-temurin:25@sha256:abc", ("java", "25", 25)),
    ("node:24-alpine", ("node", "24", 24)),
    ("python:3.12-slim", ("python", "3.12", 3)),
    ("mcr.microsoft.com/dotnet/aspnet:8.0", ("dotnet", "8.0", 8)),
    ("localhost:5000/golang:1.23-alpine", ("go", "1.23", 1)),
    ("node", None), ("node:lts-alpine", None), ("alpine:3.20", None), ("nginx:1.27", None),
    ("eclipse-temurin:${JAVA}-jre", None),
])
def test_runtime_table(image, expected):
    """The runtime and the stated version from an image's name and tag; the major is its first number."""
    found = runtime(image)
    assert (found and (found.runtime, found.version, found.major)) == expected


def test_stages_substitute_args_and_name_stages():
    """ARG defaults before the first FROM are substituted; stages are named by AS or their index."""
    text = ("# escape=\\\nARG BASE=python\nARG TAG\nFROM --platform=linux/amd64 ${BASE}:3.12 as build\n"
            "ARG LATE=x\nRUN echo \\\n\n  # comment\n  done\nFROM $BASE:${TAG}\nFROM\n")
    found = [(s.image, s.name, s.line, s.final) for s in stages(text)]
    assert found == [("python:3.12", "build", 4, False), ("python:${TAG}", "1", 10, True)]


def test_stages_with_backtick_escape():
    """The escape parser directive switches the line continuation character (Windows Dockerfiles)."""
    text = "# escape=`\nFROM mcr.microsoft.com/windows/servercore:ltsc2022 `\n  AS base\n"
    assert [(s.image, s.name, s.line) for s in stages(text)] == [
        ("mcr.microsoft.com/windows/servercore:ltsc2022", "base", 2)]


def test_analyzer_on_fixture():
    """Base images and runtime versions of the fixture match the hand-checked expected values."""
    expected = json.loads((DOCKER / "expected.json").read_text())
    target = Target(str(DOCKER), ("Dockerfile", "README.md", "web.Dockerfile"))
    analyzer = Dockerfile()
    assert analyzer.version() == __version__ and analyzer.prerequisites() == ""
    files = analyzer.applicable(target)
    assert files == ("Dockerfile", "web.Dockerfile")
    metrics = analyzer.measure(target, files, "unused").metrics
    images = [{"path": m.scope.path, "line": m.scope.line, **dict(m.labels)}
              for m in metrics if m.id == "container.base_images"]
    assert images == expected["base_images"]
    runtimes = [{"path": m.scope.path, "line": m.scope.line, "runtime": dict(m.labels)["runtime"],
                 "version": dict(m.labels)["version"], "value": m.value}
                for m in metrics if m.id == "container.runtime_major"]
    assert runtimes == expected["runtime_major"]


def test_stage_reference_states_no_runtime(tmp_path):
    """FROM an earlier stage is a base image entry, but never a runtime of its own."""
    (tmp_path / "Dockerfile").write_text("FROM node:22 AS node\nFROM node\n")
    target = Target(str(tmp_path), ("Dockerfile",))
    metrics = Dockerfile().measure(target, target.files, str(tmp_path)).metrics
    assert [m.id for m in metrics] == ["container.base_images", "container.runtime_major",
                                       "container.base_images"]
