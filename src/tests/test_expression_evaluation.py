"""Independent arithmetic and truth oracles for shared evaluation boundaries."""

from datetime import date
import subprocess
import sys
from uuid import uuid4

import pytest

from rangekeeper.errors import UnitError
from rangekeeper.model import Quantity, Reference
from rangekeeper.model.expression import Expression, ExpressionKind, Operator
from rangekeeper.model.expression.evaluation import evaluate as numerical
from rangekeeper.policies.predicate import evaluate as predicate
from rangekeeper.execution.evaluator import comparisons
from rangekeeper.execution.errors import NumericalError, UnsupportedProblem
from rangekeeper.units import default_units


def literal(amount, units="dimensionless"):
    return Expression(
        id=uuid4(),
        kind=ExpressionKind.QUANTITY,
        quantity=Quantity(magnitude=amount, units=units),
    )


def binary(op, left, right):
    return Expression(
        id=uuid4(), kind=ExpressionKind.BINARY, operator=op, operands=(left, right)
    )


def boolean(value):
    return Expression(id=uuid4(), kind=ExpressionKind.BOOLEAN, boolean=value)


@pytest.mark.parametrize(
    "operator,left,right,expected,units",
    [
        (Operator.ADD, literal(1, "m"), literal(50, "cm"), 1.5, "m"),
        (Operator.SUBTRACT, literal(1, "m"), literal(50, "cm"), 0.5, "m"),
        (Operator.MULTIPLY, literal(3, "m"), literal(2, "m"), 6, "m**2"),
        (Operator.DIVIDE, literal(6, "m"), literal(2, "s"), 3, "m/s"),
        (Operator.POWER, literal(3, "m"), literal(200, "percent"), 9, "m**2"),
    ],
)
def test_arithmetic_and_converted_units_have_independent_expected_values(
    operator, left, right, expected, units
):
    expression = binary(operator, left, right)
    for evaluate in (numerical, predicate):
        result = evaluate(expression, {}, units=default_units)
        assert default_units.convert(result, to=units).magnitude == pytest.approx(
            expected
        )


def test_reference_and_negation_use_only_supplied_values():
    identity = uuid4()
    expression = Expression(
        id=uuid4(), kind=ExpressionKind.REFERENCE, target=Reference(target=identity)
    )
    negation = Expression(
        id=uuid4(),
        kind=ExpressionKind.UNARY,
        operator=Operator.NEGATE,
        operand=expression,
    )
    assert (
        numerical(
            negation, {identity: Quantity(magnitude=3, units="m")}, units=default_units
        ).magnitude
        == -3
    )
    with pytest.raises(KeyError):
        numerical(expression, {}, units=default_units)


@pytest.mark.parametrize(
    "operator,expected",
    [
        (Operator.EQUAL, False),
        (Operator.NOT_EQUAL, True),
        (Operator.LESS_THAN, True),
        (Operator.LESS_THAN_OR_EQUAL, True),
        (Operator.GREATER_THAN, False),
        (Operator.GREATER_THAN_OR_EQUAL, False),
    ],
)
def test_policy_comparisons_remain_exact(operator, expected):
    assert (
        predicate(
            binary(operator, literal(1, "m"), literal(100.00000001, "cm")),
            {},
            units=default_units,
        )
        is expected
    )


def test_near_equality_is_exact_for_policy_but_has_an_acceptance_residual():
    expression = binary(Operator.EQUAL, literal(1), literal(1 + 1e-10))
    assert predicate(expression, {}, units=default_units) is False
    relation, left, right, exact = next(
        comparisons(expression, {}, units=default_units)
    )
    residual = left.magnitude - right.magnitude
    assert relation == "equal" and not exact and residual < 0
    assert abs(residual) < 1e-8 + 1e-9 * max(abs(left.magnitude), abs(right.magnitude))


def test_boolean_equality_negation_and_short_circuit():
    absent = Expression(
        id=uuid4(), kind=ExpressionKind.REFERENCE, target=Reference(target=uuid4())
    )
    assert (
        predicate(
            binary(Operator.LOGICAL_AND, boolean(False), absent),
            {},
            units=default_units,
        )
        is False
    )
    assert (
        predicate(
            binary(Operator.LOGICAL_OR, boolean(True), absent), {}, units=default_units
        )
        is True
    )
    assert (
        predicate(
            binary(Operator.EQUAL, boolean(False), boolean(False)),
            {},
            units=default_units,
        )
        is True
    )
    assert (
        predicate(
            binary(Operator.NOT_EQUAL, boolean(False), boolean(True)),
            {},
            units=default_units,
        )
        is True
    )
    negation = Expression(
        id=uuid4(),
        kind=ExpressionKind.UNARY,
        operator=Operator.LOGICAL_NOT,
        operand=boolean(False),
    )
    assert predicate(negation, {}, units=default_units) is True
    with pytest.raises(ValueError, match="Boolean"):
        predicate(
            binary(Operator.LOGICAL_AND, literal(1), boolean(True)),
            {},
            units=default_units,
        )


@pytest.mark.parametrize(
    "expression,error",
    [
        (binary(Operator.ADD, literal(1, "m"), literal(1, "s")), UnitError),
        (binary(Operator.DIVIDE, literal(1), literal(0)), ZeroDivisionError),
        (binary(Operator.POWER, literal(1e308), literal(2)), OverflowError),
        (binary(Operator.POWER, literal(-1), literal(0.5)), ValueError),
    ],
)
def test_policy_arithmetic_errors_and_numerical_acceptance_translation(
    expression, error
):
    with pytest.raises(error):
        predicate(expression, {}, units=default_units)
    comparison = binary(Operator.EQUAL, expression, literal(0))
    with pytest.raises(NumericalError):
        tuple(comparisons(comparison, {}, units=default_units))


def test_conjunction_diagnostics_preserve_expression_order():
    expression = binary(
        Operator.LOGICAL_AND,
        binary(Operator.EQUAL, literal(2), literal(1)),
        binary(Operator.LESS_THAN_OR_EQUAL, literal(3), literal(5)),
    )
    results = tuple(comparisons(expression, {}, units=default_units))
    assert [
        (relation, left.magnitude - right.magnitude)
        for relation, left, right, _ in results
    ] == [("equal", 1), ("less_than_or_equal", -2)]
    with pytest.raises(UnsupportedProblem):
        tuple(comparisons(literal(1), {}, units=default_units))


def test_availability_combines_dates_without_runtime_imports():
    from rangekeeper.policies._availability import available_on

    assert available_on() is None
    assert available_on(period_end=date(2027, 2, 1)) == date(2027, 1, 31)
    assert available_on(
        movement_date=date(2027, 1, 2), period_end=date(2027, 2, 1)
    ) == date(2027, 1, 2)
    assert available_on(
        movement_date=date(2027, 1, 2),
        scenario_dates=(date(2027, 1, 3), date(2027, 1, 4)),
        declared=date(2027, 1, 5),
    ) == date(2027, 1, 5)
    for imports in (
        "import rangekeeper.specification.validation; import rangekeeper.policies._availability",
        "import rangekeeper.policies._availability; import rangekeeper.specification.validation",
    ):
        subprocess.run(
            [
                sys.executable,
                "-c",
                imports
                + "; import sys; assert not any(n.startswith(('rangekeeper.policies.evaluation', 'rangekeeper.execution.compiler', 'numpy', 'scipy', 'pint', 'pyomo')) for n in sys.modules)",
            ],
            check=True,
        )
    for imports in (
        "import rangekeeper.specification.validation; from rangekeeper.policies import evaluate",
        "from rangekeeper.policies import evaluate; import rangekeeper.specification.validation",
    ):
        subprocess.run([sys.executable, "-c", imports], check=True)
