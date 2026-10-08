"""Optional numerical adapters; importing this package loads no numerical backend."""

from rangekeeper.run.execution.backends.base import Backend, Result
from rangekeeper.run.execution.backends.pyomo import PyomoHighs

__all__ = ["Backend", "Result", "PyomoHighs"]
