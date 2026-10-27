"""Static public graph composition; schema quantities and UUID lookup stay typed."""

from uuid import UUID

from rangekeeper import Model
from rangekeeper.model import Entity, Quantity
from rangekeeper.model.system import Hierarchy, Reduction, RollupResult, View, reducers
from rangekeeper.model.system.selection import select_value


def inspect(model: Model, id: UUID) -> Quantity | None:
    view = View(model, entities=(id,))
    entity: Entity = view.entity(id)
    hierarchy = Hierarchy.from_relationships(view)
    reduction = Reduction(
        select=select_value("net"), reducer=reducers.sum, units="m ** 2"
    )
    result: RollupResult = reduction.execute(hierarchy)
    value = result.value(entity.id)
    assert value is None or isinstance(value, Quantity)
    return value
