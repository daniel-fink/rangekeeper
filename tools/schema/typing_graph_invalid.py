"""These calls must be statically rejected."""

from rangekeeper import Model
from rangekeeper.model.system import View, Reduction
from rangekeeper.model.system.selection import select_value
from rangekeeper.model.system import reducers


def reject(model: Model) -> None:
    View({})
    View(model).entity("code")
    select_value("net", measure="area")
    Reduction(select=select_value("net"), reducer=reducers.sum, units=3)
    View(model).aggregate(model)
