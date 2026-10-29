"""Convert a Bundle of an earlier release to a new Bundle of the current formats.

The current Reader opens only a Bundle whose schema pin is the current slot
map. This module reads the Parquet tables with the slot map of the release that
wrote the Bundle (`RELEASES`), converts each document with `convert`, and
writes a new Bundle with `rangekeeper.io.bundle.write`. The old Bundle does not
change.
"""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

import pyarrow.parquet as pq

from rangekeeper import Model, Run, Specification
from rangekeeper.io import MemoryStore
from rangekeeper.io import bundle as current
from rangekeeper.shared import pointer

from .convert import RELEASES, ConversionError, Release, convert

# The Bundle identifiers that 1.0.0a1 and 1.0.0a2 write.
FORMAT = "rangekeeper.bundle/2-proposal"
MAPPING = "rangekeeper.parquet/1-proposal"
KINDS = {"Model": Model, "Specification": Specification, "Run": Run}


def _check(root: Path, manifest: dict[str, Any], *, release: str) -> None:
    """Require the Bundle identifiers, the schema pin and the file hashes."""
    if (manifest.get("format"), manifest.get("mapping")) != (FORMAT, MAPPING):
        raise ConversionError(f"not a Bundle that {release} wrote")
    if manifest.get("schema_digest") != RELEASES[release].digest:
        raise ConversionError(f"the Bundle schema pin is not the {release} slot map")
    for entry in manifest["files"]:
        path = root / entry["path"]
        if sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ConversionError(f"Bundle file changed: {entry['path']}")


def _cell(meta, cell, path, name, locator, visit):
    """Decode one typed union cell of a legacy table."""
    option = meta["options"][cell["tag"]]
    value = cell[f"v{cell['tag']}"]
    category, kind = option["category"], option["kind"]
    if category in ("record", "keyed"):
        expected = pointer.child(path, name, *(() if locator is None else (locator,)))
        if value != expected:
            raise ConversionError("embedded record path does not match its owner")
        return visit(value, kind)
    if category == "opaque":
        return json.loads(value)
    if category == "primitive" and kind in ("decimal", "double", "integer"):
        return (
            int(value["integer"]) if value["integer"] is not None else value["number"]
        )
    return value


def _document(
    root: Path,
    tables: list[dict[str, Any]],
    *,
    kind: str,
    release: Release,
) -> dict[str, Any]:
    """Reconstruct the data of one document from its tables."""
    rows = {}
    for table in tables:
        for row in pq.read_table(root / table["path"]).to_pylist():
            rows[row["_path"]] = table["kind"], row
    visited = set()

    def visit(path, expected):
        found, row = rows[path]
        if found != expected or path in visited:
            raise ConversionError("embedded record kind or owner mismatch")
        visited.add(path)
        data = {}
        for name, meta in release.slots[found].items():
            state, physical = row[name + "__state"], row[name]
            if state == 1:
                data[name] = None
            elif state == 2:

                def item(cell, locator=None, meta=meta, name=name):
                    return _cell(meta, cell, path, name, locator, visit)

                if meta["mapping"]:
                    data[name] = {
                        e["key"]: item(e["value"], e["key"]) for e in physical
                    }
                elif meta["many"]:
                    data[name] = [item(v, i) for i, v in enumerate(physical)]
                else:
                    data[name] = item(physical)
        return data

    data = visit("", kind)
    if visited != set(rows):
        raise ConversionError("orphan embedded records")
    return data


def read(root: Path, *, release: str) -> list[tuple[str, dict[str, Any]]]:
    """Return the kind and data of each document, the main Model first."""
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if release not in RELEASES:
        raise ConversionError(f"unknown release {release!r}")
    _check(root, manifest, release=release)
    tables = [("Model", manifest["tables"])] + [
        (descriptor["kind"], descriptor["tables"])
        for descriptor in manifest["documents"]
    ]
    return [
        (kind, _document(root, found, kind=kind, release=RELEASES[release]))
        for kind, found in tables
    ]


def upgrade(source: Path, destination: Path, *, release: str) -> dict[str, Any]:
    """Write a current Bundle at ``destination`` from the Bundle at ``source``.

    ``release`` names the release that wrote ``source``, a key of `RELEASES`.
    The documents keep their UUIDs. Native Geometry files are copied from the
    old Bundle. ``destination`` must not exist. Return the new manifest.
    """
    source = Path(source)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    store = MemoryStore()
    documents = [
        KINDS[kind].from_data(convert(data, kind, release=release))
        for kind, data in read(source, release=release)
    ]
    # A store checks references, so a Run follows its Specification and Models.
    order = (Model, Specification, Run)
    for document in sorted(documents, key=lambda d: order.index(type(d))):
        store.put(document)
    model, others = documents[0], documents[1:]
    geometries = {
        UUID(identity): source / path
        for identity, path in manifest.get("geometry_paths", {}).items()
    }
    roots = {(r["kind"], r["id"]) for r in manifest.get("roots", [])}
    selected = [d for d in others if (type(d).__name__, str(d.id)) in roots]
    return current.write(
        destination,
        model,
        documents=selected,
        resolver=store,
        geometries=geometries,
    )


__all__ = ["read", "upgrade"]
