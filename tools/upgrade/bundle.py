"""Convert a Bundle of 0.x documents to a new 1.0.0 Bundle.

The 1.0 Reader does not open a Bundle with 0.x documents. This module reads
the Parquet tables with the 1.0.0a1 slot map, converts each document with
`convert`, and writes a new Bundle with `rangekeeper.io.bundle.write`. The old
Bundle does not change.
"""

import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pyarrow.parquet as pq

from rangekeeper import Model, Run, Specification
from rangekeeper.io import MemoryStore
from rangekeeper.io import bundle as current
from rangekeeper.shared import pointer

from .convert import LEGACY, ConversionError, convert

FORMAT = "rangekeeper.bundle/2-proposal"
MAPPING = "rangekeeper.parquet/1-proposal"
LEGACY_DIGEST = sha256(
    Path(__file__).with_name("legacy_slots.json").read_bytes()
).hexdigest()
KINDS = {"Model": Model, "Specification": Specification, "Run": Run}


def _check(root: Path, manifest: dict) -> None:
    """Require the 0.x Bundle identifiers and the recorded file hashes."""
    if (manifest.get("format"), manifest.get("mapping")) != (FORMAT, MAPPING):
        raise ConversionError("not a Bundle that 1.0.0a1 or earlier wrote")
    if manifest.get("schema_digest") != LEGACY_DIGEST:
        raise ConversionError("the Bundle schema pin is not the 1.0.0a1 slot map")
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


def _document(root: Path, tables: list[dict], kind: str) -> dict:
    """Reconstruct the data of one legacy document from its tables."""
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
        for name, meta in LEGACY[found].items():
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


def read(root: Path) -> list[tuple[str, dict]]:
    """Return the kind and 0.x data of each document, the main Model first."""
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    _check(root, manifest)
    result = [("Model", _document(root, manifest["tables"], "Model"))]
    for descriptor in manifest["documents"]:
        kind = descriptor["kind"]
        result.append((kind, _document(root, descriptor["tables"], kind)))
    return result


def upgrade(source: Path, destination: Path) -> dict:
    """Write a 1.0.0 Bundle at ``destination`` from the 0.x Bundle at ``source``.

    The documents keep their UUIDs. Native Geometry files are copied from the
    old Bundle. ``destination`` must not exist. Return the new manifest.
    """
    source = Path(source)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    store = MemoryStore()
    documents = [
        KINDS[kind].from_data(convert(data, kind)) for kind, data in read(source)
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
