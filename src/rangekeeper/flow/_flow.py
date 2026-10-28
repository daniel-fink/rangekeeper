"""Movement and Flow: the value types of dated and period quantities.

Stream coordinates several Flows.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from rangekeeper.flow._options import MissingValueHandling
from rangekeeper.schema import records
from rangekeeper.schema.kinds import register
from rangekeeper.schema.runtime import UNSET

if TYPE_CHECKING:
    from rangekeeper.duration import Period
    from rangekeeper.duration.calendar import DayCount
    from rangekeeper.duration.period import PeriodTiming
    from rangekeeper.flow._options import MeanWeighting, ResamplingMethod
    from rangekeeper.model.display import StreamTable
    from rangekeeper.quantity import UnitSystem
    from rangekeeper.schema.records import Quantity


@register
class Movement(records.Movement):
    """Coordinate and numerical access without changing recorded evidence."""

    __slots__ = ()

    @property
    def number(self) -> float:
        """Read a finite magnitude; unresolved data must be handled before arithmetic."""
        movement = self
        value = movement.magnitude
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


@register
class Flow(records.Flow):
    """Validate or transform one immutable Flow, preserving coordinate meaning."""

    __slots__ = ()

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

        return Stream({"Flow" if name is None else name: self}).display(
            transpose=transpose,
            precision=precision,
        )

    def _repr_html_(self) -> str:
        return self.display()._repr_html_()

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

    def check(self, *, resolved: bool = False, units: UnitSystem | None = None) -> Flow:
        """Check units, movement identity, date ordering and non-overlapping period coverage.

        Return this Flow after checking; resolved=True also requires finite numbers.
        This check does not repair content or assign missing magnitudes.
        All movements in one Flow use either periods or dated events. Period order uses
        coverage, not optional payment dates; those dates may lie outside the period.
        """
        flow = self

        from rangekeeper.duration.calendar import require_date
        from rangekeeper.quantity import default_units

        units = default_units if units is None else units
        units.compatible(flow.units, flow.units)
        identities = set()
        events: dict[date, list[str | None]] = {}
        previous = None
        previous_end = None
        mode = None
        for movement in flow.movements:
            if movement.id in identities:
                raise ValueError(f"duplicate Movement UUID: {movement.id}")
            identities.add(movement.id)
            if movement.date is not None:
                require_date(movement.date)
            if movement.period is None and movement.date is None:
                raise ValueError("movement requires a date or period")
            period_mode = movement.period is not None
            if mode is not None and mode != period_mode:
                raise ValueError("Flow cannot mix event and period movements")
            mode = period_mode
            if movement.period is not None:
                movement.period.check()
                if previous_end is not None and movement.period.start < previous_end:
                    raise ValueError("Flow periods overlap or are out of order")
                previous_end = movement.period.end
            else:
                assert movement.date is not None
                if previous is not None and movement.date < previous:
                    raise ValueError("Flow movements must be ordered by date")
                previous = movement.date
                keys = events.setdefault(movement.date, [])
                keys.append(movement.key)
                if len(keys) > 1 and (None in keys or len(set(keys)) != len(keys)):
                    raise ValueError(
                        "repeated event dates require distinct nonblank matching keys"
                    )
            if len(movement.claims or ()) != len(set(movement.claims or ())):
                raise ValueError("duplicate movement Claim")
        if resolved:
            for movement in flow.movements:
                _ = movement.number  # Raises for a Movement without a resolved number.
        return flow

    @classmethod
    def from_events(
        cls,
        dates: Sequence[date],
        magnitudes: Sequence[int | float | None],
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
        result.check()
        return result

    @classmethod
    def from_periods(
        cls,
        periods: Sequence[Period],
        magnitudes: Sequence[int | float | None],
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
        movements = []
        for i, (period, magnitude) in enumerate(zip(periods, magnitudes, strict=True)):
            period.check()
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
        result.check()
        return result

    def clone(self) -> Flow:
        """Copy content with fresh Movement IDs for an independent owning Value.

        Dates, matching keys, magnitudes and evidence remain unchanged. Revision
        updates use replace() instead, preserving the existing identities.
        """
        flow = self
        return flow.replace(
            movements=tuple(m.replace(id=uuid4()) for m in flow.movements)
        ).check()

    def convert(self, *, units: str, unit_system: UnitSystem | None = None) -> Flow:
        """Convert all known movements together; retain unresolved movements and evidence."""
        flow = self
        from rangekeeper.quantity import default_units
        from rangekeeper.schema.records import Quantity

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
        ).check()

    def scale(self, factor: float) -> Flow:
        """Create independent scaled movements with fresh IDs, retaining missing amounts."""
        flow = self
        if type(factor) not in (int, float) or not math.isfinite(factor):
            raise ValueError("factor must be finite")
        return flow.replace(
            movements=tuple(
                s.replace(
                    id=uuid4(),
                    magnitude=None if s.magnitude is None else s.magnitude * factor,
                )
                for s in flow.movements
            )
        ).check()

    def negate(self) -> Flow:
        """Reverse each known magnitude while keeping unresolved entries and Claims."""
        flow = self
        return flow.scale(-1)

    def total(
        self, *, missing: MissingValueHandling = MissingValueHandling.ERROR
    ) -> Quantity | None:
        """Sum entries over time, retaining their units.

        This is a numerical sum. The model determines whether summation expresses
        the intended quantity; no balance, rate or other interpretation is inferred.
        """
        flow = self
        from rangekeeper.schema.records import Quantity

        flow.check()
        if not isinstance(missing, MissingValueHandling):
            raise TypeError("missing must be a MissingValueHandling")
        if missing not in (
            MissingValueHandling.ERROR,
            MissingValueHandling.PROPAGATE,
            MissingValueHandling.SKIP,
        ):
            raise ValueError("total missing must be error, propagate or skip")
        values = [s.magnitude for s in flow.movements if s.magnitude is not None]
        if len(values) != len(flow.movements):
            if missing == MissingValueHandling.ERROR:
                raise ValueError("cannot total unresolved movements")
            if missing == MissingValueHandling.PROPAGATE or not values:
                return None
        return Quantity(magnitude=math.fsum(values), units=flow.units)

    def trim(self, span: Period) -> Flow:
        """Select dates in [start, end) of a Period or Span, or whole periods inside it.

        Partial period overlap raises ValueError; trimming must not silently allocate
        a period quantity or substitute an assumed payment date for its coverage.
        """
        flow = self
        from rangekeeper.duration import Period

        if not isinstance(span, Period):
            raise TypeError("span must be a Period or Span")
        span.check()
        start, end = span.start, span.end
        flow.check()
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
        return flow.replace(movements=tuple(selected)).check()

    def resample(
        self,
        periods: Sequence[Period],
        *,
        method: ResamplingMethod,
        weighting: MeanWeighting | None = None,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
    ) -> Flow:
        """Group whole movements onto explicit periods; a mean needs an explicit weighting.

        ``Stream.resample`` takes the same arguments and also reports coverage.
        """
        flow = self
        from rangekeeper.flow._batch import Batch

        return (
            Batch.prepare((flow,))
            .resample(
                periods, methods=(method,), weightings=(weighting,), missing=missing
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
        from rangekeeper.quantity import default_units
        from rangekeeper.schema.records import Quantity

        flow.check()
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
                        magnitude=movement.magnitude * exposure.magnitude,
                        units=product_unit,
                    ),
                    to=output_units,
                ).magnitude
            )
            movements.append(movement.replace(id=uuid4(), magnitude=magnitude))
        return flow.replace(movements=tuple(movements), units=output_units).check()

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
        return flows[0].replace(movements=tuple(movements), units=unit).check()

    def clean(self, *, remove_zeroes: bool = False) -> Flow:
        """Explicitly remove unresolved movements, and optionally zeroes; do not impute data."""
        flow = self
        return flow.replace(
            movements=tuple(
                s
                for s in flow.movements
                if s.magnitude is not None and (not remove_zeroes or s.magnitude != 0)
            )
        ).check()

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
                else movement.magnitude - previous
            )
            movements.append(movement.replace(id=uuid4(), magnitude=magnitude))
            previous = movement.magnitude
        return flow.replace(movements=tuple(movements)).check()

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
        return flow.replace(movements=tuple([movement])).check()

    def extent(self, *, include_zeroes: bool = False) -> tuple[date, date] | None:
        """Return selected period coverage [start,end), or first/last dated events.

        Unresolved movements and, by default, zeroes are excluded. Period boundaries
        describe coverage even when independent payment dates are recorded.
        """
        flow = self
        flow.check()
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
        flow.check()
        selected = [
            i
            for i, s in enumerate(flow.movements)
            if s.magnitude is not None and s.magnitude != 0
        ]
        return flow.replace(
            movements=tuple(
                flow.movements[selected[0] : selected[-1] + 1] if selected else ()
            )
        ).check()
