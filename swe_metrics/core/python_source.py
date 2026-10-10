"""Static facts of Python source, parsed with ast and never executed: module names and imports."""
from __future__ import annotations

import ast
from collections.abc import Container
from pathlib import PurePosixPath


def module_name(path: str) -> tuple[str, bool]:
    """The dotted module of a file path and whether it is a package; parts up to a `src` dir are dropped."""
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if "src" in parts[:-1]:
        parts = parts[parts.index("src") + 1:]
    package = parts[-1] == "__init__"
    return ".".join(parts[:-1] if package else parts), package


def imported_names(source: bytes, module: str, package: bool, filename: str = "<source>") -> set[str]:
    """Every absolute dotted name the source imports anywhere; `from X import a` yields `X.a`."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source, filename)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _base(node, module, package)
            names.update(base if alias.name == "*" else f"{base}.{alias.name}".lstrip(".")
                         for alias in node.names)
    return names


def _base(node: ast.ImportFrom, module: str, package: bool) -> str:
    """The absolute module a `from … import` refers to, resolving leading dots against the importer."""
    if not node.level:
        return node.module or ""
    parts = module.split(".") if package else module.split(".")[:-1]
    parts = parts[:len(parts) - node.level + 1]
    return ".".join([*parts, *([node.module] if node.module else [])])


def resolve(name: str, modules: Container[str]) -> str | None:
    """The longest leading part of a dotted name that is one of the modules; None if there is none."""
    parts = name.split(".")
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in modules:
            return candidate
    return None


def doc_flags(source: bytes, module: str, filename: str = "<source>") -> list[bool]:
    """Whether each public API (the module, its classes, functions and methods) has a docstring.

    Public means no leading underscore in the name, nor in any enclosing module or class.
    """
    tree = ast.parse(source, filename)
    public = not any(part.startswith("_") for part in module.split("."))
    return [bool(ast.get_docstring(tree)), *_definition_flags(tree.body)] if public else []


def _definition_flags(body: list[ast.stmt]) -> list[bool]:
    """Docstring flags of the public classes and functions in a module or class body, and their members."""
    flags = []
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and node.name[:1] != "_":
            flags.append(bool(ast.get_docstring(node)))
            if isinstance(node, ast.ClassDef):
                flags += _definition_flags(node.body)
    return flags
