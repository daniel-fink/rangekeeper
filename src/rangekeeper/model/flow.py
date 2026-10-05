"""Immutable Flow content and revision-pinned Stream selection.

Movements use date coordinates or period coverage. An optional date on a period
movement is an independent payment/observation fact, not a cached boundary date.
The overall model logic gives quantities their meaning and selects operations.
Flow records do not classify their content as amounts, rates, balances or factors.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from .._schema.records import Flow, Movement, Period, Value
from ..temporal.calendar import require_date
from ..temporal.period import PeriodTiming, resolve_period_date, validate_period
from ..units import UnitSystem, default_units

if TYPE_CHECKING:
    from .model import Model

__all__ = [
    "Flow",
    "Movement",
    "Stream",
    "from_events",
    "from_periods",
    "validate_flow",
    "movement_coordinate",
    "resolve_date",
]


def movement_coordinate(movement: Movement) -> tuple:
    """Return alignment identity; independently recorded dates must also agree."""
    if movement.period is not None:
        return (
            "period",
            movement.period.start.isoformat(),
            movement.period.end.isoformat(),
            None if movement.date is None else movement.date.isoformat(),
        )
    if movement.date is None:
        raise ValueError("movement requires a date or period")
    return ("event", movement.date.isoformat(), movement.key)


def resolve_date(movement: Movement, *, timing: PeriodTiming | None = None) -> date:
    """Use a recorded date, or derive one from a period with an explicit convention.

    Recorded dates take precedence over the fallback convention. No movement is
    changed, and payment outside its coverage period is permitted.
    """
    if timing not in (None, "start", "last_day", "end"):
        raise ValueError("timing must be start, last_day or end")
    if movement.date is not None:
        return require_date(movement.date)
    if movement.period is None:
        raise ValueError("movement requires a date or period")
    if timing is None:
        raise ValueError("undated period movement requires explicit timing")
    return resolve_period_date(movement.period, timing=timing)


def validate_flow(flow: Flow, *, units: UnitSystem = default_units) -> None:
    """Check units, movement identity, date ordering and non-overlapping period coverage.

    All movements in one Flow use either periods or dated events. Period order uses
    coverage, not optional payment dates; those dates may lie outside the period.
    """
    units.compatible(flow.units, flow.units)
    keys = set()
    previous = None
    previous_end = None
    mode = None
    for movement in flow.movements:
        if movement.key in keys:
            raise ValueError(f"duplicate movement key: {movement.key}")
        keys.add(movement.key)
        if movement.date is not None:
            require_date(movement.date)
        if movement.period is None and movement.date is None:
            raise ValueError("movement requires a date or period")
        period_mode = movement.period is not None
        if mode is not None and mode != period_mode:
            raise ValueError("Flow cannot mix event and period movements")
        mode = period_mode
        if movement.period is not None:
            validate_period(movement.period)
            if previous_end is not None and movement.period.start < previous_end:
                raise ValueError("Flow periods overlap or are out of order")
            previous_end = movement.period.end
        else:
            assert movement.date is not None
            if previous is not None and movement.date < previous:
                raise ValueError("Flow movements must be ordered by date")
            previous = movement.date
        if len(movement.claims or ()) != len(set(movement.claims or ())):
            raise ValueError("duplicate movement Claim")


def from_events(
    dates: Sequence[date],
    magnitudes: Sequence[int | float | None],
    *,
    units: str,
    keys: Sequence[str] | None = None,
) -> Flow:
    """Construct ordered dated entries; repeated dates require distinct keys."""
    if len(dates) != len(magnitudes) or keys is not None and len(keys) != len(dates):
        raise ValueError("coordinates, magnitudes and keys must have equal lengths")
    for value in dates:
        require_date(value)
    selected_keys = (
        tuple(keys) if keys is not None else tuple(d.isoformat() for d in dates)
    )
    result = Flow(
        units=units,
        movements=tuple(
            Movement(key=key, date=day, magnitude=value)
            for day, key, value in zip(dates, selected_keys, magnitudes)
        ),
    )
    validate_flow(result)
    return result


def from_periods(
    periods: Sequence[Period],
    magnitudes: Sequence[int | float | None],
    *,
    units: str,
    dates: Sequence[date | None] | None = None,
) -> Flow:
    """Construct quantities over periods without inventing payment dates.

    Supply dates only for independently known payment/observation dates. Omitted
    dates remain absent; valuation and presentation can resolve a convention later.
    """
    if (
        len(periods) != len(magnitudes)
        or dates is not None
        and len(dates) != len(periods)
    ):
        raise ValueError("periods, magnitudes and dates must have equal lengths")
    movements = []
    for i, (period, magnitude) in enumerate(zip(periods, magnitudes)):
        validate_period(period)
        data = dict(
            key=f"{period.start.isoformat()}/{period.end.isoformat()}",
            period=period.to_data(),
            magnitude=magnitude,
        )
        day = dates[i] if dates is not None else None
        if day is not None:
            data["date"] = require_date(day).isoformat()
        movements.append(Movement.from_data(data))
    result = Flow(units=units, movements=tuple(movements))
    validate_flow(result)
    return result


@dataclass(frozen=True, slots=True)
class Stream:
    """Ordered selection of canonical Flow Values in one immutable Model revision."""

    model: Model
    value_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        identities = tuple(self.value_ids)
        if len(identities) != len(set(identities)):
            raise ValueError("Stream cannot count the same Value twice")
        for identity in identities:
            value = self.model.value(identity)
            if value.kind != "flow":
                raise ValueError(f"Stream target is not a Flow Value: {identity}")
        object.__setattr__(self, "value_ids", identities)

    @classmethod
    def from_values(cls, model: Model, value_ids: Iterable[UUID]) -> Stream:
        return cls(model=model, value_ids=tuple(value_ids))

    @property
    def values(self) -> tuple[Value, ...]:
        return tuple(self.model.value(identity) for identity in self.value_ids)

    @property
    def flows(self) -> tuple[Flow, ...]:
        flows = tuple(value.flow for value in self.values)
        if any(flow is None for flow in flows):
            raise ValueError("Stream contains an unresolved Flow Value")
        return tuple(flow for flow in flows if flow is not None)

    def select(self, *, value_ids: Iterable[UUID]) -> Stream:
        selected = tuple(value_ids)
        if any(identity not in self.value_ids for identity in selected):
            raise KeyError("selection contains a Value outside this Stream")
        return Stream(self.model, selected)

    def merge(self, other: Stream) -> Stream:
        """Union selections in encounter order; different revisions cannot be merged."""
        if (
            self.model.id != other.model.id
            or self.model.to_data() != other.model.to_data()
        ):
            raise ValueError("Streams must pin the same Model revision and content")
        return Stream(
            self.model, tuple(dict.fromkeys(self.value_ids + other.value_ids))
        )
