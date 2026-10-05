"""Explicit offline migration. Ordinary document loading never invokes these tools."""

from .graph import ConversionResult, convert_graph, upgrade_model

__all__ = ["ConversionResult", "convert_graph", "upgrade_model"]
