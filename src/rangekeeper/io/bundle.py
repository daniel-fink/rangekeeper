"""Review candidate: schema-derived Model Parquet and an exact native Geometry pin.

The manifest is the publication marker. No JSON Model is retained or consulted.
Import this optional IO module explicitly; domain imports need no Arrow or DuckDB.
"""

from collections import defaultdict
from hashlib import sha256
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import shutil

import pyarrow as pa
import pyarrow.parquet as pq

from rangekeeper import Model
from rangekeeper.io.atomic import write_new
from rangekeeper.model.geometry import safe_path
from rangekeeper.schema.runtime import comparison_data
from rangekeeper.schema.validation import slots_for

FORMAT = "rangekeeper.bundle/1-proposal"
MAPPING = "rangekeeper.parquet/1-proposal"
SCHEMA_BYTES = files("rangekeeper.schema").joinpath("slots.json").read_bytes()
SLOTS = json.loads(SCHEMA_BYTES)
SCHEMA_DIGEST = sha256(SCHEMA_BYTES).hexdigest()


def encoded(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def digest(value):
    return sha256(encoded(value).encode()).hexdigest()


def model_digest(model):
    return digest(comparison_data("Model", model.to_data()))


def identity(model):
    return digest(dict(format=FORMAT, mapping=MAPPING, model=model_digest(model)))


def _pointer(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def _option_type(option):
    category, kind = option["category"], option["kind"]
    if category == "primitive" and kind in ("decimal", "double", "integer"):
        # Decimal/integer strings preserve arbitrary precision; floats remain doubles.
        return pa.struct([("integer", pa.string()), ("number", pa.float64())])
    if category == "primitive" and kind == "boolean":
        return pa.bool_()
    if category in {"record", "keyed", "uuid", "enum", "opaque", "primitive"}:
        return pa.string()
    raise ValueError(f"Unsupported schema option: {option}")


def _value_type(meta):
    return pa.struct(
        [pa.field("tag", pa.int16(), nullable=False)]
        + [
            pa.field(f"v{i}", _option_type(option))
            for i, option in enumerate(meta["options"])
        ]
    )


def table_schema(kind):
    fields = [pa.field("_path", pa.string(), nullable=False)]
    for name, meta in slots_for(kind).items():
        fields.append(pa.field(name + "__state", pa.uint8(), nullable=False))
        value = _value_type(meta)
        if meta["mapping"]:
            value = pa.list_(
                pa.field(
                    "element",
                    pa.struct(
                        [
                            pa.field("key", pa.string(), nullable=False),
                            pa.field("value", value, nullable=False),
                        ]
                    ),
                )
            )
        elif meta["many"]:
            value = pa.list_(pa.field("element", value))
        fields.append(pa.field(name, value))
    return pa.schema(
        fields,
        metadata={
            b"rk.mapping": MAPPING.encode(),
            b"rk.kind": kind.encode(),
            b"rk.schema": SCHEMA_DIGEST.encode(),
        },
    )


def _select(meta, value):
    for position, option in enumerate(meta["options"]):
        category, kind = option["category"], option["kind"]
        if category in ("record", "keyed") and isinstance(value, dict):
            return position
        if category == "opaque":
            return position
        if category in ("uuid", "enum") and isinstance(value, str):
            return position
        if category == "primitive":
            if kind == "boolean" and type(value) is bool:
                return position
            if kind in ("decimal", "double", "integer") and type(value) in (int, float):
                return position
            if (
                kind not in ("boolean", "decimal", "double", "integer")
                and type(value) is str
            ):
                return position
    raise ValueError("Value does not match a generated slot option")


def _shred(model):
    tables, records, references = defaultdict(list), [], []

    def visit(kind, data, path="", owner=None):
        fields = slots_for(kind)
        record_id = data.get("id") if "id" in fields else None
        records.append(
            dict(path=path, kind=kind, canonical_id=record_id, owner_id=owner)
        )
        row = {"_path": path}
        for name, meta in fields.items():
            state = 0 if name not in data else 1 if data[name] is None else 2
            row[name + "__state"] = state
            if state != 2:
                row[name] = None
                continue

            def item(value, locator=None):
                tag = _select(meta, value)
                option = meta["options"][tag]
                category, target = option["category"], option["kind"]
                if category in ("record", "keyed"):
                    child = (
                        path
                        + "/"
                        + _pointer(name)
                        + ("/" + _pointer(locator) if locator is not None else "")
                    )
                    visit(target, value, child, record_id or owner)
                    physical = child
                elif category == "opaque":
                    # Only the schema's explicitly opaque Content slot uses inert JSON.
                    physical = encoded(value)
                elif category == "primitive" and target in (
                    "decimal",
                    "double",
                    "integer",
                ):
                    physical = (
                        dict(integer=str(value), number=None)
                        if type(value) is int
                        else dict(integer=None, number=value)
                    )
                else:
                    physical = value
                if (
                    category == "uuid"
                    and target != "UUID"
                    and (kind, name) != ("Metadata", "previous")
                ):
                    references.append(
                        dict(
                            path=path,
                            slot=name,
                            target=value,
                            locator=str(locator) if locator is not None else "",
                        )
                    )
                return {
                    "tag": tag,
                    **{
                        f"v{i}": physical if i == tag else None
                        for i in range(len(meta["options"]))
                    },
                }

            value = data[name]
            if meta["mapping"]:
                row[name] = [dict(key=k, value=item(v, k)) for k, v in value.items()]
            elif meta["many"]:
                row[name] = [item(v, i) for i, v in enumerate(value)]
            else:
                row[name] = item(value)
        tables[kind].append(row)

    visit("Model", model.to_data())
    return tables, records, references


RECORD_SCHEMA = pa.schema(
    [(k, pa.string()) for k in ("path", "kind", "canonical_id", "owner_id")]
)
REF_SCHEMA = pa.schema(
    [(k, pa.string()) for k in ("path", "slot", "target", "locator")]
)


def inventory(root, paths):
    result = []
    for name in sorted(paths):
        if not safe_path(name):
            raise ValueError("Unsafe Bundle file path")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Bundle files must be local regular files")
        checksum = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                checksum.update(chunk)
        result.append(
            dict(path=name, size=path.stat().st_size, sha256=checksum.hexdigest())
        )
    return result


def write(
    root,
    model,
    *,
    geometry=None,
    provider=None,
    compression="zstd",
    row_group_size=8192,
):
    """Write a new directory. Publish its manifest only after complete validation.

    On failure an unpublished directory can remain for diagnosis. Existing paths
    are never replaced. Core separately owns catalogue registration and acceptance.
    """
    model = Model.from_data(model.to_data())
    root = Path(root)
    if model.geometry is not None:
        if geometry is None or provider is None:
            raise ValueError(
                "Geometry needs its exact native files and explicit provider"
            )
        provider.validate(Path(geometry), model.geometry)
    elif geometry is not None:
        raise ValueError("Model-only Bundle cannot acquire undeclared Geometry")
    tables, records, references = _shred(model)
    root.mkdir(parents=True, exist_ok=False)
    (root / "model").mkdir()
    declarations = []
    for kind, rows in sorted(tables.items()):
        name = f"model/{kind}.parquet"
        pq.write_table(
            pa.Table.from_pylist(rows, schema=table_schema(kind)),
            root / name,
            compression=compression,
            row_group_size=row_group_size,
        )
        declarations.append(dict(kind=kind, path=name, rows=len(rows)))
    for name, rows, schema in (
        ("records", records, RECORD_SCHEMA),
        ("references", references, REF_SCHEMA),
    ):
        pq.write_table(
            pa.Table.from_pylist(rows, schema=schema),
            root / f"model/{name}.parquet",
            compression=compression,
            row_group_size=row_group_size,
        )
    if model.geometry is not None:
        for entry in model.geometry.pin.files:
            source = Path(geometry) / entry.path
            destination = root / "geometry" / entry.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        provider.validate(root / "geometry", model.geometry)
    payloads = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    for name in payloads:
        with (root / name).open("rb") as stream:
            os.fsync(stream.fileno())
    manifest = dict(
        format=FORMAT,
        id=identity(model),
        mapping=MAPPING,
        schema_digest=SCHEMA_DIGEST,
        model=dict(
            id=str(model.id),
            schema_version=model.metadata.schema_version,
            digest=model_digest(model),
        ),
        tables=declarations,
        files=inventory(root, payloads),
        geometry=model.geometry.pin.to_data() if model.geometry else None,
    )
    restored = Reader(root, provider=provider, _manifest=manifest).model()
    if restored.to_data() != model.to_data():
        raise ValueError("Bundle reconstruction differs from the supplied Model")
    write_new(root / "manifest.json", encoded(manifest) + "\n")
    return manifest


class Reader:
    """Strict reference reader and bounded DuckDB projections for the proof profile.

    Opening verifies every Model file. Native Geometry verification is explicit;
    ordinary record queries do not read its blobs. Call verify_geometry before
    registering or accepting data from an untrusted delivery.
    """

    def __init__(
        self,
        root,
        *,
        provider=None,
        max_bytes=4 * 1024**3,
        max_rows=1_000_000,
        _manifest=None,
    ):
        self.root = Path(root).resolve(strict=True)
        marker = self.root / "manifest.json"
        if _manifest is None:
            if marker.is_symlink() or marker.stat().st_size > 4 * 1024**2:
                raise ValueError("Invalid or oversized Bundle manifest")
            self.manifest = json.loads(marker.read_text())
        else:
            self.manifest = _manifest
        m = self.manifest
        if set(m) != {
            "format",
            "id",
            "mapping",
            "schema_digest",
            "model",
            "tables",
            "files",
            "geometry",
        } or (m["format"], m["mapping"], m["schema_digest"]) != (
            FORMAT,
            MAPPING,
            SCHEMA_DIGEST,
        ):
            raise ValueError("Unsupported Bundle format, mapping or schema pin")
        entries = m["files"]
        if (
            len(entries) > 10000
            or any(type(e.get("size")) is not int or e["size"] < 0 for e in entries)
            or sum(e["size"] for e in entries) > max_bytes
        ):
            raise ValueError("Bundle size limit exceeded")
        names = [e["path"] for e in entries]
        if len(set(names)) != len(names) or any(not safe_path(n) for n in names):
            raise ValueError("Invalid or duplicate inventory paths")
        if any(p.is_symlink() for p in self.root.rglob("*")):
            raise ValueError("Symlinks are not Bundle content")
        actual = {
            p.relative_to(self.root).as_posix()
            for p in self.root.rglob("*")
            if p.is_file()
        }
        if actual != set(names) | ({"manifest.json"} if _manifest is None else set()):
            raise ValueError("Bundle file closure differs from its manifest")
        for entry in entries:
            path = self.root / entry["path"]
            if not path.is_file() or path.stat().st_size != entry["size"]:
                raise ValueError("Bundle file missing or changed size")
        model_entries = [e for e in entries if e["path"].startswith("model/")]
        if inventory(self.root, [e["path"] for e in model_entries]) != sorted(
            model_entries, key=lambda e: e["path"]
        ):
            raise ValueError("Model file integrity mismatch")
        if sum(e["size"] for e in model_entries) > 256 * 1024**2:
            raise ValueError("Model compressed size limit exceeded")
        expanded = 0
        for entry in model_entries:
            physical = pq.ParquetFile(self.root / entry["path"])
            expanded += sum(
                physical.metadata.row_group(i).total_byte_size
                for i in range(physical.metadata.num_row_groups)
            )
            if physical.metadata.num_rows > max_rows or expanded > 512 * 1024**2:
                raise ValueError("Model expanded work limit exceeded")
        self.tables = {}
        for table in m["tables"]:
            kind = table["kind"]
            if (
                kind not in SLOTS
                or kind in self.tables
                or table["path"] != f"model/{kind}.parquet"
                or table["path"] not in names
            ):
                raise ValueError("Invalid or duplicate Model table")
            path = self.root / table["path"]
            physical = pq.ParquetFile(path)
            if (
                not physical.schema_arrow.equals(
                    table_schema(kind), check_metadata=True
                )
                or physical.metadata.num_rows != table["rows"]
            ):
                raise ValueError("Table schema or row count mismatch")
            self.tables[kind] = path
        if sum(t["rows"] for t in m["tables"]) > max_rows:
            raise ValueError("Model row limit exceeded")
        expected = {t["path"] for t in m["tables"]} | {
            "model/records.parquet",
            "model/references.parquet",
        }
        if {e["path"] for e in model_entries} != expected:
            raise ValueError("Unexpected Model files")
        self.provider = provider
        self._model = self._reconstruct()
        if (
            dict(
                id=str(self._model.id),
                schema_version=self._model.metadata.schema_version,
                digest=model_digest(self._model),
            )
            != m["model"]
            or identity(self._model) != m["id"]
        ):
            raise ValueError("Canonical Model or Bundle identity mismatch")
        pin = self._model.geometry.pin.to_data() if self._model.geometry else None
        if pin != m["geometry"]:
            raise ValueError("Manifest Geometry pin differs from its Model")
        native = [
            {**e, "path": e["path"][9:]}
            for e in entries
            if e["path"].startswith("geometry/")
        ]
        if sorted(native, key=lambda e: e["path"]) != sorted(
            pin["files"] if pin else [], key=lambda e: e["path"]
        ):
            raise ValueError("Geometry inventory differs from its Model")
        if any(
            not (n.startswith("model/") or n.startswith("geometry/")) for n in names
        ):
            raise ValueError("Unsupported Bundle payload")

    def _reconstruct(self):
        rows = {}
        for kind, path in self.tables.items():
            for row in pq.read_table(path).to_pylist():
                if row["_path"] in rows:
                    raise ValueError("Duplicate embedded record path")
                rows[row["_path"]] = kind, row
        visited = set()

        def visit(path, expected_kind):
            if path in visited or path not in rows:
                raise ValueError("Missing or multiply owned embedded record")
            visited.add(path)
            kind, row = rows[path]
            if kind != expected_kind:
                raise ValueError("Embedded record kind mismatch")
            data = {}
            for name, meta in slots_for(kind).items():
                state, physical = row[name + "__state"], row[name]
                if (
                    state not in (0, 1, 2)
                    or (state != 2 and physical is not None)
                    or (state == 2 and physical is None)
                ):
                    raise ValueError("Invalid field presence")
                if state == 0:
                    continue
                if state == 1:
                    data[name] = None
                    continue

                def item(cell, locator=None):
                    tag = cell["tag"]
                    if (
                        type(tag) is not int
                        or not 0 <= tag < len(meta["options"])
                        or any(
                            v is not None
                            for k, v in cell.items()
                            if k not in ("tag", f"v{tag}")
                        )
                    ):
                        raise ValueError("Invalid typed union tag")
                    value = cell[f"v{tag}"]
                    option = meta["options"][tag]
                    category, target = option["category"], option["kind"]
                    if value is None:
                        raise ValueError("A present union needs its selected value")
                    if category in ("record", "keyed"):
                        expected = (
                            path
                            + "/"
                            + _pointer(name)
                            + ("/" + _pointer(locator) if locator is not None else "")
                        )
                        if value != expected:
                            raise ValueError(
                                "Embedded record path does not match its owner"
                            )
                        return visit(value, target)
                    if category == "opaque":
                        return json.loads(value)
                    if category == "primitive" and target in (
                        "decimal",
                        "double",
                        "integer",
                    ):
                        if (value["integer"] is None) == (value["number"] is None):
                            raise ValueError(
                                "Numeric union must have one exact representation"
                            )
                        return (
                            int(value["integer"])
                            if value["integer"] is not None
                            else value["number"]
                        )
                    return value

                if meta["mapping"]:
                    if len({e["key"] for e in physical}) != len(physical):
                        raise ValueError("Duplicate map key")
                    data[name] = {
                        e["key"]: item(e["value"], e["key"]) for e in physical
                    }
                elif meta["many"]:
                    data[name] = [item(value, i) for i, value in enumerate(physical)]
                else:
                    data[name] = item(physical)
            return data

        model = Model.from_data(visit("", "Model"))
        if visited != set(rows):
            raise ValueError("Orphan embedded records")
        _, records, references = _shred(model)
        for name, expected, schema in (
            ("records", records, RECORD_SCHEMA),
            ("references", references, REF_SCHEMA),
        ):
            table = pq.read_table(self.root / f"model/{name}.parquet")
            if not table.schema.equals(schema) or sorted(
                map(encoded, table.to_pylist())
            ) != sorted(map(encoded, expected)):
                raise ValueError(
                    "Derived reference index differs from canonical tables"
                )
        return model

    def model(self):
        return self._model

    def verify_geometry(self):
        if self._model.geometry is not None:
            if self.provider is None:
                raise ValueError("Unsupported Geometry: supply its explicit provider")
            self.provider.validate(self.root / "geometry", self._model.geometry)

    def records(self, *, kind=None, canonical_id=None, offset=0, limit=100):
        """A bounded public projection. No caller-supplied SQL or filesystem path."""
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 1000
        ):
            raise ValueError("Invalid page bounds")
        if kind is not None and kind not in SLOTS:
            raise ValueError("Unknown RK kind")
        import duckdb

        connection = duckdb.connect(
            config={
                "memory_limit": "128MB",
                "threads": "1",
                "enable_external_access": "false",
            }
        )
        try:
            connection.register(
                "records", pq.read_table(self.root / "model/records.parquet")
            )
            result = connection.execute(
                "SELECT path, kind, canonical_id, owner_id FROM records WHERE (? IS NULL OR kind=?) AND (? IS NULL OR canonical_id=?) ORDER BY path LIMIT ? OFFSET ?",
                [kind, kind, canonical_id, canonical_id, limit + 1, offset],
            ).fetchall()
            return dict(
                items=[
                    dict(zip(("path", "kind", "canonical_id", "owner_id"), row))
                    for row in result[:limit]
                ],
                next_offset=offset + limit if len(result) > limit else None,
            )
        finally:
            connection.close()
