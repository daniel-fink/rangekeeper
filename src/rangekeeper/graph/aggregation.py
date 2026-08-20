from __future__ import annotations

from collections.abc import Callable
from numbers import Number
from typing import TYPE_CHECKING

import networkx as nx
import pint

from .entity import Entity
from .errors import InvalidAggregationError
from .view import View

if TYPE_CHECKING:
    from .model import Model


AggregationCallback = Callable[[Entity, tuple[object, ...]], object | None]


def aggregate_view(
    model: Model,
    *,
    view: View,
    feature: str,
    into: str | None,
    reduce: AggregationCallback | None,
) -> dict[str, object]:
    """Aggregate one feature through a parent-to-child arborescence.

    Missing features and explicit ``None`` values both contribute no value.
    Numeric zero is retained. A custom reducer receives the current entity and
    its own value followed by the already-aggregated values of its children.
    """
    _validate_request(
        model=model,
        view=view,
        feature=feature,
        into=into,
        reduce=reduce,
    )

    graph = view.to_networkx()
    if not nx.is_arborescence(graph):
        raise InvalidAggregationError(
            "aggregation requires the View to be a parent-to-child arborescence; "
            "filter it to one hierarchical relationship overlay"
        )

    results: dict[str, object] = {}
    for entity_id in reversed(tuple(nx.topological_sort(graph))):
        entity = model.entity(entity_id)
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
        elif reduce is None:
            result = _sum_numeric_values(values)
        else:
            result = reduce(entity, values)
        results[entity_id] = result

    entities = view.entities()
    ordered_results = {
        entity.entity_id: results[entity.entity_id] for entity in entities
    }
    if into is not None:
        for entity in entities:
            entity.features[into] = ordered_results[entity.entity_id]
    return ordered_results


def _validate_request(
    *,
    model: Model,
    view: View,
    feature: str,
    into: str | None,
    reduce: AggregationCallback | None,
) -> None:
    if not isinstance(view, View):
        raise TypeError("view must be a View")
    if view.model is not model:
        raise InvalidAggregationError("view belongs to a different Model")
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


def _sum_numeric_values(values: tuple[object, ...]) -> object:
    for value in values:
        if not isinstance(value, (Number, pint.Quantity)):
            raise TypeError(
                "default aggregation accepts only numeric or Pint Quantity values; "
                "provide reduce for rich feature values"
            )
    result = values[0]
    for value in values[1:]:
        result = result + value
    return result
