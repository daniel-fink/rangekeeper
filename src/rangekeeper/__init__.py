"""Immutable Model, Specification and Run roots with explicit capability packages."""

from importlib import import_module
from types import ModuleType

from .model import Model
from .run import Run
from .specification import Specification

_LAZY_MODULES = frozenset(
    {
        "schema",
        "shared",
        "model",
        "specification",
        "run",
        "calculations",
        "io",
        "visualisation",
    }
)
__all__ = ["Model", "Specification", "Run", *sorted(_LAZY_MODULES)]


def __getattr__(name: str) -> ModuleType:
    if name not in _LAZY_MODULES:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), *_LAZY_MODULES})
