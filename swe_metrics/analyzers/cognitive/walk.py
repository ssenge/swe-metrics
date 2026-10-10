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
# receivers through which a method calls itself (PHP `$this->f()`, `static::f()`; Rust `Self::f()`)
SELF = frozenset({"self", "this", "cls", "Self", "$this", "static"})  # not `super`: another method
OWNERS = ("object", "operand", "value", "argument", "scope", "path", "expression")  # `x` in `x.f`, `x::f`
MEMBERS = ("property", "attribute", "field", "name")
PARAMETERS = ("parameters", "parameter_list", "formal_parameters", "function_value_parameters")
ARGUMENTS = ("arguments", "argument_list", "value_arguments")                   # `f` there


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
            name = _name(node, node.type in grammar.functions)
            walker = _Walker(grammar, name, _overload_arity(node, grammar, name))
            walker.children(node, 0)
            found.append(Scored(walker.name, node.start_point[0] + 1, walker.total))
        else:
            stack.extend(reversed(node.children))
    return sorted(found, key=lambda s: s.line)


class _Walker:
    """Walks one function's body and adds up its increments."""

    def __init__(self, grammar: Grammar, name: str, arity: int | None) -> None:
        """The grammar's roles, the function's name, and the argument count a recursive call must have."""
        self.g, self.name, self.arity, self.total = grammar, name, arity, 0

    def walk(self, node: Node, nesting: int) -> None:
        """Score a node and everything below it; a keyword token scores nothing (Ruby's `if` in an `if`)."""
        if node.is_named:
            self.named(node, nesting)

    def named(self, node: Node, nesting: int) -> None:
        """Score a syntax node by its role and walk its children."""
        kind, g = node.type, self.g
        if kind in g.ifs:
            self.if_(node, nesting, else_if=False)
        elif kind in g.loops or kind in g.switches or kind in g.catches or kind in g.ternaries:
            self.total += 1 + nesting  # the whole structure, header included, is one level deeper
            self.children(node, nesting + 1)
        elif kind in g.nested or kind in g.functions:
            self.children(node, nesting + 1)
        elif self.logical_operator(node) and not self.inside_logical(node):
            self.total += self.sequences(node)
            self.children(node, nesting)
        else:
            self.total += self.jump(node) + self.recursion(node)
            self.children(node, nesting)

    def children(self, node: Node, nesting: int) -> None:
        """Walk the children at the given nesting."""
        for child in node.children:
            self.walk(child, nesting)

    def if_(self, node: Node, nesting: int, else_if: bool) -> None:
        """if: +1 plus nesting; else if and else: +1 (hybrid); the bodies are one level deeper."""
        self.total += 1 if else_if else 1 + nesting
        after_else = False  # grammars without an `alternative` field (Kotlin): the branch after `else`
        for i, child in enumerate(node.children):
            field = node.field_name_for_child(i)
            if field == "alternative" or after_else or self.branch(child):
                self.alternative(child, nesting)
            else:
                self.walk(child, nesting if field == "condition" else nesting + 1)
            after_else = child.type == "else" and not child.is_named

    def branch(self, node: Node) -> bool:
        """Whether a child of an if is an else-if or else clause (not the keyword token of one)."""
        return bool(node.is_named) and (node.type in self.g.elifs or node.type in self.g.elses)

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
        # binary nodes have two operands; n-ary ones (Rust let chains) more, all joined by the operator
        operands = [c for c in node.named_children if c.type != "comment"]
        found = self.flatten(operands[0])
        for operand in operands[1:]:
            found += [operator, *self.flatten(operand)]
        return found

    def jump(self, node: Node) -> int:
        """goto, comprehension filters, and break or continue to a label: +1 (no nesting)."""
        if node.type in self.g.flat:
            return 1
        if node.type not in self.g.labeled:
            return 0
        return 1 if any(self.jump_label(c) for c in node.named_children) else 0

    def jump_label(self, node: Node) -> bool:
        """Whether a node is the label of a jump (by type, and by text where the grammar needs it)."""
        return node.type in self.g.labels and (not self.g.jump_labels or _text(node) in self.g.jump_labels)

    def recursion(self, node: Node) -> int:
        """A call to the function itself: +1."""
        if node.type not in self.g.calls or _callee(node, self.g.generics) != self.name:
            return 0
        return 1 if self.arity is None or _count(node, ARGUMENTS) == self.arity else 0


def _overload_arity(node: Node, grammar: Grammar, name: str) -> int | None:
    """Where a name is overloaded, the parameter count that identifies this function (-1: ambiguous).

    Without types, a call to an overload with the same number of parameters can't be told apart, so it
    isn't counted as recursion. None: the name is unique in its scope, any call by that name counts.
    """
    if not grammar.overloads or node.parent is None:
        return None
    siblings = [c for c in node.parent.named_children
                if c.type in grammar.functions and c.id != node.id and _name(c, True) == name]
    if not siblings:
        return None
    own = _count(node, PARAMETERS)
    return -1 if own in {_count(s, PARAMETERS) for s in siblings} else own


def _count(node: Node, kinds: tuple[str, ...]) -> int:
    """The number of parameters or arguments: the named children of the first matching list."""
    found = _field(node, kinds) or next((c for c in node.named_children if c.type in kinds), None)
    if found is None:
        declarator = node.child_by_field_name("declarator")
        return _count(declarator, kinds) if declarator is not None else 0
    return sum(1 for c in found.named_children if c.type != "comment")


def _name(node: Node, declared: bool) -> str:
    """A function's name (`~A`, `x=` too), the plain name a lambda is assigned to, or `<anonymous>`."""
    name = _declared(node) if declared else None
    if name is None and node.parent is not None:
        name = _declared(node.parent)
        name = name if name is not None and name.named_child_count == 0 else None  # not `{a, b} = ...`
    return _text(name) if name is not None else "<anonymous>"


def _declared(node: Node) -> Node | None:
    """The innermost name a node declares; C and C++ nest it in declarators (`int *A::f(int)` is `f`)."""
    name = _field(node, ("name", "declarator"))
    while name is not None and _field(name, ("name", "declarator")) is not None:
        name = _field(name, ("name", "declarator"))
    return name


def _callee(call: Node, generics: frozenset[str]) -> str:
    """The called function's name if the call can be recursive: `f()`, `self.f()`, `Self::f()`; else empty."""
    name, receiver = _field(call, ("name", "method")), _field(call, ("object", "receiver", "scope"))
    if name is not None:  # a method invocation (Java, Ruby, PHP static): name plus optional receiver
        return _text(name) if receiver is None or _text(receiver) in SELF else ""
    target = call.child_by_field_name("function")
    if target is None and call.named_child_count > 0:  # grammars without fields (Kotlin): the callee first
        target = call.named_children[0]
    return _function_name(target, generics)


def _function_name(target: Node | None, generics: frozenset[str]) -> str:
    """The name of a called function expression: `f`, `self.f`, `this->f`, `Self::f`; else empty."""
    if target is not None and target.type in generics:  # `f<T>()`, `f::<T>()`: the function inside
        target = _field(target, ("function", "name"))
    if target is None:
        return ""
    if target.named_child_count == 0:
        return _text(target)
    owner, member = _owner_member(target)
    return _text(member) if owner is not None and member is not None and _text(owner) in SELF else ""


def _owner_member(target: Node) -> tuple[Node | None, Node | None]:
    """The receiver and member of `x.f`, by field name, or by position where a grammar has none (Kotlin)."""
    owner, member = _field(target, OWNERS), _field(target, MEMBERS)
    if owner is None and member is None and target.named_child_count == 2:
        return target.named_children[0], target.named_children[1]
    return owner, member


def _field(node: Node, names: tuple[str, ...]) -> Node | None:
    """The first of the named fields the node has."""
    return next((f for f in (node.child_by_field_name(n) for n in names) if f is not None), None)


def _text(node: Node) -> str:
    """A node's source text."""
    return str(node.text.decode())
