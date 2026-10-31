"""One provisional solve: the affine stages with the current decided values fixed."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from uuid import UUID

from rangekeeper.duration.dates import DateValue
from rangekeeper.execution import dates, expansion, staging
from rangekeeper.execution.backends import Backend
from rangekeeper.execution.backends.base import BackendResult, Termination
from rangekeeper.execution.compiler import AffineProblem
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.preparation import Binding
from rangekeeper.execution.settings import Limits
from rangekeeper.model.targets import target_units
from rangekeeper.quantity import Quantity
from rangekeeper.schema.records import ExpressionKind, Reference
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import DecisionError, NumericalError


@dataclass(frozen=True, kw_only=True)
class Solution:
    """The values of one provisional solve: ``values`` by token, ``dates`` by Value."""

    values: Mapping[UUID, Quantity]
    dates: Mapping[UUID, DateValue]


def with_values(
    binding: Binding, *, values: Mapping[UUID, Quantity | DateValue]
) -> Binding:
    """Return ``binding`` with each given value fixed: a fixed value in the problem.

    A decided value is free in the binding of its case. A rule fixes it here, so
    the affine problem never contains a rule (ADR-021).
    """
    fixed = set(values)
    assignments = dict(binding.assignments)
    decided_dates = dict(binding.dates)
    # A decided value that no equation reads has no reference or units yet.
    references = dict(binding.references)
    units = dict(binding.value_units)
    for token, value in values.items():
        reference = references.setdefault(token, Reference(target=token))
        if isinstance(value, Quantity):
            into = units.setdefault(token, target_units(binding.model, reference))
            assignments[token] = binding.units.convert(quantity=value, to=into)
        else:
            decided_dates[token] = value
    return replace(
        binding,
        assignments=MappingProxyType(assignments),
        dates=MappingProxyType(decided_dates),
        references=MappingProxyType(references),
        value_units=MappingProxyType(units),
        unknowns=tuple(token for token in binding.unknowns if token not in fixed),
        date_unknowns=tuple(
            token for token in binding.date_unknowns if token not in fixed
        ),
    )


def solve(
    binding: Binding,
    *,
    backend: Backend,
    config: ExecutionConfig,
    limits: Limits,
    remaining: Callable[[], float],
    checkpoint: Callable[[], None],
) -> Solution:
    """Solve ``binding`` as the stages do; the result is not a candidate.

    A date constraint that the fixed dates break, and a problem that the backend
    proves infeasible, raise DecisionError with ``provisional_infeasible``, whose
    ``values`` name the constraints that it knows. Another ending raises
    NumericalError.
    """
    settled = dates.settle(binding)
    _check_dates(binding, settled=settled)
    expanded = expansion.expand(settled)

    def run(problem: AffineProblem) -> BackendResult:
        return backend.solve(
            problem=problem,
            limits=limits,
            remaining=remaining(),
            options=config.backend_options,
        )

    staged = staging.stage(expanded, solve=run, limits=limits, checkpoint=checkpoint)
    result = staged.ended if staged.ended is not None else run(staged.problem)
    if result.termination is Termination.INFEASIBLE:
        raise DecisionError(
            "the provisional problem is infeasible under the decisions so far",
            code=Code.PROVISIONAL_INFEASIBLE,
            values={"constraints": []},
        )
    if result.termination is not Termination.FEASIBLE or result.candidate is None:
        raise NumericalError(
            f"the provisional solve ended {result.termination.value}, with no solution"
        )
    solved = {**result.candidate, **staged.determined}
    values = dict(expanded.assignments)
    for token, magnitude in solved.items():
        values[token] = Quantity(
            magnitude=float(magnitude), units=expanded.value_units[token]
        )
    return Solution(values=values, dates=settled.dates)


def _check_dates(binding: Binding, *, settled: Binding) -> None:
    """Raise when the fixed dates alone break a date constraint, with no solve."""
    original = {item.constraint.id: item for item in binding.assertions}
    broken = [
        binding.text(original[item.constraint.id].predicate)
        for item in settled.assertions
        if item.predicate.kind is ExpressionKind.BOOLEAN and not item.predicate.boolean
    ]
    if broken:
        raise DecisionError(
            "the decisions so far break " + ", ".join(broken),
            code=Code.PROVISIONAL_INFEASIBLE,
            values={"constraints": broken},
        )


__all__ = ["Solution", "solve", "with_values"]
