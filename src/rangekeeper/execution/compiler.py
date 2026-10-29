"""Stage 4: lower declared scalar arithmetic to affine rows after fixed assignments.

The lowering is independent of any backend. Coefficients are expressed in each
unknown's Measure units. Rows are not scaled: each backend scales them for its own
numerical range. Numerical verification does not use these rows: it reevaluates
the original expression trees against the proposed serialized Model.
"""

import math
import operator
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from rangekeeper.execution.analysis import Analysis, equality_rank, undetermined
from rangekeeper.execution.errors import NumericalError, UnsupportedError
from rangekeeper.execution.preparation import Assertion, Binding
from rangekeeper.execution.settings import Limits
from rangekeeper.model.expression.evaluation import (
    evaluate as numerical,
)
from rangekeeper.quantity import Quantity
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import Expression, ExpressionKind, Operator
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import UnitError


@dataclass(frozen=True)
class Affine:
    """A scalar constant plus UUID-keyed coefficients, all in one result unit."""

    constant: float
    coefficients: Mapping[UUID, float]
    units: str


class Relation(StrEnum):
    """How an affine residual relates to zero."""

    EQUAL = "equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"


@dataclass(frozen=True)
class Row:
    """An affine residual constrained to equal, be below, or be above zero.

    ``assertion`` keeps the original Constraint, so that a backend can name it.
    """

    assertion: Assertion
    relation: Relation
    residual: Affine


@dataclass(frozen=True)
class AffineProblem:
    """The backend-neutral feasibility problem of one case.

    ``variables`` are the unknowns, in a fixed order. Each row relates an affine
    residual over the variables to zero; a row that is not an equality is a
    bound. ``analysis`` gives the equality rank and the free variables.
    ``binding`` keeps the roles and the original assertions.
    """

    binding: Binding
    variables: tuple[UUID, ...]
    rows: tuple[Row, ...]
    analysis: Analysis

    @property
    def equalities(self) -> tuple[Row, ...]:
        """Return the equality rows."""
        return tuple(row for row in self.rows if row.relation is Relation.EQUAL)

    @property
    def bounds(self) -> tuple[Row, ...]:
        """Return the inequality rows."""
        return tuple(row for row in self.rows if row.relation is not Relation.EQUAL)


def _affine(constant: float, coefficients: Mapping[UUID, float], units: str) -> Affine:
    if not all(math.isfinite(x) for x in (constant, *coefficients.values())):
        raise NumericalError("affine lowering produced non-finite coefficients")
    return Affine(
        float(constant),
        MappingProxyType({k: float(v) for k, v in coefficients.items() if v != 0}),
        units,
    )


class Compiler:
    """One bound scope; explicit recursive operations retain mathematical order."""

    def __init__(
        self, binding: Binding, checkpoint: Callable[[], None] = lambda: None
    ) -> None:
        self.binding = binding
        self.checkpoint = checkpoint

    def nonaffine(self, operation: str, *values: Affine) -> UnsupportedError:
        """Return the error for an operation on unknowns that is not affine."""
        ids = dict.fromkeys(id for value in values for id in value.coefficients)
        keys = tuple(self.binding.key(self.binding.references[id]) for id in ids)
        noun = "the unknown" if len(keys) == 1 else "the unknowns"
        return UnsupportedError(
            f"{operation} {noun} {', '.join(keys)} is nonlinear",
            code=Code.NONAFFINE_UNKNOWNS,
            unknowns=keys,
        )

    def convert(self, value: Affine, units: str) -> Affine:
        """Convert a whole affine expression; offset units are outside this slice."""
        zero = self.binding.units.convert(
            Quantity(magnitude=0, units=value.units), to=units
        )
        one = self.binding.units.convert(
            Quantity(magnitude=1, units=value.units), to=units
        )
        if zero.number != 0:
            raise UnsupportedError("offset unit arithmetic is not supported")
        return self.scale(value, one.number, units)

    @staticmethod
    def scale(value: Affine, factor: float, units: str) -> Affine:
        """Multiply an affine expression by a factor and attach the given units."""
        return _affine(
            value.constant * factor,
            {k: v * factor for k, v in value.coefficients.items()},
            units,
        )

    def add(self, left: Affine, right: Affine, sign: float = 1) -> Affine:
        """Add or subtract an affine expression after conversion to the left units."""
        right = self.convert(right, left.units)
        coefficients = dict(left.coefficients)
        for key, value in right.coefficients.items():
            coefficients[key] = coefficients.get(key, 0) + sign * value
        return _affine(left.constant + sign * right.constant, coefficients, left.units)

    def fold(self, node: Expression) -> Affine | None:
        """Evaluate an expression whose references are all fixed, else return None.

        A staged solve fixes the values that earlier stages determined, so a
        function of them is a constant here. None means that an unknown
        remains or that the evaluator does not support the expression.
        """
        for child, _, _ in walk(node):
            if (
                isinstance(child, Expression)
                and child.kind is ExpressionKind.REFERENCE
                and (
                    child.target is None
                    or child.target.target not in self.binding.assignments
                )
            ):
                return None
        try:
            value = numerical(node, self.binding.assignments, units=self.binding.units)
        except (UnsupportedError, UnitError):
            return None
        except (ArithmeticError, TypeError, ValueError) as error:
            raise NumericalError(str(error)) from error
        return _affine(value.number, {}, value.units)

    def expression(self, node: Expression) -> Affine:
        """Compile only arithmetic affine under this Specification's assignments."""
        self.checkpoint()
        if node.kind == ExpressionKind.QUANTITY:
            assert node.quantity is not None
            return _affine(node.quantity.number, {}, node.quantity.units)
        if node.kind == ExpressionKind.REFERENCE:
            assert node.target is not None
            token = node.target.target
            if token in self.binding.assignments:
                assigned = self.binding.assignments[token]
                return _affine(assigned.number, {}, assigned.units)
            if token in self.binding.unknowns:
                return _affine(0, {token: 1}, self.binding.value_units[token])
            raise UnsupportedError("expression reference has no explicit solve role")
        if node.kind == ExpressionKind.UNARY and node.operator == Operator.NEGATE:
            assert node.operand is not None
            value = self.expression(node.operand)
            return self.scale(value, -1, value.units)
        if node.kind != ExpressionKind.BINARY or node.operator not in {
            Operator.ADD,
            Operator.SUBTRACT,
            Operator.MULTIPLY,
            Operator.DIVIDE,
            Operator.POWER,
        }:
            folded = self.fold(node)
            if folded is None:
                raise UnsupportedError(
                    f"unsupported scalar expression: {node.kind}/{node.operator}"
                )
            return folded
        assert node.operands is not None
        left, right = (self.expression(x) for x in node.operands)
        if node.operator in {Operator.ADD, Operator.SUBTRACT}:
            return self.add(left, right, 1 if node.operator == Operator.ADD else -1)
        if node.operator == Operator.MULTIPLY:
            if left.coefficients and right.coefficients:
                raise self.nonaffine("multiplication of", left, right)
            unit = f"({left.units}) * ({right.units})"
            return (
                self.scale(left, right.constant, unit)
                if not right.coefficients
                else self.scale(right, left.constant, unit)
            )
        if node.operator == Operator.DIVIDE:
            if right.coefficients:
                raise self.nonaffine("division by", right)
            if right.constant == 0:
                raise NumericalError("division by zero in declared expression")
            return self.scale(
                left, 1 / right.constant, f"({left.units}) / ({right.units})"
            )
        right = self.convert(right, "dimensionless")
        if right.coefficients:
            raise self.nonaffine("an exponent of", right)
        if right.constant == 1:
            return left
        if right.constant == 0:
            return _affine(1, {}, "dimensionless")
        if left.coefficients:
            raise self.nonaffine("a power of", left)
        try:
            magnitude = float(left.constant**right.constant)
        except (ValueError, TypeError, OverflowError, ZeroDivisionError) as error:
            raise NumericalError(str(error)) from error
        return _affine(magnitude, {}, f"({left.units}) ** {right.constant}")

    def assertion(self, item: Assertion) -> tuple[Row, ...]:
        """Flatten conjunctions and check fixed strict predicates before lowering."""
        node = item.predicate
        if node.kind == ExpressionKind.BINARY and node.operator == Operator.LOGICAL_AND:
            assert node.operands is not None
            return tuple(
                row
                for child in node.operands
                for row in self.assertion(
                    Assertion(item.document, item.constraint, child)
                )
            )
        if node.kind == ExpressionKind.BOOLEAN:
            residual = _affine(0 if node.boolean else 1, {}, "dimensionless")
            return (Row(item, Relation.EQUAL, residual),)
        if node.kind is ExpressionKind.BINARY and node.operator in (
            Operator.LESS_THAN,
            Operator.GREATER_THAN,
        ):
            if node.operands is None or len(node.operands) != 2:
                raise UnsupportedError("comparison requires two operands")
            referenced = {
                child.target.target
                for child, _, _ in walk(node)
                if isinstance(child, Expression)
                and child.kind is ExpressionKind.REFERENCE
                and child.target is not None
            }
            if not referenced <= self.binding.assignments.keys():
                raise UnsupportedError(
                    "strict predicates require only fixed assigned or literal operands"
                )
            try:
                left = numerical(
                    node.operands[0],
                    self.binding.assignments,
                    units=self.binding.units,
                )
                right = self.binding.units.convert(
                    numerical(
                        node.operands[1],
                        self.binding.assignments,
                        units=self.binding.units,
                    ),
                    to=left.units,
                )
            except (UnsupportedError, UnitError):
                raise
            except (ArithmeticError, TypeError, ValueError) as error:
                raise NumericalError(str(error)) from error
            compare = (
                operator.lt if node.operator is Operator.LESS_THAN else operator.gt
            )
            if not compare(left.number, right.number):
                raise UnsupportedError("fixed strict predicate is false")
            return ()
        if node.kind != ExpressionKind.BINARY or node.operator not in {
            Operator.EQUAL,
            Operator.LESS_THAN_OR_EQUAL,
            Operator.GREATER_THAN_OR_EQUAL,
        }:
            raise UnsupportedError(
                "only equality, nonstrict bounds and conjunctions are supported"
            )
        assert node.operands is not None
        residual = self.add(
            self.expression(node.operands[0]), self.expression(node.operands[1]), -1
        )
        return (Row(item, Relation(node.operator.value), residual),)


def build_problem(
    binding: Binding,
    *,
    limits: Limits | None = None,
    checkpoint: Callable[[], None] = lambda: None,
) -> AffineProblem:
    """Lower each assertion of ``binding`` to immutable affine rows, and analyse them.

    Raise UnsupportedError, scoped to the original declaration and with its
    ``equation`` text, when a row is outside the affine slice: its code is
    ``nonaffine_unknowns`` for a product, quotient or power of unknowns. Raise it
    with a ``symbol_limit`` or ``constraint_limit`` code when the problem is
    larger than ``limits`` allows.
    """
    limits = Limits() if limits is None else limits
    if len(binding.references) > limits.symbol_limit:
        raise UnsupportedError(
            f"expanded symbol limit {limits.symbol_limit} exceeded",
            code=Code.SYMBOL_LIMIT,
        )
    compiler = Compiler(binding, checkpoint)
    rows: list[Row] = []
    for item in binding.assertions:
        checkpoint()
        try:
            rows.extend(compiler.assertion(item))
            if len(rows) > limits.constraint_limit:
                raise UnsupportedError(
                    f"expanded constraint limit {limits.constraint_limit} exceeded",
                    code=Code.CONSTRAINT_LIMIT,
                )
        except UnsupportedError as error:
            equation = binding.text(item.predicate)
            raise UnsupportedError(
                f'{error} in "{equation}"',
                code=error.code,
                document=item.document,
                target=item.constraint.id,
                equation=equation,
                unknowns=error.unknowns,
            ) from error
    variables = tuple(binding.unknowns)
    constrained = {key for row in rows for key in row.residual.coefficients}
    equalities = [
        row.residual.coefficients for row in rows if row.relation is Relation.EQUAL
    ]
    rank = equality_rank(equalities, len(variables))
    analysis = Analysis(
        rank=rank,
        unknown_count=len(variables),
        free=tuple(id for id in variables if id not in constrained),
        has_bounds=any(row.relation is not Relation.EQUAL for row in rows),
        undetermined=(
            undetermined(equalities, variables) if rank < len(variables) else ()
        ),
    )
    return AffineProblem(binding, variables, tuple(rows), analysis)
