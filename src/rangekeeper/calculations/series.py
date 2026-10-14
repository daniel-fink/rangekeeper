"""Pure Flow arithmetic with explicit alignment, units and missing-value rules.

Polars performs key alignment and grouped reductions. Rangekeeper checks units,
coordinates and missing values. The overall model logic selects the operations
and is responsible for their meaning.
"""

from __future__ import annotations

from uuid import uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.calculations._batch import Batch

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
import json
import math
from enum import Enum, unique

from rangekeeper.model.flux import Flow, Movement
from rangekeeper.model.duration import Period
from rangekeeper.model.measure import Quantity
from rangekeeper.model.duration.calendar import DayCount, elapsed_days, year_fraction
from rangekeeper.shared.units import default_units
from rangekeeper.schema.behaviors.flow import MissingValueHandling
from rangekeeper.schema.runtime import UNSET


@unique
class AlignmentJoin(Enum):
    EXACT = "exact"
    UNION = "union"
    INTERSECTION = "intersection"


@unique
class AggregationMethod(Enum):
    SUM = "sum"
    MIN = "min"
    MAX = "max"


@unique
class ResamplingMethod(Enum):
    SUM = "sum"
    FIRST = "first"
    LAST = "last"
    MEAN = "mean"
    MIN = "min"
    MAX = "max"


@unique
class MeanWeighting(Enum):
    OBSERVATIONS = "observations"
    ELAPSED = "elapsed"


@dataclass(frozen=True, slots=True)
class Alignment:
    """Common coordinates with the original known-value mask and missing policy.

    Construct with ``align``. Repeated reductions reuse the alignment and report
    original coverage even when absent coordinates were explicitly filled with zero.
    """

    flows: tuple[Flow, ...]
    coverage: tuple[tuple[bool, ...], ...]
    missing: MissingValueHandling = MissingValueHandling.ERROR
    _batch: Batch | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.missing, MissingValueHandling):
            raise TypeError("missing must be a MissingValueHandling")
        if not self.flows or len(self.coverage) != len(self.flows):
            raise ValueError("alignment requires one coverage row per Flow")
        coordinates = tuple(m.coordinate for m in self.flows[0].movements)
        for flow, row in zip(self.flows, self.coverage):
            flow.check(resolved=self.missing == MissingValueHandling.ERROR)
            if (
                len(row) != len(coordinates)
                or tuple(m.coordinate for m in flow.movements) != coordinates
            ):
                raise ValueError("alignment coordinates and coverage must agree")

    def reduce(
        self,
        *,
        method: AggregationMethod = AggregationMethod.SUM,
        units: str | None = None,
    ) -> Aggregation:
        """Reduce once-prepared columns; preserve original coverage and absent zeroes."""
        from rangekeeper.calculations._batch import Batch, polars

        if self._batch is None:
            batch = Batch.prepare(self.flows)
            pl = polars()
            known = [known for row in self.coverage for known in row]
            # A filled zero with false coverage denotes an absent coordinate.
            batch = Batch(
                batch.frame.with_columns(
                    pl.Series("known", known, dtype=pl.Boolean),
                    pl.Series(
                        "present",
                        [
                            k or m.magnitude is None
                            for f, row in zip(self.flows, self.coverage)
                            for m, k in zip(f.movements, row)
                        ],
                        dtype=pl.Boolean,
                    ),
                ),
                batch.units,
                batch.coordinates,
                batch.metadata,
            )
            object.__setattr__(self, "_batch", batch)
        assert self._batch is not None
        return self._batch.aggregate(
            method=method, units=units, missing=self.missing, join=AlignmentJoin.EXACT
        )


@dataclass(frozen=True, slots=True)
class Aggregation:
    """A reduced Flow and the known fraction of its inputs at each coordinate."""

    flow: Flow
    coverage: tuple[float, ...]


def align(
    flows: Sequence[Flow],
    *,
    join: AlignmentJoin = AlignmentJoin.EXACT,
    missing: MissingValueHandling = MissingValueHandling.ERROR,
) -> Alignment:
    """Align exact coordinates; fill only absent rows when ZERO is requested."""
    from rangekeeper.calculations._batch import Batch

    if not isinstance(missing, MissingValueHandling):
        raise TypeError("missing must be a MissingValueHandling")
    batch = Batch.prepare(flows)
    grid = batch.grid(join)
    templates: dict[tuple, Movement] = {}
    mappings = []
    for flow in flows:
        mapping = flow.coordinate_index()
        mappings.append(mapping)
        for key, movement in mapping.items():
            templates.setdefault(key, movement)
    aligned, coverages = [], []
    for flow, mapping in zip(flows, mappings):
        movements, coverage = [], []
        for index in grid:
            key = batch.coordinates[index]
            present = key in mapping
            source = mapping.get(key, templates[key])
            known = present and source.magnitude is not None
            if not known and missing is MissingValueHandling.ERROR:
                raise ValueError("missing/unresolved movement")
            magnitude = (
                source.magnitude
                if present
                else 0.0 if missing is MissingValueHandling.ZERO else None
            )
            movements.append(
                source
                if present
                else source.replace(id=uuid4(), magnitude=magnitude, claims=())
            )
            coverage.append(known)
        aligned.append(flow.replace(movements=tuple(movements)))
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
                    s.period.start_inclusive,
                    s.period.end_exclusive,
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
    method: ResamplingMethod,
    missing: MissingValueHandling = MissingValueHandling.ERROR,
    weighting: MeanWeighting | None = None,
) -> Aggregation:
    """Group whole movements into periods; means require explicit fixed weighting."""
    from rangekeeper.calculations._batch import Batch

    batch = Batch.prepare((flow,)).resample(
        periods, methods=(method,), weightings=(weighting,), missing=missing
    )
    return Aggregation(batch.flows()[0], tuple(batch.frame["coverage"].to_list()))


def aggregate(
    flows: Sequence[Flow],
    *,
    method: AggregationMethod = AggregationMethod.SUM,
    units: str | None = None,
    missing: MissingValueHandling = MissingValueHandling.ERROR,
    join: AlignmentJoin = AlignmentJoin.EXACT,
) -> Aggregation:
    """Combine compatible flows through the shared columnar engine."""
    from rangekeeper.calculations._batch import Batch

    return Batch.prepare(flows).aggregate(
        method=method, units=units, missing=missing, join=join
    )
