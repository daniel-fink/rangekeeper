"""Calculation provenance; sampling streams and presentation are separate evidence."""

from pathlib import Path
from importlib.metadata import version
import hashlib
import platform

from rangekeeper.shared.fingerprints import semantic_digest, manifest_digest
from rangekeeper.schema.records import CalculationProvenance, LibraryVersion
from rangekeeper.shared.units import default_units

NAME = "rangekeeper.scenarios.market"
FORMAT = "scenario-calculation/v1"
# Include calculation, normalization and record construction. random.py samples
# inputs only; view.py presents saved outputs. Neither participates in replay math.
SOURCE_PATHS = (
    "model/scenario/contracts.py",
    "model/scenario/market.py",
    "model/scenario/_paths.py",
    "model/scenario/implementation.py",
    "calculations/projection.py",
    "calculations/dynamics.py",
    "model/model.py",
    "model/update.py",
    "model/validation.py",
    "model/provenance.py",
    "shared/validation.py",
    "model/scope.py",
    "schema/behaviors/flow.py",
    "schema/behaviors/period.py",
    "schema/behaviors/distribution.py",
    "model/duration/calendar.py",
    "schema/records.py",
    "schema/enums.py",
    "schema/validation.py",
    "shared/fingerprints.py",
    "schema/runtime.py",
    "schema/revision.py",
    "schema/index.py",
    "shared/units.py",
)
RESOURCE_PATHS = ("schema/schema.json", "schema/slots.json")


def calculation_manifest(*, package: Path | None = None, versions=None) -> dict:
    """Build the exact portable manifest; every declared input must be present."""
    package = package or Path(__file__).resolve().parents[2]
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
