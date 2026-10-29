"""Five intentional type errors, checked by the schema typing tool."""

from rangekeeper import Model, Specification
from rangekeeper.execution import Tolerances, execute, solve
from rangekeeper.io import MemoryStore


def misuse(model: Model, specification: Specification) -> None:
    execute(specification=specification, store={})
    execute(specification=model, store=MemoryStore())
    output: Model = solve(specification=specification, resolver=MemoryStore()).run
    Tolerances(absolute="small")
    solve(specification)  # the arguments are keyword-only
