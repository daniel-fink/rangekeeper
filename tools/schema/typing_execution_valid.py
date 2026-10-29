"""Static examples for the public execution boundary; not executed."""

from rangekeeper import Run, Specification
from rangekeeper.execution import ExecutionConfig, Executor, Limits, Tolerances
from rangekeeper.execution.backends import Backend, PyomoHighs
from rangekeeper.io import MemoryStore


def execute(specification: Specification) -> Run:
    backend: Backend = PyomoHighs()
    config = ExecutionConfig(
        backend=backend,
        limits=Limits(time_limit=10),
        tolerances=Tolerances(relative=1e-10),
        backend_options={"presolve": "off"},
    )
    return Executor(MemoryStore(), config=config).execute(specification)
