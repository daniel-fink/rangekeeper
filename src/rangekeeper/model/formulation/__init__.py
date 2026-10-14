"""Shared Formulation records and passive equation authoring."""

from importlib import import_module
from rangekeeper.schema.records import Formulation, Binding
from .authoring import declare

_MODULES = {"account", "financial", "flow", "growth", "hierarchy"}
__all__ = ["Formulation", "Binding", "declare", *sorted(_MODULES)]


def __getattr__(name: str):
    if name not in _MODULES:
        raise AttributeError(name)
    module = import_module(f".{name}", __name__)
    globals()[name] = module
    return module
