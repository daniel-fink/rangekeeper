"""Calculation provenance; sampling streams and presentation are separate evidence."""

from pathlib import Path
from importlib.metadata import version
import hashlib
import platform

from .._implementation import semantic_digest, manifest_digest
from .._schema.records import CalculationProvenance, LibraryVersion
from ..units import default_units

NAME = "rangekeeper.scenarios.market"
FORMAT = "scenario-calculation/v1"
# Include calculation, normalization and record construction. random.py samples
# inputs only; view.py presents saved outputs. Neither participates in replay math.
SOURCE_PATHS = (
    "scenarios/contracts.py",
    "scenarios/market.py",
    "scenarios/_paths.py",
    "scenarios/implementation.py",
    "calculations/projection.py",
    "calculations/dynamics/trend.py",
    "calculations/dynamics/volatility.py",
    "calculations/dynamics/cyclicality.py",
    "calculations/dynamics/shock.py",
    "model/_scenario.py",
    "model/model.py",
    "model/update.py",
    "model/scope.py",
    "_behaviors/flow.py",
    "_behaviors/period.py",
    "_behaviors/distribution.py",
    "duration/calendar.py",
    "_schema/records.py",
    "_schema/enums.py",
    "_schema/validation.py",
    "_implementation.py",
    "_records.py",
    "_revision.py",
    "_record_index.py",
    "units.py",
)
RESOURCE_PATHS = ("_schema/schema.json", "_schema/slots.json")


def calculation_manifest(*, package: Path | None = None, versions=None) -> dict:
    """Build the exact portable manifest; every declared input must be present."""
    package = package or Path(__file__).resolve().parents[1]
    if versions is None:
        versions = [
            {"name": "python", "version": platform.python_version()},
            *(
                {"name": name, "version": version(name)}
                for name in ("pint", "jsonschema", "py-moneyed")
            ),
        ]
    versions = sorted(versions, key=lambda item: item["name"])
    if len({item["name"] for item in versions}) != len(versions):
        raise ValueError("calculation dependency names must be unique")
    return {
        "format": FORMAT,
        "name": NAME,
        "sources": {
            name: semantic_digest((package / name).read_text())
            for name in sorted(SOURCE_PATHS)
        },
        "resources": {
            name: hashlib.sha256((package / name).read_bytes()).hexdigest()
            for name in sorted(RESOURCE_PATHS)
        },
        "versions": versions,
        "currencies": list(default_units.currencies),
    }


def calculation_provenance() -> CalculationProvenance:
    manifest = calculation_manifest()
    return CalculationProvenance(
        name=NAME,
        fingerprint=FORMAT + ":" + manifest_digest(manifest),
        versions=tuple(LibraryVersion(**item) for item in manifest["versions"]),
    )
