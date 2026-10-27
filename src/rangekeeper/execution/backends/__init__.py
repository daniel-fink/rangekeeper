"""Optional numerical adapters; importing this package loads no numerical backend."""

from rangekeeper.execution.backends.base import Backend, Result
from rangekeeper.execution.backends.pyomo import PyomoHighs

__all__ = ["Backend", "Result", "PyomoHighs"]
