"""Cognitive complexity of each function in a syntax tree, after SonarSource's specification.

G. Ann Campbell, "Cognitive Complexity: A new way of measuring understandability" (SonarSource):
- +1 for each break in the linear flow: if, else if, else, switch, loops, catch, ternary, goto, a
  break or continue to a label, and each recursive call;
- +1 for each sequence of like binary logical operators (`a && b && c` is 1, `a && b || c` is 2);
- an extra +1 per level of nesting for if, switch, loops, catch and ternary (not for else, else if,
  logical operators, jumps or recursion). Nested functions and lambdas raise the nesting of their body.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from swe_metrics.analyzers.cognitive.grammars import Grammar

Node = Any  # tree_sitter.Node (untyped library)
SELF = frozenset({"self", "this", "cls", "super"})  # receivers through which a method calls itself


@dataclass(frozen=True)
class Scored:
    """One function's cognitive complexity."""

    name: str
    line: int
    complexity: int


def score_functions(root: Node, grammar: Grammar) -> list[Scored]:
    """Every function and method outside another function, with its score (nested ones count in it)."""
    found: list[Scored] = []
    stack = [root]
    while stack:
        node = stack.pop()
        # a lambda outside any function (e.g. `const f = () => ...`) is a function of its own
        if node.type in grammar.functions or node.type in grammar.nested:
            walker = _Walker(grammar, _name(node))
            walker.children(node, 0)
            found.append(Scored(walker.name, node.start_point[0] + 1, walker.total))
        else:
            stack.extend(reversed(node.children))
    return sorted(found, key=lambda s: s.line)


class _Walker:
    """Walks one function's body and adds up its increments."""

    def __init__(self, grammar: Grammar, name: str) -> None:
        """The grammar's roles, and the function's name (for recursion)."""
        self.g, self.name, self.total = grammar, name, 0

    def walk(self, node: Node, nesting: int) -> None:
        """Score a node and everything below it."""
        kind, g = node.type, self.g
        if kind in g.ifs:
            self.if_(node, nesting, else_if=False)
        elif kind in g.loops or kind in g.switches or kind in g.catches or kind in g.ternaries:
            self.total += 1 + nesting
            self.children(node, nesting, deeper=True)
        elif kind in g.nested or kind in g.functions:
            self.children(node, nesting + 1)
        elif self.logical_operator(node) and not self.inside_logical(node):
            self.total += self.sequences(node)
            self.children(node, nesting)
        else:
            self.total += self.jump(node) + self.recursion(node)
            self.children(node, nesting)

    def children(self, node: Node, nesting: int, deeper: bool = False) -> None:
        """Walk the children; with `deeper`, everything but the condition is one level deeper."""
        for i, child in enumerate(node.children):
            nested = deeper and node.field_name_for_child(i) != "condition"
            self.walk(child, nesting + 1 if nested else nesting)

    def if_(self, node: Node, nesting: int, else_if: bool) -> None:
        """if: +1 plus nesting; else if and else: +1 (hybrid); the bodies are one level deeper."""
        self.total += 1 if else_if else 1 + nesting
        for i, child in enumerate(node.children):
            field = node.field_name_for_child(i)
            if field == "alternative" or child.type in self.g.elifs or child.type in self.g.elses:
                self.alternative(child, nesting)
            else:
                self.walk(child, nesting if field == "condition" else nesting + 1)

    def alternative(self, node: Node, nesting: int) -> None:
        """The else branch: another if (else if), an elif clause, or an else body."""
        if node.type in self.g.ifs:
            self.if_(node, nesting, else_if=True)
            return
        inner = [c for c in node.named_children if c.type != "comment"]
        if node.type in self.g.elses and len(inner) == 1 and inner[0].type in self.g.ifs:
            self.if_(inner[0], nesting, else_if=True)
        elif node.type in self.g.elifs:
            self.if_(node, nesting, else_if=True)
        else:
            self.total += 1
            self.children(node, nesting + 1)

    def logical_operator(self, node: Node) -> str:
        """The logical operator of a binary node, or empty."""
        if node.type in self.g.implicit:
            return self.g.implicit[node.type]
        if node.type not in self.g.logical:
            return ""
        operator = node.child_by_field_name("operator")
        tokens = [operator] if operator is not None else [c for c in node.children if not c.is_named]
        return next((t.type for t in tokens if t.type in self.g.operators), "")

    def inside_logical(self, node: Node) -> bool:
        """Whether the node continues a logical sequence of its parent (parentheses don't break it)."""
        parent = node.parent
        while parent is not None and parent.type in self.g.parens:
            parent = parent.parent
        return parent is not None and bool(self.logical_operator(parent))

    def sequences(self, node: Node) -> int:
        """The number of runs of like operators in the flattened logical expression."""
        operators = self.flatten(node)
        return sum(1 for i, op in enumerate(operators) if i == 0 or op != operators[i - 1])

    def flatten(self, node: Node) -> list[str]:
        """The logical operators of an expression in source order, through parentheses."""
        while node.type in self.g.parens and node.named_child_count == 1:
            node = node.named_children[0]
        operator = self.logical_operator(node)
        if not operator:
            return []
        operands = [c for c in node.named_children if c.type != "comment"]
        left, right = operands[0], operands[-1]
        return [*self.flatten(left), operator, *self.flatten(right)]

    def jump(self, node: Node) -> int:
        """goto, comprehension filters, and break or continue to a label: +1 (no nesting)."""
        if node.type in self.g.flat:
            return 1
        labeled = node.type in self.g.labeled and any(c.type in self.g.labels for c in node.named_children)
        return 1 if labeled else 0

    def recursion(self, node: Node) -> int:
        """A call to the function itself: +1."""
        return 1 if node.type in self.g.calls and _callee(node) == self.name else 0


def _name(node: Node) -> str:
    """A function's name, the name it is assigned to (`const f = () => ...`), or `<anonymous>`."""
    for owner in (node, node.parent):
        name = owner.child_by_field_name("name") if owner is not None else None
        if name is not None and name.named_child_count == 0:
            return str(name.text.decode())
    return "<anonymous>"


def _callee(call: Node) -> str:
    """The called function's name if the call can be recursive: `f()`, `self.f()`, `this.f()`; else empty."""
    name, receiver = call.child_by_field_name("name"), call.child_by_field_name("object")
    if name is not None:  # Java-style method invocation: name plus optional receiver
        return _text(name) if receiver is None or _text(receiver) in SELF else ""
    target = call.child_by_field_name("function")
    if target is None:
        return ""
    if target.named_child_count == 0:
        return _text(target)
    owner = _field(target, ("object", "operand", "value"))
    member = _field(target, ("property", "attribute", "field"))
    return _text(member) if owner is not None and member is not None and _text(owner) in SELF else ""


def _field(node: Node, names: tuple[str, ...]) -> Node | None:
    """The first of the named fields the node has."""
    return next((f for f in (node.child_by_field_name(n) for n in names) if f is not None), None)


def _text(node: Node) -> str:
    """A node's source text."""
    return str(node.text.decode())
