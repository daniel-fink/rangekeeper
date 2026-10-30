"""Staged solve: determine values from the affine rows, then retry the other rows.

A row that is not affine under the fixed values, such as
``effective_income = rent_factor * reference_income``, can become affine when
other rows determine one of its unknowns. ``stage`` builds the problem of the
affine rows, reads its rank analysis, and solves it with the backend when it
determines an unknown of a deferred row. The determined values become fixed
values of the next stage. The last stage is one affine problem over the
unknowns that remain; verification then checks every original row.

A ``max`` or ``min`` call that reads an unknown is affine once one operand is
its active side (``execution.piecewise``). ``stage`` then picks the sides
first, solves the affine problem of those sides and checks them at its
solution, round by round (#308).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from uuid import UUID

from rangekeeper.execution.backends.base import BackendResult, Termination
from rangekeeper.execution.compiler import AffineProblem, Compiler, build_problem
from rangekeeper.execution.errors import NumericalError, UnsupportedError
from rangekeeper.execution.piecewise import (
    Pieces,
    Sides,
    bounds,
    chosen,
    disagreeing,
    open_calls,
    opened,
    sides,
    varying,
)
from rangekeeper.execution.preparation import Assertion, Binding
from rangekeeper.execution.settings import Limits
from rangekeeper.quantity import Quantity
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import Expression, ExpressionKind
from rangekeeper.shared.codes import Code

ROUNDS = 20
"""The most sets of sides that one solve tries before it reports ``active_side``."""


@dataclass(frozen=True)
class Staged:
    """The problem that the backend solves last, and the values found before it.

    ``problem`` is the affine problem over the unknowns that remain, with the
    determined values fixed and the rows that they satisfy removed.
    ``determined`` maps each unknown that an earlier stage determined to its
    value, in its Measure units. ``stage_count`` is the number of earlier
    stages; the Run's trace records each of them. ``ended`` is the result of
    an earlier stage that ended the solve, for example a proof of
    infeasibility; ``problem`` is then that stage's problem. ``sides`` gives
    the active side of each ``max`` and ``min`` call that reads an unknown,
    and ``rounds`` the number of sets of sides that the solve tried.
    """

    problem: AffineProblem
    determined: Mapping[UUID, float]
    stage_count: int = 0
    ended: BackendResult | None = None
    sides: Sides = field(default_factory=lambda: MappingProxyType({}))
    rounds: int = 0


def _nothing() -> None:
    """Check no deadline."""


def stage(
    binding: Binding,
    *,
    solve: Callable[[AffineProblem], BackendResult],
    limits: Limits | None = None,
    checkpoint: Callable[[], None] = _nothing,
) -> Staged:
    """Determine values stage by stage until every remaining row is affine.

    Without a deferred row, this is ``build_problem(binding=binding)``. Otherwise each
    stage builds the problem of the affine rows and solves it with ``solve``
    only when its rank analysis determines an unknown of a deferred row. A
    stage that determines none of them raises the UnsupportedError of the
    first deferred row, as ``build_problem`` does. A stage whose backend
    result is not a feasible candidate ends the solve with that result.

    With a ``max`` or ``min`` call that reads an unknown, the stages run for
    each set of active sides that ``_ActiveSides`` tries.
    """
    pieces = Pieces.of(binding.model)
    if open_calls(binding, pieces=pieces):
        return _ActiveSides(
            binding=binding,
            pieces=pieces,
            solve=solve,
            limits=limits,
            checkpoint=checkpoint,
        ).run()
    return _stages(binding, solve=solve, limits=limits, checkpoint=checkpoint)


def _stages(
    binding: Binding,
    *,
    solve: Callable[[AffineProblem], BackendResult],
    limits: Limits | None,
    checkpoint: Callable[[], None],
) -> Staged:
    """Return the problem of the last stage; see ``stage``."""
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


@dataclass(frozen=True)
class _Round:
    """One set of sides, the stages of its affine problem and its last result."""

    sides: Sides
    staged: Staged
    result: BackendResult

    @property
    def solved(self) -> bool:
        """Return whether the round ended with a feasible candidate."""
        return (
            self.result.termination is Termination.FEASIBLE
            and self.result.candidate is not None
        )

    def solution(self, binding: Binding) -> dict[UUID, Quantity]:
        """Return the fixed values and the round's value of each unknown."""
        candidate = self.result.candidate or {}
        return _values(binding, {**candidate, **self.staged.determined})


@dataclass(frozen=True, kw_only=True)
class _ActiveSides:
    """Pick the active side of each ``max`` and ``min`` call, solve, and check them.

    The first sides are the active sides where each unknown is zero. Each round
    solves the affine problem of its sides, in stages, and reads the sides that
    are active at its solution; a side that holds within the tie tolerance
    stays. When they are the sides of the round, the last problem is that of
    those sides, with the bounds that keep them active.

    A side that reads no unknown can make the affine problem infeasible, as
    ``30 AUD = max(0 AUD, need - equity)`` with the side ``0 AUD``. After an
    infeasible round, each such call takes its active side among the operands
    that read an unknown (``piecewise.varying``), and the next round tries
    those sides. A round that ends with a limit or a failure ends the solve
    with its result. An infeasible round with no such call proves nothing
    about other sides: the solve is infeasible only when the rows without an
    open call are infeasible on their own. Otherwise, and for sides that
    repeat or ``ROUNDS`` rounds without agreement, it raises NumericalError
    with the code ``active_side``.
    """

    binding: Binding
    pieces: Pieces
    solve: Callable[[AffineProblem], BackendResult]
    limits: Limits | None
    checkpoint: Callable[[], None]

    def run(self) -> Staged:
        """Return the last problem of the sides that hold at their own solution."""
        tried: list[Sides] = []
        start = _values(self.binding, {})
        current: Sides = self.sides(start)
        count = 0
        solution: Mapping[UUID, Quantity] | None = None
        while current not in tried and len(tried) < ROUNDS:
            tried.append(current)
            found = self.round(current)
            count += found.staged.stage_count + (found.staged.ended is None)
            if not found.solved:
                current = self.varying(found, values=start)
                if current == found.sides:
                    return self.unsolved(found, count=count, rounds=len(tried))
                solution = None
                continue
            start = solution = found.solution(self.binding)
            current = self.sides(solution, prefer=found.sides)
            if current == found.sides:
                return self.last(current, count=count, rounds=len(tried))
        raise self.disagreement(tried[-1], values=solution, rounds=len(tried))

    def sides(
        self, values: Mapping[UUID, Quantity], *, prefer: Sides | None = None
    ) -> Sides:
        """Return the active sides at ``values``, keeping each preferred side that holds."""
        return MappingProxyType(
            sides(
                self.binding,
                pieces=self.pieces,
                values=values,
                prefer=prefer or MappingProxyType({}),
            )
        )

    def varying(self, found: _Round, *, values: Mapping[UUID, Quantity]) -> Sides:
        """Return the sides that follow an infeasible round, else its own sides.

        Each call whose side reads no unknown takes its active side, at
        ``values``, among the operands that read one.
        """
        if found.result.termination is not Termination.INFEASIBLE:
            return found.sides
        return MappingProxyType(
            varying(self.binding, pieces=self.pieces, sides=found.sides, values=values)
        )

    def opened(self) -> tuple[bool, ...]:
        """Return, for each assertion, whether a call in it reads an unknown."""
        return opened(self.binding, pieces=self.pieces)

    def stages(self, binding: Binding) -> Staged:
        """Return the last stage of ``binding``, which has no open call."""
        return _stages(
            binding, solve=self.solve, limits=self.limits, checkpoint=self.checkpoint
        )

    def round(self, current: Sides) -> _Round:
        """Solve the affine problem of one set of sides, in stages."""
        self.checkpoint()
        staged = self.stages(chosen(self.binding, pieces=self.pieces, sides=current))
        result = staged.ended or self.solve(staged.problem)
        return _Round(sides=current, staged=staged, result=result)

    def last(self, current: Sides, *, count: int, rounds: int) -> Staged:
        """Return the problem of the sides that hold, with the bounds that keep them."""
        reduced = chosen(self.binding, pieces=self.pieces, sides=current)
        kept = bounds(self.binding, pieces=self.pieces, sides=current)
        last = self.stages(replace(reduced, assertions=reduced.assertions + kept))
        return replace(
            last, stage_count=count + last.stage_count, sides=current, rounds=rounds
        )

    def unsolved(self, found: _Round, *, count: int, rounds: int) -> Staged:
        """End a round whose result is not a feasible candidate.

        A limit or a failure ends the solve with that result. An infeasible
        round ends it with the proof of ``proof``, or raises ``disagreement``.
        """
        staged = found.staged
        if found.result.termination is Termination.INFEASIBLE:
            proof = self.proof()
            if proof is None:
                raise self.disagreement(found.sides, values=None, rounds=rounds)
            staged, count = proof, count + proof.stage_count + 1
        return replace(
            staged,
            stage_count=count,
            ended=staged.ended or found.result,
            sides=found.sides,
            rounds=rounds,
        )

    def proof(self) -> Staged | None:
        """Return the infeasible stage of the rows without an open call, or None."""
        rest = tuple(
            item
            for item, is_open in zip(
                self.binding.assertions, self.opened(), strict=True
            )
            if not is_open
        )
        try:
            staged = self.stages(replace(self.binding, assertions=rest))
        except UnsupportedError:
            return None
        result = staged.ended or self.solve(staged.problem)
        if result.termination is not Termination.INFEASIBLE:
            return None
        return replace(staged, ended=result)

    def disagreement(
        self, current: Sides, *, values: Mapping[UUID, Quantity] | None, rounds: int
    ) -> NumericalError:
        """Return the error for sides that do not hold at the solution of their round.

        It names the equations whose sides disagree at ``values``; without
        ``values``, the round was infeasible, and it names each equation with
        a call that reads an unknown.
        """
        binding = self.binding
        if values is None:
            items: tuple[Assertion, ...] = tuple(
                item
                for item, is_open in zip(binding.assertions, self.opened(), strict=True)
                if is_open
            )
            reason = "the affine problem of its sides is infeasible"
        else:
            items = disagreeing(
                binding, pieces=self.pieces, sides=current, values=values
            )
            reason = "the sides disagree at the solution"
        equations = "; ".join(f'"{binding.text(item.predicate)}"' for item in items)
        return NumericalError(
            f"No active side of each max or min held after {rounds} rounds:"
            f" {reason} of {equations}. This does not prove that the equations"
            " are infeasible.",
            code=Code.ACTIVE_SIDE,
            document_id=items[0].document if items else None,
            targets=tuple(dict.fromkeys(item.constraint.id for item in items)),
        )


def _values(binding: Binding, solved: Mapping[UUID, float]) -> dict[UUID, Quantity]:
    """Return the fixed values, and each unknown at its solved value or zero."""
    values = dict(binding.assignments)
    for id in binding.unknowns:
        values[id] = Quantity(
            magnitude=solved.get(id, 0.0), units=binding.value_units[id]
        )
    return values


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
