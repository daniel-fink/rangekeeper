"""Shared Formulation records and passive equation authoring."""

from rangekeeper.schema.records import Binding, Formulation
from rangekeeper.shared.exports import lazy as _lazy

from .authoring import declare

_MODULES = {"account", "financial", "flow", "growth", "hierarchy"}
__all__ = ["Formulation", "Binding", "declare", *sorted(_MODULES)]


__getattr__, __dir__ = _lazy(__name__, modules=_MODULES)
