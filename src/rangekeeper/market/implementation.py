"""Calculation provenance; sampling streams and presentation are separate evidence."""

import hashlib
import platform
from importlib.metadata import version
from pathlib import Path

from rangekeeper.quantity import default_units
from rangekeeper.schema.records import CalculationProvenance, LibraryVersion
from rangekeeper.shared.fingerprints import (
    import_closure,
    manifest_digest,
    semantic_digest,
)

NAME = "rangekeeper.market.generation"
FORMAT = "scenario-calculation/v1"
# The sources are the import closure of these entry modules: calculation,
# normalization and record construction, with every module that they import.
ENTRY_PATHS = ("market/implementation.py", "market/generation.py")
RESOURCE_PATHS = ("schema/schema.json", "schema/slots.json")


def source_paths(*, package: Path | None = None) -> tuple[str, ...]:
    """Return the package sources that the scenario calculation imports."""
    package = package or Path(__file__).resolve().parents[1]
    return import_closure(ENTRY_PATHS, package=package)


def calculation_manifest(*, package: Path | None = None, versions=None) -> dict:
    """Build the exact portable manifest; every imported source must be present."""
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
            for name in source_paths(package=package)
        },
        "resources": {
            name: hashlib.sha256((package / name).read_bytes()).hexdigest()
            for name in sorted(RESOURCE_PATHS)
        },
        "versions": versions,
        "currencies": list(default_units.currencies),
    }


def calculation_provenance() -> CalculationProvenance:
    """Return the calculation name, manifest fingerprint and library versions."""
    manifest = calculation_manifest()
    return CalculationProvenance(
        name=NAME,
        fingerprint=FORMAT + ":" + manifest_digest(manifest),
        versions=tuple(LibraryVersion(**item) for item in manifest["versions"]),
    )
