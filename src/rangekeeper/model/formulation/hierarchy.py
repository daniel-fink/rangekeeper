"""Passive hierarchy equations over structurally selected original Flow Values."""

from rangekeeper.model.formulation.flow import shape, _resampled_terms
from rangekeeper.model.formulation.authoring import declare
from rangekeeper.model.expression.authoring import (
    reference,
    equal,
    sum as expression_sum,
)
from rangekeeper.schema.records import Reference


def formulate(hierarchy, *, id, aggregates, selected, populations, rule):
    model = hierarchy.view.model
    if not aggregates:
        raise ValueError("declare at least one aggregate Flow")
    if len(set(aggregates.values())) != len(aggregates):
        raise ValueError("aggregate Flow Values must be distinct")
    equations = []
    bindings = []
    prepared = {}
    for owner, value in selected.items():
        if value is not None:
            if value.flow is None:
                raise ValueError("symbolic contributor requires a declared Flow shape")
            prepared[owner] = value.flow
    for entity, value_id in aggregates.items():
        hierarchy.view.entity(entity)
        if model.owner_of(value_id) != entity:
            raise ValueError("aggregate Value must belong to its entity")
        total = shape(model, value_id)
        contributors = populations[entity]
        if not contributors or any(owner not in prepared for owner in contributors):
            raise ValueError(
                "symbolic aggregation requires every selected contributor to have a declared Flow"
            )
        if value_id in {selected[owner].id for owner in contributors}:
            raise ValueError(
                "an aggregate cannot include itself; select leaves or a structural View"
            )
        terms = []
        for owner in contributors:
            source = prepared[owner]
            bindings.append(selected[owner].id)
            if rule.periods is None:
                source_map = source.coordinate_index()
                if set(source_map) != set(total.coordinate_index()):
                    raise ValueError(
                        "Flow coordinates differ; declare explicit resampling"
                    )
                terms.append(
                    [
                        reference(Reference(target=source_map[m.coordinate].id))
                        for m in total.movements
                    ]
                )
            else:
                if tuple(m.period for m in total.movements) != rule.periods:
                    raise ValueError("aggregate periods must match the reduction grid")
                terms.append(
                    _resampled_terms(
                        source,
                        rule.periods,
                        method=rule.resampling,
                        weighting=rule.weighting,
                        missing=rule.missing,
                    )
                )
        for i, movement in enumerate(total.movements):
            equations.append(
                (
                    str(movement.id),
                    equal(
                        reference(Reference(target=movement.id)),
                        expression_sum([column[i] for column in terms]),
                    ),
                )
            )
        bindings.append(value_id)
    return declare(id, "hierarchy_sum", equations, bindings)
