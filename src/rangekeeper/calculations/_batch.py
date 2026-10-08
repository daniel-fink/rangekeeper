"""Private reusable columnar Flow calculations; records are materialized at boundaries."""

from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import math
from uuid import uuid4

from rangekeeper.schema.records import Flow, Movement, Period, Quantity
from rangekeeper.schema.behaviors.flow import MissingValueHandling as Missing
from rangekeeper.model._flow_mapping import period_indices, weights
from rangekeeper.shared.units import default_units


def polars():
    try:
        import polars as pl
    except ImportError as error:
        raise ImportError(
            "Install rangekeeper[calculations] for Flow calculations"
        ) from error
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
            self.template.start_inclusive.isoformat(),
            self.template.end_exclusive.isoformat(),
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


def stable_reduce(frame, keys, method):
    """Native reductions, with fsum repair only for cancellation-sensitive groups.

    Polars computes masks and risk bounds in bulk. The uncommon ill-conditioned
    sums use the same independent summation contract as intrinsic Flow.total.
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
                pl.col("absolute") * pl.col("size") * 2.22e-16
                > pl.col("result").abs() * 1e-14
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
        raise ValueError("Flow reduction produced a non-finite magnitude")
    return result


@dataclass(frozen=True)
class Batch:
    frame: object
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
            flow.check()
            flow.coordinate_index()
            for order, movement in enumerate(flow.movements):
                key = movement.coordinate
                if key not in lookup:
                    lookup[key] = len(coordinates)
                    coordinates.append(key)
                line_ids.append(line)
                coordinate_ids.append(lookup[key])
                orders.append(order)
                values.append(movement.magnitude)
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
        span.check()
        keep = []
        for i, c in enumerate(self.coordinates):
            start = date.fromisoformat(c[1])
            end = date.fromisoformat(c[2]) if c[0] == "period" else None
            if end is None:
                if span.start_inclusive <= start < span.end_exclusive:
                    keep.append(i)
            elif end > span.start_inclusive and start < span.end_exclusive:
                if start < span.start_inclusive or end > span.end_exclusive:
                    raise ValueError(
                        "trim crosses a movement period; allocate explicitly"
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
                    if source.magnitude == magnitude
                    else source.replace(magnitude=magnitude)
                )
            )
            result[line].append(movement)
        return tuple(
            Flow(units=unit, movements=tuple(movements)).check()
            for unit, movements in zip(self.units, result)
        )

    def grid(self, join):
        from rangekeeper.calculations.series import AlignmentJoin

        if not isinstance(join, AlignmentJoin):
            raise TypeError("join must be an AlignmentJoin")
        modes = {self.coordinates[c][0] for c in self.frame["coordinate"].unique()}
        if len(modes) > 1:
            raise ValueError(
                "cannot align event dates with period coverage; resample conflicting lines to common periods"
            )
        sets = [set() for _ in self.units]
        for line, coord in self.frame.select("line", "coordinate").iter_rows():
            sets[line].add(coord)
        if not sets:
            raise ValueError("alignment needs at least one Flow")
        if join is AlignmentJoin.EXACT and any(s != sets[0] for s in sets[1:]):
            raise ValueError(
                "Flow coordinates differ; request union/intersection explicitly or resample the lines"
            )
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
        from rangekeeper.calculations.series import (
            Aggregation,
            AggregationMethod,
            AlignmentJoin,
        )

        if not isinstance(method, AggregationMethod):
            raise TypeError("method must be an AggregationMethod")
        if not isinstance(missing, Missing) or not isinstance(join, AlignmentJoin):
            raise TypeError("missing and join require their enum types")
        if not self.units:
            raise ValueError("alignment needs at least one Flow")
        pl = polars()
        unit = units or self.units[0]
        sets = [set() for _ in self.units]
        for line, c in self.frame.select("line", "coordinate").iter_rows():
            sets[line].add(c)
        grids = []
        memberships = []
        for group, indices in enumerate(groups):
            if not indices or len(set(indices)) != len(indices):
                raise ValueError("aggregation requires unique contributors")
            selected = [sets[i] for i in indices]
            if join is AlignmentJoin.EXACT and any(
                s != selected[0] for s in selected[1:]
            ):
                raise ValueError(
                    "Flow coordinates differ; request union/intersection explicitly or resample the lines"
                )
            grid = (
                set.intersection(*selected)
                if join is AlignmentJoin.INTERSECTION
                else set.union(*selected)
            )
            if len({self.coordinates[c][0] for c in grid}) > 1:
                raise ValueError(
                    "cannot align event dates with period coverage; resample conflicting lines to common periods"
                )
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
                    ).magnitude
                    one = default_units.convert(
                        Quantity(magnitude=1, units=source), to=unit
                    ).magnitude
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
            complete = count == total
            if not complete and missing is Missing.ERROR:
                raise ValueError("missing/unresolved movement in aligned flows")
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
                Aggregation(
                    Flow(units=unit, movements=tuple(movements)).check(),
                    tuple(coverage),
                )
            )
        return tuple(results)

    def resample(self, periods, *, methods, weightings, missing):
        from rangekeeper.calculations.series import ResamplingMethod, MeanWeighting

        if not isinstance(missing, Missing):
            raise TypeError("missing must be a MissingValueHandling")
        periods = tuple(periods)
        pl = polars()
        # Only coordinates present in this selection participate in bounds validation.
        active = self.frame["coordinate"].unique().to_list()
        coordinates = tuple(self.coordinates[i] for i in active)
        groups = period_indices(coordinates, periods)
        mapping = pl.DataFrame(
            {"coordinate": active, "group": groups},
            schema={"coordinate": pl.Int64, "group": pl.Int64},
        )
        frame = self.frame.join(mapping, on="coordinate", how="left").sort(
            "line", "order"
        )
        all_results = []
        for method in dict.fromkeys(methods):
            if not isinstance(method, ResamplingMethod):
                raise TypeError("method must be a ResamplingMethod")
            lines = [i for i, m in enumerate(methods) if m is method]
            for line in lines:
                w = weightings[line]
                if w is not None and not isinstance(w, MeanWeighting):
                    raise TypeError("weighting must be a MeanWeighting")
                if method is ResamplingMethod.MEAN and w is None:
                    raise ValueError("means require explicit weighting")
                if method is not ResamplingMethod.MEAN and w is not None:
                    raise ValueError("weighting applies only to means")
            part = frame.filter(pl.col("line").is_in(lines))
            if method is ResamplingMethod.MEAN:
                weighted = []
                for weighting in dict.fromkeys(weightings[i] for i in lines):
                    selected = [i for i in lines if weightings[i] is weighting]
                    subset = part.filter(pl.col("line").is_in(selected))
                    active_coords = subset["coordinate"].unique().to_list()
                    fixed = weights(
                        tuple(self.coordinates[c] for c in active_coords),
                        elapsed=weighting is MeanWeighting.ELAPSED,
                    )
                    wf = pl.DataFrame(
                        {"coordinate": active_coords, "weight": fixed},
                        schema={"coordinate": pl.Int64, "weight": pl.Float64},
                    )
                    subset = subset.join(wf, on="coordinate", how="left")
                    numerator = stable_reduce(
                        subset.with_columns(
                            (pl.col("magnitude") * pl.col("weight")).alias("magnitude")
                        ),
                        ["line", "group"],
                        "sum",
                    )
                    denominator = subset.group_by("line", "group").agg(
                        pl.col("weight")
                        .filter(pl.col("magnitude").is_not_null())
                        .sum()
                        .alias("denominator")
                    )
                    weighted.append(
                        numerator.join(denominator, on=["line", "group"])
                        .with_columns(
                            (pl.col("result") / pl.col("denominator")).alias("result")
                        )
                        .drop("denominator")
                    )
                reduced = pl.concat(weighted)
            else:
                reduced = stable_reduce(part, ["line", "group"], method.value)
            all_results.append(reduced)
        reduced = (
            pl.concat(all_results)
            if all_results
            else pl.DataFrame(
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
        )
        grid = pl.DataFrame(
            {
                "line": [i for i in range(len(self.units)) for _ in periods],
                "group": list(range(len(periods))) * len(self.units),
            },
            schema={"line": pl.Int64, "group": pl.Int64},
        )
        output = grid.join(
            reduced, on=["line", "group"], how="left", maintain_order="left"
        ).with_columns(pl.col("size", "count", "known").fill_null(0))
        complete = (pl.col("size") > 0) & (pl.col("count") == pl.col("size"))
        if missing is Missing.ERROR and output.filter(~complete).height:
            raise ValueError("empty/unresolved target period")
        usable = complete | (
            (pl.col("count") > 0) if missing is Missing.SKIP else pl.lit(False)
        )
        magnitude = (
            pl.when(usable)
            .then(pl.col("result"))
            .otherwise(pl.lit(None, dtype=pl.Float64))
        )
        if missing is Missing.ZERO:
            magnitude = pl.when(pl.col("size") == 0).then(0.0).otherwise(magnitude)
        output = output.with_columns(
            magnitude.alias("magnitude"),
            pl.when(pl.col("size") > 0)
            .then(pl.col("known") / pl.col("size"))
            .otherwise(0.0)
            .alias("coverage"),
        )
        metadata_groups = {}
        for line, group, row in frame.select("line", "group", "row").iter_rows():
            source = self.metadata[row]
            if source.claims:
                metadata_groups.setdefault((line, group), []).append(source)
        metadata = tuple(
            Derived(periods[g], claims(metadata_groups.get((line, g), ())), uuid4())
            for line, g in grid.iter_rows()
        )
        output = output.select(
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
        return Batch(
            output,
            self.units,
            tuple(
                (
                    "period",
                    p.start_inclusive.isoformat(),
                    p.end_exclusive.isoformat(),
                    None,
                )
                for p in periods
            ),
            metadata,
        )
