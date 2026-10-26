"""These calls must be statically rejected."""

from rangekeeper import Model
from rangekeeper.model.system import Reduction, View, reducers
from rangekeeper.model.system.selection import select_value


def reject(model: Model) -> None:
    View({})
    View(model).entity("code")
    select_value("net", measure="area")
    Reduction(select=select_value("net"), reducer=reducers.sum, units=3)
    View(model).aggregate(model)
