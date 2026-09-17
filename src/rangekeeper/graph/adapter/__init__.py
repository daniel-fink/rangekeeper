"""Tabular and visualization adapters for the immutable graph core."""

from importlib import import_module
from types import ModuleType

from .errors import (
    AdapterEncodingError,
    AdapterError,
)

__all__ = [
    "AdapterEncodingError",
    "AdapterError",
    "csv",
    "cytoscape",
    "ingestion",
    "pandas",
    "visualization",
]

_SUBMODULES = frozenset({"cytoscape", "csv", "ingestion", "pandas", "visualization"})


def __getattr__(name: str) -> ModuleType:
    if name not in _SUBMODULES:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), *_SUBMODULES})
