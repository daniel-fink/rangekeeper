"""Review candidate: schema-derived RK records and exact native Geometry pins.

The manifest is the publication marker. No JSON Model is retained or consulted.
Import this optional IO module explicitly; domain imports need no Arrow or DuckDB.
"""

import json
import os
import shutil
from collections import defaultdict
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from uuid import UUID

from rangekeeper import Model, Run, Specification
from rangekeeper.io._document import require_revision, require_same, snapshot
from rangekeeper.io.atomic import write_new
from rangekeeper.io.geometry import find as find_provider
from rangekeeper.model.geometry import safe_path
from rangekeeper.run.validation import validate as validate_run
from rangekeeper.schema.runtime import comparison_data
from rangekeeper.schema.validation import slots_for
from rangekeeper.shared import pointer
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.shared.errors import MissingReferenceError, ReferenceTypeError
from rangekeeper.shared.optional import requires
from rangekeeper.shared.validation import require_acyclic

with requires("bundle"):
    import pyarrow as pa
    import pyarrow.parquet as pq

FORMAT = "rangekeeper.bundle/2-proposal"
MAPPING = "rangekeeper.parquet/1-proposal"
SCHEMA_BYTES = files("rangekeeper.schema").joinpath("slots.json").read_bytes()
SLOTS = json.loads(SCHEMA_BYTES)
SCHEMA_DIGEST = sha256(SCHEMA_BYTES).hexdigest()


def encoded(value):
    """Return canonical JSON text: sorted keys, compact separators and no NaN."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def digest(value):
    """Return the SHA-256 hex digest of the canonical JSON encoding."""
    return sha256(encoded(value).encode()).hexdigest()


def model_digest(model):
    """Return the digest of the comparison data of a Model."""
    return digest(comparison_data("Model", model.to_data()))


def document_digest(document):
    """Return the digest of the comparison data of a document."""
    return digest(comparison_data(type(document).__name__, document.to_data()))


def reference(document):
    """Return the kind and ID of a document as a reference record."""
    return dict(kind=type(document).__name__, id=str(document.id))


def identity(model, *, documents=(), roots=()):
    """Logical content identity, independent of table packing and file locations."""
    records = {str(d.id): d for d in (model, *documents)}
    return digest(
        dict(
            format=FORMAT,
            mapping=MAPPING,
            primary_model=str(model.id),
            roots=sorted(roots, key=lambda r: (r["kind"], r["id"])),
            documents=[
                dict(**reference(d), digest=document_digest(d))
                for _, d in sorted(records.items())
            ],
        )
    )


KINDS = {k.__name__: k for k in (Model, Specification, Run)}


def _dependencies(document):
    """Interpretation dependencies only; historical predecessors are not followed."""
    if isinstance(document, Specification):
        record = document.record
        if record.model is not None:
            yield record.model, Model
        for identifier in (*(record.includes or ()), *(record.cases or ())):
            yield identifier, Specification
    elif isinstance(document, Run):
        record = document.record
        yield record.specification, Specification
        for identifier in record.outputs or ():
            yield identifier, Model
        for identifier in record.spawns or ():
            yield identifier, Run
        for item in (*(record.report.diagnostics or ()), *(record.report.trace or ())):
            if item.document is not None:
                yield item.document, None


class _Documents:
    def __init__(self, documents, *, validated=False):
        """Hold immutable documents by UUID.

        Caller-owned documents are validated again as detached snapshots.
        ``validated`` documents were just reconstructed and validated by this
        module, and no caller holds them, so they are kept without a snapshot.
        """
        self._documents = {}
        for value in documents:
            document = value if validated else snapshot(value)
            if document.id in self._documents:
                require_same(self._documents[document.id], document)
            else:
                self._documents[document.id] = document

    def _load(self, identifier, kind):
        require_uuid(identifier, "id")
        try:
            document = self._documents[identifier]
        except KeyError:
            raise MissingReferenceError(str(identifier)) from None
        return require_revision(document, identifier, kind)

    def load_model(self, id):
        return self._load(id, Model)

    def load_specification(self, id):
        return self._load(id, Specification)

    def load_run(self, id):
        return self._load(id, Run)

    def documents(self):
        """Exact immutable roots, ordered by UUID; no execution or mutable state."""
        return tuple(
            d for _, d in sorted(self._documents.items(), key=lambda p: str(p[0]))
        )


def _resolve(resolver, identifier, kind):
    if resolver is None:
        raise MissingReferenceError(str(identifier))
    for candidate in (kind,) if kind else (Model, Specification, Run):
        try:
            document = getattr(resolver, "load_" + candidate.__name__.lower())(
                identifier
            )
        except (MissingReferenceError, ReferenceTypeError):
            if kind:
                raise
            continue
        return snapshot(require_revision(document, identifier, candidate))
    raise MissingReferenceError(str(identifier))


def _collect(model, documents, resolver, max_documents=1000, *, validated=False):
    found = _Documents((model, *documents), validated=validated)
    pending = list(found.documents())
    while pending:
        document = pending.pop()
        if len(found._documents) > max_documents:
            raise ValueError("Bundle document limit exceeded")
        for identifier, kind in _dependencies(document):
            if identifier in found._documents:
                if kind:
                    found._load(identifier, kind)
            else:
                dependency = _resolve(resolver, identifier, kind)
                found._documents[identifier] = dependency
                pending.append(dependency)
    # Saved partial or failed investigation definitions remain valid content.
    # Check their reference graph without claiming mathematical validity.
    require_acyclic(
        {
            str(d.id): [str(i) for i, k in _dependencies(d) if k is Specification]
            for d in found.documents()
            if isinstance(d, Specification)
        },
        "Bundle Specification dependencies",
    )
    for document in found.documents():
        if isinstance(document, Run):
            validate_run(document, resolver=found).raise_if_invalid()
    return found


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
    """Return the Arrow schema of the Parquet table for one RK kind."""
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
                    child = pointer.child(
                        path, name, *(() if locator is None else (locator,))
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

    visit(type(model).__name__, model.to_data())
    return tables, records, references


RECORD_SCHEMA = pa.schema(
    [(k, pa.string()) for k in ("path", "kind", "canonical_id", "owner_id")]
)
REF_SCHEMA = pa.schema(
    [(k, pa.string()) for k in ("path", "slot", "target", "locator")]
)
# Compares record paths segment by segment. Array indices compare as numbers
# and before names, so /x/2 precedes /x/10 and a record precedes its children.
PATH_ORDER = (
    "list_transform(string_split(path, '/'), s -> CASE"
    " WHEN regexp_full_match(s, '0|[1-9][0-9]*')"
    " THEN {'name': false, 'width': length(s), 'segment': s}"
    " ELSE {'name': true, 'width': 0, 'segment': s} END)"
)


def inventory(root, paths):
    """Return the size and SHA-256 of each local Bundle file, sorted by path."""
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


def _prefix(identifier, primary):
    return "model" if identifier == primary else "documents/" + str(identifier)


def _write_document(root, document, prefix, compression, row_group_size):
    tables, records, references = _shred(document)
    (root / prefix).mkdir(parents=True)
    declarations = []
    for kind, rows in sorted(tables.items()):
        name = f"{prefix}/{kind}.parquet"
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
            root / f"{prefix}/{name}.parquet",
            compression=compression,
            row_group_size=row_group_size,
        )
    return declarations


def _pin(document):
    return (
        document.geometry.pin.to_data()
        if isinstance(document, Model) and document.geometry
        else None
    )


def _descriptor(document):
    return dict(
        **reference(document),
        schema_version=document.metadata.schema_version,
        digest=document_digest(document),
    )


def write(
    root,
    model,
    *,
    documents=(),
    resolver=None,
    geometry=None,
    provider=None,
    geometries=None,
    providers=None,
    compression="zstd",
    row_group_size=8192,
):
    """Retain selected investigations and all interpretation dependencies.

    ``model`` is the main Model. ``documents`` selects additional roots; the
    resolver supplies exact dependencies. Geometry directories are keyed by Model
    UUID; providers by (provider, format, version). No workspace state is exported.
    The manifest is published last. Failed writes never replace a destination.
    """
    if not isinstance(model, Model):
        raise TypeError("Supply a primary Model")
    documents = tuple(documents)
    roots = sorted(
        {(type(d).__name__, str(d.id)) for d in documents if d.id != model.id}
    )
    roots = [dict(kind=k, id=i) for k, i in roots]
    found = _collect(model, documents, resolver)
    model = found.load_model(model.id)
    sources = {str(k): Path(v) for k, v in (geometries or {}).items()}
    if geometry is not None:
        sources[str(model.id)] = Path(geometry)
    known_models = {str(d.id): d for d in found.documents() if isinstance(d, Model)}
    if any(k not in known_models or known_models[k].geometry is None for k in sources):
        raise ValueError("Geometry source has no declared Model pin")
    provider_map = dict(providers or {})
    geometry_paths, datasets = {}, {}
    for document in found.documents():
        pin = _pin(document)
        if pin is None:
            continue
        key = (pin["provider"], pin["format"], pin["format_version"])
        adapter = provider_map.get(key, provider) or find_provider(pin["provider"])
        if adapter is None:
            raise ValueError("Geometry needs an explicit provider")
        # Equal complete pins share bytes. A dependency can reuse a supplied pin.
        pin_id = digest(pin)
        source = sources.get(str(document.id))
        if source is None:
            source = next(
                (v for k, v in sources.items() if _pin(known_models[k]) == pin), None
            )
        if source is None:
            raise ValueError("Geometry needs its exact native files")
        adapter.validate(source, document.geometry)
        path = "geometry" if _pin(model) == pin else "assets/" + pin_id
        geometry_paths[str(document.id)] = path
        datasets[pin_id] = (path, source, document.geometry, adapter)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    primary_tables, others = None, []
    for document in found.documents():
        tables = _write_document(
            root, document, _prefix(document.id, model.id), compression, row_group_size
        )
        if document.id == model.id:
            primary_tables = tables
        else:
            others.append(
                dict(**_descriptor(document), tables=tables, geometry=_pin(document))
            )
    for path, source, spatial, adapter in datasets.values():
        for entry in spatial.pin.files:
            destination = root / path / entry.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / entry.path, destination)
        adapter.validate(root / path, spatial)
    payloads = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    for name in payloads:
        # Windows flushes only a handle that has write access.
        with (root / name).open("r+b") as stream:
            os.fsync(stream.fileno())
    manifest = dict(
        format=FORMAT,
        id=identity(model, documents=found.documents(), roots=roots),
        mapping=MAPPING,
        schema_digest=SCHEMA_DIGEST,
        model={k: v for k, v in _descriptor(model).items() if k != "kind"},
        tables=primary_tables,
        files=inventory(root, payloads),
        geometry=_pin(model),
        documents=others,
        roots=roots,
        geometry_paths=geometry_paths,
    )
    restored = Reader(
        root, provider=provider, providers=provider_map, _manifest=manifest
    )
    from rangekeeper.schema.runtime import exact_equal

    for document in found.documents():
        if not exact_equal(
            restored._documents[document.id].to_data(), document.to_data()
        ):
            raise ValueError("Bundle reconstruction differs from supplied records")
    restored.verify_geometry()
    write_new(root / "manifest.json", encoded(manifest) + "\n")
    return manifest


class _DocumentReader:
    def __init__(self, root, descriptor, prefix, names):
        self.root, self.prefix, self.kind = root, prefix, KINDS[descriptor["kind"]]
        self.tables = {}
        for table in descriptor["tables"]:
            kind = table["kind"]
            if (
                kind not in SLOTS
                or kind in self.tables
                or table["path"] != f"{prefix}/{kind}.parquet"
                or table["path"] not in names
                or type(table["rows"]) is not int
                or table["rows"] < 0
            ):
                raise ValueError("Invalid or duplicate canonical table")
            path = root / table["path"]
            physical = pq.ParquetFile(path)
            if (
                not physical.schema_arrow.equals(
                    table_schema(kind), check_metadata=True
                )
                or physical.metadata.num_rows != table["rows"]
            ):
                raise ValueError("Table schema or row count mismatch")
            self.tables[kind] = path
        expected = {t["path"] for t in descriptor["tables"]} | {
            f"{prefix}/records.parquet",
            f"{prefix}/references.parquet",
        }
        if {n for n in names if n.startswith(prefix + "/")} != expected:
            raise ValueError("Unexpected canonical files")

    def _reconstruct(self, check_index=True):
        rows, slots = {}, {}
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
            # slots_for returns a copy; reuse one per kind for this read only.
            if kind not in slots:
                slots[kind] = slots_for(kind)
            for name, meta in slots[kind].items():
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
                        expected = pointer.child(
                            path, name, *(() if locator is None else (locator,))
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

        model = self.kind.from_data(visit("", self.kind.__name__))
        if visited != set(rows):
            raise ValueError("Orphan embedded records")
        if not check_index:
            for name, schema in (
                ("records", RECORD_SCHEMA),
                ("references", REF_SCHEMA),
            ):
                path = self.root / f"{self.prefix}/{name}.parquet"
                if not pq.ParquetFile(path).schema_arrow.equals(schema):
                    raise ValueError("Derived index schema mismatch")
            return model
        _, records, references = _shred(model)
        for name, expected, schema in (
            ("records", records, RECORD_SCHEMA),
            ("references", references, REF_SCHEMA),
        ):
            table = pq.read_table(self.root / f"{self.prefix}/{name}.parquet")
            if not table.schema.equals(schema) or sorted(
                map(encoded, table.to_pylist())
            ) != sorted(map(encoded, expected)):
                raise ValueError(
                    "Derived reference index differs from canonical tables"
                )
        return model


class Reader(_Documents):
    """Verified immutable documents, public resolver reads and bounded projections.

    Opening validates canonical records and their required references. It never
    executes Specifications. Native Geometry verification is explicit.

    ``check_index=False`` skips comparing the derived record and reference index
    with the reconstructed documents; their schemas and file hashes are still
    checked. Use it only for a Bundle whose index a full open already verified
    and whose files are unchanged since.
    """

    def __init__(
        self,
        root,
        *,
        provider=None,
        providers=None,
        max_bytes=4 * 1024**3,
        max_rows=1_000_000,
        max_documents=1000,
        check_index=True,
        _manifest=None,
    ):
        self.root = Path(root).resolve(strict=True)
        marker = self.root / "manifest.json"
        if _manifest is None:
            if marker.is_symlink() or marker.stat().st_size > 4 * 1024**2:
                raise ValueError("Invalid or oversized Bundle manifest")

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate manifest key")
                    result[key] = value
                return result

            self.manifest = json.loads(
                marker.read_text(encoding="utf-8"), object_pairs_hook=unique
            )
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
            "documents",
            "roots",
            "geometry_paths",
        } or (m["format"], m["mapping"], m["schema_digest"]) != (
            FORMAT,
            MAPPING,
            SCHEMA_DIGEST,
        ):
            raise ValueError("Unsupported Bundle format, mapping or schema pin")
        if len(m["documents"]) + 1 > max_documents:
            raise ValueError("Bundle document limit exceeded")
        entries = m["files"]
        if (
            len(entries) > 10000
            or any(
                set(e) != {"path", "size", "sha256"}
                or type(e["size"]) is not int
                or e["size"] < 0
                for e in entries
            )
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
        canonical = [
            e for e in entries if e["path"].startswith(("model/", "documents/"))
        ]
        if inventory(self.root, [e["path"] for e in canonical]) != sorted(
            canonical, key=lambda e: e["path"]
        ):
            raise ValueError("Canonical file integrity mismatch")
        if sum(e["size"] for e in canonical) > 256 * 1024**2:
            raise ValueError("Canonical compressed size limit exceeded")
        expanded, rows = 0, 0
        for entry in canonical:
            physical = pq.ParquetFile(self.root / entry["path"])
            expanded += sum(
                physical.metadata.row_group(i).total_byte_size
                for i in range(physical.metadata.num_row_groups)
            )
            rows += physical.metadata.num_rows
            if rows > max_rows or expanded > 512 * 1024**2:
                raise ValueError("Canonical expanded work limit exceeded")
        self._primary = UUID(m["model"]["id"])
        descriptors = [
            dict(
                **m["model"], kind="Model", tables=m["tables"], geometry=m["geometry"]
            ),
            *m["documents"],
        ]
        if len({d["id"] for d in descriptors}) != len(descriptors):
            raise ValueError("Duplicate document identity")
        documents, expected_files, expected_geometry = [], set(), {}
        for descriptor in descriptors:
            if (
                set(descriptor)
                != {"kind", "id", "schema_version", "digest", "tables", "geometry"}
                or descriptor["kind"] not in KINDS
            ):
                raise ValueError("Invalid document descriptor")
            identifier = UUID(descriptor["id"])
            if str(identifier) != descriptor["id"]:
                raise ValueError("Noncanonical document identity")
            prefix = self._prefix(identifier)
            document = _DocumentReader(
                self.root, descriptor, prefix, names
            )._reconstruct(check_index)
            if _descriptor(document) != {
                k: v for k, v in descriptor.items() if k not in ("tables", "geometry")
            }:
                raise ValueError("Canonical document identity mismatch")
            documents.append(document)
            expected_files.update(t["path"] for t in descriptor["tables"])
            expected_files.update(
                (f"{prefix}/records.parquet", f"{prefix}/references.parquet")
            )
            pin = _pin(document)
            if pin != descriptor["geometry"]:
                raise ValueError("Manifest Geometry pin differs from its Model")
            if pin:
                path = "geometry" if m["geometry"] == pin else "assets/" + digest(pin)
                expected_geometry[str(identifier)] = path
                for entry in pin["files"]:
                    declared = dict(entry, path=path + "/" + entry["path"])
                    if declared not in entries:
                        raise ValueError("Geometry inventory differs from its Model")
                    expected_files.add(declared["path"])
        if set(names) != expected_files or m["geometry_paths"] != expected_geometry:
            raise ValueError("Unexpected Bundle files or Geometry paths")
        # Each document was validated once by _reconstruct.
        super().__init__(documents, validated=True)
        roots = m["roots"]
        if (
            type(roots) is not list
            or any(
                type(r) is not dict
                or set(r) != {"kind", "id"}
                or r["kind"] not in KINDS
                for r in roots
            )
            or roots != sorted(roots, key=lambda r: (r["kind"], r["id"]))
            or len({r["id"] for r in roots}) != len(roots)
        ):
            raise ValueError("Invalid selected roots")
        selected = [self._load(UUID(r["id"]), KINDS[r["kind"]]) for r in roots]
        if any(d.id == self._primary for d in selected):
            raise ValueError("Primary Model is already selected")
        closed = _collect(self.model(), selected, self, max_documents, validated=True)
        if set(closed._documents) != set(self._documents):
            raise ValueError("Unselected document outside dependency closure")
        if identity(self.model(), documents=self.documents(), roots=roots) != m["id"]:
            raise ValueError("Canonical Bundle identity mismatch")
        self.provider, self.providers = provider, dict(providers or {})

    def _prefix(self, identifier):
        return _prefix(identifier, self._primary)

    def model(self, id=None):
        """Return the primary Model, or the Model with the given ID."""
        return self.load_model(self._primary if id is None else id)

    def geometry_path(self, id=None):
        """Return the local Geometry file path of a Model, or None if it has no Geometry."""
        model = self.model(id)
        if model.geometry is None:
            return None
        return self.root / self.manifest["geometry_paths"][str(model.id)]

    def verify_geometry(self):
        """Validate each distinct Geometry pin with its explicit provider."""
        checked = set()
        for document in self.documents():
            pin = _pin(document)
            if pin is None or digest(pin) in checked:
                continue
            key = (pin["provider"], pin["format"], pin["format_version"])
            provider = self.providers.get(key, self.provider) or find_provider(
                pin["provider"]
            )
            if provider is None:
                raise ValueError("Unsupported Geometry: supply its explicit provider")
            provider.validate(self.geometry_path(document.id), document.geometry)
            checked.add(digest(pin))

    def copy_to(self, store):
        """Copy into an append-only store; retain IDs and reject conflicts first.

        Runs are published after their dependencies. This is idempotent, not a
        multi-document transaction: an IO failure can leave complete records.
        No workspace acceptance or investigation execution is implied.
        """
        documents = self.documents()
        for document in documents:
            try:
                existing = _resolve(store, document.id, type(document))
            except MissingReferenceError:
                continue
            require_same(existing, document)
        ordered, active, done = [], set(), set()

        def visit(document):
            if document.id in done:
                return
            if document.id in active:
                raise ValueError("Cyclic Run publication dependencies")
            active.add(document.id)
            for identifier, _ in _dependencies(document):
                if identifier != document.id:
                    visit(self._documents[identifier])
            active.remove(document.id)
            done.add(document.id)
            ordered.append(document)

        for document in documents:
            visit(document)
        for document in ordered:
            store.put(document)
        return tuple(reference(d) for d in documents)

    def records(
        self,
        *,
        document=None,
        kind=None,
        canonical_id=None,
        path=None,
        offset=0,
        limit=100,
    ):
        """Return a bounded public projection. Accept no caller-supplied SQL or filesystem path."""
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 1000
        ):
            raise ValueError("Invalid page bounds")
        if kind is not None and kind not in SLOTS:
            raise ValueError("Unknown RK kind")
        if path is not None and (type(path) is not str or len(path) > 4096):
            raise ValueError("Invalid record path")
        selected = (
            self.model()
            if document is None
            else self._documents.get(UUID(str(document)))
        )
        if selected is None:
            raise MissingReferenceError(str(document))
        prefix = self._prefix(selected.id)
        with requires("bundle"):
            import duckdb

        connection = duckdb.connect(
            config={
                "memory_limit": "128MB",
                "threads": "1",
            }
        )
        try:
            # Only this verified index is readable. No caller SQL, extension
            # loading, network or other filesystem access is enabled.
            index = str((self.root / prefix / "records.parquet").resolve())
            connection.execute("SET allowed_paths = ?", [[index]])
            connection.execute("SET enable_external_access = false")
            result = connection.execute(
                "SELECT path, kind, canonical_id, owner_id FROM read_parquet(?) WHERE (? IS NULL OR kind=?) AND (? IS NULL OR canonical_id=?) AND (? IS NULL OR path=?) "
                f"ORDER BY {PATH_ORDER} LIMIT ? OFFSET ?",
                [
                    index,
                    kind,
                    kind,
                    canonical_id,
                    canonical_id,
                    path,
                    path,
                    limit + 1,
                    offset,
                ],
            ).fetchall()
            return dict(
                items=[
                    dict(
                        zip(
                            ("path", "kind", "canonical_id", "owner_id"),
                            row,
                            strict=True,
                        )
                    )
                    for row in result[:limit]
                ],
                next_offset=offset + limit if len(result) > limit else None,
            )
        finally:
            connection.close()
