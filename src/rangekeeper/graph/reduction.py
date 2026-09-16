"""Pure hierarchical reductions and their immutable results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from statistics import median
from types import MappingProxyType
from typing import TYPE_CHECKING, Generic, TypeVar
from uuid import UUID

import networkx as nx
import pint

from ..measure import AggregationRule, Measure
from .entity import Entity
from .errors import InvalidAggregationError

if TYPE_CHECKING:
    from .view import View


T = TypeVar("T")
R = TypeVar("R")

__all__ = [
    "Aggregation",
    "Coverage",
    "Reduction",
    "by_feature",
    "by_measure",
    "collect",
    "distinct",
    "mode",
]


@dataclass(frozen=True, slots=True)
class Coverage:
    """Coverage of recorded selected contributors; not physical population certification."""

    selected: tuple[UUID, ...]
    measured: tuple[UUID, ...]
    missing: tuple[UUID, ...]

    @property
    def complete(self) -> bool:
        return bool(self.selected) and not self.missing

    @property
    def status(self) -> str:
        return (
            "empty"
            if not self.selected
            else "complete"
            if self.complete
            else "incomplete"
        )


@dataclass(frozen=True, slots=True)
class Aggregation(Generic[T]):
    """Immutable per-entity values aggregated over one hierarchical View."""

    view: View
    _values: Mapping[UUID, T | None] = field(repr=False)

    _coverage: Mapping[UUID, Coverage] = field(default_factory=dict, repr=False)
    _known_values: Mapping[UUID, T | None] = field(default_factory=dict, repr=False)
    _is_sum: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        from .view import View

        if not isinstance(self.view, View):
            raise TypeError("view must be a View")
        values = dict(self._values)
        if set(values) != {entity.id for entity in self.view.entities}:
            raise ValueError("aggregation values must match the View entities")
        object.__setattr__(self, "_values", MappingProxyType(values))
        for name in ("_coverage", "_known_values"):
            items = dict(getattr(self, name))
            if items and set(items) != set(values):
                raise ValueError(f"{name} keys must match View entities")
            object.__setattr__(self, name, MappingProxyType(items))

    @property
    def root_value(self) -> T | None:
        """Return the aggregate value at the View's sole root."""

        return self._values[self.view.roots[0].id]

    def __getitem__(self, entity: str | UUID | Entity) -> T | None:
        """Return an entity's aggregate through canonical View lookup."""

        identifier = self.view._resolve_view_entity_id(entity)
        return self._values[identifier]

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[Entity]:
        return iter(self.view.entities)

    def items(self) -> tuple[tuple[Entity, T | None], ...]:
        """Return entity-value pairs in View insertion order."""

        return tuple((entity, self._values[entity.id]) for entity in self)

    def coverage(self, entity: str | UUID | Entity) -> Coverage:
        """Selected, measured and missing contributors below and including this node."""
        return self._coverage[self.view._resolve_view_entity_id(entity)]

    def available_value(self, entity: str | UUID | Entity) -> T | None:
        """Reduction over available selected values, even when requirements are unmet."""
        return self._known_values[self.view._resolve_view_entity_id(entity)]

    def known_subtotal(self, entity: str | UUID | Entity) -> T | None:
        """Known subtotal for SUM only; an empty population is unavailable, not zero."""
        if not self._is_sum:
            raise InvalidAggregationError("known_subtotal is only defined for SUM")
        return self.available_value(entity)


class Reduction(ABC, Generic[R]):
    """A characteristic reduction executed against a hierarchical View."""

    @abstractmethod
    def _execute(self, view: View) -> Aggregation[R]:
        """Execute this reduction against a View."""


def by_measure(
    reference: str | Measure,
    *,
    contributors: Callable[[Entity], bool] | None = None,
    require_measurement: bool = False,
) -> Reduction[pint.Quantity]:
    """Reduce entity measurements using their Measure's declared rule."""
    if not isinstance(reference, (str, Measure)):
        raise TypeError("reference must be a measure code or Measure")
    if isinstance(reference, str) and not reference.strip():
        raise ValueError("measure code must not be empty")
    if contributors is not None and not callable(contributors):
        raise TypeError("contributors must be callable or None")
    if not isinstance(require_measurement, bool):
        raise TypeError("require_measurement must be a bool")
    return _MeasureReduction(reference, contributors, require_measurement)


def by_feature(
    name: str,
    *,
    reducer: Callable[[tuple[T, ...]], R],
) -> Reduction[R]:
    """Reduce a named Feature using one pure callable."""
    if not isinstance(name, str):
        raise TypeError("feature name must be a string")
    if not name.strip():
        raise ValueError("feature name must not be empty")
    if not callable(reducer):
        raise TypeError("feature reducer must be callable")
    return _FeatureReduction(name, reducer)


@dataclass(frozen=True, slots=True)
class _MeasureReduction(Reduction[pint.Quantity]):
    reference: str | Measure
    contributors: Callable[[Entity], bool] | None = None
    require_measurement: bool = False

    def _execute(self, view: View) -> Aggregation[pint.Quantity]:
        measure = view.graph.definitions._resolve_measure(self.reference)
        reducer = _MEASUREMENT_REDUCERS.get(measure.aggregation)
        if reducer is None:
            raise InvalidAggregationError(
                f"measure {measure.code!r} has no aggregation rule"
            )

        def extract(entity: Entity) -> pint.Quantity | None:
            measurement = entity.measurements.get(measure.code)
            if measurement is None:
                return None
            return measurement.quantity.to(measure.units)

        return _traverse(
            view,
            extractor=extract,
            reducer=reducer,
            contributors=self.contributors,
            require_value=self.require_measurement,
            is_sum=measure.aggregation is AggregationRule.SUM,
        )


@dataclass(frozen=True, slots=True)
class _FeatureReduction(Reduction[R], Generic[T, R]):
    name: str
    reducer: Callable[[tuple[T, ...]], R]

    def _execute(self, view: View) -> Aggregation[R]:
        def extract(entity: Entity) -> T | None:
            feature = entity.features.get(self.name)
            return None if feature is None else feature.value

        return _traverse(view, extractor=extract, reducer=self.reducer)


def collect(values: tuple[T, ...]) -> tuple[T, ...]:
    """Return every value in deterministic traversal order."""
    return values


def distinct(values: tuple[T, ...]) -> tuple[T, ...]:
    """Return first-seen unique values in deterministic traversal order."""
    result: list[T] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


def mode(values: tuple[T, ...]) -> T:
    """Return the unique most-common value, rejecting ties and empty input."""
    if not values:
        raise InvalidAggregationError("feature values have no unique mode")
    try:
        counts = Counter(values)
    except TypeError as error:
        raise InvalidAggregationError(
            "mode requires hashable feature values"
        ) from error
    frequency = max(counts.values())
    modes = tuple(value for value, count in counts.items() if count == frequency)
    if len(modes) != 1:
        raise InvalidAggregationError("feature values have no unique mode")
    return modes[0]


def _traverse(
    view: View,
    *,
    extractor: Callable[[Entity], T | None],
    reducer: Callable[[tuple[T, ...]], R],
    contributors: Callable[[Entity], bool] | None = None,
    require_value: bool = False,
    is_sum: bool = False,
) -> Aggregation[R]:
    if not view.entities:
        raise InvalidAggregationError("cannot aggregate an empty View")
    graph = view._require_arborescence()

    subtree_values: dict[UUID, tuple[T, ...]] = {}
    results: dict[UUID, R | None] = {}
    known: dict[UUID, R | None] = {}
    coverage: dict[UUID, Coverage] = {}
    root_id = view.roots[0].id
    for identifier in nx.dfs_postorder_nodes(graph, source=root_id):
        entity = view.graph.entity(identifier)
        eligible = contributors is None or contributors(entity)
        own_value = extractor(entity) if eligible else None
        selected = [identifier] if eligible else []
        measured = [identifier] if eligible and own_value is not None else []
        missing = [identifier] if eligible and own_value is None else []
        raw_values = [] if own_value is None else [own_value]
        for child_id in graph.successors(identifier):
            raw_values.extend(subtree_values[child_id])
            selected.extend(coverage[child_id].selected)
            measured.extend(coverage[child_id].measured)
            missing.extend(coverage[child_id].missing)
        values = tuple(raw_values)
        subtree_values[identifier] = values
        coverage[identifier] = Coverage(
            tuple(selected), tuple(measured), tuple(missing)
        )
        known[identifier] = None if not values else reducer(values)
        results[identifier] = (
            None
            if require_value and not coverage[identifier].complete
            else known[identifier]
        )

    ordered = {entity.id: results[entity.id] for entity in view.entities}
    return Aggregation(view, ordered, coverage, known, is_sum)


def _mean(values: tuple[pint.Quantity, ...]) -> pint.Quantity:
    """Average Pint quantities without losing their units.

    ``statistics.mean`` reconstructs Pint values through its numeric ratio
    machinery and can return a dimensionless Quantity.
    """
    return sum(values) / len(values)


_MEASUREMENT_REDUCERS: dict[
    AggregationRule, Callable[[tuple[pint.Quantity, ...]], pint.Quantity]
] = {
    AggregationRule.SUM: sum,
    AggregationRule.MEAN: _mean,
    AggregationRule.MEDIAN: median,
    AggregationRule.MINIMUM: min,
    AggregationRule.MAXIMUM: max,
}
