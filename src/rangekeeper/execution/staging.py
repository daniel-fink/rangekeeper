"""Staged solve: determine values from the affine rows, then retry the other rows.

A row that is not affine under the fixed values, such as
``effective_income = rent_factor * reference_income``, can become affine when
other rows determine one of its unknowns. ``stage`` builds the problem of the
affine rows, reads its rank analysis, and solves it with the backend when it
determines an unknown of a deferred row. The determined values become fixed
values of the next stage. The last stage is one affine problem over the
unknowns that remain; verification then checks every original row.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from uuid import UUID

from rangekeeper.execution.backends.base import BackendResult, Termination
from rangekeeper.execution.compiler import AffineProblem, Compiler, build_problem
from rangekeeper.execution.errors import UnsupportedError
from rangekeeper.execution.preparation import Assertion, Binding
from rangekeeper.execution.settings import Limits
from rangekeeper.quantity import Quantity
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import Expression, ExpressionKind


@dataclass(frozen=True)
class Staged:
    """The problem that the backend solves last, and the values found before it.

    ``problem`` is the affine problem over the unknowns that remain, with the
    determined values fixed and the rows that they satisfy removed.
    ``determined`` maps each unknown that an earlier stage determined to its
    value, in its Measure units. ``stage_count`` is the number of earlier
    stages; the Run's trace records each of them. ``ended`` is the result of
    an earlier stage that ended the solve, for example a proof of
    infeasibility; ``problem`` is then that stage's problem.
    """

    problem: AffineProblem
    determined: Mapping[UUID, float]
    stage_count: int = 0
    ended: BackendResult | None = None


def stage(
    binding: Binding,
    *,
    solve: Callable[[AffineProblem], BackendResult],
    limits: Limits | None = None,
    checkpoint: Callable[[], None] = lambda: None,
) -> Staged:
    """Determine values stage by stage until every remaining row is affine.

    Without a deferred row, this is ``build_problem(binding=binding)``. Otherwise each
    stage builds the problem of the affine rows and solves it with ``solve``
    only when its rank analysis determines an unknown of a deferred row. A
    stage that determines none of them raises the UnsupportedError of the
    first deferred row, as ``build_problem`` does. A stage whose backend
    result is not a feasible candidate ends the solve with that result.
    """
    try:
        return Staged(
            build_problem(binding=binding, limits=limits, checkpoint=checkpoint),
            MappingProxyType({}),
        )
    except UnsupportedError:
        pass  # a row is not affine; stage the solve
    current, determined, count = binding, dict[UUID, float](), 0
    while True:
        checkpoint()
        deferred = _deferred(current, checkpoint)
        if not deferred:
            final = _remaining(current, determined) if determined else current
            return Staged(
                build_problem(binding=final, limits=limits, checkpoint=checkpoint),
                MappingProxyType(determined),
                count,
            )
        affine = tuple(
            item
            for index, item in enumerate(current.assertions)
            if index not in deferred
        )
        problem = build_problem(
            binding=replace(current, assertions=affine),
            limits=limits,
            checkpoint=checkpoint,
        )
        free = set(problem.analysis.undetermined)
        needed = {
            id
            for index in deferred
            for id in _references(current.assertions[index].predicate)
        }
        known = tuple(id for id in problem.variables if id not in free)
        if not needed & set(known):
            # No stage can help: build_problem raises the first deferred row's
            # UnsupportedError, scoped to its declaration.
            build_problem(binding=current, limits=limits, checkpoint=checkpoint)
            raise AssertionError("a deferred row lowered")  # pragma: no cover
        result = solve(problem)
        count += 1
        if result.termination is not Termination.FEASIBLE or result.candidate is None:
            return Staged(problem, MappingProxyType(determined), count, ended=result)
        values = {id: result.candidate[id] for id in known}
        determined.update(values)
        current = _fix(current, values)


def _deferred(binding: Binding, checkpoint: Callable[[], None]) -> frozenset[int]:
    """Return the positions of the assertions that are not affine under ``binding``."""
    compiler = Compiler(binding, checkpoint)
    found = set()
    for index, item in enumerate(binding.assertions):
        try:
            compiler.assertion(item)
        except UnsupportedError:
            found.add(index)
    return frozenset(found)


def _fix(binding: Binding, values: Mapping[UUID, float]) -> Binding:
    """Return ``binding`` with these unknowns fixed to their values."""
    assignments = dict(binding.assignments)
    for id, value in values.items():
        assignments[id] = Quantity(magnitude=value, units=binding.value_units[id])
    return replace(
        binding,
        assignments=MappingProxyType(assignments),
        unknowns=tuple(id for id in binding.unknowns if id not in values),
    )


def _remaining(binding: Binding, determined: Mapping[UUID, float]) -> Binding:
    """Return ``binding`` without the assertions that determined values satisfy.

    These are the assertions that reference a determined value and no unknown
    that remains. An earlier stage satisfied them within the backend's
    tolerance; verification checks them again against the original
    expressions.
    """
    unknowns = set(binding.unknowns)

    def kept(item: Assertion) -> bool:
        found = _references(item.predicate)
        return bool(found & unknowns) or not found & determined.keys()

    return replace(
        binding, assertions=tuple(item for item in binding.assertions if kept(item))
    )


def _references(node: Expression) -> set[UUID]:
    return {
        child.target.target
        for child, _, _ in walk(node)
        if isinstance(child, Expression)
        and child.kind is ExpressionKind.REFERENCE
        and child.target is not None
    }
