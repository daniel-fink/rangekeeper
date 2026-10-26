"""Three deliberate static rejections across the consumer boundary."""

from rangekeeper import Model, Specification
from rangekeeper.model.system.projection import ValueColumn, to_table


def invalid(model: Model, specification: Specification) -> None:
    to_table(model)
    ValueColumn("Area", "net", 42)
    model.entity("not-a-uuid")
