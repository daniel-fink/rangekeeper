"""The distribution of one value across the cases of a batch Outcome.

``Outcome.distribution(key=)`` gives a ``Distribution`` of a scalar value and a
``DateDistribution`` of a date value. ``Outcome.mean()`` gives the ``Mean`` of
a batch's scalar values, which ``rk.execution.compare`` takes as one leaf
Outcome.

Each case has the same weight. The statistics are those of the cases
themselves: a quantile is the value of one case, so ``case(quantile=)`` gives
the case at that quantile.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from itertools import groupby
from typing import TYPE_CHECKING, Self

from rangekeeper.duration.dates import DateValue, Never, order
from rangekeeper.flow import Flow
from rangekeeper.quantity import Quantity
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError
from rangekeeper.shared.table import Table

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

    from rangekeeper.execution.outcome import Outcome

SUMMARY = (
    "count",
    "mean",
    "standard_deviation",
    "minimum",
    "quantile_05",
    "quantile_95",
    "maximum",
)
"""The statistics of ``Distribution.summary()``, in column order, after ``key``."""
COUNTS = ("value", "count", "share")
"""The columns of ``counts()``."""


@dataclass(frozen=True, kw_only=True, init=False)
class Distribution[Case]:
    """The scalar values of one key across cases, each case with the same weight.

    Make it with ``Outcome.distribution(key=)``: each case is a leaf case of
    the batch. ``values`` holds the value of each case, in case order, in the
    units of the first case.

    - ``mean()`` and ``standard_deviation()`` divide by the number of cases.
    - ``quantile(level=)`` is the smallest value whose share of cases at or
      below it is at least ``level``: the inverse of the empirical
      distribution function, which does not interpolate. It is the value of
      one case, and ``case(quantile=)`` returns that case; of equal values,
      the first in case order.
    - ``probability(below=, above=)`` is the share of cases strictly below,
      strictly above, or strictly between its bounds.
    - ``counts()`` gives each distinct value with its count and share.
    - ``summary()`` gives the count, mean, standard deviation, minimum, the
      5 % and 95 % quantiles and the maximum, as one row of a Table.

    It displays as its ``summary()``.
    """

    key: str
    units: str
    _items: tuple[tuple[Case, Quantity], ...] = field(repr=False)
    _ascending: tuple[int, ...] = field(repr=False, compare=False)

    @classmethod
    def _of(cls, *, key: str, items: Sequence[tuple[Case, Quantity]]) -> Self:
        """Return the distribution of the values of ``items``, in their order.

        Each value is converted to the units of the first; units that do not
        convert raise UnitError.
        """
        units = items[0][1].units
        converted = tuple((case, _in_units(value, units)) for case, value in items)
        made = object.__new__(cls)
        for name, value in (
            ("key", key),
            ("units", units),
            ("_items", converted),
            ("_ascending", _ascending(converted)),
        ):
            object.__setattr__(made, name, value)
        return made

    @property
    def values(self) -> tuple[Quantity, ...]:
        """Return the value of each case, in case order, in ``units``."""
        return tuple(value for _, value in self._items)

    def mean(self) -> Quantity:
        """Return the mean of the values, in ``units``."""
        return Quantity(magnitude=_mean(self._numbers()), units=self.units)

    def standard_deviation(self) -> Quantity:
        """Return the standard deviation of the values, in ``units``.

        It divides the sum of the squared deviations from the mean by the
        number of cases, as for the cases themselves, not by one less.
        """
        numbers = self._numbers()
        mean = _mean(numbers)
        variance = _mean([(number - mean) ** 2 for number in numbers])
        return Quantity(magnitude=math.sqrt(variance), units=self.units)

    def quantile(self, *, level: float) -> Quantity:
        """Return the value at the quantile ``level``, from 0 to 1.

        It is the smallest value whose share of cases at or below it is at
        least ``level``, so ``level=0`` gives the minimum and ``level=1`` the
        maximum. A level outside 0 to 1 raises ContractError.
        """
        return self._at(level)[1]

    def case(self, *, quantile: float) -> Case:
        """Return the case whose value is at the quantile ``quantile``.

        Its value is ``quantile(level=quantile)``; of cases with equal values,
        the first in case order.
        """
        return self._at(quantile)[0]

    def probability(
        self,
        *,
        below: Quantity | str | None = None,
        above: Quantity | str | None = None,
    ) -> float:
        """Return the share of cases whose value is below ``below`` and above ``above``.

        Give one bound or both, as a Quantity or Quantity text in units that
        convert to ``units``; each bound is strict. ``probability(below="0
        AUD")`` is the share of cases with a loss. With both bounds, it is the
        share of cases between them.
        """
        if below is None and above is None:
            raise TypeError("probability takes below=, above= or both")
        upper = None if below is None else _bound(below, self.units)
        lower = None if above is None else _bound(above, self.units)
        inside = [
            value
            for value in self.values
            if (upper is None or value < upper) and (lower is None or value > lower)
        ]
        return len(inside) / len(self._items)

    def counts(self) -> Table:
        """Return each distinct value with the number and the share of its cases.

        The columns are ``value``, ``count`` and ``share``, with the values in
        ascending order.
        """
        return _counts(self.values, by=_magnitude)

    def summary(self) -> Table:
        """Return the statistics of the values as one row of a Table.

        The columns are ``key``, ``count``, ``mean``, ``standard_deviation``,
        ``minimum``, ``quantile_05``, ``quantile_95`` and ``maximum``: the 5 %
        and 95 % quantiles are ``quantile(level=0.05)`` and
        ``quantile(level=0.95)``.
        """
        return Table(("key", *SUMMARY), ({"key": self.key, **self._statistics()},))

    def _statistics(self) -> dict[str, object]:
        """Return the cells of ``summary()`` after ``key``."""
        return {
            "count": len(self._items),
            "mean": self.mean(),
            "standard_deviation": self.standard_deviation(),
            "minimum": self.quantile(level=0),
            "quantile_05": self.quantile(level=0.05),
            "quantile_95": self.quantile(level=0.95),
            "maximum": self.quantile(level=1),
        }

    def _numbers(self) -> list[float]:
        return [value.number for value in self.values]

    def _at(self, level: float) -> tuple[Case, Quantity]:
        """Return the case and the value at the quantile ``level``.

        Of the cases with that value, the case is the first in case order.
        """
        position = self._ascending[_rank(level, count=len(self._items))]
        found = self._items[position][1].magnitude
        return next(item for item in self._items if item[1].magnitude == found)

    def _repr_html_(self) -> str:
        return self.summary()._repr_html_()

    def __repr__(self) -> str:
        return (
            f"Distribution(key={self.key!r}, units={self.units!r}, "
            f"count={len(self._items)})"
        )


@dataclass(frozen=True, kw_only=True, init=False)
class DateDistribution:
    """The date values of one key across the leaf cases of a batch Outcome.

    Make it with ``Outcome.distribution(key=)`` for a date value. ``values``
    holds the date of each case, or ``rk.duration.NEVER``, in case order.
    Dates have no mean: ``counts()`` gives each distinct date with its count
    and share. It displays as its ``counts()``.
    """

    key: str
    values: tuple[DateValue, ...]

    @classmethod
    def _of(cls, *, key: str, values: Sequence[DateValue]) -> Self:
        made = object.__new__(cls)
        object.__setattr__(made, "key", key)
        object.__setattr__(made, "values", tuple(values))
        return made

    def counts(self) -> Table:
        """Return each distinct date with the number and the share of its cases.

        The columns are ``value``, ``count`` and ``share``, with the dates in
        order and ``NEVER`` last.
        """
        return _counts(self.values, by=order)

    def _repr_html_(self) -> str:
        return self.counts()._repr_html_()

    def __repr__(self) -> str:
        return f"DateDistribution(key={self.key!r}, count={len(self.values)})"


@dataclass(frozen=True, kw_only=True, init=False)
class Mean:
    """The mean of a batch Outcome's scalar values, each leaf case with the same weight.

    Make it with ``Outcome.mean()``. Read the mean of a value by its key,
    ``mean["equity_npv"]``: it is ``outcome.distribution(key=).mean()``.
    ``rk.execution.compare`` takes it as one leaf Outcome, for example to
    compare the mean of a batch with the Outcome of its mean inputs. The mean
    is not the result of a solve: it has no Run, no status and no output.
    """

    outcome: "Outcome"

    @classmethod
    def _of(cls, *, outcome: "Outcome") -> Self:
        made = object.__new__(cls)
        object.__setattr__(made, "outcome", outcome)
        return made

    def __getitem__(self, key: str) -> Quantity:
        """Return the mean of the scalar value at ``key`` across the leaf cases.

        A date value has no mean: ContractError with the code
        ``DISTRIBUTION_VALUE``.
        """
        found = self.outcome.distribution(key=key)
        if not isinstance(found, Distribution):
            raise ContractError(
                f"{key} is a date value, which has no mean: read "
                "distribution(key=).counts()",
                code=Code.DISTRIBUTION_VALUE,
                document_id=self.outcome.run.id,
                values={"key": key},
            )
        return found.mean()

    def __repr__(self) -> str:
        name = self.outcome.key or str(self.outcome.run.id)
        return f"Mean(outcome={name!r})"


def _distribution_of[Case](
    *,
    key: str,
    values: Sequence[tuple[Case, Quantity | Flow | DateValue]],
) -> Distribution[Case] | DateDistribution:
    """Return the distribution of each case's value at ``key``, by its kind.

    Scalar values give a ``Distribution`` and date values a
    ``DateDistribution``. Any other value, such as a Flow, raises
    ContractError with the code ``DISTRIBUTION_VALUE``.
    """
    quantities = [
        (case, value) for case, value in values if isinstance(value, Quantity)
    ]
    if len(quantities) == len(values):
        return Distribution._of(key=key, items=quantities)
    dates = [value for _, value in values if isinstance(value, (date, Never))]
    if len(dates) == len(values):
        return DateDistribution._of(key=key, values=dates)
    raise ContractError(
        f"{key} is not a scalar or a date value in each case: "
        "a distribution takes one of them",
        code=Code.DISTRIBUTION_VALUE,
        values={"key": key},
    )


def _in_units(value: Quantity, units: str) -> Quantity:
    return value if value.units == units else value.to(units=units)


def _ascending[Case](items: tuple[tuple[Case, Quantity], ...]) -> tuple[int, ...]:
    """Return the positions of the items in ascending order of value; ties keep order."""
    return tuple(sorted(range(len(items)), key=lambda index: items[index][1].magnitude))


def _mean(numbers: Sequence[float]) -> float:
    return math.fsum(numbers) / len(numbers)


def _rank(level: float, *, count: int) -> int:
    """Return the ascending position of the quantile ``level`` among ``count`` values.

    It is the smallest position whose share of values at or below it is at
    least ``level``. The level is read as its decimal text, so that
    ``0.05 * 500`` is 25 exactly.
    """
    if isinstance(level, bool) or not isinstance(level, (int, float)):
        raise TypeError("a quantile level is a number from 0 to 1")
    if not 0 <= level <= 1:
        raise ContractError(
            f"a quantile level must be from 0 to 1, not {level}",
            code=Code.CONTRACT,
            values={"level": level},
        )
    return max(math.ceil(Fraction(str(level)) * count) - 1, 0)


def _bound(value: Quantity | str, units: str) -> Quantity:
    if isinstance(value, str):
        value = Quantity(text=value)
    if not isinstance(value, Quantity):
        raise TypeError("a probability bound is a Quantity or Quantity text")
    return _in_units(value, units)


def _magnitude(value: Quantity) -> "SupportsRichComparison":
    return value.magnitude


def _counts[Value](
    values: Sequence[Value],
    *,
    by: "Callable[[Value], SupportsRichComparison]",
) -> Table:
    """Return each distinct value in ascending order of ``by``, with its count and share."""
    rows = []
    for _, group in groupby(sorted(values, key=by), key=by):
        found = list(group)
        rows.append(
            {
                "value": found[0],
                "count": len(found),
                "share": len(found) / len(values),
            }
        )
    return Table(COUNTS, rows)


__all__ = ["DateDistribution", "Distribution", "Mean"]
