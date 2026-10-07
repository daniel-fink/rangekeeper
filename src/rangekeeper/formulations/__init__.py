"""Passive equation declarations with one shared authoring boundary."""

from .authoring import declare
from . import account, expression, financial, flow, growth

__all__ = ["declare", "account", "expression", "financial", "flow", "growth"]
