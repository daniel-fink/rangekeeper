"""Static examples for the public execution boundary; not executed."""

from rangekeeper import Run, Specification
from rangekeeper.execution import (
    ExecutionConfig,
    Limits,
    Outcome,
    Tolerances,
    execute,
    solve,
)
from rangekeeper.execution.backends import Backend, PyomoHighs
from rangekeeper.io import MemoryStore


def investigate(specification: Specification) -> Run:
    backend: Backend = PyomoHighs()
    config = ExecutionConfig(
        backend=backend,
        limits=Limits(time_limit=10),
        tolerances=Tolerances(relative=1e-10),
        backend_options={"presolve": "off"},
    )
    return execute(specification=specification, store=MemoryStore(), config=config).run


def answer(specification: Specification, store: MemoryStore) -> Outcome:
    outcome = solve(specification=specification, resolver=store)
    run: Run = outcome.run
    assert run.id == outcome.run.id
    return solve(specification=specification)
