"""Lower declared scalar arithmetic to affine rows after applying fixed assignments.

The lowering is independent of Pyomo. Coefficients are expressed in each unknown's
Measure units. Numerical acceptance does not use these rows: it reevaluates the
original expression trees against the proposed serialized Model.
"""

from dataclasses import dataclass
import math
from types import MappingProxyType
from collections.abc import Mapping, Callable
from uuid import UUID

from .._schema.records import Expression, Quantity
from .symbols import key
from .errors import UnsupportedProblem, NumericalError
from .preparation import Prepared, Assertion


@dataclass(frozen=True)
class Affine:
    """A scalar constant plus UUID-keyed coefficients, all in one result unit."""

    constant: float
    coefficients: Mapping[str, float]
    units: str


@dataclass(frozen=True)
class Row:
    """An affine residual constrained to equal, be below, or be above zero."""

    assertion: Assertion
    relation: str
    residual: Affine
    scale: float


@dataclass(frozen=True)
class Compiled:
    """Backend-independent feasibility problem, with traceable original assertions."""

    prepared: Prepared
    rows: tuple[Row, ...]


def _affine(constant: float, coefficients: Mapping[str, float], units: str) -> Affine:
    if not all(math.isfinite(x) for x in (constant, *coefficients.values())):
        raise NumericalError("affine lowering produced non-finite coefficients")
    return Affine(
        float(constant),
        MappingProxyType({k: float(v) for k, v in coefficients.items() if v != 0}),
        units,
    )


class Compiler:
    """One prepared scope; explicit recursive operations retain mathematical order."""

    def __init__(
        self, prepared: Prepared, checkpoint: Callable[[], None] = lambda: None
    ) -> None:
        self.prepared = prepared
        self.checkpoint = checkpoint

    def convert(self, value: Affine, units: str) -> Affine:
        """Convert a whole affine expression; offset units are outside this slice."""
        zero = self.prepared.units.convert(
            Quantity(magnitude=0, units=value.units), to=units
        )
        one = self.prepared.units.convert(
            Quantity(magnitude=1, units=value.units), to=units
        )
        if zero.magnitude != 0:
            raise UnsupportedProblem("offset unit arithmetic is not supported")
        return self.scale(value, float(one.magnitude), units)

    @staticmethod
    def scale(value: Affine, factor: float, units: str) -> Affine:
        return _affine(
            value.constant * factor,
            {k: v * factor for k, v in value.coefficients.items()},
            units,
        )

    def add(self, left: Affine, right: Affine, sign: float = 1) -> Affine:
        right = self.convert(right, left.units)
        coefficients = dict(left.coefficients)
        for key, value in right.coefficients.items():
            coefficients[key] = coefficients.get(key, 0) + sign * value
        return _affine(left.constant + sign * right.constant, coefficients, left.units)

    def expression(self, node: Expression) -> Affine:
        """Compile only arithmetic affine under this Specification's assignments."""
        self.checkpoint()
        if node.kind == "quantity":
            assert node.quantity is not None
            return _affine(float(node.quantity.magnitude), {}, node.quantity.units)
        if node.kind == "reference":
            assert node.target is not None
            token = key(node.target)
            if token in self.prepared.assignments:
                assigned = self.prepared.assignments[token]
                return _affine(float(assigned.magnitude), {}, assigned.units)
            if token in self.prepared.unknowns:
                return _affine(0, {token: 1}, self.prepared.value_units[token])
            raise UnsupportedProblem("expression reference has no explicit solve role")
        if node.kind == "unary" and node.operator == "negate":
            assert node.operand is not None
            value = self.expression(node.operand)
            return self.scale(value, -1, value.units)
        if node.kind != "binary" or node.operator not in {
            "add",
            "subtract",
            "multiply",
            "divide",
            "power",
        }:
            raise UnsupportedProblem(
                f"unsupported scalar expression: {node.kind}/{node.operator}"
            )
        assert node.operands is not None
        left, right = (self.expression(x) for x in node.operands)
        if node.operator in {"add", "subtract"}:
            return self.add(left, right, 1 if node.operator == "add" else -1)
        if node.operator == "multiply":
            if left.coefficients and right.coefficients:
                raise UnsupportedProblem(
                    "multiplication of two unknown expressions is nonlinear"
                )
            unit = f"({left.units}) * ({right.units})"
            return (
                self.scale(left, right.constant, unit)
                if not right.coefficients
                else self.scale(right, left.constant, unit)
            )
        if node.operator == "divide":
            if right.coefficients:
                raise UnsupportedProblem(
                    "division by an unknown expression is nonlinear"
                )
            if right.constant == 0:
                raise NumericalError("division by zero in declared expression")
            return self.scale(
                left, 1 / right.constant, f"({left.units}) / ({right.units})"
            )
        right = self.convert(right, "dimensionless")
        if right.coefficients:
            raise UnsupportedProblem("an unknown exponent is outside affine execution")
        if right.constant == 1:
            return left
        if right.constant == 0:
            return _affine(1, {}, "dimensionless")
        if left.coefficients:
            raise UnsupportedProblem("a nontrivial power of an unknown is nonlinear")
        try:
            magnitude = float(left.constant**right.constant)
        except (ValueError, TypeError, OverflowError, ZeroDivisionError) as error:
            raise NumericalError(str(error)) from error
        return _affine(magnitude, {}, f"({left.units}) ** {right.constant}")

    def assertion(self, item: Assertion) -> tuple[Row, ...]:
        """Flatten conjunctions; reject strict/disjunctive/non-arithmetic predicates."""
        node = item.predicate
        if node.kind == "binary" and node.operator == "logical_and":
            assert node.operands is not None
            return tuple(
                row
                for child in node.operands
                for row in self.assertion(
                    Assertion(item.document, item.constraint, child)
                )
            )
        if node.kind == "boolean":
            residual = _affine(0 if node.boolean else 1, {}, "dimensionless")
            return (Row(item, "equal", residual, 1),)
        if node.kind != "binary" or node.operator not in {
            "equal",
            "less_than_or_equal",
            "greater_than_or_equal",
        }:
            raise UnsupportedProblem(
                "only equality, nonstrict bounds and conjunctions are supported"
            )
        assert node.operands is not None
        residual = self.add(
            self.expression(node.operands[0]), self.expression(node.operands[1]), -1
        )
        # Scale coefficients only; large RHS values must not erase small coefficients.
        scale = max((1.0, *(abs(v) for v in residual.coefficients.values())))
        scaled = [abs(v / scale) for v in residual.coefficients.values()]
        if any(v <= 1e-12 for v in scaled) or abs(residual.constant / scale) >= 1e19:
            raise UnsupportedProblem(
                "affine row exceeds the supported HiGHS numerical scaling range"
            )
        return (Row(item, node.operator, residual, scale),)


def compile(
    prepared: Prepared,
    *,
    checkpoint: Callable[[], None] = lambda: None,
    constraint_limit: int | None = None,
) -> Compiled:
    """Produce immutable affine rows, retaining scoped diagnostics on capability errors."""
    compiler = Compiler(prepared, checkpoint)
    rows: list[Row] = []
    for item in prepared.assertions:
        checkpoint()
        try:
            rows.extend(compiler.assertion(item))
            if constraint_limit is not None and len(rows) > constraint_limit:
                raise UnsupportedProblem("expanded constraint limit exceeded")
        except UnsupportedProblem as error:
            raise UnsupportedProblem(
                str(error), document=item.document, target=item.constraint.id
            ) from error
    return Compiled(prepared, tuple(rows))
