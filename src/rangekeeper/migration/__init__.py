"""Explicit offline migration. Codecs never upgrade documents automatically."""

from .scenarios import upgrade_scenario_names
from .graph import ConversionResult, convert_graph
from .drafts import upgrade_model, upgrade_specification

__all__ = [
    "ConversionResult",
    "convert_graph",
    "upgrade_model",
    "upgrade_scenario_names",
    "upgrade_specification",
]
