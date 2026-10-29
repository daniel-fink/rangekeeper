"""These calls must be statically rejected."""

from rangekeeper import Model
from rangekeeper.model.system import QuantityRollup, View
from rangekeeper.model.system.selection import select_value


def reject(model: Model) -> None:
    View({})
    View(model).entity("code")
    select_value("net", measure="area")
    QuantityRollup(key="net", units=3)
    View(model).rollup(definition=model)
