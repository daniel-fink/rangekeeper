"""Execution implementation identities; solver evidence remains adapter-owned."""

import os
import platform
from collections.abc import Iterable
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

from rangekeeper.quantity import default_units
from rangekeeper.shared.fingerprints import (
    import_closure,
    manifest_digest,
    semantic_digest,
)

# The modification time in nanoseconds and the size in bytes of a file.
_Stamp = tuple[int, int]

_RESOURCES = ("schema/schema.json", "schema/slots.json")
# Each role's sources are the import closure of these entry modules.
_ENTRIES = {
    "compiler": ("execution/preparation.py", "execution/compiler.py"),
    "evaluator": ("execution/acceptance.py", "model/expression/evaluation.py"),
}


# The import closure of each role and package, and the stamps of its files.
_CLOSURES: dict[tuple[str, Path], tuple[tuple[str, ...], tuple[_Stamp, ...]]] = {}


def _stamps(package: Path, paths: Iterable[str]) -> tuple[_Stamp, ...]:
    """Return the modification time and the size of each file."""
    return tuple(
        (status.st_mtime_ns, status.st_size)
        for status in (os.stat(package / path) for path in paths)
    )


def sources(role: str, *, package: Path | None = None) -> tuple[str, ...]:
    """Return the package sources that a role's entry modules import.

    The closure is cached for each process (ADR-013). A change to the size or
    the modification time of one of its files calculates it again.
    """
    package = Path(__file__).resolve().parents[1] if package is None else package
    cached = _CLOSURES.get((role, package))
    if cached is not None and _stamps(package, cached[0]) == cached[1]:
        return cached[0]
    closure = import_closure(
        ("execution/implementation.py", *_ENTRIES[role]), package=package
    )
    _CLOSURES[(role, package)] = (closure, _stamps(package, closure))
    return closure


def fingerprint(role: str, *, package: Path | None = None) -> str:
    """Hash a role's imported semantic sources, schema resources and dependencies.

    It reads each source again, so the fingerprint follows each change to the
    code; only the closure is cached.
    """
    package = Path(__file__).resolve().parents[1] if package is None else package
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
