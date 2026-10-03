"""Static public graph composition; schema quantities and UUID lookup stay typed."""

from uuid import UUID
from rangekeeper import Model
from rangekeeper.model import Entity, Quantity
from rangekeeper.graph import View, Hierarchy, Reduction, Aggregation
from rangekeeper.graph.selection import select_value
from rangekeeper.graph.reducers import sum_quantities


def inspect(model: Model, id: UUID) -> Quantity | None:
    view = View(model, entities=(id,))
    entity: Entity = view.entity(id)
    hierarchy = Hierarchy.from_relationships(view)
    reduction = Reduction(
        select=select_value("net"), reducer=sum_quantities, units="m ** 2"
    )
    result: Aggregation = reduction.execute(hierarchy)
    return result.value(entity.id)
