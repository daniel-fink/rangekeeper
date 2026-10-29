"""Movement and Flow: the value types of dated and period quantities.

Stream coordinates several Flows.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from rangekeeper.flow._options import MissingValueHandling, ResampleMethod
from rangekeeper.money import (
    _encoded,
    _require,
    is_currency,
    to_number,
)
from rangekeeper.money import round as _round
from rangekeeper.quantity import Quantity, _is_number, _product, _sum_scale
from rangekeeper.schema import records
from rangekeeper.schema.kinds import register
from rangekeeper.schema.runtime import OMIT, UNSET
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    MissingReferenceError,
    NumericalError,
    UnitError,
)

if TYPE_CHECKING:
    from rangekeeper.duration import Frequency, Period
    from rangekeeper.duration.calendar import DayCount
    from rangekeeper.duration.period import PeriodTiming
    from rangekeeper.flow._options import MeanWeighting
    from rangekeeper.flow._table import StreamTable
    from rangekeeper.profile import Profile
    from rangekeeper.quantity import UnitSystem

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
            raise ValueError(f"unresolved/nonfinite movement: {movement.key}")
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
            raise ValueError("movement requires a date or period")
        return ("event", movement.date.isoformat(), movement.key)

    def resolve(self, *, timing: PeriodTiming | None = None) -> date:
        """Use a recorded date, or derive one from a period with an explicit convention.

        Recorded dates take precedence over the fallback convention. No movement is
        changed, and payment outside its coverage period is permitted.
        """
        movement = self
        from rangekeeper.duration.calendar import PeriodTiming, require_date

        if timing is not None and not isinstance(timing, PeriodTiming):
            raise TypeError("timing must be a PeriodTiming")
        if movement.date is not None:
            return require_date(movement.date)
        if movement.period is None:
            raise ValueError("movement requires a date or period")
        if timing is None:
            raise ValueError("undated period movement requires explicit timing")
        return movement.period.resolve(timing=timing)


def _from_amounts(
    amounts: Mapping[Period | date, Amount], units: str | None
) -> tuple[str, tuple[Movement, ...]]:
    """Return the units and Movements of a mapping of Periods or dates to amounts."""
    from rangekeeper.duration import Period
    from rangekeeper.quantity import default_units

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
    keys, magnitudes = [], []
    for key, value in amounts.items():
        if isinstance(value, str):
            value = Quantity(text=value)
        if isinstance(value, records.Quantity):
            value = (
                value.magnitude
                if value.units == units
                else default_units.convert(value, to=units).magnitude
            )
        elif value is not None and not _is_number(value):
            if not isinstance(value, Decimal):
                raise TypeError(f"amount {value!r} is not a number or a Quantity")
        keys.append(key)
        magnitudes.append(value)
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
        from rangekeeper.flow import Stream

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
        result = {}
        for movement in flow.movements:
            coordinate = movement.coordinate
            if coordinate in result:
                raise ValueError(
                    "duplicate coordinates make alignment ambiguous; use explicit key equations"
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

    def check(self, *, resolved: bool = False, units: UnitSystem | None = None) -> Flow:
        """Check the units against a unit system; resolved=True also requires numbers.

        A Flow keeps its own order and identity rules at construction. This
        check adds what depends on context: the unit system, and with
        resolved=True a finite number for every Movement. It returns this Flow
        and does not repair content or assign missing magnitudes.
        """
        from rangekeeper.quantity import default_units

        units = default_units if units is None else units
        units.compatible(self.units, self.units)
        if resolved:
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
        ids: Sequence[UUID] | None = None,
    ) -> Flow:
        """Construct dated entries with supplied or fresh IDs; repeated dates need distinct keys."""
        factory = cls
        from rangekeeper.duration.calendar import require_date

        if (
            len(dates) != len(magnitudes)
            or keys is not None
            and len(keys) != len(dates)
            or ids is not None
            and len(ids) != len(dates)
        ):
            raise ValueError("dates, magnitudes, keys and IDs must have equal lengths")
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
                    tuple(ids) if ids is not None else tuple(uuid4() for _ in dates),
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
        dates: Sequence[date | None] | None = None,
        ids: Sequence[UUID] | None = None,
        keys: Sequence[str | None] | None = None,
    ) -> Flow:
        """Construct quantities over periods without inventing payment dates.

        Supply dates only for independently known payment/observation dates. Omitted
        dates remain absent; valuation and presentation can resolve a convention later.
        Omitted IDs are generated. Omitted matching keys remain absent.
        """
        factory = cls
        from rangekeeper.duration.calendar import require_date

        if (
            len(periods) != len(magnitudes)
            or dates is not None
            and len(dates) != len(periods)
            or ids is not None
            and len(ids) != len(periods)
            or keys is not None
            and len(keys) != len(periods)
        ):
            raise ValueError(
                "periods, magnitudes, dates, keys and IDs must have equal lengths"
            )
        if is_currency(units):
            # Convert once here, so the Flow need not rebuild its Movements.
            magnitudes = [
                None if v is None else cast(str, _encoded(v)) for v in magnitudes
            ]
        movements = []
        for i, (period, magnitude) in enumerate(zip(periods, magnitudes, strict=True)):
            day = dates[i] if dates is not None else None
            movements.append(
                Movement(
                    id=ids[i] if ids is not None else uuid4(),
                    key=keys[i] if keys is not None and keys[i] is not None else UNSET,
                    period=period,
                    magnitude=magnitude,
                    date=UNSET if day is None else require_date(day),
                )
            )
        result = factory(units=units, movements=tuple(movements))
        return result

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
        from rangekeeper.profile import Profile

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
            raise ValueError("the profile must give one factor for each Period")
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
        from rangekeeper.quantity import Quantity, default_units

        unit_system = default_units if unit_system is None else unit_system
        if not unit_system.compatible(flow.units, units):
            raise ValueError("incompatible Flow units")
        return flow.replace(
            movements=tuple(
                s.replace(
                    magnitude=(
                        None
                        if s.magnitude is None
                        else unit_system.convert(
                            Quantity(magnitude=s.magnitude, units=flow.units),
                            to=units,
                        ).magnitude
                    )
                )
                for s in flow.movements
            ),
            units=units,
        )

    def scale(self, factor: float) -> Flow:
        """Create independent scaled movements with fresh IDs, retaining missing amounts."""
        flow = self
        if type(factor) not in (int, float) or not math.isfinite(factor):
            raise ValueError("factor must be finite")
        return flow.replace(
            movements=tuple(
                s.replace(
                    id=uuid4(),
                    magnitude=(None if s.magnitude is None else s.number * factor),
                )
                for s in flow.movements
            )
        )

    def round(self, *, places: int | None = None, mode: str = ROUND_HALF_EVEN) -> Flow:
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
                            Decimal(s.magnitude),
                            flow.units,
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

        This is a numerical sum. The model determines whether summation expresses
        the intended quantity; no balance, rate or other interpretation is inferred.
        """
        flow = self
        from rangekeeper.quantity import Quantity

        if not isinstance(missing, MissingValueHandling):
            raise TypeError("missing must be a MissingValueHandling")
        if missing not in (
            MissingValueHandling.ERROR,
            MissingValueHandling.PROPAGATE,
            MissingValueHandling.SKIP,
        ):
            raise ValueError("total missing must be error, propagate or skip")
        values = [s.number for s in flow.movements if s.magnitude is not None]
        if len(values) != len(flow.movements):
            if missing == MissingValueHandling.ERROR:
                raise ValueError("cannot total unresolved movements")
            if missing == MissingValueHandling.PROPAGATE or not values:
                return None
        return Quantity(magnitude=math.fsum(values), units=flow.units)

    def at(self, *, on: date) -> Quantity:
        """Return the amount of the Period that contains a date, or of the event on it.

        A date with no amount raises MissingReferenceError; several events on
        one date raise AmbiguousReferenceError; an unresolved amount raises
        NumericalError.
        """
        from rangekeeper.duration.calendar import require_date

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
            raise ValueError("only a Flow over Periods can shift by Periods")
        if any(
            a.period.end != b.period.start  # type: ignore[union-attr]
            for a, b in pairwise(movements)
        ):
            raise ValueError("shift needs gap-free Periods")
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
            raise ValueError(
                "cannot add dated and period amounts; use Stream.sum, which dates "
                "each period amount"
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
            from rangekeeper.flow._mapping import alignment

            product = _product(self.units, other.units, divide)
            movements = []
            for movement, (match,) in alignment((other,), self):
                value = (
                    None
                    if movement.magnitude is None or match.magnitude is None
                    else product.apply(movement.number, match.number, divide)
                )
                movements.append(movement.replace(id=uuid4(), magnitude=value))
            return self._checked(movements, product.units)
        return NotImplemented

    def _each(self, operation, units: str) -> Flow:
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

        Partial period overlap raises ValueError; trimming must not silently allocate
        a period quantity or substitute an assumed payment date for its coverage.
        """
        flow = self
        from rangekeeper.duration import Period

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
                    raise ValueError(
                        "trim crosses a movement period; allocate explicitly"
                    )
                selected.append(movement)
        return flow.replace(movements=tuple(selected))

    def resample(
        self,
        *,
        periods: Sequence[Period] | None = None,
        frequency: Frequency | None = None,
        method: ResampleMethod,
        weighting: MeanWeighting | None = None,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
    ) -> Flow:
        """Put the amounts on other Periods: explicit ``periods``, or a ``frequency``.

        A frequency makes the Periods from the start of the first Period to the
        end of the last one; they must fit exactly. ``SPLIT`` divides each
        amount equally over the shorter Periods inside its Period. The other
        methods group whole movements onto longer Periods; a mean needs an
        explicit weighting. ``Stream.resample`` takes the same arguments and
        also reports coverage.
        """
        flow = self
        periods = _target(flow.movements, periods=periods, frequency=frequency)
        if method is ResampleMethod.SPLIT:
            if weighting is not None:
                raise ValueError("weighting applies only to means")
            return _split(flow, periods)
        from rangekeeper.flow._batch import Batch

        return (
            Batch.prepare((flow,))
            .resample(
                periods=periods,
                methods=(method,),
                weightings=(weighting,),
                missing=missing,
            )
            .flows()[0]
        )

    def integrate(
        self,
        *,
        exposures: Sequence[Quantity] | None = None,
        day_count: DayCount | None = None,
        units: str | None = None,
    ) -> Flow:
        """Multiply entries by supplied exposures or declared period year fractions.

        Explicit exposures support calendar-month conventions and non-time exposures.
        A day-count convention uses period boundaries and a quantity measured in years.
        Calling this operation supplies the integration rule; the Flow has no rate kind.
        """
        flow = self
        from rangekeeper.duration.calendar import DayCount, year_fraction
        from rangekeeper.quantity import Quantity, default_units

        if day_count is not None and not isinstance(day_count, DayCount):
            raise TypeError("day_count must be a DayCount")
        if (exposures is None) == (day_count is None):
            raise ValueError("supply exactly one of exposures or day_count")
        if exposures is None:
            assert day_count is not None
            if any(s.period is None for s in flow.movements):
                raise ValueError("day-count integration requires bounded periods")
            exposures = tuple(
                Quantity(
                    magnitude=year_fraction(
                        s.period.start, s.period.end, convention=day_count
                    ),
                    units="year",
                )
                for s in flow.movements
                if s.period is not None
            )
        if len(exposures) != len(flow.movements):
            raise ValueError("exposure count differs from movement count")
        output_units = units or (
            default_units.multiply(flow.units, exposures[0].units)
            if exposures
            else None
        )
        if output_units is None:
            raise ValueError("empty integration requires explicit output units")
        movements = []
        for movement, exposure in zip(flow.movements, exposures, strict=True):
            product_unit = default_units.multiply(flow.units, exposure.units)
            magnitude = (
                None
                if movement.magnitude is None
                else default_units.convert(
                    Quantity(
                        magnitude=movement.number * exposure.number,
                        units=product_unit,
                    ),
                    to=output_units,
                ).magnitude
            )
            movements.append(movement.replace(id=uuid4(), magnitude=magnitude))
        return flow.replace(movements=tuple(movements), units=output_units)

    def multiply(self, *others: Flow) -> Flow:
        """Multiply known movements at exact common coordinates, with their units.

        Dimensionless scales such as percent become ratios first. Physical dimensions,
        including time, remain in the result. The calling model determines the
        meaning of the product; no semantic classification is inferred.
        """
        from rangekeeper.flow._batch import align
        from rangekeeper.flow._options import AlignmentJoin
        from rangekeeper.quantity import default_units

        flows = tuple(
            (
                flow.convert(units="dimensionless")
                if default_units.compatible(flow.units, "dimensionless")
                else flow
            )
            for flow in (self, *others)
        )
        aligned, _ = align(
            flows, join=AlignmentJoin.EXACT, missing=MissingValueHandling.ERROR
        )
        unit = "dimensionless"
        for flow in flows:
            unit = default_units.multiply(unit, flow.units)
        movements = [
            group[0].replace(
                id=uuid4(),
                magnitude=math.prod(s.number for s in group),
                claims=tuple(dict.fromkeys(c for s in group for c in s.claims or ())),
            )
            for group in zip(*(flow.movements for flow in aligned), strict=True)
        ]
        return flows[0].replace(movements=tuple(movements), units=unit)

    def clean(self, *, remove_zeroes: bool = False) -> Flow:
        """Explicitly remove unresolved movements, and optionally zeroes; do not impute data."""
        flow = self
        return flow.replace(
            movements=tuple(
                s
                for s in flow.movements
                if s.magnitude is not None and (not remove_zeroes or s.magnitude != 0)
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
        on: date | None = None,
        timing: PeriodTiming | None = None,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
    ) -> Flow:
        """Place one total on a selected date and retain input Claims.

        For period content, supply on or a timing convention unless the final movement
        already records a date. This explicit loss of temporal detail does not mutate
        the source Flow. Empty input is returned unchanged.
        """
        flow = self
        from rangekeeper.duration.calendar import PeriodTiming, require_date

        if timing is not None and not isinstance(timing, PeriodTiming):
            raise TypeError("timing must be a PeriodTiming")
        if not isinstance(missing, MissingValueHandling):
            raise TypeError("missing must be a MissingValueHandling")
        if missing is MissingValueHandling.ZERO:
            raise ValueError("total missing must be error, propagate or skip")
        if on is not None and timing is not None:
            raise ValueError("supply on or timing, not both")
        if not flow.movements:
            return flow
        quantity = flow.total(missing=missing)
        day = (
            require_date(on)
            if on is not None
            else flow.movements[-1].resolve(timing=timing)
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

    def extent(self, *, include_zeroes: bool = False) -> tuple[date, date] | None:
        """Return selected period coverage [start,end), or first/last dated events.

        Unresolved movements and, by default, zeroes are excluded. Period boundaries
        describe coverage even when independent payment dates are recorded.
        """
        flow = self
        selected = [
            s
            for s in flow.movements
            if s.magnitude is not None and (include_zeroes or s.magnitude != 0)
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
    from rangekeeper.duration import Periods
    from rangekeeper.duration.calendar import count_steps, offset

    assert frequency is not None
    covered = [m.period for m in movements if m.period is not None]
    if len(covered) != len(movements):
        raise ValueError("give periods= to resample dated movements")
    if not covered:
        raise ValueError("an empty Flow needs periods= to resample")
    start = min(period.start for period in covered)
    end = max(period.end for period in covered)
    count = count_steps(start, end, frequency=frequency)
    if offset(start, frequency=frequency, count=count) != end:
        raise ValueError(
            f"{frequency.value} Periods from {start} do not end at {end}; give periods="
        )
    return Periods(start=start, frequency=frequency, count=count)


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
            raise ValueError("SPLIT needs period movements")
        while (
            position < len(targets) and targets[position].end <= movement.period.start
        ):
            position += 1
        parts = []
        cursor = movement.period.start
        while position < len(targets) and targets[position].start < movement.period.end:
            part = targets[position]
            if part.start != cursor or part.end > movement.period.end:
                raise ValueError("the target Periods must partition each Period")
            parts.append(part)
            cursor = part.end
            position += 1
        if cursor != movement.period.end:
            raise ValueError("the target Periods must partition each Period")
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
