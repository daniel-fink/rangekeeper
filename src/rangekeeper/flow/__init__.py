"""Canonical Flow records and ordered, immutable coordination through Stream."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import UUID

from rangekeeper.schema.behaviors.flow import MissingValueHandling
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.records import Flow, Movement, Value

if TYPE_CHECKING:
    from polars import DataFrame

    from rangekeeper.duration import Period, Span
    from rangekeeper.flow._batch import Batch
    from rangekeeper.flow.series import (
        AggregationMethod,
        AlignmentJoin,
        FlowAggregate,
        MeanWeighting,
        ResamplingMethod,
    )
    from rangekeeper.model.model import Model

__all__ = ["Flow", "Movement", "Stream", "MissingValueHandling"]


@dataclass(frozen=True, init=False, eq=False)
class Stream:
    """Ordered labelled flows, optionally pinned to exact Model Value identities.

    Numerical operations are detached calculations. Passive equation builders can
    consume original Model selections, including structural trims, without reading
    their magnitudes. Resampling must be declared separately for symbolic use.
    """

    names: tuple[str, ...]
    model: Model | None
    value_ids: tuple[UUID, ...]
    missing: MissingValueHandling
    join: AlignmentJoin
    _flows: tuple[Flow | None, ...] | None
    _batch: Batch | None
    _symbolic: bool

    def __init__(
        self,
        flows: Mapping[str, Flow],
        *,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
        join: AlignmentJoin | None = None,
    ):
        from rangekeeper.flow.series import AlignmentJoin

        if not isinstance(flows, Mapping):
            raise TypeError(
                "Stream requires a name-to-Flow mapping; use from_values for a Model selection"
            )
        names = tuple(flows)
        self._initialize(
            names,
            tuple(flows.values()),
            None,
            (),
            missing,
            AlignmentJoin.EXACT if join is None else join,
            None,
            False,
        )

    def _initialize(
        self,
        names,
        flows,
        model,
        value_ids,
        missing,
        join,
        batch,
        symbolic,
    ):
        from rangekeeper.flow.series import AlignmentJoin

        if any(
            not isinstance(label, str) or not label.strip() for label in names
        ) or len(set(names)) != len(names):
            raise ValueError(
                "Stream names must be nonempty and unique; supply explicit names"
            )
        if not isinstance(missing, MissingValueHandling) or not isinstance(
            join, AlignmentJoin
        ):
            raise TypeError("missing and join require their enum types")
        if flows is not None and any(
            f is not None and not isinstance(f, Flow) for f in flows
        ):
            raise TypeError("Stream members must be Flows")
        for name, value in (
            ("names", tuple(names)),
            ("_flows", flows),
            ("model", model),
            ("value_ids", tuple(value_ids)),
            ("missing", missing),
            ("join", join),
            ("_batch", batch),
            ("_symbolic", symbolic),
        ):
            object.__setattr__(self, name, value)

    @classmethod
    def from_values(
        cls,
        model: Model,
        value_ids: Iterable[UUID],
        *,
        names: Sequence[str] | None = None,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
        join: AlignmentJoin | None = None,
    ) -> Stream:
        """Pin original Values; duplicate identities or ambiguous names are errors."""
        from rangekeeper.flow.series import AlignmentJoin

        ids = tuple(value_ids)
        if len(set(ids)) != len(ids):
            raise ValueError("Stream cannot count the same Value twice")
        values = tuple(model.value(i) for i in ids)
        if any(v.kind is not ValueKind.FLOW for v in values):
            raise ValueError("Stream target is not a Flow Value")
        names = tuple(names) if names is not None else tuple(v.key for v in values)
        if len(names) != len(ids):
            raise ValueError("one label is required per Value")
        result = object.__new__(cls)
        result._initialize(
            names,
            tuple(v.flow for v in values),
            model,
            ids,
            missing,
            AlignmentJoin.EXACT if join is None else join,
            None,
            True,
        )
        return result

    @property
    def source_values(self) -> tuple[Value, ...]:
        """Original canonical Values, even when this Stream contains derived calculations."""
        return (
            ()
            if self.model is None
            else tuple(self.model.value(i) for i in self.value_ids)
        )

    @property
    def values(self) -> tuple[Value, ...]:
        """Original canonical Values of an untransformed symbolic selection."""
        if not self._symbolic:
            raise ValueError(
                "derived Stream has no canonical Values; inspect source_values or declare intermediate Flow Values"
            )
        return self.source_values

    @property
    def flows(self) -> tuple[Flow, ...]:
        """Materialize current calculation content, retaining original records where possible."""
        if self._flows is None:
            assert self._batch is not None
            object.__setattr__(self, "_flows", self._batch.flows())
        assert self._flows is not None
        if any(f is None for f in self._flows):
            raise ValueError(
                "Stream contains an unresolved Flow Value without a declared shape"
            )
        return cast(tuple[Flow, ...], self._flows)

    def _prepared(self):
        if self._batch is None:
            from rangekeeper.flow._batch import Batch

            object.__setattr__(self, "_batch", Batch.prepare(self.flows))
        return self._batch

    def _derive(self, *, names=None, flows=None, batch=None, ids=None, symbolic=None):
        result = object.__new__(type(self))
        result._initialize(
            self.names if names is None else names,
            flows,
            self.model,
            self.value_ids if ids is None else ids,
            self.missing,
            self.join,
            batch,
            self._symbolic if symbolic is None else symbolic,
        )
        return result

    def select(
        self,
        names: Iterable[str] | None = None,
        *,
        value_ids: Iterable[UUID] | None = None,
    ) -> Stream:
        """Select lines in requested order by names or original Value IDs."""
        if (names is None) == (value_ids is None):
            raise ValueError("supply names or value_ids")
        requested = tuple(names if names is not None else (value_ids or ()))
        available = self.names if names is not None else self.value_ids
        if len(set(requested)) != len(requested):
            raise ValueError("duplicate selection")
        if any(i not in available for i in requested):
            raise KeyError("selection contains a member outside this Stream")
        indices = tuple(available.index(i) for i in requested)
        return self._derive(
            names=tuple(self.names[i] for i in indices),
            flows=(
                None if self._flows is None else tuple(self._flows[i] for i in indices)
            ),
            batch=None if self._batch is None else self._batch.select(indices),
            ids=tuple(self.value_ids[i] for i in indices) if self.value_ids else (),
        )

    def merge(self, other: Stream) -> Stream:
        """Union compatible selections; conflicting names or revisions require resolution."""
        if not isinstance(other, Stream):
            raise TypeError("other must be a Stream")
        if self.missing is not other.missing or self.join is not other.join:
            raise ValueError("Stream policies must agree")
        if self.model is not other.model and (
            self.model is None
            or other.model is None
            or self.model.id != other.model.id
            or self.model._record != other.model._record
        ):
            raise ValueError("Streams must pin the same Model revision and content")
        if not self._symbolic or not other._symbolic:
            if self.model is not None:
                raise ValueError(
                    "merge transformed model selections only after explicit materialization as labelled flows"
                )
        names = list(self.names)
        flows = list(self._flows if self._flows is not None else self.flows)
        other_flows = other._flows if other._flows is not None else other.flows
        ids = list(self.value_ids)
        for i, label in enumerate(other.names):
            if ids and other.value_ids[i] in ids:
                position = ids.index(other.value_ids[i])
                if names[position] != label or flows[position] != other_flows[i]:
                    raise ValueError(
                        "duplicate Value has conflicting label or selection"
                    )
                continue
            if label in names:
                if self.model is None and flows[names.index(label)] == other_flows[i]:
                    continue
                raise ValueError(f"conflicting Stream label: {label}")
            names.append(label)
            flows.append(other_flows[i])
            if other.value_ids:
                ids.append(other.value_ids[i])
        return self._derive(names=names, flows=tuple(flows), ids=ids)

    def trim(self, span: Span) -> Stream:
        """Select whole periods or dates inside an extent without allocating amounts."""
        if self._batch is None:
            span.check()
            return self._derive(
                flows=tuple(
                    f.trim(start=span.start_inclusive, end=span.end_exclusive)
                    for f in self.flows
                )
            )
        return self._derive(batch=self._batch.trim(span))

    def resample(
        self,
        periods: Sequence[Period],
        *,
        method: ResamplingMethod | Mapping[str, ResamplingMethod],
        weighting: MeanWeighting | Mapping[str, MeanWeighting] | None = None,
        missing: MissingValueHandling | None = None,
    ) -> Stream:
        """Group each line onto explicit periods; declare all line-specific methods."""
        from rangekeeper.flow.series import ResamplingMethod

        if isinstance(method, Mapping):
            if set(method) != set(self.names):
                raise ValueError("method mapping must cover every label exactly")
            methods = tuple(method[label] for label in self.names)
        else:
            methods = (method,) * len(self.names)
        if isinstance(weighting, Mapping):
            mean_labels = {
                label
                for label, m in zip(self.names, methods, strict=True)
                if m is ResamplingMethod.MEAN
            }
            if set(weighting) != mean_labels:
                raise ValueError(
                    "weighting mapping must cover exactly the lines with a mean method"
                )
            weightings = tuple(weighting.get(label) for label in self.names)
        else:
            weightings = tuple(
                weighting if m is ResamplingMethod.MEAN else None for m in methods
            )
        if (
            not isinstance(weighting, Mapping)
            and weighting is not None
            and all(m is not ResamplingMethod.MEAN for m in methods)
        ):
            raise ValueError("weighting applies only to means")
        batch = self._prepared().resample(
            periods,
            methods=methods,
            weightings=weightings,
            missing=self.missing if missing is None else missing,
        )
        return self._derive(batch=batch, symbolic=False)

    @property
    def coverage(self) -> Mapping[str, tuple[float, ...]]:
        """Per-line coverage of the last resampling step; separate from aggregation coverage."""
        from types import MappingProxyType

        batch = self._prepared()
        column = "coverage" if "coverage" in batch.frame.columns else "known"
        values: list[list[float]] = [[] for _ in self.names]
        for line, value in (
            batch.frame.sort("line", "order").select("line", column).iter_rows()
        ):
            values[line].append(float(value))
        return MappingProxyType(dict(zip(self.names, map(tuple, values), strict=True)))

    def aggregate(
        self,
        *,
        method: AggregationMethod | None = None,
        units: str | None = None,
        missing: MissingValueHandling | None = None,
        join: AlignmentJoin | None = None,
    ) -> FlowAggregate:
        """Combine compatible line items at matching coordinates and report known coverage."""
        from rangekeeper.flow.series import AggregationMethod

        return self._prepared().aggregate(
            method=AggregationMethod.SUM if method is None else method,
            units=units,
            missing=self.missing if missing is None else missing,
            join=self.join if join is None else join,
        )

    def sum(
        self,
        *,
        units: str | None = None,
        missing: MissingValueHandling | None = None,
        join: AlignmentJoin | None = None,
    ) -> Flow:
        """Return the elementwise sum; use aggregate for coverage details."""
        from rangekeeper.flow.series import AggregationMethod

        return self.aggregate(
            method=AggregationMethod.SUM, units=units, missing=missing, join=join
        ).flow

    def min(
        self,
        *,
        units: str | None = None,
        missing: MissingValueHandling | None = None,
        join: AlignmentJoin | None = None,
    ) -> Flow:
        """Return the elementwise minimum; use aggregate for coverage details."""
        from rangekeeper.flow.series import AggregationMethod

        return self.aggregate(
            method=AggregationMethod.MIN, units=units, missing=missing, join=join
        ).flow

    def max(
        self,
        *,
        units: str | None = None,
        missing: MissingValueHandling | None = None,
        join: AlignmentJoin | None = None,
    ) -> Flow:
        """Return the elementwise maximum; use aggregate for coverage details."""
        from rangekeeper.flow.series import AggregationMethod

        return self.aggregate(
            method=AggregationMethod.MAX, units=units, missing=missing, join=join
        ).flow

    def to_frame(self) -> DataFrame:
        """Return a detached numeric projection; canonical interchange is Flow-specific."""
        from rangekeeper.io.polars import stream_frame

        return stream_frame(self)

    def display(self, *, transpose: bool = False, precision: int = 2):
        """Return an HTML/text table with line names, units and explicit missing states."""
        from rangekeeper.model.display import StreamTable

        return StreamTable(self, transpose=transpose, precision=precision)

    def _repr_html_(self):
        return self.display()._repr_html_()

    def __repr__(self):
        return f"Stream(names={self.names!r})"
