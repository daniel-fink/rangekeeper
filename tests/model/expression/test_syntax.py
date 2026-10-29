"""The grammar of equation text: tokens, precedence, literals and syntax errors."""

import pytest

from rangekeeper.errors import Code, EquationError
from rangekeeper.model.expression.syntax import (
    Binary,
    Call,
    Constant,
    Literal,
    Member,
    Name,
    Node,
    Unary,
    parse,
    path,
)
from rangekeeper.model.expression.tokens import TokenKind, tokenize
from rangekeeper.schema.enums import Operator

SYMBOLS = {
    Operator.LOGICAL_OR: "or",
    Operator.LOGICAL_AND: "and",
    Operator.LOGICAL_NOT: "not",
    Operator.EQUAL: "=",
    Operator.NOT_EQUAL: "!=",
    Operator.LESS_THAN: "<",
    Operator.LESS_THAN_OR_EQUAL: "<=",
    Operator.GREATER_THAN: ">",
    Operator.GREATER_THAN_OR_EQUAL: ">=",
    Operator.ADD: "+",
    Operator.SUBTRACT: "-",
    Operator.MULTIPLY: "*",
    Operator.DIVIDE: "/",
    Operator.POWER: "**",
    Operator.NEGATE: "-",
}


def tree(node: Node) -> str:
    """Return a syntax tree as a bracketed prefix form, such as ``(= a (+ b c))``."""
    if isinstance(node, Literal):
        return node.number if node.units is None else f"[{node.number} {node.units}]"
    if isinstance(node, Constant):
        return node.word
    if isinstance(node, Name):
        return node.name
    if isinstance(node, Member):
        return f"{tree(node.base)}.{node.name}"
    if isinstance(node, Call):
        arguments = (
            tree(a.value) if a.name is None else f"{a.name}={tree(a.value)}"
            for a in node.arguments
        )
        return f"{tree(node.callee)}({', '.join(arguments)})"
    if isinstance(node, Unary):
        return f"({SYMBOLS[node.operator]} {tree(node.operand)})"
    assert isinstance(node, Binary)
    return f"({SYMBOLS[node.operator]} {tree(node.left)} {tree(node.right)})"


def syntax_error(text: str) -> EquationError:
    with pytest.raises(EquationError) as caught:
        parse(text)
    assert caught.value.code is Code.EQUATION_SYNTAX
    assert caught.value.text == text
    return caught.value


def test_tokens_have_their_kinds_and_positions():
    tokens = tokenize("a_1 >= 2.5e3 % pa**x")
    assert [(t.kind, t.text, t.start, t.end) for t in tokens] == [
        (TokenKind.NAME, "a_1", 0, 3),
        (TokenKind.SYMBOL, ">=", 4, 6),
        (TokenKind.NUMBER, "2.5e3", 7, 12),
        (TokenKind.SYMBOL, "%", 13, 14),
        (TokenKind.NAME, "pa", 15, 17),
        (TokenKind.SYMBOL, "**", 17, 19),
        (TokenKind.NAME, "x", 19, 20),
        (TokenKind.END, "", 20, 20),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "total_cost = land_cost + works_cost",
            "(= total_cost (+ land_cost works_cost))",
        ),
        ("a = b * c + d", "(= a (+ (* b c) d))"),
        ("a = b + c * d", "(= a (+ b (* c d)))"),
        ("a = (b + c) * d", "(= a (* (+ b c) d))"),
        ("a - b - c >= 0", "(>= (- (- a b) c) 0)"),
        ("a / b / c <= 1", "(<= (/ (/ a b) c) 1)"),
        ("a = b ** c ** d", "(= a (** b (** c d)))"),
        ("a = -b ** 2", "(= a (- (** b 2)))"),
        ("a = b ** -c", "(= a (** b (- c)))"),
        ("a = -b * c", "(= a (* (- b) c))"),
        ("a = b - -c", "(= a (- b (- c)))"),
        ("a >= b and c < d or e != f", "(or (and (>= a b) (< c d)) (!= e f))"),
        ("not a = b", "(not (= a b))"),
        ("not a and b", "(and (not a) b)"),
        ("a or b and c", "(or a (and b c))"),
        ("(a = b) = c", "(= (= a b) c)"),
        ("b_start = NEVER or b_open = True", "(or (= b_start NEVER) (= b_open True))"),
    ],
)
def test_operators_have_python_precedence(text, expected):
    assert tree(parse(text)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a = 1", "(= a 1)"),
        ("a = 1 year", "(= a [1 year])"),
        ("a = 2.5e6 AUD", "(= a [2.5e6 AUD])"),
        ("a = 7 % pa", "(= a [7 % pa])"),
        ("a = 5 %", "(= a [5 %])"),
        ("a = 750 AUD per sqm pa", "(= a [750 AUD per sqm pa])"),
        ("a = (750 AUD per sqm pa) * b", "(= a (* [750 AUD per sqm pa] b))"),
        # ``*`` and ``/`` are never part of a literal.
        ("a = 1 year * rate", "(= a (* [1 year] rate))"),
        ("a = 1 AUD / year", "(= a (/ [1 AUD] year))"),
        ("a = 1 year and b", "(and (= a [1 year]) b)"),
        ("a = -5 %", "(= a (- [5 %]))"),
    ],
)
def test_a_literal_is_a_number_and_the_unit_words_after_it(text, expected):
    assert tree(parse(text)) == expected


def test_literal_positions_mark_the_number_and_the_units():
    literal = parse("a = 7 % pa").right
    assert isinstance(literal, Literal)
    assert (literal.start, literal.end, literal.units_start) == (4, 10, 6)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "land = -rx.flow.event(amount=land_cost, on=start_date)",
            "(= land (- rx.flow.event(amount=land_cost, on=start_date)))",
        ),
        (
            "a = rx.profile.uniform(total=b, start=c + 1 year, length=2 years)",
            "(= a rx.profile.uniform(total=b, start=(+ c [1 year]), length=[2 years]))",
        ),
        ("p = rx.max(0 AUD, need - equity)", "(= p rx.max([0 AUD], (- need equity)))"),
        (
            "v = operating.at(on=sale_date + 1 year) / cap",
            "(= v (/ operating.at(on=(+ sale_date [1 year])) cap))",
        ),
        ("n = -(a + b).cumulative()", "(= n (- (+ a b).cumulative()))"),
        ("t = building_a.income", "(= t building_a.income)"),
        ("t = rx.max(a, b,)", "(= t rx.max(a, b))"),
    ],
)
def test_calls_members_and_named_arguments_parse(text, expected):
    assert tree(parse(text)) == expected


def test_path_gives_the_names_of_a_dotted_name():
    call = parse("rx.flow.event(amount=a)")
    assert isinstance(call, Call)
    assert path(call.callee) == ("rx", "flow", "event")
    assert path(parse("(a + b).total")) is None


def test_nodes_keep_their_positions():
    text = "total_cost = land_cost + works_cost"
    node = parse(text)
    assert isinstance(node, Binary) and isinstance(node.right, Binary)
    assert text[node.right.start : node.right.end] == "land_cost + works_cost"
    assert text[node.right.right.start : node.right.right.end] == "works_cost"


@pytest.mark.parametrize(
    ("text", "start", "end", "suggestions"),
    [
        ("noi == coverage", 4, 6, ("=",)),
        ("a = b & c", 6, 7, ("and",)),
        ("a = b | c", 6, 7, ("or",)),
        ("a = ~b", 4, 5, ("not",)),
        ("a = b ^ 2", 6, 7, ("**",)),
        ("a = b = c", 6, 7, ("and",)),
        ("a < b <= c", 6, 8, ("and",)),
    ],
)
def test_python_spellings_suggest_the_text_spelling(text, start, end, suggestions):
    error = syntax_error(text)
    assert (error.start, error.end, error.suggestions) == (start, end, suggestions)


@pytest.mark.parametrize(
    ("text", "start", "end", "message"),
    [
        ("", 0, 0, "empty"),
        ("a = ", 4, 4, "ends"),
        ("a = (b + c", 10, 10, "not closed"),
        ("a = b)", 5, 6, "unexpected"),
        ("a = b c", 6, 7, "unexpected"),
        ('a = "hotel"', 4, 5, "character"),
        ("a = rent[use]", 8, 9, "character"),
        ("a = b if c else d", 6, 8, "unexpected"),
        ("a = lambda", 4, 10, "keyword"),
        ("a = None", 4, 8, "keyword"),
        ("a = b and", 9, 9, "ends"),
        ("a = and b", 4, 7, "unexpected"),
        ("a = b.", 6, 6, "ends"),
        ("a = rx.max(x=1, x=2)", 16, 17, "twice"),
        ("a = rx.max(x=1, 2)", 16, 17, "positional"),
        ("a = b % 2", 6, 7, "unexpected"),
        ("a = 5 dwelling per 100 sqm", 19, 22, "unexpected"),
    ],
)
def test_syntax_errors_name_the_position(text, start, end, message):
    error = syntax_error(text)
    assert (error.start, error.end) == (start, end)
    assert message in str(error)
    # The message marks the part that fails under the text.
    marker = str(error).splitlines()[-1]
    assert marker.index("^") - 2 == start
