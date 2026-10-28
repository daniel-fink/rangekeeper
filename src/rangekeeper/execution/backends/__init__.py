"""Optional numerical adapters; importing this package loads no numerical backend.

``registry`` holds the execution backends by name (ADR-013). The built-in
``pyomo-highs`` backend solves with Pyomo and HiGHS in a worker process. An
installed distribution can add a backend in the entry point group
``rangekeeper.backends``.
"""

from rangekeeper.execution.backends.base import Backend, Result
from rangekeeper.execution.backends.pyomo import PyomoHighs
from rangekeeper.shared.registry import Registry

registry: Registry[Backend] = Registry("backends", Backend)
# The worker runs as a module in a child process, so no import reaches it.
registry.register(
    "pyomo-highs",
    PyomoHighs(),
    modules=("rangekeeper.execution.backends._worker",),
)

__all__ = ["Backend", "Result", "PyomoHighs", "registry"]
