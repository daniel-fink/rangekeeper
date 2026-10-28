"""Passive equation authoring; `rangekeeper.model` exports Formulation and Binding."""

from rangekeeper.shared.exports import lazy as _lazy

from .authoring import declare

_MODULES = {"financial", "flow", "growth", "hierarchy"}
__all__ = ["declare", *sorted(_MODULES)]


__getattr__, __dir__ = _lazy(__name__, modules=_MODULES)
