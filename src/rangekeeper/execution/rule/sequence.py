"""Sequential rule evaluation: the rules stage of ADR-021, for one case.

``run_rules`` processes dates in order and runs the rules in their written order
on each date. It solves the provisional problem only when a rule reads a solved
value and the state changed since the last solve. It returns the decided values
and the trace; the stages then solve once with those values fixed
(``Decisions.bind``), so the affine problem never contains a rule.

The dates are each rule's window dates and the next date of its calendar after
its last window date, on which it takes ``otherwise``. A rule whose calendar ends
takes ``otherwise`` on its last date, after all rules on that date.
"""

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.execution import dates as date_equations
from rangekeeper.execution.acceptance import Tolerances
from rangekeeper.execution.backends import Backend
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.preparation import Binding
from rangekeeper.execution.rule.provisional import Solution, solve, with_values
from rangekeeper.execution.settings import Limits
from rangekeeper.flow import Movement
from rangekeeper.market.paths import Paths
from rangekeeper.model.expression.evaluation import compare_dates, evaluate_date
from rangekeeper.quantity import Quantity
from rangekeeper.run._rule.availability import known_on, path_known
from rangekeeper.run._rule.result import DecisionResult
from rangekeeper.run._rule.trace import (
    Check,
    Reading,
    calendar,
    leaf_name,
    naming,
)
from rangekeeper.run._rule.truth import UNKNOWN, truth
from rangekeeper.schema.enums import ObservationSource, ValueKind
from rangekeeper.schema.records import (
    Expression,
    ExpressionKind,
    Operator,
    Reference,
    Value,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AvailabilityError,
    ContractError,
    DecisionError,
    UnsupportedError,
)
from rangekeeper.specification.rule._query import (
    RuleQuery,
    check_queries,
    definitions,
    dependencies,
    leaves,
    parameter_id,
    read_targets,
    shift_of,
)


@dataclass(frozen=True, kw_only=True)
class Decided:
    """The value that a rule fixed, and its decision date."""

    target: UUID
    key: str
    value: Quantity | DateValue
    on: date


@dataclass(frozen=True, kw_only=True)
class Decisions:
    """The result of the rules stage for one case.

    ``decided`` holds one Decided for each rule, by target, in the written order.
    ``checks`` is the trace. ``solves`` counts the provisional solves; the stages
    add one more. ``solution`` is the last provisional solution, and ``since`` the
    date of the first decision after it: the final candidate must agree with it on
    each Movement before that date. Both are None without a provisional solve.
    """

    decided: Mapping[UUID, Decided]
    checks: tuple[Check, ...]
    solves: int
    solution: Solution | None = None
    since: date | None = None

    def bind(self, binding: Binding) -> Binding:
        """Return ``binding`` with every decided value fixed."""
        return with_values(
            binding, values={item.target: item.value for item in self.decided.values()}
        )


@dataclass(kw_only=True)
class Progress:
    """The trace so far, which a case that fails during its rules still records."""

    checks: list[Check] = field(default_factory=list)
    solves: int = 0


@dataclass(frozen=True, kw_only=True)
class Solver:
    """What a provisional solve uses: the same backend and limits as the case."""

    backend: Backend
    config: ExecutionConfig
    limits: Limits
    checkpoint: Callable[[], None] = lambda: None


def run_rules(
    *,
    binding: Binding,
    rules: Sequence[RuleQuery],
    solver: Solver,
    parameters: Mapping[str, Quantity] | None = None,
    paths: Paths | None = None,
    progress: Progress | None = None,
) -> Decisions:
    """Return the decisions of ``rules`` on one case.

    ``binding`` is the bound case, with each decided value free. ``paths`` is the
    document of the case's path, when it has one. ``progress`` holds the trace as
    it grows, so a caller keeps it when this raises. Static failures of the rules
    raise as ``check_queries`` says; an unavailable observation raises
    AvailabilityError, a decision that moves an earlier date or Movement raises
    DecisionError, and so does an infeasible provisional solve, with the window
    date and the decisions so far in its ``values``.
    """
    rules = tuple(rules)
    fixed = {*binding.assignments, *binding.dates}
    check_queries(rules=rules, model=binding.model, fixed=fixed)
    path = binding.composition.requirements.path
    known = {}
    if path is not None and paths is not None:
        known = dict(path_known(path=path, paths=paths))
    return _Evaluation(
        binding=binding,
        rules=rules,
        parameters=dict(parameters or {}),
        path_known=known,
        solver=solver,
        progress=Progress() if progress is None else progress,
    ).run()


def check_past(
    *,
    binding: Binding,
    decisions: Decisions,
    solved: Mapping[UUID, Quantity | DateValue],
    tolerances: Tolerances,
) -> None:
    """Raise DecisionError when the final values move a Movement of the past."""
    if decisions.solution is None or decisions.since is None:
        return
    _compare_past(
        binding=binding,
        earlier=decisions.solution.values,
        later=solved,
        since=decisions.since,
        decision="the final solve",
        tolerances=tolerances,
    )


def _compare_past(
    *,
    binding: Binding,
    earlier: Mapping[UUID, Quantity | DateValue],
    later: Mapping[UUID, Quantity | DateValue],
    since: date,
    decision: str,
    tolerances: Tolerances,
) -> None:
    for record in binding.model._index.records.values():
        if not isinstance(record, Movement) or not _before(record, since):
            continue
        first, second = earlier.get(record.id), later.get(record.id)
        if not isinstance(first, Quantity) or not isinstance(second, Quantity):
            continue
        gap = abs(first.number - second.number)
        scale = max(abs(first.number), abs(second.number))
        if gap > tolerances.absolute + tolerances.relative * scale:
            key = binding.model.key_of(record.id)
            raise DecisionError(
                f"{decision} changes {key} before {since}",
                document_id=binding.model.id,
                targets=(record.id,),
                values={
                    "decision": decision,
                    "movement": key,
                    "before": since.isoformat(),
                    "earlier": first.number,
                    "later": second.number,
                },
            )


def _before(movement: Movement, on: date) -> bool:
    """Return whether a Movement is wholly before a date."""
    if movement.date is not None:
        return movement.date < on
    assert movement.period is not None
    return movement.period.end <= on


class _Evaluation:
    """The state of one path: the decided values and the provisional solution."""

    def __init__(
        self,
        *,
        binding: Binding,
        rules: tuple[RuleQuery, ...],
        parameters: Mapping[str, Quantity],
        path_known: Mapping[UUID, date],
        solver: Solver,
        progress: Progress,
    ) -> None:
        self.binding = binding
        self.rules = rules
        self.parameters = {parameter_id(k): (k, v) for k, v in parameters.items()}
        self.path_known = path_known
        self.solver = solver
        self.started = time.monotonic()
        self.tolerances = solver.config.tolerances
        self.targets = {rule.target for rule in rules}
        self.keys = {rule.target: _key(binding, rule.target) for rule in rules}
        self.name = naming(model=binding.model, parameters=parameters)
        self.defined = definitions(binding.model)
        self.calendars = {
            rule.target: calendar(rule, model=binding.model, path_known=path_known)
            for rule in rules
        }
        self.decided: dict[UUID, Decided] = {}
        self.progress = progress
        self.solution: Solution | None = None
        self.since: date | None = None
        self.stale = True
        self.certain: tuple[int, Mapping[UUID, DateValue]] | None = None

    def run(self) -> Decisions:
        """Process each date in order until every rule has fixed its value."""
        on = self._next_date(None)
        while on is not None and self._waiting():
            self._date(on)
            following = self._next_date(on)
            if following is None:
                self._finish(on)
            on = following
        if self._waiting():
            keys = [self.keys[rule.target] for rule in self._waiting()]
            raise ContractError(
                "a rule has no window date: give it periods, a bound or a Flow",
                code=Code.RULE_CAPABILITY,
                targets=tuple(rule.target for rule in self._waiting()),
                values={"keys": keys},
            )
        return Decisions(
            decided=MappingProxyType(
                {rule.target: self.decided[rule.target] for rule in self.rules}
            ),
            checks=tuple(self.progress.checks),
            solves=self.progress.solves,
            solution=self.solution,
            since=self.since,
        )

    def _waiting(self) -> tuple[RuleQuery, ...]:
        return tuple(rule for rule in self.rules if rule.target not in self.decided)

    def _date(self, on: date) -> None:
        for rule in self._waiting():
            self._run(rule, on)
        changed = True
        while changed:
            changed = False
            for rule in self._waiting():
                if self._closed_for_good(rule, on):
                    self._otherwise(rule, on)
                    changed = True

    def _finish(self, on: date) -> None:
        """Fix ``otherwise`` for the rules that no later date can reach."""
        for rule in self._waiting():
            self._otherwise(rule, on)

    def _next_date(self, after: date | None) -> date | None:
        found = [
            item
            for rule in self._waiting()
            for item in self._dates_of(rule)
            if after is None or item > after
        ]
        return min(found, default=None)

    def _dates_of(self, rule: RuleQuery) -> tuple[date, ...]:
        """Return the dates that a rule can act on, as far as the state gives them."""
        own = list(self.calendars[rule.target])
        if rule.periods is not None:
            own.append(rule.periods[-1].end)
        elif not own:
            own.extend(self._bound_dates(rule))
        return tuple(own)

    def _bound_dates(self, rule: RuleQuery) -> tuple[date, ...]:
        found = (self._bound(rule.earliest), self._bound(rule.latest))
        return tuple(item for item in found if isinstance(item, date))

    def _run(self, rule: RuleQuery, on: date) -> None:
        earliest, latest = self._bound(rule.earliest), self._bound(rule.latest)
        if self._passed(rule, on, latest=latest):
            self._otherwise(rule, on)
        elif self._is_window_date(rule, on):
            self._check(rule, on, earliest=earliest, latest=latest)

    @staticmethod
    def _passed(rule: RuleQuery, on: date, *, latest: DateValue | None) -> bool:
        if isinstance(latest, date) and latest < on:
            return True
        return rule.periods is not None and rule.periods[-1].end <= on

    def _is_window_date(self, rule: RuleQuery, on: date) -> bool:
        if not self._inside_literal_bounds(rule, on):
            return False
        if on in self.calendars[rule.target]:
            return True
        if rule.periods is not None:
            return False
        if not self.calendars[rule.target] and on in self._bound_dates(rule):
            return True
        return any(
            target in self.decided and self.decided[target].on == on
            for target in read_targets(rule.condition)
        )

    @staticmethod
    def _inside_literal_bounds(rule: RuleQuery, on: date) -> bool:
        for node, within in (
            (rule.earliest, lambda bound: bound <= on),
            (rule.latest, lambda bound: bound >= on),
        ):
            if node is not None and node.kind is ExpressionKind.DATE:
                if node.date is not None and not within(node.date):
                    return False
        return True

    def _closed_for_good(self, rule: RuleQuery, on: date) -> bool:
        """Return whether the state leaves a rule no later date to act on."""
        earliest, latest = self._bound(rule.earliest), self._bound(rule.latest)
        if earliest is NEVER or self._passed(rule, on, latest=latest):
            return True
        if rule.earliest is not None and earliest is None:
            if not self.calendars[rule.target]:
                return False
        if any(
            target in self.targets and target not in self.decided
            for target in read_targets(rule.condition)
        ):
            return False
        return not any(item > on for item in self._dates_of(rule))

    def _check(
        self,
        rule: RuleQuery,
        on: date,
        *,
        earliest: DateValue | None,
        latest: DateValue | None,
    ) -> None:
        key = self.keys[rule.target]
        if not _open(rule, on, earliest=earliest, latest=latest):
            self.progress.checks.append(
                Check(
                    rule=rule.target,
                    key=key,
                    on=on,
                    result=DecisionResult.SKIPPED,
                    earliest=earliest,
                    latest=latest,
                )
            )
            return
        readings = self._readings(rule, on)
        condition = self._truth(rule, readings=readings)
        if condition is True:
            value = rule.then if rule.then is not None else on
            self._fix(rule, on=on, value=value)
        self.progress.checks.append(
            Check(
                rule=rule.target,
                key=key,
                on=on,
                result=(
                    DecisionResult.DECIDED
                    if condition is True
                    else DecisionResult.NOT_MET
                ),
                readings=readings,
                condition=condition,
                earliest=earliest,
                latest=latest,
                value=self.decided[rule.target].value if condition is True else None,
            )
        )

    def _otherwise(self, rule: RuleQuery, on: date) -> None:
        self._fix(rule, on=on, value=rule.otherwise)
        self.progress.checks.append(
            Check(
                rule=rule.target,
                key=self.keys[rule.target],
                on=on,
                result=DecisionResult.OTHERWISE,
                earliest=self._bound(rule.earliest),
                latest=self._bound(rule.latest),
                value=rule.otherwise,
            )
        )

    def _fix(self, rule: RuleQuery, *, on: date, value: Quantity | DateValue) -> None:
        before = self._certain()
        self.decided[rule.target] = Decided(
            target=rule.target, key=self.keys[rule.target], value=value, on=on
        )
        self._check_dates(rule, on=on, before=before)
        self.stale = True
        if self.since is None:
            self.since = on

    def _check_dates(
        self, rule: RuleQuery, *, on: date, before: Mapping[UUID, DateValue]
    ) -> None:
        """Raise when a decision determines a date before its decision date."""
        for token, value in self._certain().items():
            if token in before or not isinstance(value, date) or value >= on:
                continue
            key, moved = self.keys[rule.target], _key(self.binding, token)
            raise DecisionError(
                f"the decision of {key} on {on} moves {moved} to {value}, before it",
                document_id=self.binding.model.id,
                targets=(rule.target, token),
                values={
                    "decision": key,
                    "decision_date": on.isoformat(),
                    "movement": moved,
                    "date": value.isoformat(),
                },
            )

    def _state(self) -> Mapping[UUID, Quantity | DateValue]:
        """Return the fixed values of the current state: undecided, ``otherwise``."""
        return {
            rule.target: (
                self.decided[rule.target].value
                if rule.target in self.decided
                else rule.otherwise
            )
            for rule in self.rules
        }

    def _certain(self) -> Mapping[UUID, DateValue]:
        """Return the dates that fixed and decided dates determine, with no guess."""
        count = len(self.decided)
        if self.certain is None or self.certain[0] != count:
            values = {item.target: item.value for item in self.decided.values()}
            state = with_values(self.binding, values=values)
            self.certain = (count, date_equations.determined(state))
        return self.certain[1]

    def _bound(self, node: Expression | None) -> DateValue | None:
        """Return a bound, or None without one or when it reads an undecided value."""
        if node is None:
            return None
        values: dict[UUID, Quantity | DateValue] = {
            **self.binding.assignments,
            **self._certain(),
            **{token: item[1] for token, item in self.parameters.items()},
        }
        try:
            return evaluate_date(node, values, units=self.binding.units)
        except KeyError:
            return None

    def _readings(self, rule: RuleQuery, on: date) -> tuple[Reading, ...]:
        found: dict[str, Reading] = {}
        for leaf in leaves(rule.condition):
            name = leaf_name(leaf, name=self.name)
            if name not in found:
                found[name] = self._read(leaf, on=on, rule=rule, name=name)
        return tuple(found.values())

    def _truth(self, rule: RuleQuery, *, readings: tuple[Reading, ...]) -> bool | None:
        values = {reading.name: reading.value for reading in readings}

        def read(leaf: Expression) -> Quantity | DateValue | object:
            value = values[leaf_name(leaf, name=self.name)]
            return UNKNOWN if value is None else value

        return truth(rule.condition, read=read, units=self.binding.units)  # type: ignore[arg-type]

    def _read(
        self, leaf: Expression, *, on: date, rule: RuleQuery, name: str
    ) -> Reading:
        shift = shift_of(leaf)
        if shift is not None:
            return self._flow(shift.flow, on=on, by=shift.by, rule=rule, name=name)
        if leaf.kind is ExpressionKind.CALL or leaf.target is None:
            raise UnsupportedError(
                f"the condition of a rule cannot read {name}: it reads values and "
                "flow.shift(by=)",
            )
        return self._value(leaf.target.target, on=on, rule=rule, name=name)

    def _value(self, target: UUID, *, on: date, rule: RuleQuery, name: str) -> Reading:
        if target in self.parameters:
            return Reading(
                name=name,
                target=target,
                value=self.parameters[target][1],
                available_on=None,
                source=ObservationSource.PARAMETER,
            )
        if target in self.targets:
            return self._decided_reading(target, name=name)
        value = self.binding.model.value(id=target)
        if value.kind is ValueKind.FLOW:
            return self._flow(target, on=on, by=0, rule=rule, name=name)
        if value.kind is ValueKind.DATE:
            return self._date_reading(target, name=name)
        return self._scalar(target, on=on, rule=rule, name=name)

    def _decided_reading(self, target: UUID, *, name: str) -> Reading:
        found = self.decided.get(target)
        return Reading(
            name=name,
            target=target,
            value=None if found is None else found.value,
            available_on=None if found is None else found.on,
            source=ObservationSource.DECIDED,
        )

    def _date_reading(self, target: UUID, *, name: str) -> Reading:
        """Read a date: fixed, or determined by decided dates; else undecided."""
        if target in self.binding.dates:
            return Reading(
                name=name,
                target=target,
                value=self.binding.dates[target],
                available_on=None,
                source=ObservationSource.FIXED,
            )
        value = self._certain().get(target)
        reach = dependencies(target, defined=self.defined) & self.decided.keys()
        return Reading(
            name=name,
            target=target,
            value=value,
            available_on=max((self.decided[t].on for t in reach), default=None),
            source=ObservationSource.SOLVED,
        )

    def _scalar(self, target: UUID, *, on: date, rule: RuleQuery, name: str) -> Reading:
        if target in self.binding.assignments:
            return Reading(
                name=name,
                target=target,
                value=self.binding.assignments[target],
                available_on=None,
                source=ObservationSource.FIXED,
            )
        known = self._require_inputs(target, on=on, rule=rule)
        solved = self._solved(on)
        return Reading(
            name=name,
            target=target,
            value=solved.values[target],
            available_on=known,
            source=ObservationSource.SOLVED,
        )

    def _require_inputs(
        self, target: UUID, *, on: date, rule: RuleQuery
    ) -> date | None:
        """Raise when a solved scalar depends on a Movement that is not yet known."""
        latest: date | None = None
        for item in dependencies(target, defined=self.defined):
            record = self.binding.model._index.records.get(item)
            if not isinstance(record, Value) or record.flow is None:
                continue
            for movement in record.flow.movements:
                known = self._known(movement)
                if known > on:
                    self._unavailable(rule, target, on=on, available_on=known)
                latest = known if latest is None else max(known, latest)
        return latest

    def _known(self, movement: Movement) -> date:
        return self.path_known.get(movement.id, known_on(movement))

    def _unavailable(
        self, rule: RuleQuery, target: UUID, *, on: date, available_on: date | None
    ) -> None:
        key = self.keys[rule.target]
        read = self.binding.model.key_of(target)
        raise AvailabilityError(
            f"the rule for {key} reads {read} on {on}, before it is known",
            key=key,
            available_on=available_on,
            decision_date=on,
            document_id=self.binding.model.id,
            targets=(rule.target, target),
        )

    def _flow(
        self, target: UUID, *, on: date, by: int, rule: RuleQuery, name: str
    ) -> Reading:
        """Read the Movement ``by`` Periods before the latest one known on ``on``."""
        value = self.binding.model.value(id=target)
        assert value.flow is not None
        movements = sorted(value.flow.movements, key=self._known)
        position = sum(self._known(m) <= on for m in movements) - 1 - by
        if position < 0 or position >= len(movements):
            soonest = movements[by] if 0 <= by < len(movements) else None
            self._unavailable(
                rule,
                target,
                on=on,
                available_on=None if soonest is None else self._known(soonest),
            )
        movement = movements[position]
        if self._known(movement) > on:
            self._unavailable(rule, target, on=on, available_on=self._known(movement))
        return Reading(
            name=name,
            target=movement.id,
            value=self._amount(movement, on=on),
            available_on=self._known(movement),
            source=self._source(movement),
        )

    def _source(self, movement: Movement) -> ObservationSource:
        if movement.id in self.path_known:
            return ObservationSource.PATH
        if movement.id in self.binding.assignments:
            return ObservationSource.FIXED
        return ObservationSource.SOLVED

    def _amount(self, movement: Movement, *, on: date) -> Quantity:
        if movement.id in self.binding.assignments:
            return self.binding.assignments[movement.id]
        return self._solved(on).values[movement.id]

    def _provisional(self, state: Binding) -> Solution:
        limits = self.solver.limits
        return solve(
            state,
            backend=self.solver.backend,
            config=self.solver.config,
            limits=limits,
            remaining=lambda: limits.time_limit - (time.monotonic() - self.started),
            checkpoint=self.solver.checkpoint,
        )

    def _named_state(self, on: date) -> Mapping[str, object]:
        """Return the window date and the decisions so far, for a diagnostic."""
        return {
            "window_date": on.isoformat(),
            "decided": {item.key: _text(item.value) for item in self.decided.values()},
        }

    def _solved(self, on: date) -> Solution:
        """Return the provisional solution of the current state, solving when stale."""
        if self.solution is not None and not self.stale:
            return self.solution
        state = with_values(self.binding, values=self._state())
        try:
            new = self._provisional(state)
        except DecisionError as error:
            error.values = {**error.values, **self._named_state(on)}
            raise
        self.progress.solves += 1
        if self.solution is not None and self.since is not None:
            _compare_past(
                binding=self.binding,
                earlier=self.solution.values,
                later=new.values,
                since=self.since,
                decision=f"the decisions up to {on}",
                tolerances=self.tolerances,
            )
        self.solution, self.stale, self.since = new, False, None
        return new


def _text(value: Quantity | DateValue) -> str:
    return "NEVER" if value is NEVER else str(value)


def _open(
    rule: RuleQuery, on: date, *, earliest: DateValue | None, latest: DateValue | None
) -> bool:
    """Return whether a window date is open: ADR-021, evaluation order, step 2."""
    if rule.earliest is not None and (
        earliest is None or not compare_dates(Operator.LESS_THAN_OR_EQUAL, earliest, on)
    ):
        return False
    return latest is None or compare_dates(Operator.GREATER_THAN_OR_EQUAL, latest, on)


def _key(binding: Binding, token: UUID) -> str:
    return binding.key(binding.references.get(token) or Reference(target=token))


__all__ = ["Decided", "Decisions", "Progress", "Solver", "check_past", "run_rules"]
