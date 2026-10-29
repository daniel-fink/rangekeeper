from uuid import uuid4

import pytest

from rangekeeper.model.expression.authoring import binary, literal, reference
from rangekeeper.model.expression.text import render
from rangekeeper.schema.enums import ExpressionKind, Operator
from rangekeeper.schema.records import Expression, Reference

NAMES = {}


def ref(key):
    target = Reference(target=uuid4())
    NAMES[target.target] = key
    return reference(target)


def text(expression):
    return render(expression, name=lambda target: NAMES[target.target])


def negate(operand):
    return Expression(
        id=uuid4(), kind=ExpressionKind.UNARY, operator=Operator.NEGATE, operand=operand
    )


A, B, C = ref("a"), ref("b"), ref("c")


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (binary(Operator.EQUAL, A, binary(Operator.MULTIPLY, B, C)), "a = b * c"),
        (binary(Operator.MULTIPLY, binary(Operator.ADD, A, B), C), "(a + b) * c"),
        (binary(Operator.SUBTRACT, A, binary(Operator.SUBTRACT, B, C)), "a - (b - c)"),
        (binary(Operator.SUBTRACT, binary(Operator.SUBTRACT, A, B), C), "a - b - c"),
        (binary(Operator.POWER, A, binary(Operator.POWER, B, C)), "a ** b ** c"),
        (binary(Operator.POWER, binary(Operator.POWER, A, B), C), "(a ** b) ** c"),
        (negate(binary(Operator.ADD, A, B)), "-(a + b)"),
        (binary(Operator.MULTIPLY, literal(1.25), A), "1.25 * a"),
        (binary(Operator.LESS_THAN_OR_EQUAL, A, literal(2e7, "AUD")), "a <= 2e+07 AUD"),
        (
            binary(
                Operator.LOGICAL_AND,
                binary(Operator.GREATER_THAN_OR_EQUAL, A, B),
                binary(Operator.LESS_THAN, A, C),
            ),
            "(a >= b) & (a < c)",
        ),
        (binary(Operator.EQUAL, binary(Operator.EQUAL, A, B), C), "(a = b) = c"),
    ],
)
def test_render_writes_equation_text_with_minimal_parentheses(expression, expected):
    assert text(expression) == expected
