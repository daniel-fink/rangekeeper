"""Private reusable columnar Flow calculations; records are materialized at boundaries."""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

from rangekeeper.duration import Period
from rangekeeper.duration.errors import AlignmentError
from rangekeeper.flow._flow import Flow, Movement, _number
from rangekeeper.flow._mapping import MEANS, period_indices, weights
from rangekeeper.flow._options import MissingValueHandling as Missing
from rangekeeper.flow._options import ResampleMethod
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, NumericalError
from rangekeeper.shared.optional import requires

if TYPE_CHECKING:
    from polars import DataFrame


def polars():
    with requires("calculations"):
        import polars as pl
    return pl


@dataclass(frozen=True)
class Derived:
    """Small transient metadata; constructing a result does not build Flow records."""

    template: Movement | Period
    claims: tuple
    id: object

    @property
    def coordinate(self):
        if isinstance(self.template, Movement):
            return self.template.coordinate
        return (
            "period",
            self.template.start.isoformat(),
            self.template.end.isoformat(),
            None,
        )

    def movement(self, magnitude):
        if isinstance(self.template, Movement):
            return self.template.replace(
                id=self.id, magnitude=magnitude, claims=self.claims
            )
        return Movement(
            id=self.id, period=self.template, magnitude=magnitude, claims=self.claims
        )


def claims(metadata):
    return tuple(dict.fromkeys(c for row in metadata for c in (row.claims or ())))


# Relative error accepted from a native sum before the fsum repair.
SUM_TOLERANCE = 1e-8


def stable_reduce(frame, keys, method):
    """Native reductions, with fsum repair only for cancellation-sensitive groups.

    Polars computes masks and risk bounds in bulk. A native sum of n values has a
    relative error of at most n * eps * sum(|x|) / |sum(x)|. Groups where this
    bound exceeds SUM_TOLERANCE use the same independent summation contract as
    intrinsic Flow.total. A group without cancellation has sum(|x|) = |sum(x)|,
    so it stays native below 1 / (SUM_TOLERANCE * eps), about 45 million rows.
    No Python row UDF participates in the dataframe expression.
    """
    pl = polars()
    expr = getattr(pl.col("magnitude"), method)().alias("result")
    result = frame.group_by(keys, maintain_order=True).agg(
        expr,
        pl.col("magnitude").count().alias("count"),
        pl.len().alias("size"),
        pl.col("known").sum().alias("known"),
        pl.col("magnitude").abs().sum().alias("absolute"),
    )
    if method == "sum" and result.height:
        suspect = result.filter(
            (
                pl.col("absolute") * pl.col("size") * sys.float_info.epsilon
                > pl.col("result").abs() * SUM_TOLERANCE
            )
            & (pl.col("absolute") > 0)
        ).select(keys)
        if suspect.height:
            groups = (
                frame.join(suspect, on=keys, how="inner")
                .group_by(keys, maintain_order=True)
                .agg(pl.col("magnitude").drop_nulls())
            )
            repairs = {
                tuple(row[:-1]): math.fsum(row[-1]) for row in groups.iter_rows()
            }
            values = [
                repairs.get(tuple(row[: len(keys)]), row[len(keys)])
                for row in result.select(*keys, "result").iter_rows()
            ]
            result = result.with_columns(pl.Series("result", values, dtype=pl.Float64))
    if result.filter(pl.col("result").is_infinite() | pl.col("result").is_nan()).height:
        raise NumericalError("Flow reduction produced a non-finite magnitude")
    return result


@dataclass(frozen=True)
class Batch:
    frame: DataFrame
    units: tuple[str, ...]
    coordinates: tuple[tuple, ...]
    metadata: tuple[Movement | Derived, ...]

    @classmethod
    def prepare(cls, flows: Sequence[Flow]):
        pl = polars()
        coordinates: list[tuple] = []
        lookup: dict[tuple, int] = {}
        rows: list[Movement] = []
        line_ids, coordinate_ids, orders, values = [], [], [], []
        for line, flow in enumerate(flows):
            flow.coordinate_index()
            for order, movement in enumerate(flow.movements):
                key = movement.coordinate
                if key not in lookup:
                    lookup[key] = len(coordinates)
                    coordinates.append(key)
                line_ids.append(line)
                coordinate_ids.append(lookup[key])
                orders.append(order)
                values.append(_number(movement.magnitude))
                rows.append(movement)
        frame = pl.DataFrame(
            {
                "line": line_ids,
                "coordinate": coordinate_ids,
                "order": orders,
                "row": range(len(rows)),
                "magnitude": values,
            },
            schema={
                "line": pl.Int64,
                "coordinate": pl.Int64,
                "order": pl.Int64,
                "row": pl.Int64,
                "magnitude": pl.Float64,
            },
        ).with_columns(
            pl.col("magnitude").is_not_null().alias("known"),
            pl.lit(True).alias("present"),
        )
        return cls(
            frame, tuple(f.units for f in flows), tuple(coordinates), tuple(rows)
        )

    def select(self, indices):
        pl = polars()
        mapping = pl.DataFrame(
            {"line": indices, "new_line": range(len(indices))},
            schema={"line": pl.Int64, "new_line": pl.Int64},
        )
        frame = (
            self.frame.join(mapping, on="line", how="inner")
            .drop("line")
            .rename({"new_line": "line"})
            .sort("line", "order")
        )
        return self._compact(frame, tuple(self.units[i] for i in indices))

    def _compact(self, frame, units):
        """Release unselected identity and coordinate metadata with the parent batch."""
        pl = polars()
        positions = frame["row"].to_list()
        coordinates = frame["coordinate"].unique(maintain_order=True).to_list()
        mapping = pl.DataFrame(
            {"coordinate": coordinates, "selected_coordinate": range(len(coordinates))},
            schema={"coordinate": pl.Int64, "selected_coordinate": pl.Int64},
        )
        frame = (
            frame.join(mapping, on="coordinate", how="left", maintain_order="left")
            .drop("coordinate")
            .rename({"selected_coordinate": "coordinate"})
            .with_columns(pl.Series("row", range(len(positions)), dtype=pl.Int64))
        )
        return Batch(
            frame,
            units,
            tuple(self.coordinates[i] for i in coordinates),
            tuple(self.metadata[i] for i in positions),
        )

    def trim(self, span):
        pl = polars()
        keep = []
        for i, c in enumerate(self.coordinates):
            start = date.fromisoformat(c[1])
            end = date.fromisoformat(c[2]) if c[0] == "period" else None
            if end is None:
                if span.start <= start < span.end:
                    keep.append(i)
            elif end > span.start and start < span.end:
                if start < span.start or end > span.end:
                    raise AlignmentError(
                        "trim crosses a movement period; allocate explicitly",
                        code=Code.ALIGNMENT_CROSSES,
                        values={
                            "span": f"{span.start}/{span.end}",
                            "period": f"{c[1]}/{c[2]}",
                        },
                    )
                keep.append(i)
        frame = self.frame.filter(pl.col("coordinate").is_in(keep))
        return self._compact(frame, self.units)

    def flows(self):
        result = [[] for _ in self.units]
        for line, row, magnitude in (
            self.frame.sort("line", "order")
            .select("line", "row", "magnitude")
            .iter_rows()
        ):
            source = self.metadata[row]
            movement = (
                source.movement(magnitude)
                if isinstance(source, Derived)
                else (
                    source
                    if _number(source.magnitude) == magnitude
                    else source.replace(magnitude=magnitude)
                )
            )
            result[line].append(movement)
        return tuple(
            Flow(units=unit, movements=tuple(movements))
            for unit, movements in zip(self.units, result, strict=True)
        )

    def grid(self, join):
        from rangekeeper.flow._options import AlignmentJoin

        if not isinstance(join, AlignmentJoin):
            raise TypeError("join must be an AlignmentJoin")
        modes = {self.coordinates[c][0] for c in self.frame["coordinate"].unique()}
        if len(modes) > 1:
            raise _mixed()
        sets = [set() for _ in self.units]
        for line, coord in self.frame.select("line", "coordinate").iter_rows():
            sets[line].add(coord)
        if not sets:
            raise ContractError("alignment needs at least one Flow")
        if join is AlignmentJoin.EXACT and any(s != sets[0] for s in sets[1:]):
            raise _differ()
        selected = (
            set.intersection(*sets)
            if join is AlignmentJoin.INTERSECTION
            else set.union(*sets)
        )
        return tuple(
            sorted(
                selected,
                key=lambda c: (self.coordinates[c][1], str(self.coordinates[c])),
            )
        )

    def aligned(self, flows, coverage):
        """Mark the original coverage of aligned Flows; a filled zero stays absent."""
        pl = polars()
        known = [known for row in coverage for known in row]
        present = [
            k or m.magnitude is None
            for f, row in zip(flows, coverage, strict=True)
            for m, k in zip(f.movements, row, strict=True)
        ]
        return Batch(
            self.frame.with_columns(
                pl.Series("known", known, dtype=pl.Boolean),
                pl.Series("present", present, dtype=pl.Boolean),
            ),
            self.units,
            self.coordinates,
            self.metadata,
        )

    def aggregate(self, *, method, units, missing, join):
        return self.aggregate_groups(
            (tuple(range(len(self.units))),),
            method=method,
            units=units,
            missing=missing,
            join=join,
        )[0]

    def aggregate_groups(self, groups, *, method, units, missing, join):
        """Convert inputs once and reduce all selected contributor groups in one batch."""
        from rangekeeper.flow._options import (
            AggregationMethod,
            AlignmentJoin,
            FlowAggregate,
        )

        if not isinstance(method, AggregationMethod):
            raise TypeError("method must be an AggregationMethod")
        if not isinstance(missing, Missing) or not isinstance(join, AlignmentJoin):
            raise TypeError("missing and join require their enum types")
        if not self.units:
            raise ContractError("alignment needs at least one Flow")
        pl = polars()
        unit = units or self.units[0]
        sets = [set() for _ in self.units]
        for line, c in self.frame.select("line", "coordinate").iter_rows():
            sets[line].add(c)
        grids = []
        memberships = []
        for group, indices in enumerate(groups):
            if not indices or len(set(indices)) != len(indices):
                raise ContractError(
                    "aggregation requires unique contributors", code=Code.UNIQUE
                )
            selected = [sets[i] for i in indices]
            if join is AlignmentJoin.EXACT and any(
                s != selected[0] for s in selected[1:]
            ):
                raise _differ()
            grid = (
                set.intersection(*selected)
                if join is AlignmentJoin.INTERSECTION
                else set.union(*selected)
            )
            if len({self.coordinates[c][0] for c in grid}) > 1:
                raise _mixed()
            grids.append(
                tuple(
                    sorted(
                        grid,
                        key=lambda c: (
                            self.coordinates[c][1],
                            str(self.coordinates[c]),
                        ),
                    )
                )
            )
            memberships.extend((i, group) for i in indices)
        factors = []
        offsets = []
        conversions = {}
        for source in self.units:
            if source not in conversions:
                if source == unit:
                    default_units.validate_units(unit)
                    conversions[source] = (1.0, 0.0)
                else:
                    zero = default_units.convert(
                        Quantity(magnitude=0, units=source), to=unit
                    ).number
                    one = default_units.convert(
                        Quantity(magnitude=1, units=source), to=unit
                    ).number
                    conversions[source] = (one - zero, zero)
            factor, offset = conversions[source]
            factors.append(factor)
            offsets.append(offset)
        conversion = pl.DataFrame(
            {"line": range(len(self.units)), "factor": factors, "offset": offsets}
        )
        membership = pl.DataFrame(
            memberships, schema={"line": pl.Int64, "group": pl.Int64}, orient="row"
        )
        grid = pl.DataFrame(
            [(g, c) for g, coords in enumerate(grids) for c in coords],
            schema={"group": pl.Int64, "coordinate": pl.Int64},
            orient="row",
        )
        converted = self.frame.join(conversion, on="line", how="left").with_columns(
            pl.when(~pl.col("present") & pl.lit(missing is Missing.ZERO))
            .then(0.0)
            .otherwise(pl.col("magnitude") * pl.col("factor") + pl.col("offset"))
            .alias("magnitude")
        )
        frame = (
            converted.join(membership, on="line", how="inner")
            .join(grid, on=["group", "coordinate"], how="inner")
            .sort("group", "line", "order")
        )
        reduced = stable_reduce(frame, ["group", "coordinate"], method.value)
        templates = frame.group_by("group", "coordinate").agg(
            pl.col("row").first().alias("template")
        )
        reduced = reduced.join(templates, on=["group", "coordinate"])
        by_group = {}
        for g, c, value, count, size, known, _, template in reduced.iter_rows():
            total = len(groups[g])
            # A coordinate that a line does not have is no movement, not a
            # missing amount; only unresolved amounts are missing.
            complete = count == size
            if not complete and missing is Missing.ERROR:
                raise NumericalError("missing/unresolved movement in aligned flows")
            if missing is Missing.ZERO and count == size:
                if size < total and method is AggregationMethod.MIN:
                    value = min(value, 0.0)
                if size < total and method is AggregationMethod.MAX:
                    value = max(value, 0.0)
            elif not complete and not (missing is Missing.SKIP and count):
                value = None
            by_group[g, c] = (value, known / total, template)
        evidence = {}
        # Evidence is immutable metadata, not numerical row arithmetic.
        claim_rows = [i for i, m in enumerate(self.metadata) if m.claims]
        if claim_rows:
            for g, c, row in (
                frame.filter(pl.col("row").is_in(claim_rows))
                .select("group", "coordinate", "row")
                .iter_rows()
            ):
                evidence.setdefault((g, c), []).append(self.metadata[row])
        results = []
        for g, coords in enumerate(grids):
            movements = []
            coverage = []
            for c in coords:
                value, known, row = by_group[g, c]
                origin = self.metadata[row]
                template = origin.template if isinstance(origin, Derived) else origin
                movements.append(
                    Derived(
                        template, claims(evidence.get((g, c), ())), uuid4()
                    ).movement(value)
                )
                coverage.append(known)
            results.append(
                FlowAggregate(
                    Flow(units=unit, movements=tuple(movements)),
                    tuple(coverage),
                )
            )
        return tuple(results)

    def resample(
        self,
        periods: Sequence[Period],
        *,
        methods: Sequence[ResampleMethod],
        missing: Missing,
    ) -> Batch:
        """Reduce each line onto the target Periods with its own method.

        ``methods`` has one method for each line of this batch.
        """
        _check_resample(methods, missing=missing, lines=len(self.units))
        targets = tuple(periods)
        assigned = self._assign(targets)
        reduced = _concat(
            [
                self._reduce(assigned, method=method, lines=lines)
                for method, lines in _plan(methods).items()
            ]
        )
        grid = _fill_grid(reduced, lines=len(self.units), periods=len(targets))
        return self._period_batch(
            _apply_missing(grid, missing),
            targets,
            cells=_claims_by_cell(assigned, self.metadata),
        )

    def _assign(self, periods: tuple[Period, ...]) -> DataFrame:
        """Add the index of the target Period that holds each value."""
        pl = polars()
        # Only coordinates present in this selection participate in bounds validation.
        active = self.frame["coordinate"].unique().to_list()
        groups = period_indices(tuple(self.coordinates[i] for i in active), periods)
        mapping = pl.DataFrame(
            {"coordinate": active, "group": groups},
            schema={"coordinate": pl.Int64, "group": pl.Int64},
        )
        return self.frame.join(mapping, on="coordinate", how="left").sort(
            "line", "order"
        )

    def _reduce(
        self, frame: DataFrame, *, method: ResampleMethod, lines: tuple[int, ...]
    ) -> DataFrame:
        """Reduce the values of some lines in each target Period with one method."""
        pl = polars()
        part = frame.filter(pl.col("line").is_in(lines))
        if method in MEANS:
            return self._mean(part, method=method)
        return stable_reduce(part, ["line", "group"], _REDUCTIONS[method])

    def _mean(self, frame: DataFrame, *, method: ResampleMethod) -> DataFrame:
        """Return the weighted mean of the known values in each target Period."""
        pl = polars()
        active = frame["coordinate"].unique().to_list()
        fixed = weights(tuple(self.coordinates[c] for c in active), method=method)
        weighted = frame.join(
            pl.DataFrame(
                {"coordinate": active, "weight": fixed},
                schema={"coordinate": pl.Int64, "weight": pl.Float64},
            ),
            on="coordinate",
            how="left",
        )
        numerator = stable_reduce(
            weighted.with_columns(
                (pl.col("magnitude") * pl.col("weight")).alias("magnitude")
            ),
            ["line", "group"],
            "sum",
        )
        denominator = weighted.group_by("line", "group").agg(
            pl.col("weight")
            .filter(pl.col("magnitude").is_not_null())
            .sum()
            .alias("denominator")
        )
        return (
            numerator.join(denominator, on=["line", "group"])
            .with_columns((pl.col("result") / pl.col("denominator")).alias("result"))
            .drop("denominator")
        )

    def _period_batch(
        self,
        output: DataFrame,
        periods: tuple[Period, ...],
        *,
        cells: dict[tuple[int, int], list[Movement | Derived]],
    ) -> Batch:
        """Return the resampled lines as a batch on the target Periods."""
        pl = polars()
        metadata = tuple(
            Derived(periods[group], claims(cells.get((line, group), ())), uuid4())
            for line, group in output.select("line", "group").iter_rows()
        )
        frame = output.select(
            "line",
            pl.col("group").alias("coordinate"),
            pl.col("group").alias("order"),
            "magnitude",
            "coverage",
        ).with_columns(
            pl.Series("row", range(len(metadata)), dtype=pl.Int64),
            pl.col("magnitude").is_not_null().alias("known"),
            pl.lit(True).alias("present"),
        )
        coordinates = tuple(
            ("period", p.start.isoformat(), p.end.isoformat(), None) for p in periods
        )
        return Batch(frame, self.units, coordinates, metadata)


# The Polars reduction of each resample method that is not a mean.
_REDUCTIONS: dict[ResampleMethod, str] = {
    ResampleMethod.SUM: "sum",
    ResampleMethod.FIRST: "first",
    ResampleMethod.LAST: "last",
    ResampleMethod.MIN: "min",
    ResampleMethod.MAX: "max",
}


def _mixed() -> AlignmentError:
    """Return the error for lines that mix dated and period coordinates."""
    return AlignmentError(
        "cannot align event dates with period coverage; "
        "resample conflicting lines to common periods",
        code=Code.ALIGNMENT_MIXED,
    )


def _differ() -> AlignmentError:
    """Return the error for lines whose coordinates differ under an exact join."""
    return AlignmentError(
        "Flow coordinates differ; request union/intersection explicitly or "
        "resample the lines",
        code=Code.ALIGNMENT_DIFFER,
    )


def _check_resample(
    methods: Sequence[ResampleMethod], *, missing: Missing, lines: int
) -> None:
    """Require one ResampleMethod for each line and a MissingValueHandling."""
    if not isinstance(missing, Missing):
        raise TypeError("missing must be a MissingValueHandling")
    if any(not isinstance(method, ResampleMethod) for method in methods):
        raise TypeError("method must be a ResampleMethod")
    if len(methods) != lines:
        raise ContractError("resample needs one method for each line")


def _plan(methods: Sequence[ResampleMethod]) -> dict[ResampleMethod, tuple[int, ...]]:
    """Return the lines of each method, in the order of first use."""
    plan: dict[ResampleMethod, list[int]] = {}
    for line, method in enumerate(methods):
        plan.setdefault(method, []).append(line)
    return {method: tuple(lines) for method, lines in plan.items()}


def _concat(reduced: list[DataFrame]) -> DataFrame:
    """Join the reductions of each method, or return an empty reduction."""
    pl = polars()
    if reduced:
        return pl.concat(reduced)
    return pl.DataFrame(
        schema={
            "line": pl.Int64,
            "group": pl.Int64,
            "result": pl.Float64,
            "count": pl.UInt32,
            "size": pl.UInt32,
            "known": pl.UInt32,
            "absolute": pl.Float64,
        }
    )


def _fill_grid(reduced: DataFrame, *, lines: int, periods: int) -> DataFrame:
    """Return one row for each line and target Period; a Period with no value has size 0."""
    pl = polars()
    grid = pl.DataFrame(
        {
            "line": [line for line in range(lines) for _ in range(periods)],
            "group": list(range(periods)) * lines,
        },
        schema={"line": pl.Int64, "group": pl.Int64},
    )
    return grid.join(
        reduced, on=["line", "group"], how="left", maintain_order="left"
    ).with_columns(pl.col("size", "count", "known").fill_null(0))


def _apply_missing(grid: DataFrame, missing: Missing) -> DataFrame:
    """Set the amount and the coverage of each cell by the missing-value rule.

    ``ERROR`` raises for an empty or unresolved Period. ``SKIP`` keeps the
    reduction of the known values. ``ZERO`` gives zero for an empty Period.
    """
    pl = polars()
    complete = (pl.col("size") > 0) & (pl.col("count") == pl.col("size"))
    if missing is Missing.ERROR and grid.filter(~complete).height:
        raise NumericalError("empty/unresolved target period")
    usable = complete | (
        (pl.col("count") > 0) if missing is Missing.SKIP else pl.lit(False)
    )
    magnitude = (
        pl.when(usable).then(pl.col("result")).otherwise(pl.lit(None, dtype=pl.Float64))
    )
    if missing is Missing.ZERO:
        magnitude = pl.when(pl.col("size") == 0).then(0.0).otherwise(magnitude)
    return grid.with_columns(
        magnitude.alias("magnitude"),
        pl.when(pl.col("size") > 0)
        .then(pl.col("known") / pl.col("size"))
        .otherwise(0.0)
        .alias("coverage"),
    )


def _claims_by_cell(
    frame: DataFrame, metadata: tuple[Movement | Derived, ...]
) -> dict[tuple[int, int], list[Movement | Derived]]:
    """Return the sources with Claims of each line and target Period."""
    cells: dict[tuple[int, int], list[Movement | Derived]] = {}
    for line, group, row in frame.select("line", "group", "row").iter_rows():
        source = metadata[row]
        if source.claims:
            cells.setdefault((line, group), []).append(source)
    return cells


def align(flows, *, join, missing):
    """Align exact coordinates; fill only absent rows when ZERO is requested.

    Return the aligned Flows and, for each Flow, the coordinates with a known value.
    """
    from rangekeeper.flow._options import AlignmentJoin

    if not isinstance(missing, Missing) or not isinstance(join, AlignmentJoin):
        raise TypeError("missing and join require their enum types")
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
    for flow, mapping in zip(flows, mappings, strict=True):
        movements, coverage = [], []
        for index in grid:
            key = batch.coordinates[index]
            present = key in mapping
            source = mapping.get(key, templates[key])
            known = present and source.magnitude is not None
            if not known and missing is Missing.ERROR:
                raise NumericalError("missing/unresolved movement")
            magnitude = (
                source.magnitude
                if present
                else 0.0
                if missing is Missing.ZERO
                else None
            )
            movements.append(
                source
                if present
                else source.replace(id=uuid4(), magnitude=magnitude, claims=())
            )
            coverage.append(known)
        aligned.append(flow.replace(movements=tuple(movements)))
        coverages.append(tuple(coverage))
    return tuple(aligned), tuple(coverages)
