from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING, Generic, TypeVar
from uuid import UUID

import networkx as nx
import pint

from ..measure import AggregationRule, Measure
from .aggregation import Aggregation
from .entity import Entity
from .errors import InvalidAggregationError

if TYPE_CHECKING:
    from .view import View


T = TypeVar("T")
R = TypeVar("R")

__all__ = [
    "Reduction",
    "by_feature",
    "by_measure",
    "collect",
    "distinct",
    "mode",
]


class Reduction(ABC, Generic[R]):
    """A characteristic reduction executed against a hierarchical View."""

    @abstractmethod
    def _execute(self, view: View) -> Aggregation[R]:
        """Execute this reduction against a View."""


def by_measure(reference: str | Measure) -> Reduction[pint.Quantity]:
    """Reduce entity measurements using their Measure's declared rule."""
    if not isinstance(reference, (str, Measure)):
        raise TypeError("reference must be a measure code or Measure")
    if isinstance(reference, str) and not reference.strip():
        raise ValueError("measure code must not be empty")
    return _MeasureReduction(reference)


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

    def _execute(self, view: View) -> Aggregation[pint.Quantity]:
        measure = (
            view.graph.definitions.measures[self.reference]
            if isinstance(self.reference, str)
            else view.graph.definitions.measures._require_catalog_instance(
                self.reference
            )
        )
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

        return _traverse(view, extractor=extract, reducer=reducer)


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
) -> Aggregation[R]:
    if not view.entities:
        raise InvalidAggregationError("cannot aggregate an empty View")
    graph = view.to_networkx()
    if not nx.is_arborescence(graph):
        raise InvalidAggregationError(
            "aggregation requires a parent-to-child arborescence View"
        )

    subtree_values: dict[UUID, tuple[T, ...]] = {}
    results: dict[UUID, R | None] = {}
    root_id = view.roots[0].id
    for identifier in nx.dfs_postorder_nodes(graph, source=root_id):
        entity = view.graph.entity(identifier)
        own_value = extractor(entity)
        raw_values = [] if own_value is None else [own_value]
        for child_id in graph.successors(identifier):
            raw_values.extend(subtree_values[child_id])

        values = tuple(raw_values)
        subtree_values[identifier] = values
        results[identifier] = None if not values else reducer(values)

    ordered = {entity.id: results[entity.id] for entity in view.entities}
    return Aggregation(view=view, _values=ordered)


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
