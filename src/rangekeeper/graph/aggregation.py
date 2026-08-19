from __future__ import annotations

from numbers import Number
from typing import TYPE_CHECKING, Protocol

import networkx as nx
import pint

from .entity import Entity
from .errors import InvalidAggregationError
from .view import View

if TYPE_CHECKING:
    from .model import Model


class AggregationFunction(Protocol):
    def __call__(
        self,
        *,
        entity: Entity,
        own_value: object | None,
        child_values: tuple[object, ...],
    ) -> object: ...


def aggregate_view(
    model: Model,
    *,
    view: View,
    feature: str,
    into: str | None,
    function: AggregationFunction | None,
    outgoing: bool,
) -> dict[str, object]:
    """Aggregate one feature through an oriented arborescence.

    Missing features and explicit ``None`` values both contribute no value.
    Numeric zero is retained. A custom function is called with keyword arguments
    ``entity``, ``own_value``, and ``child_values``.
    """
    _validate_request(
        model=model,
        view=view,
        feature=feature,
        into=into,
        function=function,
        outgoing=outgoing,
    )

    graph = view.to_networkx()
    oriented = graph if outgoing else graph.reverse(copy=True)
    if not nx.is_arborescence(oriented):
        raise InvalidAggregationError(
            "aggregation requires the oriented View to be an arborescence; "
            "filter it to one hierarchical relationship overlay"
        )

    results: dict[str, object] = {}
    for entity_id in reversed(tuple(nx.topological_sort(oriented))):
        entity = model.entity(entity_id)
        own_value = entity.features.get(feature)
        child_values = tuple(
            results[child_id] for child_id in oriented.successors(entity_id)
        )
        if function is None:
            result = _sum_numeric_values((own_value, *child_values))
        else:
            result = function(
                entity=entity,
                own_value=own_value,
                child_values=child_values,
            )
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
    function: AggregationFunction | None,
    outgoing: bool,
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
    if function is not None and not callable(function):
        raise TypeError("function must be callable or None")
    if not isinstance(outgoing, bool):
        raise TypeError("outgoing must be a bool")


def _sum_numeric_values(values: tuple[object, ...]) -> object:
    available = tuple(value for value in values if value is not None)
    if not available:
        return None
    for value in available:
        if not isinstance(value, (Number, pint.Quantity)):
            raise TypeError(
                "default aggregation accepts only numeric or Pint Quantity values; "
                "provide function for rich feature values"
            )
    result = available[0]
    for value in available[1:]:
        result = result + value
    return result
