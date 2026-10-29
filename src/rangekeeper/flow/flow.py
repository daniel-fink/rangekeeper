"""Movement and Flow: the value types of dated and period quantities.

Stream coordinates several Flows.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from rangekeeper.duration import Period, Periods
from rangekeeper.duration.calendar import (
    DayCount,
    PeriodTiming,
    count_steps,
    offset,
    require_date,
    year_fraction,
)
from rangekeeper.duration.errors import AlignmentError
from rangekeeper.flow.options import MissingValueHandling, ResampleMethod
from rangekeeper.money import (
    RoundingMode,
    _encoded,
    _require,
    is_currency,
    to_number,
)
from rangekeeper.money import round as _round
from rangekeeper.profile import Profile
from rangekeeper.quantity import (
    Quantity,
    UnitSystem,
    _is_number,
    _product,
    _sum_scale,
    default_units,
)
from rangekeeper.schema import records
from rangekeeper.schema.kinds import register
from rangekeeper.schema.runtime import OMIT, UNSET
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    MissingReferenceError,
    NumericalError,
    UnitError,
)

if TYPE_CHECKING:
    from rangekeeper.duration import Frequency
    from rangekeeper.flow.table import StreamTable

# A number, a currency amount or None in a Flow constructor.
type Amount = Quantity | str | Decimal | int | float | None


def _number(magnitude: Decimal | int | float | None) -> float | None:
    """Return a magnitude as a number for a calculation; keep None."""
    if isinstance(magnitude, Decimal):
        return to_number(magnitude)
    return magnitude


def _values(flow: records.Flow) -> list[tuple]:
    """Return the coordinate, key and amount of each Movement, without identity."""
    return [
        (
            None if m.period is None else (m.period.start, m.period.end),
            m.date,
            m.key,
            m.magnitude,
        )
        for m in flow.movements
    ]


@register
class Movement(records.Movement):
    """Coordinate and numerical access without changing recorded evidence."""

    __slots__ = ()

    def _invariants(self) -> None:
        """Require a date or a period, and distinct Claims."""
        if self.period is None and self.date is None:
            raise ValueError("movement requires a date or period")
        claims = self.claims or ()
        if len(claims) != len(set(claims)):
            raise ValueError("duplicate movement Claim")

    @property
    def number(self) -> float:
        """Read a finite magnitude; unresolved data must be handled before arithmetic."""
        movement = self
        value = _number(movement.magnitude)
        if value is None or not math.isfinite(value):
            raise NumericalError(
                f"unresolved/nonfinite movement: {movement.key}",
                targets=(movement.id,),
            )
        return float(value)

    @property
    def coordinate(self) -> tuple:
        """Return the matching coordinate independently of UUID identity."""
        movement = self
        if movement.period is not None:
            return (
                "period",
                movement.period.start.isoformat(),
                movement.period.end.isoformat(),
                None if movement.date is None else movement.date.isoformat(),
            )
        if movement.date is None:
            raise ContractError(
                "movement requires a date or period",
                code=Code.INVARIANT_MOVEMENT,
                targets=(movement.id,),
            )
        return ("event", movement.date.isoformat(), movement.key)

    def resolve(self, *, timing: PeriodTiming | None = None) -> date:
        """Use a recorded date, or derive one from a period with an explicit convention.

        Recorded dates take precedence over the fallback convention. No movement is
        changed, and payment outside its coverage period is permitted.
        """
        movement = self
        if timing is not None and not isinstance(timing, PeriodTiming):
            raise TypeError("timing must be a PeriodTiming")
        if movement.date is not None:
            return require_date(movement.date)
        if movement.period is None:
            raise ContractError(
                "movement requires a date or period",
                code=Code.INVARIANT_MOVEMENT,
                targets=(movement.id,),
            )
        if timing is None:
            raise ContractError(
                "undated period movement requires explicit timing",
                targets=(movement.id,),
            )
        return movement.period.resolve(timing=timing)


def _magnitude(value: Amount, units: str) -> Decimal | int | float | None:
    """Return the magnitude of one amount in ``units``; a Quantity converts."""
    if isinstance(value, str):
        value = Quantity(text=value)
    if isinstance(value, records.Quantity):
        if value.units == units:
            return value.magnitude
        return default_units.convert(quantity=value, to=units).magnitude
    if value is not None and not _is_number(value) and not isinstance(value, Decimal):
        raise TypeError(f"amount {value!r} is not a number or a Quantity")
    return value


def _from_amounts(
    amounts: Mapping[Period | date, Amount], units: str | None
) -> tuple[str, tuple[Movement, ...]]:
    """Return the units and Movements of a mapping of Periods or dates to amounts."""
    if not isinstance(amounts, Mapping):
        raise TypeError("amounts must map Periods or dates to amounts")
    if units is None:
        units = next(
            (
                (Quantity(text=v) if isinstance(v, str) else v).units
                for v in amounts.values()
                if isinstance(v, (str, records.Quantity))
            ),
            None,
        )
        if units is None:
            raise TypeError("give units, or give the amounts as Quantities")
    keys = list(amounts)
    magnitudes = [_magnitude(value, units) for value in amounts.values()]
    periods = [key for key in keys if isinstance(key, Period)]
    dates = [key for key in keys if type(key) is date]
    if len(periods) == len(keys):
        order = sorted(range(len(keys)), key=lambda i: periods[i].start)
        flow = Flow.from_periods(
            [periods[i] for i in order], [magnitudes[i] for i in order], units=units
        )
    elif len(dates) == len(keys):
        order = sorted(range(len(keys)), key=lambda i: dates[i])
        flow = Flow.from_events(
            [dates[i] for i in order], [magnitudes[i] for i in order], units=units
        )
    else:
        raise TypeError("key the amounts by Periods or by dates, not both")
    return units, flow.movements


@register
class Flow(records.Flow):
    """An ordered series of amounts in one unit, one for each Period or date.

    Make one from a mapping, ``Flow(amounts={period: 100, ...}, units="USD")``;
    with Quantities as amounts, the units come from them. ``movements=`` gives
    the Movements directly. Arithmetic works on amounts: ``2 * flow``,
    ``flow / rate``, ``flow + other`` and ``-flow`` give new Flows.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        units: str | None = None,
        movements: Sequence[Movement] | None = None,
        amounts: Mapping[Period | date, Amount] | None = None,
    ) -> None:
        if (movements is None) == (amounts is None):
            raise TypeError("give movements or amounts, not both")
        if amounts is not None:
            units, movements = _from_amounts(amounts, units)
        if units is None:
            raise TypeError("give units")
        assert movements is not None
        super().__init__(units=units, movements=tuple(movements))

    def display(
        self,
        *,
        name: str | None = None,
        transpose: bool = False,
        precision: int = 2,
    ) -> StreamTable:
        """Present one labelled line through the shared Stream table renderer.

        The name is a display label only. Rendering preserves the Flow's units,
        coordinates, unresolved amounts and canonical content.
        """
        from rangekeeper.flow.stream import Stream  # noqa: PLC0415 - stream imports this module

        return Stream(flows={"Flow" if name is None else name: self}).display(
            transpose=transpose,
            precision=precision,
        )

    def _repr_html_(self) -> str:
        return self.display()._repr_html_()

    def __eq__(self, other: object) -> bool:
        """Compare values: the units, and each Movement's coordinate and amount.

        Movement IDs and Claims are identity and evidence, not value, so a
        calculation that gives the same amounts on the same coordinates gives
        an equal Flow. ``equivalent`` and ``to_data`` compare the records.
        ``rangekeeper.quantity.isclose`` compares with a tolerance.
        """
        if not isinstance(other, records.Flow):
            return NotImplemented
        return self.units == other.units and _values(self) == _values(other)

    __hash__ = None  # type: ignore[assignment]

    def coordinate_index(self) -> dict[tuple, Movement]:
        """Index exact coordinates in encounter order, rejecting ambiguous matches.

        Return the recorded Movements without reading magnitudes or changing IDs.
        The caller selects any alignment, ordering, or missing-value policy.
        """
        flow = self
        result: dict[tuple, Movement] = {}
        for movement in flow.movements:
            coordinate = movement.coordinate
            if coordinate in result:
                raise AlignmentError(
                    "duplicate coordinates make alignment ambiguous; use explicit key equations",
                    code=Code.ALIGNMENT_DUPLICATE,
                    values={"coordinate": list(coordinate)},
                    targets=(result[coordinate].id, movement.id),
                )
            result[coordinate] = movement
        return result

    @classmethod
    def _coerce(cls, data: dict[str, object]) -> dict[str, object]:
        """Convert each magnitude in currency units to a currency amount (ADR-023)."""
        units, movements = data.get("units"), data.get("movements")
        if not isinstance(units, str) or not is_currency(units):
            return data
        if not isinstance(movements, (list, tuple)):
            return data
        result, changed = [], False
        for movement in movements:
            magnitude = (
                movement.get("magnitude") if isinstance(movement, Mapping) else None
            )
            # The Movement field encoder already made decimal text canonical.
            if magnitude is not None and type(magnitude) is not str:
                encoded = _encoded(magnitude)
                if encoded is not magnitude:
                    movement, changed = {**movement, "magnitude": encoded}, True
            result.append(movement)
        return {**data, "movements": result} if changed else data

    def _invariants(self) -> None:
        """Require unique Movement IDs and ordered, unmixed, non-overlapping coordinates.

        All movements in one Flow use either periods or dated events. Period
        order uses coverage, not optional payment dates; those dates may lie
        outside the period. Repeated event dates need distinct keys. Magnitudes
        in currency units are currency amounts; other magnitudes are numbers.
        """
        identities = set()
        events: dict[date, list[str | None]] = {}
        previous = None
        previous_end = None
        mode = None
        for movement in self.movements:
            if movement.id in identities:
                raise ValueError(f"duplicate Movement UUID: {movement.id}")
            identities.add(movement.id)
            period_mode = movement.period is not None
            if mode is not None and mode != period_mode:
                raise ValueError("Flow cannot mix event and period movements")
            mode = period_mode
            if movement.period is not None:
                if previous_end is not None and movement.period.start < previous_end:
                    raise ValueError("Flow periods overlap or are out of order")
                previous_end = movement.period.end
            elif movement.date is None:
                raise ValueError("movement requires a date or period")
            else:
                if previous is not None and movement.date < previous:
                    raise ValueError("Flow movements must be ordered by date")
                previous = movement.date
                keys = events.setdefault(movement.date, [])
                keys.append(movement.key)
                if len(keys) > 1 and (None in keys or len(set(keys)) != len(keys)):
                    raise ValueError(
                        "repeated event dates require distinct nonblank matching keys"
                    )
        currency = is_currency(self.units)
        for movement in self.movements:
            _require(movement._data.get("magnitude"), self.units, currency)

    def check(self, *, units: UnitSystem | None = None) -> Flow:
        """Check the units against a unit system and return this Flow.

        A Flow keeps its own order and identity rules at construction. This
        check adds what depends on context: the unit system, by default
        ``default_units``. It does not repair content or assign missing
        magnitudes. ``require_resolved`` checks the amounts.
        """
        units = default_units if units is None else units
        units.compatible(self.units, self.units)
        return self

    def require_resolved(self) -> Flow:
        """Require a finite number for every Movement and return this Flow.

        Use it before arithmetic that cannot carry an unresolved amount, such as
        a valuation. It does not repair content.
        """
        for movement in self.movements:
            _ = movement.number  # Raises for a Movement without a resolved number.
        return self

    @classmethod
    def from_events(
        cls,
        dates: Sequence[date],
        magnitudes: Sequence[Decimal | str | int | float | None],
        *,
        units: str,
        keys: Sequence[str | None] | None = None,
    ) -> Flow:
        """Make dated Movements with fresh IDs; repeated dates need distinct keys.

        To give IDs, or other fields, make the ``Movement`` records and pass
        them as ``Flow(units=, movements=)``.
        """
        factory = cls
        if (
            len(dates) != len(magnitudes)
            or keys is not None
            and len(keys) != len(dates)
        ):
            raise ContractError(
                "dates, magnitudes and keys must have equal lengths",
                values={"dates": len(dates), "magnitudes": len(magnitudes)},
            )
        for value in dates:
            require_date(value)
        selected_keys = tuple(keys) if keys is not None else (None,) * len(dates)
        if is_currency(units):
            # Convert once here, so the Flow need not rebuild its Movements.
            magnitudes = [
                None if v is None else cast(str, _encoded(v)) for v in magnitudes
            ]
        result = factory(
            units=units,
            movements=tuple(
                Movement(
                    id=identity,
                    key=UNSET if key is None else key,
                    date=day,
                    magnitude=value,
                )
                for day, key, value, identity in zip(
                    dates,
                    selected_keys,
                    magnitudes,
                    tuple(uuid4() for _ in dates),
                    strict=True,
                )
            ),
        )
        return result

    @classmethod
    def from_periods(
        cls,
        periods: Sequence[Period],
        magnitudes: Sequence[Decimal | str | int | float | None],
        *,
        units: str,
        keys: Sequence[str | None] | None = None,
    ) -> Flow:
        """Make Movements over Periods with fresh IDs and no payment dates.

        The Movements record coverage only; valuation and presentation resolve
        a date convention later. To record a known payment date, or to give
        IDs, make the ``Movement`` records and pass them as
        ``Flow(units=, movements=)``. Omitted matching keys remain absent.
        """
        if (
            len(periods) != len(magnitudes)
            or keys is not None
            and len(keys) != len(periods)
        ):
            raise ContractError(
                "periods, magnitudes and keys must have equal lengths",
                values={"periods": len(periods), "magnitudes": len(magnitudes)},
            )
        if is_currency(units):
            # Convert once here, so the Flow need not rebuild its Movements.
            magnitudes = [
                None if v is None else cast(str, _encoded(v)) for v in magnitudes
            ]
        selected_keys = tuple(keys) if keys is not None else (None,) * len(periods)
        movements = tuple(
            Movement(
                id=uuid4(),
                key=UNSET if key is None else key,
                period=period,
                magnitude=magnitude,
            )
            for period, magnitude, key in zip(
                periods, magnitudes, selected_keys, strict=True
            )
        )
        return cls(units=units, movements=movements)

    @classmethod
    def from_profile(
        cls,
        *,
        profile: Profile,
        periods: Sequence[Period],
        initial: Quantity | str | None = None,
        total: Quantity | str | None = None,
    ) -> Flow:
        """Make a Flow over Periods from a profile and an amount.

        A growth profile takes ``initial=``: the first Period holds it, and
        each Period holds it times the profile's factor. A distribution
        profile takes ``total=`` and divides it over the Periods; the last
        Period takes the remainder, so the amounts add up to the total. The
        amount is a Quantity or its text, and gives the Flow its units.
        """
        if not isinstance(profile, Profile):
            raise TypeError("profile must be a rangekeeper.profile Profile")
        given = {"initial": initial, "total": total}
        supplied = [name for name, value in given.items() if value is not None]
        if supplied != [profile.takes]:
            other = "total" if profile.takes == "initial" else "initial"
            raise TypeError(
                f"{type(profile).__name__} takes {profile.takes}=, not {other}="
            )
        amount = given[profile.takes]
        quantity = Quantity(text=amount) if isinstance(amount, str) else amount
        if not isinstance(quantity, records.Quantity):
            raise TypeError(f"{profile.takes} must be a Quantity or its text")
        factors = profile.factors(periods=periods)
        if len(factors) != len(periods):
            raise ContractError(
                "the profile must give one factor for each Period",
                values={"factors": len(factors), "periods": len(periods)},
            )
        values = [quantity.number * factor for factor in factors]
        if profile.takes == "total":
            values[-1] = quantity.number - math.fsum(values[:-1])
        if any(not math.isfinite(value) for value in values):
            raise NumericalError("the profile produced a non-finite amount")
        return cls.from_periods(periods, values, units=quantity.units)

    def clone(self) -> Flow:
        """Copy content with fresh Movement IDs for an independent owning Value.

        Dates, matching keys, magnitudes and evidence remain unchanged. Revision
        updates use replace() instead, preserving the existing identities.
        """
        flow = self
        return flow.replace(
            movements=tuple(m.replace(id=uuid4()) for m in flow.movements)
        )

    def convert(self, *, units: str, unit_system: UnitSystem | None = None) -> Flow:
        """Convert all known movements together; retain unresolved movements and evidence."""
        flow = self
        unit_system = default_units if unit_system is None else unit_system
        if not unit_system.compatible(flow.units, units):
            raise UnitError(f"cannot convert a Flow in {flow.units!r} to {units!r}")
        return flow.replace(
            movements=tuple(
                s.replace(
                    magnitude=(
                        None
                        if s.magnitude is None
                        else unit_system.convert(
                            quantity=Quantity(magnitude=s.magnitude, units=flow.units),
                            to=units,
                        ).magnitude
                    )
                )
                for s in flow.movements
            ),
            units=units,
        )

    def scale(self, factor: float) -> Flow:
        """Return ``factor * self``: each known amount times a number, with fresh IDs.

        It follows the rule of ``*``: unresolved amounts stay unresolved, and a
        non-finite result raises ``UnitError``.
        """
        if not _is_number(factor):
            raise TypeError("factor must be a number")
        return self._combine(factor, divide=False, reverse=True)

    def round(
        self, *, places: int | None = None, mode: RoundingMode = RoundingMode.HALF_EVEN
    ) -> Flow:
        """Round each amount to ``places``, by default the minor unit (ADR-023).

        Only currency amounts round; see ``rangekeeper.money.round``. The
        movements get fresh IDs and unresolved movements stay unresolved. The
        total of the rounded movements can differ from the rounded total.
        """
        flow = self
        if not is_currency(flow.units):
            raise UnitError(f"{flow.units!r} is not a currency; only amounts round")
        return flow.replace(
            movements=tuple(
                s.replace(
                    id=uuid4(),
                    magnitude=(
                        None
                        if s.magnitude is None
                        else _round(
                            amount=Decimal(s.magnitude),
                            currency=flow.units,
                            places=places,
                            mode=mode,
                        )
                    ),
                )
                for s in flow.movements
            )
        )

    def negate(self) -> Flow:
        """Reverse each known magnitude while keeping unresolved entries and Claims.

        The sign change is exact, also for a currency amount. The movements get
        fresh IDs.
        """
        flow = self
        return flow.replace(
            movements=tuple(
                s.replace(
                    id=uuid4(),
                    magnitude=None if s.magnitude is None else -s.magnitude,
                )
                for s in flow.movements
            )
        )

    def total(
        self, *, missing: MissingValueHandling = MissingValueHandling.ERROR
    ) -> Quantity | None:
        """Sum entries over time, retaining their units.

        ``missing`` treats unresolved amounts: ``ERROR`` raises, ``PROPAGATE``
        gives None, ``SKIP`` adds the known amounts (None when no amount is
        known) and ``ZERO`` adds the known amounts (zero when no amount is
        known). This is a numerical sum. The model determines whether summation
        expresses the intended quantity; no balance, rate or other
        interpretation is inferred.
        """
        if not isinstance(missing, MissingValueHandling):
            raise TypeError("missing must be a MissingValueHandling")
        values = [s.number for s in self.movements if s.magnitude is not None]
        if len(values) != len(self.movements) and not _total_known(missing, values):
            return None
        return Quantity(magnitude=math.fsum(values), units=self.units)

    def at(self, *, on: date) -> Quantity:
        """Return the amount of the Period that contains a date, or of the event on it.

        A date with no amount raises MissingReferenceError; several events on
        one date raise AmbiguousReferenceError; an unresolved amount raises
        NumericalError.
        """
        require_date(on)
        found = [
            m
            for m in self.movements
            if (m.period.start <= on < m.period.end if m.period else m.date == on)
        ]
        if not found:
            raise MissingReferenceError(
                on.isoformat(), kind="amount", by="date", where=f"Flow in {self.units}"
            )
        if len(found) > 1:
            raise AmbiguousReferenceError(
                on.isoformat(),
                kind="amount",
                by="date",
                where=f"Flow in {self.units}",
                candidates=[str(m.key) for m in found],
            )
        if found[0].magnitude is None:
            raise NumericalError(f"the amount on {on.isoformat()} is unresolved")
        return Quantity(magnitude=found[0].magnitude, units=self.units)

    def shift(self, *, by: int) -> Flow:
        """Move each amount by whole Periods; the Periods stay the same.

        ``by=-1`` moves each amount one Period earlier, so each Period holds the
        amount of the next one. A Period that no amount moves into is
        unresolved, and an amount that moves past the first or last Period is
        left out. The Periods must be gap-free; dated Flows cannot shift.
        """
        if type(by) is not int:
            raise TypeError("by must be a whole number of Periods")
        movements = self.movements
        if any(m.period is None for m in movements):
            raise ContractError("only a Flow over Periods can shift by Periods")
        gaps = [
            (a, b)
            for a, b in pairwise(movements)
            if a.period.end != b.period.start  # type: ignore[union-attr]
        ]
        if gaps:
            raise AlignmentError(
                "shift needs gap-free Periods",
                code=Code.ALIGNMENT_GAP,
                values={
                    "end": gaps[0][0].period.end.isoformat(),  # type: ignore[union-attr]
                    "start": gaps[0][1].period.start.isoformat(),  # type: ignore[union-attr]
                },
            )
        shifted = []
        for i, movement in enumerate(movements):
            j = i - by
            source = movements[j] if 0 <= j < len(movements) else None
            shifted.append(
                movement.replace(
                    id=uuid4(),
                    magnitude=None if source is None else source.magnitude,
                    claims=OMIT
                    if source is None or not source.claims
                    else source.claims,
                )
            )
        return self.replace(movements=tuple(shifted))

    def __neg__(self) -> Flow:
        return self.negate()

    def __pos__(self) -> Flow:
        return self

    def __add__(self, other: object) -> Flow:
        return self._sum(other, subtract=False)

    def __sub__(self, other: object) -> Flow:
        return self._sum(other, subtract=True)

    def __mul__(self, other: object) -> Flow:
        return self._combine(other, divide=False, reverse=False)

    def __rmul__(self, other: object) -> Flow:
        return self._combine(other, divide=False, reverse=True)

    def __truediv__(self, other: object) -> Flow:
        return self._combine(other, divide=True, reverse=False)

    def _sum(self, other: object, *, subtract: bool) -> Flow:
        """Add or subtract amounts on matching coordinates.

        A coordinate that only one Flow has keeps that amount, because the other
        Flow has nothing there. An unresolved amount gives an unresolved result.
        """
        if not isinstance(other, Flow):
            return NotImplemented
        scale = _sum_scale(self.units, other.units)
        left, right = self.coordinate_index(), other.coordinate_index()
        if len({key[0] for key in (*left, *right)}) > 1:
            raise AlignmentError(
                "cannot add dated and period amounts; use Stream.sum, which dates "
                "each period amount",
                code=Code.ALIGNMENT_MIXED,
            )
        sign = -1.0 if subtract else 1.0
        movements = []
        for key in sorted({**left, **right}, key=lambda k: (k[1], str(k))):
            a, b = left.get(key), right.get(key)
            template = cast(Movement, a if a is not None else b)
            if (a is not None and a.magnitude is None) or (
                b is not None and b.magnitude is None
            ):
                value = None
            else:
                value = (0.0 if a is None else a.number) + sign * (
                    0.0 if b is None else b.number * scale
                )
            claims = tuple(
                dict.fromkeys(
                    c for m in (a, b) if m is not None for c in (m.claims or ())
                )
            )
            movements.append(
                template.replace(
                    id=uuid4(), magnitude=value, claims=claims if claims else OMIT
                )
            )
        return Flow(units=self.units, movements=tuple(movements))

    def _combine(self, other: object, *, divide: bool, reverse: bool) -> Flow:
        """Multiply or divide each amount by a number, a Quantity or a Flow."""
        if _is_number(other):
            number = float(cast(int | float, other))
            if reverse and divide:
                return NotImplemented
            return self._each(
                lambda value: value / number if divide else value * number,
                self.units,
            )
        if isinstance(other, records.Quantity):
            quantity = cast(Quantity, other)
            if reverse:
                product = _product(quantity.units, self.units, divide)
                return self._each(
                    lambda value: product.apply(quantity.number, value, divide),
                    product.units,
                )
            product = _product(self.units, quantity.units, divide)
            return self._each(
                lambda value: product.apply(value, quantity.number, divide),
                product.units,
            )
        if isinstance(other, Flow):
            from rangekeeper.flow._mapping import alignment  # noqa: PLC0415 - _mapping imports this module

            product = _product(self.units, other.units, divide)
            movements = []
            for movement, (match,) in alignment((other,), self):
                value = (
                    None
                    if movement.magnitude is None or match.magnitude is None
                    else product.apply(movement.number, match.number, divide)
                )
                claims = tuple(
                    dict.fromkeys((*(movement.claims or ()), *(match.claims or ())))
                )
                movements.append(
                    movement.replace(
                        id=uuid4(), magnitude=value, claims=claims if claims else OMIT
                    )
                )
            return self._checked(movements, product.units)
        return NotImplemented

    def _each(self, operation: Callable[[float], float], units: str) -> Flow:
        movements = [
            m.replace(
                id=uuid4(),
                magnitude=None if m.magnitude is None else operation(m.number),
            )
            for m in self.movements
        ]
        return self._checked(movements, units)

    def _checked(self, movements: list[Movement], units: str) -> Flow:
        if any(
            m.magnitude is not None and not math.isfinite(_number(m.magnitude) or 0)
            for m in movements
        ):
            raise UnitError(f"arithmetic in {units!r} produced a non-finite magnitude")
        return Flow(units=units, movements=tuple(movements))

    def trim(self, *, span: Period) -> Flow:
        """Select dates in [start, end) of a Period or Span, or whole periods inside it.

        Partial period overlap raises AlignmentError; trimming must not silently allocate
        a period quantity or substitute an assumed payment date for its coverage.
        """
        flow = self
        if not isinstance(span, Period):
            raise TypeError("span must be a Period or Span")
        start, end = span.start, span.end
        selected = []
        for movement in flow.movements:
            if movement.period is None:
                if start <= movement.resolve() < end:
                    selected.append(movement)
            else:
                period = movement.period
                if period.end <= start or period.start >= end:
                    continue
                if period.start < start or period.end > end:
                    raise AlignmentError(
                        "trim crosses a movement period; allocate explicitly",
                        code=Code.ALIGNMENT_CROSSES,
                        values={
                            "span": f"{start.isoformat()}/{end.isoformat()}",
                            "period": (
                                f"{period.start.isoformat()}/{period.end.isoformat()}"
                            ),
                        },
                        targets=(movement.id,),
                    )
                selected.append(movement)
        return flow.replace(movements=tuple(selected))

    def resample(
        self,
        *,
        periods: Sequence[Period] | None = None,
        frequency: Frequency | None = None,
        method: ResampleMethod,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
    ) -> Flow:
        """Reduce the amounts onto longer Periods: explicit ``periods``, or a ``frequency``.

        A frequency makes the Periods from the start of the first Period to the
        end of the last one; they must fit exactly. ``method`` reduces the
        whole movements inside each target Period to one amount, and
        ``missing`` treats a Period with no amount or an unresolved amount.
        ``split`` divides amounts over shorter Periods. ``Stream.resample``
        takes the same arguments and also reports coverage.
        """
        from rangekeeper.flow._batch import Batch  # noqa: PLC0415 - _batch imports this module

        periods = _target(self.movements, periods=periods, frequency=frequency)
        batch = Batch.prepare((self,))
        return batch.resample(periods, methods=(method,), missing=missing).flows()[0]

    def split(
        self,
        *,
        periods: Sequence[Period] | None = None,
        frequency: Frequency | None = None,
    ) -> Flow:
        """Divide each amount equally over shorter Periods: explicit ``periods``, or a ``frequency``.

        The target Periods must partition the Period of each movement. The last
        part takes the remainder, so the parts add up to the amount. An
        unresolved amount gives unresolved parts. A frequency makes the Periods
        from the start of the first Period to the end of the last one.
        """
        return _split(
            self, _target(self.movements, periods=periods, frequency=frequency)
        )

    def integrate_time(self, *, day_count: DayCount, units: str | None = None) -> Flow:
        """Multiply each amount by the year fraction of its Period.

        ``day_count`` gives the year fraction of each Period, as a quantity in
        years. ``units`` converts the products, as for ``integrate``.
        """
        if not isinstance(day_count, DayCount):
            raise TypeError("day_count must be a DayCount")
        if any(s.period is None for s in self.movements):
            raise ContractError("day-count integration requires bounded periods")
        exposures = [
            Quantity(
                magnitude=year_fraction(
                    s.period.start, s.period.end, convention=day_count
                ),
                units="year",
            )
            for s in self.movements
            if s.period is not None
        ]
        return self.integrate(exposures=exposures, units=units)

    def integrate(
        self,
        *,
        exposures: Sequence[Quantity],
        units: str | None = None,
    ) -> Flow:
        """Multiply each amount by its exposure, one exposure for each Movement.

        Explicit exposures support calendar-month conventions and non-time
        exposures. ``units`` converts the products; an empty Flow needs it.
        ``integrate_time`` uses the year fraction of each Period. Calling this
        operation supplies the integration rule; the Flow has no rate kind.
        """
        flow = self
        if len(exposures) != len(flow.movements):
            raise ContractError(
                "exposure count differs from movement count",
                values={"exposures": len(exposures), "movements": len(flow.movements)},
            )
        output_units = units or (
            default_units.multiply(flow.units, exposures[0].units)
            if exposures
            else None
        )
        if output_units is None:
            raise UnitError("empty integration requires explicit output units")
        movements = []
        for movement, exposure in zip(flow.movements, exposures, strict=True):
            product_unit = default_units.multiply(flow.units, exposure.units)
            magnitude = (
                None
                if movement.magnitude is None
                else default_units.convert(
                    quantity=Quantity(
                        magnitude=movement.number * exposure.number,
                        units=product_unit,
                    ),
                    to=output_units,
                ).magnitude
            )
            movements.append(movement.replace(id=uuid4(), magnitude=magnitude))
        return flow.replace(movements=tuple(movements), units=output_units)

    def multiply(self, *others: Flow) -> Flow:
        """Return ``self * others[0] * ...``: the products at exact common coordinates.

        It follows the rule of ``*``: dimensionless scales such as percent
        become ratios, physical dimensions remain in the result, and an
        unresolved amount gives an unresolved product. The calling model
        determines the meaning of the product.
        """
        product = self
        for other in others:
            if not isinstance(other, Flow):
                raise TypeError("multiply takes Flows")
            product = product * other
        return product

    def clean(self) -> Flow:
        """Remove the unresolved movements; do not impute data."""
        return self.replace(
            movements=tuple(s for s in self.movements if s.magnitude is not None)
        )

    def drop_zeroes(self) -> Flow:
        """Remove the movements whose amount is zero; keep the unresolved movements."""
        return self.replace(
            movements=tuple(
                s for s in self.movements if s.magnitude is None or s.magnitude != 0
            )
        )

    def difference(self, *, initial: float | None = None) -> Flow:
        """Return adjacent differences; a missing neighbour yields an unresolved movement.

        The first movement is unresolved unless the caller supplies an initial value in
        the Flow's units. The model determines what the changes represent.
        """
        flow = self

        previous, movements = initial, []
        for movement in flow.movements:
            magnitude = (
                None
                if previous is None or movement.magnitude is None
                else movement.number - previous
            )
            movements.append(movement.replace(id=uuid4(), magnitude=magnitude))
            previous = None if movement.magnitude is None else movement.number
        return flow.replace(movements=tuple(movements))

    def collapse(
        self,
        *,
        on: date | PeriodTiming | None = None,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
    ) -> Flow:
        """Place one total on one date and retain input Claims.

        ``on`` is the date, or a ``PeriodTiming`` that dates the last movement
        by its Period. Without it, the last movement must record a date.
        ``missing`` treats unresolved amounts as ``total`` does. This explicit
        loss of temporal detail does not mutate the source Flow. Empty input
        is returned unchanged.
        """
        flow = self
        if not isinstance(missing, MissingValueHandling):
            raise TypeError("missing must be a MissingValueHandling")
        if not flow.movements:
            return flow
        quantity = flow.total(missing=missing)
        day = (
            flow.movements[-1].resolve(timing=on)
            if on is None or isinstance(on, PeriodTiming)
            else require_date(on)
        )
        claims = tuple(
            dict.fromkeys(c for s in flow.movements for c in (s.claims or ()))
        )
        movement = Movement(
            id=uuid4(),
            key=UNSET if flow.movements[-1].key is None else flow.movements[-1].key,
            date=day,
            magnitude=None if quantity is None else quantity.magnitude,
            claims=claims,
        )
        return flow.replace(movements=tuple([movement]))

    def extent(self) -> tuple[date, date] | None:
        """Return the coverage [start, end) of the nonzero amounts, or their first and last dates.

        Unresolved movements and zeroes are excluded. Period boundaries describe
        coverage even when independent payment dates are recorded.
        """
        flow = self
        selected = [
            s for s in flow.movements if s.magnitude is not None and s.magnitude != 0
        ]
        if not selected:
            return None
        first, last = selected[0], selected[-1]
        if first.period is not None and last.period is not None:
            return first.period.start, last.period.end
        return first.resolve(), last.resolve()

    def trim_empty(self) -> Flow:
        """Remove leading/trailing zero or unresolved rows, retaining interior gaps."""
        flow = self
        selected = [
            i
            for i, s in enumerate(flow.movements)
            if s.magnitude is not None and s.magnitude != 0
        ]
        return flow.replace(
            movements=tuple(
                flow.movements[selected[0] : selected[-1] + 1] if selected else ()
            )
        )


def _total_known(missing: MissingValueHandling, values: list[float]) -> bool:
    """Return whether the known values give the total of a Flow with unresolved amounts.

    ``ERROR`` raises. ``PROPAGATE`` gives no total; ``SKIP`` totals the known
    values when there is one; ``ZERO`` always totals them.
    """
    if missing is MissingValueHandling.ERROR:
        raise NumericalError("cannot total unresolved movements")
    return missing is MissingValueHandling.ZERO or (
        missing is MissingValueHandling.SKIP and bool(values)
    )


def _target(
    movements: Sequence[records.Movement],
    *,
    periods: Sequence[Period] | None,
    frequency: Frequency | None,
) -> Sequence[Period]:
    """Return the target Periods of a resample: given, or made from a frequency."""
    if (periods is None) == (frequency is None):
        raise TypeError("give periods or frequency, not both")
    if periods is not None:
        return periods
    assert frequency is not None
    covered = [m.period for m in movements if m.period is not None]
    if len(covered) != len(movements):
        raise ContractError("give periods= to resample dated movements")
    if not covered:
        raise ContractError("an empty Flow needs periods= to resample")
    start = min(period.start for period in covered)
    end = max(period.end for period in covered)
    count = count_steps(start, end, frequency=frequency)
    if offset(value=start, frequency=frequency, count=count) != end:
        raise AlignmentError(
            f"{frequency.value} Periods from {start} do not end at {end}; give periods=",
            code=Code.ALIGNMENT_PARTIAL,
            values={
                "span": f"{start.isoformat()}/{end.isoformat()}",
                "frequency": frequency.value,
            },
        )
    return Periods(start=start, frequency=frequency, count=count)


def _unpartitioned(movement: Movement, part: Period | None) -> AlignmentError:
    """Return the error for target Periods that do not partition a movement's Period.

    A target Period that ends after the movement's Period crosses it; otherwise
    the target Periods leave a gap in it.
    """
    period = cast("Period", movement.period)
    crosses = part is not None and part.end > period.end
    return AlignmentError(
        "the target Periods must partition each Period",
        code=Code.ALIGNMENT_CROSSES if crosses else Code.ALIGNMENT_GAP,
        values={"period": f"{period.start.isoformat()}/{period.end.isoformat()}"},
        targets=(movement.id,),
    )


def _split(flow: Flow, periods: Sequence[Period]) -> Flow:
    """Divide each period amount equally over the target Periods inside it.

    The target Periods must partition each source Period. The last part takes
    the remainder, so the parts add up to the amount.
    """
    targets = list(periods)
    movements = []
    position = 0
    for movement in flow.movements:
        if movement.period is None:
            raise ContractError("split needs period movements")
        while (
            position < len(targets) and targets[position].end <= movement.period.start
        ):
            position += 1
        parts = []
        cursor = movement.period.start
        while position < len(targets) and targets[position].start < movement.period.end:
            part = targets[position]
            if part.start != cursor or part.end > movement.period.end:
                raise _unpartitioned(movement, part)
            parts.append(part)
            cursor = part.end
            position += 1
        if cursor != movement.period.end:
            raise _unpartitioned(movement, None)
        if movement.magnitude is None:
            values: list[float | None] = [None] * len(parts)
        else:
            share = movement.number / len(parts)
            values = [share] * len(parts)
            values[-1] = movement.number - math.fsum([share] * (len(parts) - 1))
        for part, value in zip(parts, values, strict=True):
            movements.append(
                Movement(
                    id=uuid4(),
                    period=part,
                    magnitude=value,
                    claims=movement.claims if movement.claims else UNSET,
                )
            )
    return Flow(units=flow.units, movements=tuple(movements))
