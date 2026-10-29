"""Static public graph composition; schema quantities and UUID lookup stay typed."""

from uuid import UUID

from rangekeeper import Model
from rangekeeper.model import Entity
from rangekeeper.model.system import (
    Hierarchy,
    QuantityRollup,
    Reducer,
    RollupResult,
    View,
)
from rangekeeper.quantity import Quantity


def inspect(model: Model, id: UUID) -> Quantity | None:
    view = View(model=model, entities=(id,))
    entity: Entity = view.entity(id)
    hierarchy = Hierarchy.from_relationships(view)
    rollup = QuantityRollup(key="net", reducer=Reducer.SUM, units="m ** 2")
    result: RollupResult = rollup.execute(hierarchy)
    value = result.value(entity.id)
    assert value is None or isinstance(value, Quantity)
    return value
