"""Rule observation dates derived from coordinates and declared dates."""

from collections.abc import Mapping
from datetime import date
from uuid import UUID

from rangekeeper.flow import Movement
from rangekeeper.market.paths import Paths
from rangekeeper.quantity import Quantity
from rangekeeper.schema.records import PathCase


def known_on(movement: Movement) -> date:
    """Return when a Movement that no path fixes is known (ADR-021).

    A dated Movement is known on its date, and a period Movement at the end of
    its Period: the excluded boundary, so a yearly amount is known on 1 January.
    """
    if movement.date is not None:
        return movement.date
    assert movement.period is not None  # a Movement has a date or a Period
    return movement.period.end


def path_known(*, path: PathCase, paths: Paths) -> Mapping[UUID, date]:
    """Return when each Movement that a path fixes is known: its end plus the lag."""
    found: dict[UUID, date] = {}
    for binding in path.series:
        dates = paths.available(name=binding.series)
        for reference, known in zip(binding.movements, dates, strict=True):
            found[reference.target] = known
    return found


def path_amounts(*, path: PathCase, paths: Paths) -> Mapping[UUID, Quantity]:
    """Return the amount of the path for each Movement that it fixes."""
    found: dict[UUID, Quantity] = {}
    for binding in path.series:
        flow = paths[path.key][binding.series]
        for reference, amount in zip(binding.movements, flow.movements, strict=True):
            found[reference.target] = Quantity(
                magnitude=amount.magnitude, units=flow.units
            )
    return found
