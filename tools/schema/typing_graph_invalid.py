"""These calls must be statically rejected."""

from rangekeeper import Model
from rangekeeper.model.system import QuantityRollup, View
from rangekeeper.model.system.selection import select_value


def reject(model: Model) -> None:
    View(model={})
    View(model=model).entity("code")
    select_value(key="net", measure="area")
    QuantityRollup(key="net", units=3)
    View(model=model).rollup(definition=model)
