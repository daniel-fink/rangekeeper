"""Immutable Model, Specification and Run roots with explicit capability packages."""

from importlib import import_module
from importlib import metadata as _metadata
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
    }
)
__all__ = ["Model", "Specification", "Run", "__version__", *sorted(_LAZY_MODULES)]

try:
    __version__ = _metadata.version("rangekeeper")
except _metadata.PackageNotFoundError:  # A source tree that is not installed.
    __version__ = "0+unknown"


def __getattr__(name: str) -> ModuleType:
    if name not in _LAZY_MODULES:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), *_LAZY_MODULES})
