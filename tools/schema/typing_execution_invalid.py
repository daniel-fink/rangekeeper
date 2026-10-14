"""Four intentional type errors, checked by the schema typing tool."""

from rangekeeper import Model, Specification
from rangekeeper.run.execution import Executor, Tolerances
from rangekeeper.io import MemoryStore


def misuse(model: Model, specification: Specification) -> None:
    Executor({})
    Executor(MemoryStore()).execute(model)
    output: Model = Executor(MemoryStore()).execute(specification)
    Tolerances(absolute="small")
