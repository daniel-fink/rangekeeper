"""Canonical Flow records and ordered, immutable coordination through Stream."""

from __future__ import annotations
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import UUID

from rangekeeper.schema.records import Flow, Movement, Value
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.behaviors.flow import MissingValueHandling

if TYPE_CHECKING:
    from rangekeeper.model.model import Model
    from rangekeeper.model.duration import Period, Span
    from rangekeeper.calculations.series import (
        AlignmentJoin,
        AggregationMethod,
        ResamplingMethod,
        MeanWeighting,
        Aggregation,
    )
    from polars import DataFrame
    from rangekeeper.calculations._batch import Batch

__all__ = ["Flow", "Movement", "Stream", "MissingValueHandling"]


@dataclass(frozen=True, init=False, eq=False)
class Stream:
    """Ordered labelled flows, optionally pinned to exact Model Value identities.

    Numerical operations are detached calculations. Passive equation builders can
    consume original Model selections, including structural trims, without reading
    their magnitudes. Resampling must be declared separately for symbolic use.
    """

    labels: tuple[str, ...]
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
        from rangekeeper.calculations.series import AlignmentJoin

        if not isinstance(flows, Mapping):
            raise TypeError(
                "Stream requires a label-to-Flow mapping; use from_values for a Model selection"
            )
        labels = tuple(flows)
        self._initialize(
            labels,
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
        labels,
        flows,
        model,
        value_ids,
        missing,
        join,
        batch,
        symbolic,
    ):
        from rangekeeper.calculations.series import AlignmentJoin

        if any(
            not isinstance(label, str) or not label.strip() for label in labels
        ) or len(set(labels)) != len(labels):
            raise ValueError(
                "Stream labels must be nonempty and unique; supply explicit labels"
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
            ("labels", tuple(labels)),
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
        labels: Sequence[str] | None = None,
        missing: MissingValueHandling = MissingValueHandling.ERROR,
        join: AlignmentJoin | None = None,
    ) -> Stream:
        """Pin original Values; duplicate identities or ambiguous labels are errors."""
        from rangekeeper.calculations.series import AlignmentJoin

        ids = tuple(value_ids)
        if len(set(ids)) != len(ids):
            raise ValueError("Stream cannot count the same Value twice")
        values = tuple(model.value(i) for i in ids)
        if any(v.kind is not ValueKind.FLOW for v in values):
            raise ValueError("Stream target is not a Flow Value")
        labels = tuple(labels) if labels is not None else tuple(v.key for v in values)
        if len(labels) != len(ids):
            raise ValueError("one label is required per Value")
        result = object.__new__(cls)
        result._initialize(
            labels,
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
            from rangekeeper.calculations._batch import Batch

            object.__setattr__(self, "_batch", Batch.prepare(self.flows))
        return self._batch

    def _derive(self, *, labels=None, flows=None, batch=None, ids=None, symbolic=None):
        result = object.__new__(type(self))
        result._initialize(
            self.labels if labels is None else labels,
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
        labels: Iterable[str] | None = None,
        *,
        value_ids: Iterable[UUID] | None = None,
    ) -> Stream:
        """Select lines in requested order by labels or original Value IDs."""
        if (labels is None) == (value_ids is None):
            raise ValueError("supply labels or value_ids")
        requested = tuple(labels if labels is not None else (value_ids or ()))
        available = self.labels if labels is not None else self.value_ids
        if len(set(requested)) != len(requested):
            raise ValueError("duplicate selection")
        if any(i not in available for i in requested):
            raise KeyError("selection contains a member outside this Stream")
        indices = tuple(available.index(i) for i in requested)
        return self._derive(
            labels=tuple(self.labels[i] for i in indices),
            flows=(
                None if self._flows is None else tuple(self._flows[i] for i in indices)
            ),
            batch=None if self._batch is None else self._batch.select(indices),
            ids=tuple(self.value_ids[i] for i in indices) if self.value_ids else (),
        )

    def merge(self, other: Stream) -> Stream:
        """Union compatible selections; conflicting labels or revisions require resolution."""
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
        labels = list(self.labels)
        flows = list(self._flows if self._flows is not None else self.flows)
        other_flows = other._flows if other._flows is not None else other.flows
        ids = list(self.value_ids)
        for i, label in enumerate(other.labels):
            if ids and other.value_ids[i] in ids:
                position = ids.index(other.value_ids[i])
                if labels[position] != label or flows[position] != other_flows[i]:
                    raise ValueError(
                        "duplicate Value has conflicting label or selection"
                    )
                continue
            if label in labels:
                if self.model is None and flows[labels.index(label)] == other_flows[i]:
                    continue
                raise ValueError(f"conflicting Stream label: {label}")
            labels.append(label)
            flows.append(other_flows[i])
            if other.value_ids:
                ids.append(other.value_ids[i])
        return self._derive(labels=labels, flows=tuple(flows), ids=ids)

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
        from rangekeeper.calculations.series import ResamplingMethod

        if isinstance(method, Mapping):
            if set(method) != set(self.labels):
                raise ValueError("method mapping must cover every label exactly")
            methods = tuple(method[label] for label in self.labels)
        else:
            methods = (method,) * len(self.labels)
        if isinstance(weighting, Mapping):
            mean_labels = {
                label
                for label, m in zip(self.labels, methods)
                if m is ResamplingMethod.MEAN
            }
            if set(weighting) != mean_labels:
                raise ValueError("weighting mapping must cover exactly the mean labels")
            weightings = tuple(weighting.get(label) for label in self.labels)
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
        values: list[list[float]] = [[] for _ in self.labels]
        for line, value in (
            batch.frame.sort("line", "order").select("line", column).iter_rows()
        ):
            values[line].append(float(value))
        return MappingProxyType(dict(zip(self.labels, map(tuple, values))))

    def aggregate(
        self,
        *,
        method: AggregationMethod | None = None,
        units: str | None = None,
        missing: MissingValueHandling | None = None,
        join: AlignmentJoin | None = None,
    ) -> Aggregation:
        """Combine compatible line items at matching coordinates and report known coverage."""
        from rangekeeper.calculations.series import AggregationMethod

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
        from rangekeeper.calculations.series import AggregationMethod

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
        from rangekeeper.calculations.series import AggregationMethod

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
        from rangekeeper.calculations.series import AggregationMethod

        return self.aggregate(
            method=AggregationMethod.MAX, units=units, missing=missing, join=join
        ).flow

    def to_frame(self) -> DataFrame:
        """Return a detached numeric projection; canonical interchange is Flow-specific."""
        from rangekeeper.adapters.polars import stream_frame

        return stream_frame(self)

    def display(self, *, transpose: bool = False, precision: int = 2):
        """Return an HTML/text table with line labels, units and explicit missing states."""
        from rangekeeper.adapters.presentation import StreamTable

        return StreamTable(self, transpose=transpose, precision=precision)

    def _repr_html_(self):
        return self.display()._repr_html_()

    def __repr__(self):
        return f"Stream(labels={self.labels!r})"
