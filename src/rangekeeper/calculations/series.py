"""Pure Flow arithmetic with explicit alignment, units and missing-value rules.

Polars performs key alignment and grouped reductions. Rangekeeper checks units,
coordinates and missing values. The overall model logic selects the operations
and is responsible for their meaning.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import json
import math
from typing import Literal

from ..model.flow import (
    Flow,
    Movement,
    movement_coordinate,
    validate_flow,
    resolve_date,
)
from ..model.duration import Period
from ..model.measure import Quantity
from ..temporal.period import PeriodTiming, validate_period
from ..temporal.calendar import DayCount, elapsed_days, year_fraction
from ..units import UnitSystem, default_units

from ._flow import replace_movements, replace_movement

Missing = Literal["error", "propagate", "skip", "zero"]


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    flows: tuple[Flow, ...]
    coverage: tuple[tuple[bool, ...], ...]


@dataclass(frozen=True, slots=True)
class AggregateResult:
    flow: Flow
    coverage: tuple[float, ...]


def _polars():
    try:
        import polars as pl
    except ImportError as error:
        raise ImportError(
            "Install rangekeeper[calculations] for Flow calculations"
        ) from error
    return pl


def _key(movement: Movement) -> str:
    return json.dumps(movement_coordinate(movement))


def align(
    flows: Sequence[Flow], *, join: str = "exact", missing: Missing = "error"
) -> AlignmentResult:
    """Align on explicit coordinates; zero fills absent rows, never unresolved movements.

    Exact alignment is the default. Union/intersection must be requested. Coverage
    records whether each input had a known movement before any requested filling.
    """
    if join not in ("exact", "union", "intersection") or missing not in (
        "error",
        "propagate",
        "skip",
        "zero",
    ):
        raise ValueError("invalid alignment or missing policy")
    if not flows:
        raise ValueError("alignment needs at least one Flow")
    maps, templates = [], {}
    modes: set[bool] = set()
    for flow in flows:
        validate_flow(flow)
        mapping = {_key(movement): movement for movement in flow.movements}
        maps.append(mapping)
        templates.update(
            {key: movement for key, movement in mapping.items() if key not in templates}
        )
        modes.update(movement.period is not None for movement in flow.movements)
    if len(modes) > 1:
        raise ValueError("cannot align event dates with period coverage")
    keys = list(maps[0])
    if join == "exact" and any(list(mapping) != keys for mapping in maps[1:]):
        raise ValueError(
            "Flow coordinates differ; request union/intersection explicitly"
        )
    if join == "union":
        keys = list(templates)
    elif join == "intersection":
        keys = [key for key in keys if all(key in mapping for mapping in maps)]

    def order(key: str) -> tuple[date, str]:
        movement = templates[key]
        period = movement.period
        return (period.start if period is not None else resolve_date(movement), key)

    keys.sort(key=order)
    pl = _polars()
    grid = pl.DataFrame({"coordinate": keys}, schema={"coordinate": pl.String})
    aligned, coverages = [], []
    for flow, mapping in zip(flows, maps):
        frame = pl.DataFrame(
            {
                "coordinate": list(mapping),
                "magnitude": [s.magnitude for s in mapping.values()],
            },
            schema={"coordinate": pl.String, "magnitude": pl.Float64},
        )
        values = grid.join(frame, on="coordinate", how="left", maintain_order="left")[
            "magnitude"
        ].to_list()
        movements, coverage = [], []
        for key, magnitude in zip(keys, values):
            present = key in mapping
            known = present and magnitude is not None
            coverage.append(known)
            if not known and missing == "error":
                raise ValueError(f"missing/unresolved movement: {templates[key].key}")
            if not present and missing == "zero":
                magnitude = 0.0
            source = mapping.get(key, templates[key])
            movements.append(
                replace_movement(
                    source, magnitude, claims=source.claims if present else ()
                )
            )
        aligned.append(replace_movements(flow, movements))
        coverages.append(tuple(coverage))
    return AlignmentResult(tuple(aligned), tuple(coverages))


def convert(flow: Flow, *, units: str, unit_system: UnitSystem = default_units) -> Flow:
    """Convert all known movements together; retain unresolved movements and evidence."""
    if not unit_system.compatible(flow.units, units):
        raise ValueError("incompatible Flow units")
    return replace_movements(
        flow,
        [
            replace_movement(
                s,
                (
                    None
                    if s.magnitude is None
                    else unit_system.convert(
                        Quantity(magnitude=s.magnitude, units=flow.units), to=units
                    ).magnitude
                ),
            )
            for s in flow.movements
        ],
        units=units,
    )


def sum_flows(
    flows: Sequence[Flow],
    *,
    units: str | None = None,
    missing: Missing = "error",
    join: str = "exact",
) -> AggregateResult:
    """Add compatible quantities pointwise; all-missing results remain unresolved."""
    if not flows:
        raise ValueError("sum needs at least one Flow")
    converted = tuple(convert(flow, units=units or flows[0].units) for flow in flows)
    aligned = align(converted, join=join, missing=missing)
    movements, coverage = [], []
    for index, group in enumerate(zip(*(flow.movements for flow in aligned.flows))):
        known = [s.magnitude for s in group if s.magnitude is not None]
        complete = len(known) == len(group)
        magnitude = (
            math.fsum(known) if known and (complete or missing == "skip") else None
        )
        claims = tuple(
            dict.fromkeys(c for movement in group for c in (movement.claims or ()))
        )
        movements.append(replace_movement(group[0], magnitude, claims=claims))
        coverage.append(sum(row[index] for row in aligned.coverage) / len(group))
    return AggregateResult(replace_movements(converted[0], movements), tuple(coverage))


def multiply_flows(flows: Sequence[Flow]) -> Flow:
    """Multiply aligned known movements and units without removing time dimensions.

    Normalize dimensionless scales such as percent to ratios before multiplication.
    Physical dimensions, including time, remain in the result. The calling model
    determines the meaning of the product; no semantic classification is inferred.
    """
    if not flows:
        raise ValueError("product needs at least one Flow")
    flows = tuple(
        convert(flow, units="dimensionless")
        if default_units.compatible(flow.units, "dimensionless")
        else flow
        for flow in flows
    )
    aligned = align(flows)
    unit = "dimensionless"
    for flow in flows:
        unit = default_units.multiply(unit, flow.units)
    movements = [
        replace_movement(
            group[0],
            math.prod(s.magnitude for s in group),
            claims=tuple(dict.fromkeys(c for s in group for c in (s.claims or ()))),
        )
        for group in zip(*(flow.movements for flow in aligned.flows))
    ]
    return replace_movements(flows[0], movements, units=unit)


def scale(flow: Flow, factor: float) -> Flow:
    """Multiply by a finite dimensionless scalar, preserving missing movements."""
    if type(factor) not in (int, float) or not math.isfinite(factor):
        raise ValueError("factor must be finite")
    return replace_movements(
        flow,
        [
            replace_movement(s, None if s.magnitude is None else s.magnitude * factor)
            for s in flow.movements
        ],
    )


def negate(flow: Flow) -> Flow:
    return scale(flow, -1)


def total(flow: Flow, *, missing: Missing = "error") -> Quantity | None:
    """Sum entries over time, retaining their units.

    This is a numerical sum. The model determines whether summation expresses
    the intended quantity; no balance, rate or other interpretation is inferred.
    """
    validate_flow(flow)
    if missing not in ("error", "propagate", "skip"):
        raise ValueError("total missing must be error, propagate or skip")
    values = [s.magnitude for s in flow.movements if s.magnitude is not None]
    if len(values) != len(flow.movements):
        if missing == "error":
            raise ValueError("cannot total unresolved movements")
        if missing == "propagate" or not values:
            return None
    return Quantity(magnitude=math.fsum(values), units=flow.units)


def integrate(
    flow: Flow,
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
    validate_flow(flow)
    if (exposures is None) == (day_count is None):
        raise ValueError("supply exactly one of exposures or day_count")
    if exposures is None:
        assert day_count is not None
        if any(s.period is None for s in flow.movements):
            raise ValueError("day-count integration requires bounded periods")
        exposures = tuple(
            Quantity(
                magnitude=year_fraction(
                    s.period.start,
                    s.period.end,
                    convention=day_count,
                ),
                units="year",
            )
            for s in flow.movements
            if s.period is not None
        )
    if len(exposures) != len(flow.movements):
        raise ValueError("exposure count differs from movement count")
    output_units = units or (
        default_units.multiply(flow.units, exposures[0].units) if exposures else None
    )
    if output_units is None:
        raise ValueError("empty integration requires explicit output units")
    movements = []
    for movement, exposure in zip(flow.movements, exposures):
        product_unit = default_units.multiply(flow.units, exposure.units)
        magnitude = (
            None
            if movement.magnitude is None
            else default_units.convert(
                Quantity(
                    magnitude=movement.magnitude * exposure.magnitude, units=product_unit
                ),
                to=output_units,
            ).magnitude
        )
        movements.append(replace_movement(movement, magnitude))
    return replace_movements(flow, movements, units=output_units)


def resample(
    flow: Flow,
    *,
    periods: Sequence[Period],
    reduction: str,
    missing: Missing = "error",
    weighting: Literal["observations", "elapsed"] | None = None,
) -> AggregateResult:
    """Reduce observations into a complete period grid with explicit missing rules.

    The caller selects sum, first, last, min, max or mean. Means require an explicit
    observations/elapsed weighting choice; elapsed weighting requires bounded
    movements. No reduction is inferred from the meaning of the data. Coverage is
    the fraction of known movements, not continuous time coverage. Bounded movements
    cannot cross target periods; allocate them explicitly first. missing="zero"
    fills empty target groups only, never unresolved entries in a populated group.
    """
    from ..model.flow import from_periods

    validate_flow(flow)
    if missing not in ("error", "propagate", "skip", "zero"):
        raise ValueError("invalid missing policy")
    if reduction not in {"sum", "first", "last", "mean", "min", "max"}:
        raise ValueError("unsupported resampling reduction")
    if (
        weighting not in (None, "observations", "elapsed")
        or weighting is not None
        and reduction != "mean"
    ):
        raise ValueError("weighting applies only to means")
    if reduction == "mean" and weighting is None:
        raise ValueError("means require explicit weighting")
    if weighting == "elapsed" and any(s.period is None for s in flow.movements):
        raise ValueError("elapsed weighting requires bounded movements")
    periods = tuple(periods)
    for i, period in enumerate(periods):
        validate_period(period)
        if i and elapsed_days(periods[i - 1].end, period.start) < 0:
            raise ValueError("resampling periods overlap or are unordered")
    groups: list[list[Movement]] = [[] for _ in periods]
    for movement in flow.movements:
        if movement.period is not None:
            # Resampling period content groups by coverage, not payment date.
            matches = [
                i
                for i, period in enumerate(periods)
                if period.start <= movement.period.start
                and movement.period.end <= period.end
            ]
        else:
            point = resolve_date(movement)
            matches = [
                i
                for i, period in enumerate(periods)
                if period.start <= point < period.end
            ]
        if not matches:
            raise ValueError(
                f"movement is outside or crosses target periods: {movement.key}"
            )
        groups[matches[0]].append(movement)
    pl = _polars()
    rows = [
        {
            "group": i,
            "magnitude": s.magnitude,
            "weight": (
                elapsed_days(s.period.start, s.period.end)
                if weighting == "elapsed" and s.period is not None
                else 1.0
            ),
        }
        for i, movements in enumerate(groups)
        for s in movements
    ]
    frame = pl.DataFrame(
        rows, schema={"group": pl.Int64, "magnitude": pl.Float64, "weight": pl.Float64}
    )
    if reduction == "mean":
        numerator = (pl.col("magnitude") * pl.col("weight")).sum()
        denominator = pl.col("weight").filter(pl.col("magnitude").is_not_null()).sum()
        expr = (numerator / denominator).alias("result")
    else:
        expr = getattr(pl.col("magnitude"), reduction)().alias("result")
    reduced = dict(frame.group_by("group", maintain_order=True).agg(expr).iter_rows())
    values, coverages = [], []
    for i, movements in enumerate(groups):
        known = sum(s.magnitude is not None for s in movements)
        complete = bool(movements) and known == len(movements)
        coverages.append(known / len(movements) if movements else 0.0)
        if not complete and missing == "error":
            raise ValueError(f"empty/unresolved target period: {i}")
        value = reduced.get(i) if complete or missing == "skip" and known else None
        if not movements and missing == "zero":
            value = 0.0
        values.append(value)
    result = from_periods(
        periods,
        values,
        units=flow.units,
    )
    result = replace_movements(
        result,
        [
            replace_movement(
                s,
                s.magnitude,
                claims=tuple(
                    dict.fromkeys(c for origin in group for c in (origin.claims or ()))
                ),
            )
            for s, group in zip(result.movements, groups)
        ],
    )
    return AggregateResult(result, tuple(coverages))


def trim(flow: Flow, *, start: date, end: date) -> Flow:
    """Select dates in [start, end) or whole periods contained in that interval.

    Partial period overlap raises ValueError; trimming must not silently allocate
    a period quantity or substitute an assumed payment date for its coverage.
    """
    validate_flow(flow)
    if elapsed_days(start, end) < 0:
        raise ValueError("trim end precedes start")
    selected = []
    for movement in flow.movements:
        if movement.period is None:
            if start <= resolve_date(movement) < end:
                selected.append(movement)
        else:
            period = movement.period
            if period.end <= start or period.start >= end:
                continue
            if period.start < start or period.end > end:
                raise ValueError("trim crosses a movement period; allocate explicitly")
            selected.append(movement)
    return replace_movements(flow, selected)


def clean(flow: Flow, *, remove_zeroes: bool = False) -> Flow:
    """Explicitly remove unresolved movements, and optionally zeroes; do not impute data."""
    return replace_movements(
        flow,
        [
            s
            for s in flow.movements
            if s.magnitude is not None and (not remove_zeroes or s.magnitude != 0)
        ],
    )


def difference(flow: Flow, *, initial: float | None = None) -> Flow:
    """Return adjacent differences; a missing neighbour yields an unresolved movement.

    The first movement is unresolved unless the caller supplies an initial value in
    the Flow's units. The model determines what the changes represent.
    """
    previous, movements = initial, []
    for movement in flow.movements:
        magnitude = (
            None
            if previous is None or movement.magnitude is None
            else movement.magnitude - previous
        )
        movements.append(replace_movement(movement, magnitude))
        previous = movement.magnitude
    return replace_movements(flow, movements)


def collapse(
    flow: Flow,
    *,
    on: date | None = None,
    timing: PeriodTiming | None = None,
    missing: Missing = "error",
) -> Flow:
    """Place one total on a selected date and retain input Claims.

    For period content, supply on or a timing convention unless the final movement
    already records a date. This explicit loss of temporal detail does not mutate
    the source Flow. Empty input is returned unchanged.
    """
    from ..temporal.calendar import require_date

    if on is not None and timing is not None:
        raise ValueError("supply on or timing, not both")
    if not flow.movements:
        return flow
    quantity = total(flow, missing=missing)
    day = (
        require_date(on)
        if on is not None
        else resolve_date(flow.movements[-1], timing=timing)
    )
    claims = tuple(dict.fromkeys(c for s in flow.movements for c in (s.claims or ())))
    movement = Movement(
        key=flow.movements[-1].key,
        date=day,
        magnitude=None if quantity is None else quantity.magnitude,
        claims=claims,
    )
    return replace_movements(flow, [movement])


def reduce_flows(
    flows: Sequence[Flow],
    *,
    reducer: str,
    units: str | None = None,
    missing: Missing = "error",
    join: str = "exact",
) -> AggregateResult:
    """Reduce aligned compatible Flows with sum/min/max and explicit partial coverage."""
    if reducer == "sum":
        return sum_flows(flows, units=units, missing=missing, join=join)
    if reducer not in {"min", "max"} or not flows:
        raise ValueError("extrema require compatible Flows and min/max reducer")
    converted = tuple(convert(flow, units=units or flows[0].units) for flow in flows)
    aligned = align(converted, join=join, missing=missing)
    result, coverage = [], []
    for i, movements in enumerate(zip(*(flow.movements for flow in aligned.flows))):
        known = [s.magnitude for s in movements if s.magnitude is not None]
        value = (
            (min if reducer == "min" else max)(known)
            if known and (len(known) == len(movements) or missing == "skip")
            else None
        )
        result.append(
            replace_movement(
                movements[0],
                value,
                claims=tuple(
                    dict.fromkeys(c for s in movements for c in (s.claims or ()))
                ),
            )
        )
        coverage.append(sum(row[i] for row in aligned.coverage) / len(movements))
    return AggregateResult(replace_movements(converted[0], result), tuple(coverage))


def find_extent(
    flow: Flow, *, include_zeroes: bool = False
) -> tuple[date, date] | None:
    """Return selected period coverage [start,end), or first/last dated events.

    Unresolved movements and, by default, zeroes are excluded. Period boundaries
    describe coverage even when independent payment dates are recorded.
    """
    validate_flow(flow)
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
    return resolve_date(first), resolve_date(last)


def trim_empty(flow: Flow) -> Flow:
    """Remove leading/trailing zero or unresolved rows, retaining interior gaps."""
    validate_flow(flow)
    selected = [
        i
        for i, s in enumerate(flow.movements)
        if s.magnitude is not None and s.magnitude != 0
    ]
    return replace_movements(
        flow, flow.movements[selected[0] : selected[-1] + 1] if selected else ()
    )
