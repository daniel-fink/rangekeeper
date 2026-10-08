"""Static examples for the public execution boundary; not executed."""

from rangekeeper import Run, Specification
from rangekeeper.run.execution import Executor, Tolerances
from rangekeeper.io import MemoryStore
from rangekeeper.run.execution.backends import Backend, PyomoHighs


def execute(specification: Specification) -> Run:
    backend: Backend = PyomoHighs()
    return Executor(
        MemoryStore(), backend=backend, tolerances=Tolerances(relative=1e-10)
    ).execute(specification)
