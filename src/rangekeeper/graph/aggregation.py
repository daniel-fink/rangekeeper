from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import networkx as nx

from .entity import Entity
from .errors import InvalidAggregationError

if TYPE_CHECKING:
    from .view import View


AggregationCallback = Callable[[Entity, tuple[object, ...]], object | None]


def aggregate(
    *,
    view: View,
    feature: str,
    into: str | None,
    reducer: AggregationCallback | None,
) -> dict[str, object]:
    """Aggregate one feature through a parent-to-child arborescence.

    Missing features and explicit ``None`` values both contribute no value.
    Numeric zero is retained. A custom reducer receives the current entity and
    its own value followed by the already-aggregated values of its children.
    """
    _validate(
        view=view,
        feature=feature,
        into=into,
        reduce=reducer,
    )

    graph = view.to_networkx()
    if not nx.is_arborescence(graph):
        raise InvalidAggregationError(
            "aggregation requires the View to be a parent-to-child arborescence; "
            "filter it to one hierarchical relationship overlay"
        )

    results: dict[str, object] = {}
    for entity_id in reversed(tuple(nx.topological_sort(graph))):
        entity = view.graph.entities[entity_id]
        values = tuple(
            value
            for value in (
                entity.features.get(feature),
                *(results[child_id] for child_id in graph.successors(entity_id)),
            )
            if value is not None
        )
        if not values:
            result = None
        elif reducer is None:
            result = sum(values)
        else:
            result = reducer(entity, values)
        results[entity_id] = result

    entities = view.entities()
    ordered_results = {
        entity.entity_id: results[entity.entity_id] for entity in entities
    }
    if into is not None:
        for entity in entities:
            entity.features[into] = ordered_results[entity.entity_id]
    return ordered_results


def _validate(
    *,
    view: View,
    feature: str,
    into: str | None,
    reduce: AggregationCallback | None,
) -> None:
    if not view.entity_ids:
        raise InvalidAggregationError("cannot aggregate an empty View")
    if not isinstance(feature, str):
        raise TypeError("feature must be a string")
    if not feature.strip():
        raise ValueError("feature must not be empty")
    if into is not None:
        if not isinstance(into, str):
            raise TypeError("into must be a string or None")
        if not into.strip():
            raise ValueError("into must not be empty")
        if into == feature:
            raise InvalidAggregationError(
                "into must differ from feature so repeated aggregation is idempotent"
            )
    if reduce is not None and not callable(reduce):
        raise TypeError("reduce must be callable or None")
