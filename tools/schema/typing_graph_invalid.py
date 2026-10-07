"""These calls must be statically rejected."""

from rangekeeper import Model
from rangekeeper.graph import View, Reduction
from rangekeeper.graph.selection import select_value
from rangekeeper.graph import reducers


def reject(model: Model) -> None:
    View({})
    View(model).entity("code")
    select_value("net", measure="area")
    Reduction(select=select_value("net"), reducer=reducers.sum, units=3)
    View(model).aggregate(model)
