"""Traverse original comparisons for independent numerical acceptance."""

from collections.abc import Mapping
from uuid import UUID

from .._schema.records import Expression, ExpressionKind, Operator, Quantity
from .._record_index import walk
from ..model.expression.evaluation import evaluate, quantity, UnsupportedExpression
from ..units import UnitSystem
from .errors import NumericalError, UnsupportedProblem


def comparisons(
    node: Expression,
    values: Mapping[UUID, Quantity],
    *,
    units: UnitSystem,
    fixed=frozenset(),
):
    """Retain conjunction order; fixed strict predicates use exact comparison."""
    try:
        if node.kind is ExpressionKind.BOOLEAN:
            yield "equal", quantity(
                0 if node.boolean else 1, "dimensionless"
            ), quantity(0, "dimensionless"), True
        elif (
            node.kind is ExpressionKind.BINARY and node.operator is Operator.LOGICAL_AND
        ):
            if node.operands is None or len(node.operands) != 2:
                raise UnsupportedProblem("conjunction requires two operands")
            for child in node.operands:
                yield from comparisons(child, values, units=units, fixed=fixed)
        elif node.kind is ExpressionKind.BINARY and node.operator in (
            Operator.EQUAL,
            Operator.LESS_THAN_OR_EQUAL,
            Operator.GREATER_THAN_OR_EQUAL,
            Operator.LESS_THAN,
            Operator.GREATER_THAN,
        ):
            if node.operands is None or len(node.operands) != 2:
                raise UnsupportedProblem("comparison requires two operands")
            strict = node.operator in (Operator.LESS_THAN, Operator.GREATER_THAN)
            if strict and any(
                child.target.target not in fixed
                for child, _, _ in walk(node)
                if isinstance(child, Expression)
                and child.kind is ExpressionKind.REFERENCE
                and child.target is not None
            ):
                raise UnsupportedProblem(
                    "strict predicates require only fixed assigned or literal operands"
                )
            left = evaluate(node.operands[0], values, units=units)
            right = units.convert(
                evaluate(node.operands[1], values, units=units), to=left.units
            )
            yield node.operator.value, left, right, strict
        else:
            raise UnsupportedProblem("unsupported predicate in numerical acceptance")
    except UnsupportedExpression as error:
        raise UnsupportedProblem(str(error)) from error
    except UnsupportedProblem:
        raise
    except (ArithmeticError, ValueError, TypeError) as error:
        raise NumericalError(str(error)) from error
