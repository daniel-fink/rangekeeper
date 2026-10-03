"""Three deliberate static rejections across the consumer boundary."""

from pathlib import Path
from rangekeeper import Model, Specification
from rangekeeper.graph.projection import ValueColumn, to_table
from rangekeeper.workflow.runtime import run


def invalid(model: Model, specification: Specification) -> None:
    to_table(model)
    ValueColumn("Area", "net", 42)
    run(specification, input_root=Path("."))
