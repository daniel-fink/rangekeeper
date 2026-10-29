"""Canonical Flow records and ordered, immutable coordination through Stream."""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import UUID

from rangekeeper.duration.calendar import PeriodTiming
from rangekeeper.flow._flow import Flow, Movement, _target
from rangekeeper.flow._options import (
    AggregationMethod,
    AlignmentJoin,
    FlowAggregate,
    MissingValueHandling,
    ResampleMethod,
)
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.records import Value
from rangekeeper.schema.runtime import OMIT

if TYPE_CHECKING:
    from polars import DataFrame

    from rangekeeper.duration import Frequency, Period
    from rangekeeper.flow._batch import Batch
    from rangekeeper.model.model import Model

__all__ = [
    "Flow",
    "Movement",
    "Stream",
    "FlowAggregate",
    "AlignmentJoin",
    "AggregationMethod",
    "ResampleMethod",
    "MissingValueHandling",
]


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
        *,
        flows: Mapping[str, Flow],
        missing: MissingValueHandling = MissingValueHandling.ERROR,
        join: AlignmentJoin | None = None,
    ):
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
            AlignmentJoin.UNION if join is None else join,
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
            AlignmentJoin.UNION if join is None else join,
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

    def __getitem__(self, name: str) -> Flow:
        """Return the Flow with a name."""
        if name not in self.names:
            from rangekeeper.shared.errors import MissingReferenceError

            raise MissingReferenceError(
                name,
                kind="Flow",
                by="name",
                where="Stream",
                candidates=difflib.get_close_matches(name, self.names),
            )
        return self.flows[self.names.index(name)]

    def with_flows(self, *, flows: Mapping[str, Flow]) -> Stream:
        """Return a Stream with more named Flows.

        A name that is already in the Stream gets the new Flow in its place; a
        new name is added at the end. The new Stream has no Model Values.
        """
        if not isinstance(flows, Mapping):
            raise TypeError("flows must map names to Flows")
        lines = dict(zip(self.names, self.flows, strict=True))
        lines.update(flows)
        return Stream(flows=lines, missing=self.missing, join=self.join)

    def select(self, *names: str) -> Stream:
        """Select lines by name, in the requested order."""
        return self._select(self.names, names)

    def select_values(self, ids: Iterable[UUID]) -> Stream:
        """Select lines by their original Model Value IDs, in the requested order."""
        return self._select(self.value_ids, tuple(ids))

    def with_policy(
        self,
        *,
        missing: MissingValueHandling | None = None,
        join: AlignmentJoin | None = None,
    ) -> Stream:
        """Return this Stream with another missing-value or join policy.

        The policies apply to ``align``, ``resample`` and ``aggregate``. A
        policy that is None stays as it is.
        """
        result = object.__new__(type(self))
        result._initialize(
            self.names,
            self._flows,
            self.model,
            self.value_ids,
            self.missing if missing is None else missing,
            self.join if join is None else join,
            self._batch,
            self._symbolic,
        )
        return result

    def _select(self, available: tuple, requested: tuple) -> Stream:
        """Select the lines whose names or Value IDs are ``requested``."""
        if not requested:
            raise ValueError("select at least one line")
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

    def align(self) -> Stream:
        """Put every line on common coordinates with the join and missing policies.

        An absent coordinate becomes zero with ``ZERO`` and unresolved otherwise.
        Coverage and aggregation keep the original known values, so a filled zero
        stays absent.
        """
        from rangekeeper.flow._batch import Batch, align

        flows, coverage = align(self.flows, join=self.join, missing=self.missing)
        batch = Batch.prepare(flows).aligned(flows, coverage)
        return self._derive(flows=flows, batch=batch, symbolic=False)

    def trim(self, *, span: Period) -> Stream:
        """Select whole periods or dates inside an extent without allocating amounts."""
        if self._batch is None:
            return self._derive(flows=tuple(f.trim(span=span) for f in self.flows))
        return self._derive(batch=self._batch.trim(span=span))

    def resample(
        self,
        *,
        periods: Sequence[Period] | None = None,
        frequency: Frequency | None = None,
        method: ResampleMethod | Mapping[str, ResampleMethod],
    ) -> Stream:
        """Reduce each line onto explicit ``periods``, or onto Periods of a ``frequency``.

        A frequency makes the Periods from the earliest start to the latest end
        of the lines. ``method`` is one ResampleMethod for every line, or a
        mapping from each name to its method. The Stream's ``missing`` policy
        treats empty and unresolved Periods. ``split`` divides amounts over
        shorter Periods.
        """
        methods = self._line_methods(method)
        batch = self._prepared().resample(
            self._target(periods=periods, frequency=frequency),
            methods=methods,
            missing=self.missing,
        )
        return self._derive(batch=batch, symbolic=False)

    def split(
        self,
        *,
        periods: Sequence[Period] | None = None,
        frequency: Frequency | None = None,
    ) -> Stream:
        """Divide each amount of each line equally over shorter Periods.

        ``Flow.split`` gives the rule. A frequency makes the Periods from the
        earliest start to the latest end of the lines.
        """
        targets = self._target(periods=periods, frequency=frequency)
        return self._derive(
            flows=tuple(flow.split(periods=targets) for flow in self.flows),
            symbolic=False,
        )

    def _line_methods(
        self, method: ResampleMethod | Mapping[str, ResampleMethod]
    ) -> tuple[ResampleMethod, ...]:
        """Return the method of each line; a mapping must name every line once."""
        if not isinstance(method, Mapping):
            return (method,) * len(self.names)
        if set(method) != set(self.names):
            raise ValueError("method mapping must cover every label exactly")
        return tuple(method[name] for name in self.names)

    def _target(
        self, *, periods: Sequence[Period] | None, frequency: Frequency | None
    ) -> Sequence[Period]:
        """Return the given Periods, or the Periods of a frequency over all lines."""
        # Read the lines only for a frequency: given Periods need no materialized Flows.
        movements = (
            ()
            if frequency is None
            else sorted(
                (m for f in self.flows for m in f.movements),
                key=lambda m: m.coordinate[1:],
            )
        )
        return _target(movements, periods=periods, frequency=frequency)

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
        method: AggregationMethod = AggregationMethod.SUM,
        units: str | None = None,
    ) -> FlowAggregate:
        """Combine compatible line items at matching coordinates and report known coverage.

        A coordinate that a line does not have adds nothing; an unresolved
        amount follows the Stream's ``missing`` policy, and ``join`` selects
        the coordinates. When the lines mix dated and period Flows, each period
        amount is dated at its recorded date, or else at the end of its Period,
        as in ``rangekeeper.finance``. ``dated`` chooses another date.
        """
        batch = self._prepared()
        if len({coordinate[0] for coordinate in batch.coordinates}) > 1:
            batch = self.dated()._prepared()
        return batch.aggregate(
            method=method, units=units, missing=self.missing, join=self.join
        )

    def dated(self, *, timing: PeriodTiming = PeriodTiming.END) -> Stream:
        """Return a Stream whose period amounts are dated events.

        Each period amount keeps its recorded date, or gets the date that
        ``timing`` gives in its Period. Dated amounts do not change.
        """
        if not isinstance(timing, PeriodTiming):
            raise TypeError("timing must be a PeriodTiming")
        return self._derive(
            flows=tuple(_dated(flow, timing) for flow in self.flows), symbolic=False
        )

    def sum(self, *, units: str | None = None) -> Flow:
        """Return the elementwise sum; use aggregate for coverage details."""
        return self.aggregate(method=AggregationMethod.SUM, units=units).flow

    def min(self, *, units: str | None = None) -> Flow:
        """Return the elementwise minimum; use aggregate for coverage details."""
        return self.aggregate(method=AggregationMethod.MIN, units=units).flow

    def max(self, *, units: str | None = None) -> Flow:
        """Return the elementwise maximum; use aggregate for coverage details."""
        return self.aggregate(method=AggregationMethod.MAX, units=units).flow

    def to_frame(self) -> DataFrame:
        """Return a detached numeric projection; canonical interchange is Flow-specific."""
        from rangekeeper.flow._table import stream_frame

        return stream_frame(self)

    def display(self, *, transpose: bool = False, precision: int = 2):
        """Return an HTML/text table with line names, units and explicit missing states."""
        from rangekeeper.flow._table import StreamTable

        return StreamTable(self, transpose=transpose, precision=precision)

    def _repr_html_(self):
        return self.display()._repr_html_()

    def __repr__(self):
        return f"Stream(names={self.names!r})"


def _dated(flow: Flow, timing: PeriodTiming) -> Flow:
    """Return a Flow whose period amounts are dated events."""
    return flow.replace(
        movements=tuple(
            m
            if m.period is None
            else m.replace(period=OMIT, date=m.resolve(timing=timing))
            for m in flow.movements
        )
    )
