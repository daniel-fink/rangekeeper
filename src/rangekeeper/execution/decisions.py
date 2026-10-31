"""Read the decision traces of an Outcome: ``outcome.decisions`` and ``.trace``."""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.quantity import Quantity
from rangekeeper.run._rule.result import DecisionResult
from rangekeeper.run._rule.stored import read_checks
from rangekeeper.run._rule.trace import Check
from rangekeeper.schema.enums import ObservationSource
from rangekeeper.schema.records import RuleEvidence
from rangekeeper.shared.errors import MissingReferenceError
from rangekeeper.shared.table import Table

Read = Quantity | DateValue | None
"""A value that a rule read or fixed; None when it was undecided, or fixed nothing."""


@dataclass(frozen=True, kw_only=True)
class ObservationRow:
    """One value that a rule read on a window date, with its availability date."""

    case: str | None
    key: str
    decision_date: date
    name: str
    target: UUID
    value: Quantity | DateValue
    available_on: date
    source: ObservationSource


@dataclass(frozen=True, kw_only=True)
class DecisionRow:
    """One record of a decision trace: a case, a rule and a window date.

    ``decision_date`` is the window date, or the date on which the rule took
    ``otherwise``. ``condition`` is None when it is unknown, or when the record
    tested no condition. ``value`` is what the record fixes, else None.
    ``observed`` holds each value that the condition read, by the text that reads
    it: None for an undecided value. ``observations`` holds those with an
    availability date.
    """

    case: str | None
    key: str
    decision_date: date
    result: DecisionResult
    condition: bool | None
    value: Read
    observed: Mapping[str, Read]
    observations: tuple[ObservationRow, ...]


class DecisionTable:
    """The records of decision traces, one row for each case and window date.

    Iterate over it for its ``DecisionRow`` rows. ``where(key=, result=)`` selects
    rows, ``observations`` gives what they read, and ``table`` gives a ``Table``.
    A case that failed during its rules holds the records up to its failure.
    """

    __slots__ = ("_keys", "_rows")

    def __init__(
        self, *, rows: Iterable[DecisionRow], keys: Iterable[str] | None = None
    ) -> None:
        self._rows = tuple(rows)
        found = dict.fromkeys(row.key for row in self._rows)
        self._keys = tuple(found) if keys is None else tuple(keys)

    @property
    def keys(self) -> tuple[str, ...]:
        """Return the keys of the rules that this table's traces record."""
        return self._keys

    @property
    def observations(self) -> tuple[ObservationRow, ...]:
        """Return each value that the rows read and that has an availability date.

        A fixed value and a parameter are always available, and an undecided value
        has no value yet, so they have no row. ``row.observed`` shows them.
        """
        return tuple(item for row in self._rows for item in row.observations)

    @property
    def table(self) -> Table:
        """Return a Table with one row for each record, for display and for columns."""
        return Table(
            (
                "case",
                "key",
                "decision_date",
                "result",
                "condition",
                "value",
                "observed",
            ),
            (
                {
                    "case": row.case,
                    "key": row.key,
                    "decision_date": row.decision_date,
                    "result": row.result,
                    "condition": row.condition,
                    "value": row.value,
                    "observed": _observed_text(row.observed),
                }
                for row in self._rows
            ),
        )

    def where(
        self,
        *,
        key: str | None = None,
        result: DecisionResult | None = None,
    ) -> "DecisionTable":
        """Return the rows of one rule, of one result, or of both.

        A key that no rule of this table decides raises MissingReferenceError.
        """
        if key is not None and key not in self._keys:
            raise MissingReferenceError(
                key,
                kind="Rule",
                by="key",
                where="the decision trace",
                candidates=list(self._keys),
            )
        if result is not None and not isinstance(result, DecisionResult):
            raise TypeError("result must be a DecisionResult")
        return DecisionTable(
            rows=(
                row
                for row in self._rows
                if (key is None or row.key == key)
                and (result is None or row.result is result)
            ),
            keys=self._keys,
        )

    def __iter__(self) -> Iterator[DecisionRow]:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int) -> DecisionRow:
        return self._rows[index]

    def __repr__(self) -> str:
        return f"DecisionTable({len(self._rows)} rows, keys={list(self._keys)!r})"

    def _repr_html_(self) -> str:
        return self.table._repr_html_()


def decision_rows(
    case: str | None, evidence: RuleEvidence | None
) -> tuple[DecisionRow, ...]:
    """Return the rows of one case's stored trace; a case without rules has none."""
    if evidence is None:
        return ()
    return tuple(_row(case, check) for check in read_checks(evidence))


def _row(case: str | None, check: Check) -> DecisionRow:
    observations = []
    for reading in check.readings:
        if reading.available_on is not None and reading.value is not None:
            observations.append(
                ObservationRow(
                    case=case,
                    key=check.key,
                    decision_date=check.on,
                    name=reading.name,
                    target=reading.target,
                    value=reading.value,
                    available_on=reading.available_on,
                    source=reading.source,
                )
            )
    return DecisionRow(
        case=case,
        key=check.key,
        decision_date=check.on,
        result=check.result,
        condition=check.condition,
        value=check.value,
        observed=MappingProxyType(
            {reading.name: reading.value for reading in check.readings}
        ),
        observations=tuple(observations),
    )


def _observed_text(observed: Mapping[str, Read]) -> str:
    return "; ".join(f"{name} = {_text(value)}" for name, value in observed.items())


def _text(value: Read) -> str:
    if value is None:
        return "undecided"
    if value is NEVER:
        return "NEVER"
    return str(value)


__all__ = ["DecisionRow", "DecisionTable", "ObservationRow", "decision_rows"]
