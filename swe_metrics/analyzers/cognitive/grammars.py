"""Per-language tables for cognitive complexity: which tree-sitter node types play which role.

The walker (walk.py) implements SonarSource's rules once; a language only names its node types here.
Adding a language: a Grammar entry, its package in pyproject (pinned) and white-paper-style tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

AND_OR = frozenset({"&&", "||"})


@dataclass(frozen=True)
class Grammar:
    """The node types of one tree-sitter grammar, by role (see walk.py for what each role scores)."""

    module: str                       # Python package of the grammar
    loader: str                       # its function that returns the language pointer
    functions: frozenset[str]         # functions and methods that get their own score
    ifs: frozenset[str]
    loops: frozenset[str]
    switches: frozenset[str] = frozenset()
    catches: frozenset[str] = frozenset()
    ternaries: frozenset[str] = frozenset()
    nested: frozenset[str] = frozenset()        # lambdas and closures: +1 nesting for their body, no score
    elifs: frozenset[str] = frozenset()         # else-if clauses (Python elif): +1, no nesting increment
    elses: frozenset[str] = frozenset()         # else clauses that wrap an else body or an else-if
    flat: frozenset[str] = frozenset()          # +1 without nesting: goto, comprehension filters
    labeled: frozenset[str] = frozenset()       # break/continue: +1 only when they carry a label
    labels: frozenset[str] = frozenset()        # node types of such a label
    jump_labels: frozenset[str] = frozenset()   # label texts that make a jump, where the type can't (Kotlin)
    logical: frozenset[str] = frozenset()       # binary nodes that may hold a logical operator
    operators: frozenset[str] = AND_OR          # the logical operator tokens
    implicit: dict[str, str] = field(default_factory=dict)  # node type -> operator, where there's no token
    calls: frozenset[str] = frozenset()         # call nodes, for recursion
    parens: frozenset[str] = frozenset({"parenthesized_expression"})


JAVA = Grammar(
    "tree_sitter_java", "language",
    functions=frozenset({"method_declaration", "constructor_declaration", "compact_constructor_declaration"}),
    ifs=frozenset({"if_statement"}),
    loops=frozenset({"for_statement", "enhanced_for_statement", "while_statement", "do_statement"}),
    switches=frozenset({"switch_expression"}),
    catches=frozenset({"catch_clause"}),
    ternaries=frozenset({"ternary_expression"}),
    nested=frozenset({"lambda_expression"}),
    labeled=frozenset({"break_statement", "continue_statement"}), labels=frozenset({"identifier"}),
    logical=frozenset({"binary_expression"}),
    calls=frozenset({"method_invocation"}),
)

JAVASCRIPT = Grammar(
    "tree_sitter_javascript", "language",
    functions=frozenset({"function_declaration", "generator_function_declaration", "method_definition"}),
    ifs=frozenset({"if_statement"}),
    loops=frozenset({"for_statement", "for_in_statement", "while_statement", "do_statement"}),
    switches=frozenset({"switch_statement"}),
    catches=frozenset({"catch_clause"}),
    ternaries=frozenset({"ternary_expression"}),
    nested=frozenset({"arrow_function", "function_expression", "generator_function", "function"}),
    elses=frozenset({"else_clause"}),
    labeled=frozenset({"break_statement", "continue_statement"}), labels=frozenset({"statement_identifier"}),
    logical=frozenset({"binary_expression"}),
    calls=frozenset({"call_expression"}),
)

TYPESCRIPT = replace(JAVASCRIPT, module="tree_sitter_typescript", loader="language_typescript")
TSX = replace(TYPESCRIPT, loader="language_tsx")

PYTHON = Grammar(
    "tree_sitter_python", "language",
    functions=frozenset({"function_definition"}),
    ifs=frozenset({"if_statement"}),
    loops=frozenset({"for_statement", "while_statement", "for_in_clause"}),  # comprehension `for` is a loop
    switches=frozenset({"match_statement"}),
    catches=frozenset({"except_clause", "except_group_clause"}),
    ternaries=frozenset({"conditional_expression"}),
    nested=frozenset({"lambda"}),
    elifs=frozenset({"elif_clause"}), elses=frozenset({"else_clause"}),
    flat=frozenset({"if_clause"}),  # a comprehension filter
    logical=frozenset({"boolean_operator"}), operators=frozenset({"and", "or"}),
    calls=frozenset({"call"}),
)

GO = Grammar(
    "tree_sitter_go", "language",
    functions=frozenset({"function_declaration", "method_declaration"}),
    ifs=frozenset({"if_statement"}),
    loops=frozenset({"for_statement"}),
    switches=frozenset({"expression_switch_statement", "type_switch_statement", "select_statement"}),
    nested=frozenset({"func_literal"}),
    flat=frozenset({"goto_statement"}),
    labeled=frozenset({"break_statement", "continue_statement"}), labels=frozenset({"label_name"}),
    logical=frozenset({"binary_expression"}),
    calls=frozenset({"call_expression"}),
)

CSHARP = Grammar(
    "tree_sitter_c_sharp", "language",
    functions=frozenset({"method_declaration", "constructor_declaration", "destructor_declaration",
                         "operator_declaration", "conversion_operator_declaration", "accessor_declaration"}),
    ifs=frozenset({"if_statement"}),
    loops=frozenset({"for_statement", "foreach_statement", "while_statement", "do_statement"}),
    switches=frozenset({"switch_statement", "switch_expression"}),
    catches=frozenset({"catch_clause"}),
    ternaries=frozenset({"conditional_expression"}),
    nested=frozenset({"local_function_statement", "lambda_expression", "anonymous_method_expression"}),
    flat=frozenset({"goto_statement"}),
    logical=frozenset({"binary_expression"}),
    calls=frozenset({"invocation_expression"}),
)

KOTLIN = Grammar(  # no ternary: the elvis operator `?:` is not a branch
    "tree_sitter_kotlin", "language",
    functions=frozenset({"function_declaration", "secondary_constructor", "getter", "setter"}),
    ifs=frozenset({"if_expression"}),
    loops=frozenset({"for_statement", "while_statement", "do_while_statement"}),
    switches=frozenset({"when_expression"}),
    catches=frozenset({"catch_block"}),
    nested=frozenset({"lambda_literal", "anonymous_function"}),
    # `break@outer` parses as a labeled expression with the label `break@`
    labeled=frozenset({"labeled_expression"}), labels=frozenset({"label"}),
    jump_labels=frozenset({"break@", "continue@"}),
    logical=frozenset({"binary_expression"}),
    calls=frozenset({"call_expression"}),
)

PHP = Grammar(
    "tree_sitter_php", "language_php",
    functions=frozenset({"function_definition", "method_declaration"}),
    ifs=frozenset({"if_statement"}),
    loops=frozenset({"for_statement", "foreach_statement", "while_statement", "do_statement"}),
    switches=frozenset({"switch_statement", "match_expression"}),
    catches=frozenset({"catch_clause"}),
    ternaries=frozenset({"conditional_expression"}),  # also the short form `?:`
    nested=frozenset({"anonymous_function", "arrow_function"}),
    elifs=frozenset({"else_if_clause"}), elses=frozenset({"else_clause"}),
    flat=frozenset({"goto_statement"}),
    # `break 2` / `continue 2` leave several loops at once: PHP's jump to a label
    labeled=frozenset({"break_statement", "continue_statement"}), labels=frozenset({"integer"}),
    logical=frozenset({"binary_expression"}), operators=frozenset({"&&", "||", "and", "or"}),
    calls=frozenset({"function_call_expression", "member_call_expression", "scoped_call_expression"}),
)

# file suffix -> grammar
GRAMMARS: dict[str, Grammar] = {
    ".java": JAVA, ".js": JAVASCRIPT, ".jsx": JAVASCRIPT, ".mjs": JAVASCRIPT, ".cjs": JAVASCRIPT,
    ".ts": TYPESCRIPT, ".tsx": TSX, ".py": PYTHON, ".go": GO, ".cs": CSHARP, ".kt": KOTLIN, ".kts": KOTLIN,
    ".php": PHP,
}
