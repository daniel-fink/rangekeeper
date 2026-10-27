"""Execution implementation identities; solver evidence remains adapter-owned."""

import platform
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

from rangekeeper.shared.fingerprints import (
    import_closure,
    manifest_digest,
    semantic_digest,
)
from rangekeeper.shared.units import default_units

_RESOURCES = ("schema/schema.json", "schema/slots.json")
# Each role's sources are the import closure of these entry modules.
_ENTRIES = {
    "compiler": ("run/execution/preparation.py", "run/execution/compiler.py"),
    "evaluator": ("run/execution/acceptance.py", "model/expression/evaluation.py"),
}


def sources(role: str, *, package: Path | None = None) -> tuple[str, ...]:
    """Return the package sources that a role's entry modules import."""
    package = Path(__file__).resolve().parents[2] if package is None else package
    return import_closure(
        ("run/execution/implementation.py", *_ENTRIES[role]), package=package
    )


def fingerprint(role: str, *, package: Path | None = None) -> str:
    """Hash a role's imported semantic sources, schema resources and dependencies."""
    package = Path(__file__).resolve().parents[2] if package is None else package
    paths = sources(role, package=package)
    manifest = {
        "format": "execution-implementation/v1",
        "role": role,
        "currencies": default_units.currencies,
        "sources": {
            name: semantic_digest((package / name).read_text()) for name in paths
        },
        "resources": {
            name: sha256((package / name).read_bytes()).hexdigest()
            for name in _RESOURCES
        },
        "versions": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("pint", "py-moneyed", "jsonschema")},
        },
    }
    return "execution-implementation/v1:" + manifest_digest(manifest)
