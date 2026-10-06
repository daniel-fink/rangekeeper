"""Pure Flow arithmetic with explicit alignment, units and missing-value rules.

Polars performs key alignment and grouped reductions. Rangekeeper checks units,
coordinates and missing values. The overall model logic selects the operations
and is responsible for their meaning.
"""

from __future__ import annotations

from uuid import uuid4

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import json
import math
from typing import Literal

from ..model.flow import Flow, Movement
from ..model.duration import Period
from ..model.measure import Quantity
from ..duration.calendar import DayCount, elapsed_days, year_fraction
from ..units import default_units
from .._behaviors.flow import Missing
from .._records import UNSET


@dataclass(frozen=True, slots=True)
class Alignment:
    """Common coordinates with the original known-value mask and missing policy.

    Construct with ``align``. Repeated reductions reuse the alignment and report
    original coverage even when absent coordinates were explicitly filled with zero.
    """

    flows: tuple[Flow, ...]
    coverage: tuple[tuple[bool, ...], ...]
    missing: Missing = "error"

    def __post_init__(self) -> None:
        if not self.flows or len(self.coverage) != len(self.flows):
            raise ValueError("alignment requires one coverage row per Flow")
        if self.missing not in ("error", "propagate", "skip", "zero"):
            raise ValueError("invalid missing policy")
        coordinates = tuple(m.coordinate for m in self.flows[0].movements)
        for flow, row in zip(self.flows, self.coverage):
            flow.check(resolved=self.missing == "error")
            if (
                len(row) != len(coordinates)
                or tuple(m.coordinate for m in flow.movements) != coordinates
            ):
                raise ValueError("alignment coordinates and coverage must agree")

    def reduce(self, *, reducer: str = "sum", units: str | None = None) -> Aggregation:
        """Reduce compatible quantities with one rule for Claims and missing values.

        All-missing groups remain unresolved, including with skip. Zero filling
        applies only to absent coordinates, as selected when the alignment was made.
        Unit conversion occurs before reduction; coverage uses the original mask.
        """
        if reducer not in ("sum", "min", "max"):
            raise ValueError("reducer must be sum, min or max")
        converted = []
        for flow, row in zip(self.flows, self.coverage):
            result = flow.convert(units=units or self.flows[0].units)
            if self.missing == "zero":
                # Absent coordinates contribute zero in the requested units, even
                # when conversion has an offset (for example, Celsius to Kelvin).
                result = result.replace(
                    movements=tuple(
                        (
                            movement.replace(magnitude=0.0)
                            if not known and movement.magnitude is not None
                            else movement
                        )
                        for movement, known in zip(result.movements, row)
                    )
                )
            converted.append(result)
        movements, coverage = [], []
        for index, group in enumerate(zip(*(flow.movements for flow in converted))):
            known = [
                movement.number for movement in group if movement.magnitude is not None
            ]
            value = None
            if known and (len(known) == len(group) or self.missing == "skip"):
                value = (
                    math.fsum(known)
                    if reducer == "sum"
                    else (min(known) if reducer == "min" else max(known))
                )
            claims = tuple(
                dict.fromkeys(
                    claim for movement in group for claim in (movement.claims or ())
                )
            )
            movements.append(
                group[0].replace(id=uuid4(), magnitude=value, claims=claims)
            )
            coverage.append(sum(row[index] for row in self.coverage) / len(group))
        return Aggregation(
            converted[0].replace(movements=tuple(movements)).check(), tuple(coverage)
        )


@dataclass(frozen=True, slots=True)
class Aggregation:
    """A reduced Flow and the known fraction of its inputs at each coordinate."""

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
    return json.dumps(movement.coordinate)


def align(
    flows: Sequence[Flow], *, join: str = "exact", missing: Missing = "error"
) -> Alignment:
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
        flow.check()
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
        return (period.start if period is not None else movement.resolve(), key)

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
                source.replace(
                    id=source.id if present else uuid4(),
                    magnitude=magnitude,
                    claims=UNSET if present else (),
                )
            )
        aligned.append(flow.replace(movements=tuple(movements)).check())
        coverages.append(tuple(coverage))
    return Alignment(tuple(aligned), tuple(coverages), missing)


def multiply(flows: Sequence[Flow]) -> Flow:
    """Multiply aligned known movements and units without removing time dimensions.

    Normalize dimensionless scales such as percent to ratios before multiplication.
    Physical dimensions, including time, remain in the result. The calling model
    determines the meaning of the product; no semantic classification is inferred.
    """
    if not flows:
        raise ValueError("product needs at least one Flow")
    flows = tuple(
        (
            flow.convert(units="dimensionless")
            if default_units.compatible(flow.units, "dimensionless")
            else flow
        )
        for flow in flows
    )
    aligned = align(flows)
    unit = "dimensionless"
    for flow in flows:
        unit = default_units.multiply(unit, flow.units)
    movements = [
        group[0].replace(
            id=uuid4(),
            magnitude=math.prod(s.number for s in group),
            claims=tuple(dict.fromkeys((c for s in group for c in s.claims or ()))),
        )
        for group in zip(*(flow.movements for flow in aligned.flows))
    ]
    return flows[0].replace(movements=tuple(movements), units=unit).check()


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
    flow.check()
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
                    magnitude=movement.magnitude * exposure.magnitude,
                    units=product_unit,
                ),
                to=output_units,
            ).magnitude
        )
        movements.append(movement.replace(id=uuid4(), magnitude=magnitude))
    return flow.replace(movements=tuple(movements), units=output_units).check()


def resample(
    flow: Flow,
    *,
    periods: Sequence[Period],
    reduction: str,
    missing: Missing = "error",
    weighting: Literal["observations", "elapsed"] | None = None,
) -> Aggregation:
    """Reduce observations into a complete period grid with explicit missing rules.

    The caller selects sum, first, last, min, max or mean. Means require an explicit
    observations/elapsed weighting choice; elapsed weighting requires bounded
    movements. No reduction is inferred from the meaning of the data. Coverage is
    the fraction of known movements, not continuous time coverage. Bounded movements
    cannot cross target periods; allocate them explicitly first. missing="zero"
    fills empty target groups only, never unresolved entries in a populated group.
    """

    flow.check()
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
        period.check()
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
            point = movement.resolve()
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
    result = Flow.from_periods(periods, values, units=flow.units)
    result = result.replace(
        movements=tuple(
            s.replace(
                magnitude=s.magnitude,
                claims=tuple(
                    dict.fromkeys((c for origin in group for c in origin.claims or ()))
                ),
            )
            for s, group in zip(result.movements, groups)
        )
    ).check()
    return Aggregation(result, tuple(coverages))


def aggregate(
    flows: Sequence[Flow],
    *,
    reducer: str = "sum",
    units: str | None = None,
    missing: Missing = "error",
    join: str = "exact",
) -> Aggregation:
    """Align and reduce compatible Flows; use Alignment.reduce to reuse a shared grid."""
    return align(flows, join=join, missing=missing).reduce(reducer=reducer, units=units)
