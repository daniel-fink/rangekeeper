"""Explicit offline migration. Codecs never upgrade documents automatically."""

from rangekeeper.migration.scenarios import upgrade_scenario_names
from rangekeeper.migration.graph import ConversionResult, convert_graph
from rangekeeper.migration.drafts import upgrade_model, upgrade_specification

__all__ = [
    "ConversionResult",
    "convert_graph",
    "upgrade_model",
    "upgrade_scenario_names",
    "upgrade_specification",
]
