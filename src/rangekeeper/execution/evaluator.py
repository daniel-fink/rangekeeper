"""Evaluate original expression trees without importing the compiler or a backend."""

from collections.abc import Mapping
import math
from uuid import UUID

from .._schema.records import Expression, Quantity
from ..units import UnitSystem
from .symbols import key
from .errors import NumericalError, UnsupportedProblem


def quantity(magnitude: float, units: str) -> Quantity:
    """Reject undefined/non-finite arithmetic before it enters a record."""
    if isinstance(magnitude, bool) or not math.isfinite(magnitude):
        raise NumericalError("expression evaluation produced a non-finite magnitude")
    return Quantity(magnitude=float(magnitude), units=units)


def evaluate(
    node: Expression, values: Mapping[str, Quantity], *, units: UnitSystem
) -> Quantity:
    """Read supplied quantities only; never fall back to recorded Model amounts."""
    if node.kind == "quantity":
        assert node.quantity is not None
        return node.quantity
    if node.kind == "reference":
        assert node.target is not None
        return values[key(node.target)]
    if node.kind == "unary" and node.operator == "negate":
        assert node.operand is not None
        value = evaluate(node.operand, values, units=units)
        return quantity(-float(value.magnitude), value.units)
    if node.kind != "binary" or node.operator not in {
        "add",
        "subtract",
        "multiply",
        "divide",
        "power",
    }:
        raise UnsupportedProblem(
            f"unsupported numerical expression: {node.kind}/{node.operator}"
        )
    assert node.operands is not None
    left = evaluate(node.operands[0], values, units=units)
    right = evaluate(node.operands[1], values, units=units)
    a, b = float(left.magnitude), float(right.magnitude)
    try:
        if node.operator in {"add", "subtract"}:
            b = float(units.convert(right, to=left.units).magnitude)
            return quantity(a + b if node.operator == "add" else a - b, left.units)
        if node.operator == "multiply":
            return quantity(a * b, f"({left.units}) * ({right.units})")
        if node.operator == "divide":
            return quantity(a / b, f"({left.units}) / ({right.units})")
        b = float(units.convert(right, to="dimensionless").magnitude)
        return quantity(float(a**b), f"({left.units}) ** {b}")
    except (ArithmeticError, TypeError, ValueError) as error:
        raise NumericalError(str(error)) from error


def comparisons(node: Expression, values: Mapping[str, Quantity], *, units: UnitSystem):
    """Yield original comparison sides, retaining conjunction and operand order."""
    if node.kind == "boolean":
        yield "equal", quantity(0 if node.boolean else 1, "dimensionless"), quantity(
            0, "dimensionless"
        ), True
    elif node.kind == "binary" and node.operator == "logical_and":
        assert node.operands is not None
        for child in node.operands:
            yield from comparisons(child, values, units=units)
    elif node.kind == "binary" and node.operator in {
        "equal",
        "less_than_or_equal",
        "greater_than_or_equal",
    }:
        assert node.operands is not None
        left = evaluate(node.operands[0], values, units=units)
        right = units.convert(
            evaluate(node.operands[1], values, units=units), to=left.units
        )
        yield node.operator, left, right, False
    else:
        raise UnsupportedProblem("unsupported predicate in numerical acceptance")
