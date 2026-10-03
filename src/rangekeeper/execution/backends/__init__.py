"""Optional numerical adapters; importing this package loads no numerical backend."""

from .base import Backend, Result
from .pyomo import PyomoHighs

__all__ = ["Backend", "Result", "PyomoHighs"]
