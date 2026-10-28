"""Four intentional type errors, checked by the schema typing tool."""

from rangekeeper import Model, Specification
from rangekeeper.execution import Tolerances, execute, solve
from rangekeeper.io import MemoryStore


def misuse(model: Model, specification: Specification) -> None:
    execute(specification, {})
    execute(model, MemoryStore())
    output: Model = solve(specification, MemoryStore()).run
    Tolerances(absolute="small")
