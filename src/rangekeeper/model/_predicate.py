"""Pure finite Boolean expression evaluation over explicitly supplied quantities.

Used to check policy decisions. There is no Model, store or solver access here.
"""

import math
from .._schema.records import Expression, Quantity
from ._references import reference_key
from ..units import default_units


def evaluate(node: Expression, quantities, *, units=default_units):
    if node.kind == "boolean":
        return node.boolean
    if node.kind == "quantity":
        return node.quantity
    if node.kind == "reference":
        assert node.target is not None
        return quantities[reference_key(node.target.to_data())]
    if node.kind == "unary":
        assert node.operand is not None
        value = evaluate(node.operand, quantities, units=units)
        if node.operator == "logical_not" and type(value) is bool:
            return not value
        if node.operator == "negate" and isinstance(value, Quantity):
            return Quantity(magnitude=-value.magnitude, units=value.units)
        raise ValueError("unsupported policy unary expression")
    if node.kind != "binary":
        raise ValueError(
            "policy supports finite literals, observations and operators only"
        )
    assert node.operands is not None
    left = evaluate(node.operands[0], quantities, units=units)
    if node.operator in ("logical_and", "logical_or"):
        if type(left) is not bool:
            raise ValueError("Boolean operand required")
        if node.operator == "logical_and" and not left:
            return False
        if node.operator == "logical_or" and left:
            return True
        right = evaluate(node.operands[1], quantities, units=units)
        if type(right) is not bool:
            raise ValueError("Boolean operand required")
        return right
    right = evaluate(node.operands[1], quantities, units=units)
    if (
        type(left) is bool
        and type(right) is bool
        and node.operator in ("equal", "not_equal")
    ):
        return (left == right) if node.operator == "equal" else (left != right)
    if not isinstance(left, Quantity) or not isinstance(right, Quantity):
        raise ValueError("numerical operands required")
    a, b = float(left.magnitude), float(right.magnitude)
    operator = node.operator
    result_units = left.units
    if operator in (
        "add",
        "subtract",
        "equal",
        "not_equal",
        "less_than",
        "less_than_or_equal",
        "greater_than",
        "greater_than_or_equal",
    ):
        b = float(units.convert(right, to=left.units).magnitude)
    if operator in (
        "equal",
        "not_equal",
        "less_than",
        "less_than_or_equal",
        "greater_than",
        "greater_than_or_equal",
    ):
        return {
            "equal": a == b,
            "not_equal": a != b,
            "less_than": a < b,
            "less_than_or_equal": a <= b,
            "greater_than": a > b,
            "greater_than_or_equal": a >= b,
        }[operator]
    if operator == "add":
        result = a + b
    elif operator == "subtract":
        result = a - b
    elif operator == "multiply":
        result, result_units = a * b, f"({left.units}) * ({right.units})"
    elif operator == "divide":
        result, result_units = a / b, f"({left.units}) / ({right.units})"
    elif operator == "power":
        b = float(units.convert(right, to="dimensionless").magnitude)
        result, result_units = a**b, f"({left.units}) ** {b}"
    else:
        raise ValueError("unsupported policy operator")
    if isinstance(result, complex) or not math.isfinite(result):
        raise ValueError("non-finite policy calculation")
    return Quantity(magnitude=result, units=result_units)
