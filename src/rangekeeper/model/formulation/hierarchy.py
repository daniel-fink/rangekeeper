"""Passive hierarchy equations over structurally selected original Flow Values."""

from rangekeeper.model.expression.authoring import (
    equal,
    reference,
)
from rangekeeper.model.expression.authoring import (
    sum as expression_sum,
)
from rangekeeper.model.formulation.authoring import declare
from rangekeeper.model.formulation.flow import _resampled_terms, shape
from rangekeeper.schema.records import Reference
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError


def formulate(hierarchy, *, id, aggregates, selected, populations, rule):
    """Declare one sum equation per aggregate movement over its selected contributors."""
    model = hierarchy.view.model
    if not aggregates:
        raise ContractError("declare at least one aggregate Flow")
    if len(set(aggregates.values())) != len(aggregates):
        raise ContractError(
            "aggregate Flow Values must be distinct",
            code=Code.UNIQUE,
            targets=aggregates.values(),
        )
    equations = []
    bindings = []
    prepared = {}
    for owner, value in selected.items():
        if value is not None:
            if value.flow is None:
                raise ContractError(
                    "a symbolic contributor needs a declared Flow shape",
                    targets=(value.id,),
                )
            prepared[owner] = value.flow
    for entity, value_id in aggregates.items():
        hierarchy.view.entity(entity)
        if model.owner_of(value_id) != entity:
            raise ContractError(
                "an aggregate Value must belong to its Entity",
                targets=(entity, value_id),
            )
        total = shape(model=model, value=value_id)
        contributors = populations[entity]
        if not contributors or any(owner not in prepared for owner in contributors):
            raise ContractError(
                "symbolic aggregation needs a declared Flow for each selected "
                "contributor",
                targets=(entity, *contributors),
            )
        if value_id in {selected[owner].id for owner in contributors}:
            raise ContractError(
                "an aggregate cannot include itself; select leaves or a "
                "structural View",
                targets=(value_id,),
            )
        terms = []
        for owner in contributors:
            source = prepared[owner]
            bindings.append(selected[owner].id)
            if rule.periods is None:
                source_map = source._coordinate_index()
                if set(source_map) != set(total._coordinate_index()):
                    raise ContractError(
                        "Flow coordinates differ; declare explicit resampling",
                        targets=(selected[owner].id, value_id),
                    )
                terms.append(
                    [
                        reference(Reference(target=source_map[m._coordinate].id))
                        for m in total.movements
                    ]
                )
            else:
                if tuple(m.period for m in total.movements) != rule.periods:
                    raise ContractError(
                        "aggregate periods must match the reduction grid",
                        targets=(value_id,),
                    )
                terms.append(
                    _resampled_terms(
                        source,
                        rule.periods,
                        method=rule.resampling,
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
    return declare(id=id, name="hierarchy_sum", equations=equations, values=bindings)
