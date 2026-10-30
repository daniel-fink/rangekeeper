"""Replay a stored Run: solve its Specification again and compare the results.

This is the replay of a Run. It is not the path replay of ``rangekeeper.market``
(``market.replay``), which checks captured market paths against their captured
inputs and solves nothing.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from itertools import zip_longest
from typing import Self
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.execution.acceptance import Tolerances
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.pipeline import solve
from rangekeeper.flow import Movement
from rangekeeper.model import Model
from rangekeeper.quantity import Quantity, isclose
from rangekeeper.run import Run, Severity
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import Diagnostic, Value, ValueKind
from rangekeeper.schema.runtime import JSONValue
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, UnitError
from rangekeeper.shared.references import DocumentResolver

__all__ = ["Replay", "replay"]

Recorded = Quantity | DateValue | None
"""One recorded amount or date of a Value: a scalar, a date or NEVER, or None."""


def replay(
    *,
    run: Run,
    store: DocumentResolver,
    config: ExecutionConfig | None = None,
) -> "Replay":
    """Solve the Specification of a stored Run again, and compare the results.

    ``store`` holds the Run's documents: its Specification and the documents
    that it names, its case Runs and its outputs, as ``execute`` puts them.
    Replay reads them and writes nothing. It solves the Specification with
    ``store`` as resolver and with ``config``, as ``solve`` does; give the
    configuration of the execution that made the Run. It then compares each
    case of the new Outcome with the stored case of the same key: the status,
    the number of outputs, and each value of the output Model, within the
    tolerances of ``config.tolerances``. Dates compare exactly.

    The returned ``Replay`` holds the stored Outcome, the new Outcome and one
    ``replay_mismatch`` diagnostic for each difference;
    ``raise_for_status()`` raises the first. Missing documents raise
    MissingReferenceError, as for ``solve``.
    """
    if not isinstance(run, Run):
        raise TypeError("run must be a Run")
    config = ExecutionConfig() if config is None else config
    stored = _stored(run, store, models={})
    specification = store.load_specification(run.record.specification)
    outcome = solve(specification=specification, resolver=store, config=config)
    return Replay._of(
        stored=stored,
        outcome=outcome,
        diagnostics=tuple(_differences(stored, outcome, tolerances=config.tolerances)),
    )


@dataclass(frozen=True, kw_only=True, init=False, repr=False)
class Replay:
    """A stored Run, solved again, and the differences between the two results.

    Make it with ``rk.execution.replay``. ``stored`` is the Outcome that the
    store holds: the stored Run, its outputs and its cases. ``outcome`` is the
    Outcome of the new solve; it is not stored. ``diagnostics`` has one
    diagnostic with the code ``replay_mismatch`` for each difference, in case
    order; it is empty when the replay gives the stored result. Each
    diagnostic's ``values`` name the ``case`` (None for a leaf Run), the
    ``key`` of the value, the coordinate ``on`` of a Flow amount, and the
    ``stored`` and ``replayed`` results as text.
    """

    stored: Outcome
    outcome: Outcome
    diagnostics: tuple[Diagnostic, ...]

    @classmethod
    def _of(
        cls,
        *,
        stored: Outcome,
        outcome: Outcome,
        diagnostics: tuple[Diagnostic, ...],
    ) -> Self:
        made = object.__new__(cls)
        object.__setattr__(made, "stored", stored)
        object.__setattr__(made, "outcome", outcome)
        object.__setattr__(made, "diagnostics", diagnostics)
        return made

    def raise_for_status(self) -> Self:
        """Return this Replay when it gives the stored result; otherwise raise.

        The first difference raises ContractError with the code
        ``REPLAY_MISMATCH``, the stored Run as ``document_id`` and the
        diagnostic's ``values``.
        """
        if not self.diagnostics:
            return self
        first = self.diagnostics[0]
        raise ContractError(
            f"the replay differs from the stored Run: {first.message}",
            code=Code.REPLAY_MISMATCH,
            document_id=self.stored.run.id,
            values=dict(first.values) if isinstance(first.values, Mapping) else {},
        )

    def __repr__(self) -> str:
        return f"Replay(run={self.stored.run.id}, differences={len(self.diagnostics)})"


def _stored(run: Run, store: DocumentResolver, *, models: dict[UUID, Model]) -> Outcome:
    """Return the Outcome of a stored Run: its outputs and its case Outcomes.

    ``models`` keeps each output Model that is read, so that a batch and its
    case read it once.
    """
    for identity in run.record.outputs or ():
        if identity not in models:
            models[identity] = store.load_model(identity)
    return Outcome(
        run=run,
        outputs=tuple(models[identity] for identity in run.record.outputs or ()),
        cases=tuple(
            _stored(store.load_run(identity), store, models=models)
            for identity in run.record.spawns or ()
        ),
        key=store.load_specification(run.record.specification).metadata.name,
    )


def _leaves(
    outcome: Outcome,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[str | None, Outcome]]:
    """Yield each leaf case with its case key, as ``Outcome.table`` names it."""
    if not outcome.cases:
        yield ("/".join(path) if path else None), outcome
        return
    for position, case in enumerate(outcome.cases):
        yield from _leaves(case, (*path, case.key or str(position)))


def _differences(
    stored: Outcome,
    replayed: Outcome,
    *,
    tolerances: Tolerances,
) -> Iterator[Diagnostic]:
    """Yield one ``replay_mismatch`` diagnostic for each difference, case by case."""
    before = dict(_leaves(stored))
    after = dict(_leaves(replayed))
    if list(before) != list(after):
        yield _mismatch(
            "the replay has other cases",
            stored=[str(key) for key in before],
            replayed=[str(key) for key in after],
        )
        return
    for case, old in before.items():
        yield from _case_differences(case, old, after[case], tolerances=tolerances)


def _case_differences(
    case: str | None,
    stored: Outcome,
    replayed: Outcome,
    *,
    tolerances: Tolerances,
) -> Iterator[Diagnostic]:
    """Yield the differences of one case: status, outputs, then each value."""
    if stored.status is not replayed.status:
        yield _mismatch(
            f"{_named(case)} is {replayed.status.value}, not {stored.status.value}",
            case=case,
            stored=stored.status.value,
            replayed=replayed.status.value,
        )
        return
    if len(stored.outputs) != len(replayed.outputs):
        yield _mismatch(
            f"{_named(case)} has {len(replayed.outputs)} outputs, "
            f"not {len(stored.outputs)}",
            case=case,
            stored=len(stored.outputs),
            replayed=len(replayed.outputs),
        )
        return
    for old, new in zip(stored.outputs, replayed.outputs, strict=True):
        yield from _model_differences(case, old, new, tolerances=tolerances)


def _model_differences(
    case: str | None,
    stored: Model,
    replayed: Model,
    *,
    tolerances: Tolerances,
) -> Iterator[Diagnostic]:
    """Yield the first difference of each recorded Value of the stored Model."""
    if stored.system is None:
        return
    for record, _, _ in walk(stored.system):
        if not isinstance(record, Value):
            continue
        key = stored.key_of(record.id)
        old = _items(stored, record.id)
        new = _items(replayed, record.id)
        for (on, before), (where, now) in zip_longest(old, new, fillvalue=(None, None)):
            if on != where or not _agree(before, now, tolerances=tolerances):
                yield _mismatch(
                    f"{key} of {_named(case)} is {_text(now)}, not {_text(before)}",
                    case=case,
                    key=key,
                    **_on(on if on is not None else where),
                    stored=_text(before),
                    replayed=_text(now),
                )
                break


def _items(model: Model, id: UUID) -> list[tuple[str | None, Recorded]]:
    """Return the recorded results of a Value, each with its coordinate.

    A scalar or a date Value has one result, with no coordinate. A Flow has
    one result for each Movement, with its Period or date as ISO text.
    """
    value = model.value(id=id)
    if value.flow is not None:
        return [
            (_coordinate(movement), _amount(movement, value.flow.units))
            for movement in value.flow.movements
        ]
    if value.kind is ValueKind.DATE:
        return [(None, NEVER if value.never is not None else value.date)]
    return [(None, value.quantity)]


def _coordinate(movement: Movement) -> str:
    """Return the Period of a Movement as an ISO interval, else its date."""
    if movement.period is not None:
        return f"{movement.period.start.isoformat()}/{movement.period.end.isoformat()}"
    return str(movement.date)


def _amount(movement: Movement, units: str) -> Quantity | None:
    """Return the amount of a Movement, or None when it is unresolved."""
    if movement.magnitude is None:
        return None
    return Quantity(magnitude=movement.magnitude, units=units)


def _agree(stored: Recorded, replayed: Recorded, *, tolerances: Tolerances) -> bool:
    """Return whether two results agree: amounts within the tolerances."""
    if isinstance(stored, Quantity) and isinstance(replayed, Quantity):
        try:
            return isclose(
                actual=replayed,
                expected=stored,
                tolerance=Quantity(magnitude=tolerances.absolute, units=stored.units),
                relative=tolerances.relative,
            )
        except UnitError:
            return False
    return type(stored) is type(replayed) and stored == replayed


def _on(coordinate: str | None) -> dict[str, JSONValue]:
    """Return the ``on`` value of a Flow amount's diagnostic; a scalar has none."""
    return {} if coordinate is None else {"on": coordinate}


def _text(result: Recorded) -> str | None:
    if result is None:
        return None
    if result is NEVER:
        return "never"
    if isinstance(result, Quantity):
        return str(result)
    return result.isoformat()


def _named(case: str | None) -> str:
    return "the Run" if case is None else f"case {case}"


def _mismatch(message: str, **values: JSONValue) -> Diagnostic:
    return Diagnostic(
        severity=Severity.ERROR,
        code=Code.REPLAY_MISMATCH.value,
        message=message,
        values=values,
    )
