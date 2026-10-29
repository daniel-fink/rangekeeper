"""Geometry providers: adapters that check native Geometry files for a Bundle.

``geometry_providers`` holds providers by the provider name of a Geometry pin
(ADR-013). An installed distribution can add one in the entry point group
``rangekeeper.geometry_providers``. Rangekeeper registers no provider.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from rangekeeper.schema.records import Geometry
from rangekeeper.shared.registry import Registry

__all__ = ["GeometryProvider", "geometry_providers"]


@runtime_checkable
class GeometryProvider(Protocol):
    """Check that native files resolve the selectors of one Geometry."""

    def validate(self, path: Path, geometry: Geometry) -> None:
        """Raise an error when the files at ``path`` do not match ``geometry``."""
        ...


geometry_providers: Registry[GeometryProvider] = Registry(
    "geometry_providers", GeometryProvider
)


def find(provider: str) -> GeometryProvider | None:
    """Return the registered provider for a pin's provider name, or None."""
    return geometry_providers.get(provider) if provider in geometry_providers else None
