"""Optional numerical adapters; importing this package loads no numerical backend.

``registry`` holds the execution backends by name (ADR-013). The built-in
``pyomo-highs`` backend solves with Pyomo and HiGHS in a worker process. An
installed distribution can add a backend in the entry point group
``rangekeeper.backends``.
"""

from rangekeeper.execution.backends.base import Backend, BackendResult, Termination
from rangekeeper.execution.backends.pyomo import PyomoHighs
from rangekeeper.execution.backends.registry import registry

__all__ = ["Backend", "BackendResult", "PyomoHighs", "Termination", "registry"]
