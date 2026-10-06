"""Canonical domain records and explicit, lazy capability packages.

Temporary predecessors are isolated in rangekeeper.legacy while the Windows
connector gate is open. Numerical work uses calculations and formulations.
"""

from importlib import import_module
from types import ModuleType

from . import validate as validate
from .model import Model as Model
from .specification import Specification as Specification
from .run import Run as Run

_LAZY_MODULES = frozenset(
    {
        "execution",
        "calculations",
        "formulations",
        "scenarios",
        "policies",
        "migration",
        "legacy",
        "adapters",
        "workflow",
        "table",
        "evidence",
        "operation",
        "io",
        "units",
        "graph",
        "duration",
    }
)

__all__ = [
    "Model",
    "Specification",
    "Run",
    "model",
    "specification",
    "run",
    "io",
    "units",
    "execution",
    "calculations",
    "formulations",
    "scenarios",
    "policies",
    "migration",
    "legacy",
    "adapters",
    "workflow",
    "table",
    "evidence",
    "operation",
    "duration",
    "graph",
    "validate",
]


def __getattr__(name: str) -> ModuleType:
    if name not in _LAZY_MODULES:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), *_LAZY_MODULES})
