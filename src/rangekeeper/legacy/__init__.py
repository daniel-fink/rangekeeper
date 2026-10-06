"""Temporary predecessor APIs held for Windows connector acceptance.

Import these modules explicitly. Canonical code must never import this package.
Relocation preserves predecessor behaviour; it does not accept the Windows gate.
"""

from importlib import import_module
from types import ModuleType

__all__ = ["graph", "measure", "api"]


def __getattr__(name: str) -> ModuleType:
    if name not in __all__:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
