"""Three deliberate static rejections across the consumer boundary."""

from rangekeeper import Model, Specification
from rangekeeper.model.system.table import ValueColumn, to_table


def invalid(model: Model, specification: Specification) -> None:
    to_table(model)
    ValueColumn(name="Area", key="net", units=42)
    model.entity("not-a-uuid")
