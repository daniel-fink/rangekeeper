"""Write and read a Bundle: Model, Specification and Run records in Parquet tables.

A Bundle is a directory with one main Model, the documents that a caller
selects, their exact dependencies and the native Geometry files that the
Models pin. The manifest is the publication marker. No JSON Model is retained
or consulted. Import this optional IO module explicitly; domain imports need no
Arrow or DuckDB.

``write`` publishes a Bundle and ``Reader`` opens and checks one.
``GeometrySources`` gives ``write`` the native files and their providers, and
``ParquetOptions`` sets how it writes the tables. ``ReadLimits`` and
``IndexCheck`` set how much ``Reader`` reads and checks.
"""

import json
import os
import shutil
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum, unique
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeAlias
from uuid import UUID

from rangekeeper import Model, Run, Specification
from rangekeeper.io._atomic import write_new
from rangekeeper.io._document import (
    Document,
    require_revision,
    require_same,
    trusted,
)
from rangekeeper.io.geometry import GeometryProvider
from rangekeeper.io.geometry import find as find_provider
from rangekeeper.model.geometry import safe_path
from rangekeeper.run.validation import validate as validate_run
from rangekeeper.schema.records import Geometry
from rangekeeper.schema.runtime import comparison_data, exact_equal
from rangekeeper.schema.validation import slots_for
from rangekeeper.shared import pointer
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.shared.errors import (
    ContractError,
    MissingReferenceError,
    ReferenceTypeError,
)
from rangekeeper.shared.optional import requires
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.shared.store import RecordStore
from rangekeeper.shared.validation import require_acyclic

with requires("bundle"):
    import pyarrow as pa
    import pyarrow.parquet as pq

__all__ = [
    "GeometrySources",
    "IndexCheck",
    "ParquetOptions",
    "ReadLimits",
    "Reader",
    "write",
]

FORMAT = "rangekeeper.bundle/2-proposal"
MAPPING = "rangekeeper.parquet/1-proposal"
SCHEMA_BYTES = files("rangekeeper.schema").joinpath("slots.json").read_bytes()
SLOTS = json.loads(SCHEMA_BYTES)
SCHEMA_DIGEST = sha256(SCHEMA_BYTES).hexdigest()

# A Geometry pin's (provider, format, format_version).
ProviderKey: TypeAlias = tuple[str, str, str]
_NO_PROVIDERS: Mapping[ProviderKey, GeometryProvider] = MappingProxyType({})
_COMPRESSIONS = frozenset({"none", "snappy", "gzip", "brotli", "lz4", "zstd"})
# The fixed limits of one Bundle; ReadLimits holds the limits a caller sets.
_MANIFEST_BYTES = 4 * 1024**2
_FILES = 10_000
_CANONICAL_BYTES = 256 * 1024**2
_EXPANDED_BYTES = 512 * 1024**2
_MANIFEST_KEYS = frozenset(
    {
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
    }
)
_DESCRIPTOR_KEYS = frozenset(
    {"kind", "id", "schema_version", "digest", "tables", "geometry"}
)


def _require_count(value: object, name: str) -> None:
    """Require a positive int: TypeError for another type, ContractError below 1."""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value < 1:
        raise ContractError(
            f"{name} must be at least 1, not {value}", values={name: value}
        )


@dataclass(frozen=True, kw_only=True)
class GeometrySources:
    """The native Geometry files of the Models in a Bundle, and their providers.

    ``directories`` maps a Model UUID to the directory of its native files. A
    directory for one Model also serves another Model with the same complete
    pin. ``providers`` maps a pin's ``(provider, format, format_version)`` to
    the provider that checks its files. A pin with no entry uses the provider
    registered under its provider name in ``rangekeeper.io.geometry_providers``.
    """

    directories: Mapping[UUID, Path] = field(default_factory=dict)
    providers: Mapping[ProviderKey, GeometryProvider] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key in self.directories:
            require_uuid(key, "directories key")
        if not all(isinstance(p, GeometryProvider) for p in self.providers.values()):
            raise TypeError("each provider must be a GeometryProvider")
        directories = {key: Path(value) for key, value in self.directories.items()}
        object.__setattr__(self, "directories", MappingProxyType(directories))
        object.__setattr__(self, "providers", MappingProxyType(dict(self.providers)))


@dataclass(frozen=True, kw_only=True)
class ParquetOptions:
    """How ``write`` writes the Parquet tables.

    ``compression`` is a Parquet codec: ``none``, ``snappy``, ``gzip``,
    ``brotli``, ``lz4`` or ``zstd``. ``row_group_size`` is the most rows in one
    row group. Neither option changes the Bundle identity.
    """

    compression: str = "zstd"
    row_group_size: int = 8192

    def __post_init__(self) -> None:
        if not isinstance(self.compression, str):
            raise TypeError("compression must be a string")
        if self.compression not in _COMPRESSIONS:
            raise ContractError(
                f"unknown Parquet compression {self.compression!r}",
                values={"compression": self.compression},
            )
        _require_count(self.row_group_size, "row_group_size")


@dataclass(frozen=True, kw_only=True)
class ReadLimits:
    """The most that ``Reader`` reads from one Bundle.

    ``documents`` counts the main Model and each other document. ``bytes`` is
    the total size of the files in the manifest. ``rows`` counts the physical
    rows of the canonical tables and their indexes. The reader also limits a
    Bundle to 10,000 files, 256 MiB of compressed canonical tables and 512 MiB
    of declared expanded table bytes. These are proof bounds, not tested
    production capacity.
    """

    documents: int = 1000
    bytes: int = 4 * 1024**3
    rows: int = 1_000_000

    def __post_init__(self) -> None:
        for name in ("documents", "bytes", "rows"):
            _require_count(getattr(self, name), name)


@unique
class IndexCheck(StrEnum):
    """How ``Reader`` checks the derived record and reference index of a document.

    ``FULL`` makes the index again from the rebuilt document and compares the
    two. ``SCHEMA`` checks only the schemas of the index tables; the manifest
    hashes still check each file. Use ``SCHEMA`` only for a Bundle that a
    ``FULL`` open checked before and whose files have not changed since.
    """

    FULL = "full"
    SCHEMA = "schema"


# The defaults of write and Reader; each is frozen.
_NO_GEOMETRY = GeometrySources()
_PARQUET = ParquetOptions()
_LIMITS = ReadLimits()


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
    def __init__(self, documents: Iterable[Document]) -> None:
        """Hold immutable, validated documents by UUID."""
        self._documents: dict[UUID, Document] = {}
        for value in documents:
            document = trusted(value)
            if document.id in self._documents:
                require_same(self._documents[document.id], document)
            else:
                self._documents[document.id] = document

    def _load(self, identifier, kind):
        require_uuid(identifier, "id")
        try:
            document = self._documents[identifier]
        except KeyError:
            raise MissingReferenceError(
                identifier, kind=kind.__name__, where=type(self).__name__
            ) from None
        return require_revision(document, identifier, kind)

    def load_model(self, id: UUID) -> Model:
        """Return the retained Model with this UUID."""
        return self._load(id, Model)

    def load_specification(self, id: UUID) -> Specification:
        """Return the retained Specification with this UUID."""
        return self._load(id, Specification)

    def load_run(self, id: UUID) -> Run:
        """Return the retained Run with this UUID."""
        return self._load(id, Run)

    def documents(self) -> tuple[Document, ...]:
        """Exact immutable roots, ordered by UUID; no execution or mutable state."""
        return tuple(
            d for _, d in sorted(self._documents.items(), key=lambda p: str(p[0]))
        )


def _resolve(resolver, identifier, kind):
    if resolver is None:
        raise MissingReferenceError(
            identifier, kind=kind.__name__ if kind else "document", where="no resolver"
        )
    for candidate in (kind,) if kind else (Model, Specification, Run):
        try:
            document = getattr(resolver, "load_" + candidate.__name__.lower())(
                identifier
            )
        except (MissingReferenceError, ReferenceTypeError):
            if kind:
                raise
            continue
        return trusted(require_revision(document, identifier, candidate))
    raise MissingReferenceError(
        identifier, kind="document", where=type(resolver).__name__
    )


def _collect(model, documents, resolver, max_documents=1000):
    found = _Documents((model, *documents))
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
    if category == "primitive" and kind in ("double", "integer"):
        # Integer strings preserve arbitrary precision; floats remain doubles.
        # A currency amount (the Amount option) is a string with its canonical
        # text (ADR-023).
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
            if kind in ("double", "integer") and type(value) in (int, float):
                return position
            if kind not in ("boolean", "double", "integer") and type(value) is str:
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
                elif category == "primitive" and target in ("double", "integer"):
                    physical = (
                        dict(integer=str(value), number=None)
                        if type(value) is int
                        else dict(integer=None, number=value)
                    )
                else:
                    physical = value
                # Lineage slots, such as Metadata.previous, name other revisions.
                # They are not references to records in this Model.
                if category == "uuid" and target != "UUID" and not meta["lineage"]:
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


def _write_document(
    root: Path,
    document: Document,
    *,
    prefix: str,
    parquet: ParquetOptions,
) -> list[dict[str, Any]]:
    tables, records, references = _shred(document)
    (root / prefix).mkdir(parents=True)
    declarations = []
    for kind, rows in sorted(tables.items()):
        name = f"{prefix}/{kind}.parquet"
        _write_table(root / name, rows, schema=table_schema(kind), parquet=parquet)
        declarations.append(dict(kind=kind, path=name, rows=len(rows)))
    for name, rows, schema in (
        ("records", records, RECORD_SCHEMA),
        ("references", references, REF_SCHEMA),
    ):
        path = root / f"{prefix}/{name}.parquet"
        _write_table(path, rows, schema=schema, parquet=parquet)
    return declarations


def _write_table(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    schema: "pa.Schema",
    parquet: ParquetOptions,
) -> None:
    pq.write_table(
        pa.Table.from_pylist(rows, schema=schema),
        path,
        compression=parquet.compression,
        row_group_size=parquet.row_group_size,
    )


def _pin(document: Document) -> dict[str, Any] | None:
    return (
        document.geometry.pin.to_data()
        if isinstance(document, Model) and document.geometry
        else None
    )


def _descriptor(document: Document) -> dict[str, Any]:
    return dict(
        **reference(document),
        schema_version=document.metadata.schema_version,
        digest=document_digest(document),
    )


def _provider(
    pin: Mapping[str, Any],
    providers: Mapping[ProviderKey, GeometryProvider],
) -> GeometryProvider:
    """Return the provider of a pin: the explicit one, else the registered one."""
    key = (pin["provider"], pin["format"], pin["format_version"])
    provider = providers.get(key) or find_provider(pin["provider"])
    if provider is None:
        raise ValueError("Geometry needs an explicit provider")
    return provider


def _roots(model: Model, documents: tuple[Document, ...]) -> list[dict[str, str]]:
    """Return the selected roots beyond the main Model, sorted by kind and UUID."""
    selected = {(type(d).__name__, str(d.id)) for d in documents if d.id != model.id}
    return [dict(kind=kind, id=identifier) for kind, identifier in sorted(selected)]


def _plan_geometry(
    found: _Documents,
    model: Model,
    sources: GeometrySources,
) -> tuple[dict[str, str], dict[str, tuple[str, Path, Geometry]]]:
    """Return the Geometry path of each spatial Model and each distinct dataset.

    Each dataset is its path in the Bundle, its source directory and the
    Geometry whose pin it satisfies. The provider checks each source here.
    """
    models = {d.id: d for d in found.documents() if isinstance(d, Model)}
    if any(k not in models or models[k].geometry is None for k in sources.directories):
        raise ValueError("Geometry source has no declared Model pin")
    paths, datasets = {}, {}
    for document in models.values():
        geometry = document.geometry
        if geometry is None:
            continue
        pin = geometry.pin.to_data()
        provider = _provider(pin, sources.providers)
        # Equal complete pins share bytes. A dependency can reuse a supplied pin.
        source = sources.directories.get(document.id) or next(
            (v for k, v in sources.directories.items() if _pin(models[k]) == pin),
            None,
        )
        if source is None:
            raise ValueError("Geometry needs its exact native files")
        provider.validate(source, geometry)
        path = "geometry" if _pin(model) == pin else "assets/" + digest(pin)
        paths[str(document.id)] = path
        datasets[digest(pin)] = (path, source, geometry)
    return paths, datasets


def _copy_geometry(
    root: Path,
    datasets: Mapping[str, tuple[str, Path, Geometry]],
    providers: Mapping[ProviderKey, GeometryProvider],
) -> None:
    """Copy each dataset's pinned files into the Bundle and check the copies."""
    for path, source, geometry in datasets.values():
        for entry in geometry.pin.files:
            destination = root / path / entry.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / entry.path, destination)
        _provider(geometry.pin.to_data(), providers).validate(root / path, geometry)


def _flush(root: Path) -> list[str]:
    """Flush each file under root to disk; return their paths, relative to root."""
    payloads = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    for name in payloads:
        # Windows flushes only a handle that has write access.
        with (root / name).open("r+b") as stream:
            os.fsync(stream.fileno())
    return payloads


def write(
    root: Path,
    model: Model,
    *,
    documents: Iterable[Document] = (),
    resolver: DocumentResolver | None = None,
    geometry: GeometrySources = _NO_GEOMETRY,
    parquet: ParquetOptions = _PARQUET,
) -> dict[str, Any]:
    """Write a new Bundle with a main Model, selected documents and their dependencies.

    ``model`` is the main Model. ``documents`` selects other root Models,
    Specifications and Runs; ``resolver`` supplies the exact documents that they
    depend on. ``geometry`` gives the native files of each Model with a
    Geometry pin, and the providers that check them. No workspace state is
    exported. The writer reads the Bundle back and compares it with the
    documents before it publishes the manifest, last. A failed write never
    replaces a destination, but it can leave a directory with no manifest.
    Return the manifest.
    """
    if not isinstance(model, Model):
        raise TypeError("Supply a primary Model")
    selected = tuple(documents)
    roots = _roots(model, selected)
    found = _collect(model, selected, resolver)
    model = found.load_model(model.id)
    geometry_paths, datasets = _plan_geometry(found, model, geometry)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    primary_tables, others = None, []
    for document in found.documents():
        tables = _write_document(
            root, document, prefix=_prefix(document.id, model.id), parquet=parquet
        )
        if document.id == model.id:
            primary_tables = tables
        else:
            others.append(
                dict(**_descriptor(document), tables=tables, geometry=_pin(document))
            )
    _copy_geometry(root, datasets, geometry.providers)
    manifest = dict(
        format=FORMAT,
        id=identity(model, documents=found.documents(), roots=roots),
        mapping=MAPPING,
        schema_digest=SCHEMA_DIGEST,
        model={k: v for k, v in _descriptor(model).items() if k != "kind"},
        tables=primary_tables,
        files=inventory(root, _flush(root)),
        geometry=_pin(model),
        documents=others,
        roots=roots,
        geometry_paths=geometry_paths,
    )
    _check_written(root, manifest, found=found, providers=geometry.providers)
    write_new(root / "manifest.json", encoded(manifest) + "\n")
    return manifest


def _check_written(
    root: Path,
    manifest: dict[str, Any],
    *,
    found: _Documents,
    providers: Mapping[ProviderKey, GeometryProvider],
) -> None:
    """Read a written Bundle before its manifest exists; compare each document."""
    restored = Reader._unpublished(root, manifest, providers=providers)
    for document in found.documents():
        if not exact_equal(
            restored._documents[document.id].to_data(), document.to_data()
        ):
            raise ValueError("Bundle reconstruction differs from supplied records")
    restored.verify_geometry()


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

    def _reconstruct(self, index: IndexCheck) -> Document:
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
                    if category == "primitive" and target in ("double", "integer"):
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
        if index is IndexCheck.SCHEMA:
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


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Return the JSON object of the pairs; reject a duplicate key."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest key")
        result[key] = value
    return result


def _read_manifest(root: Path) -> dict[str, Any]:
    """Read the manifest of a published Bundle, with no duplicate keys."""
    marker = root / "manifest.json"
    if marker.is_symlink() or marker.stat().st_size > _MANIFEST_BYTES:
        raise ValueError("Invalid or oversized Bundle manifest")
    return json.loads(marker.read_text(encoding="utf-8"), object_pairs_hook=_unique)


def _check_format(manifest: Mapping[str, Any], limits: ReadLimits) -> None:
    """Require the manifest keys, the format pins and the document limit."""
    if set(manifest) != _MANIFEST_KEYS or (
        manifest["format"],
        manifest["mapping"],
        manifest["schema_digest"],
    ) != (FORMAT, MAPPING, SCHEMA_DIGEST):
        raise ValueError("Unsupported Bundle format, mapping or schema pin")
    if len(manifest["documents"]) + 1 > limits.documents:
        raise ValueError("Bundle document limit exceeded")


def _check_inventory(
    root: Path,
    entries: list[dict[str, Any]],
    *,
    limits: ReadLimits,
    published: bool,
) -> list[str]:
    """Require that the files under root are the manifest's files; return their paths.

    A Bundle that ``write`` has not published yet has no manifest file.
    """
    if (
        len(entries) > _FILES
        or any(
            set(e) != {"path", "size", "sha256"}
            or type(e["size"]) is not int
            or e["size"] < 0
            for e in entries
        )
        or sum(e["size"] for e in entries) > limits.bytes
    ):
        raise ValueError("Bundle size limit exceeded")
    names = [e["path"] for e in entries]
    if len(set(names)) != len(names) or any(not safe_path(n) for n in names):
        raise ValueError("Invalid or duplicate inventory paths")
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Symlinks are not Bundle content")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(names) | ({"manifest.json"} if published else set()):
        raise ValueError("Bundle file closure differs from its manifest")
    for entry in entries:
        path = root / entry["path"]
        if not path.is_file() or path.stat().st_size != entry["size"]:
            raise ValueError("Bundle file missing or changed size")
    return names


def _check_canonical(
    root: Path,
    entries: list[dict[str, Any]],
    limits: ReadLimits,
) -> None:
    """Require the hashes of the canonical tables, and their size and row limits."""
    canonical = [e for e in entries if e["path"].startswith(("model/", "documents/"))]
    if inventory(root, [e["path"] for e in canonical]) != sorted(
        canonical, key=lambda e: e["path"]
    ):
        raise ValueError("Canonical file integrity mismatch")
    if sum(e["size"] for e in canonical) > _CANONICAL_BYTES:
        raise ValueError("Canonical compressed size limit exceeded")
    expanded, rows = 0, 0
    for entry in canonical:
        physical = pq.ParquetFile(root / entry["path"])
        expanded += sum(
            physical.metadata.row_group(i).total_byte_size
            for i in range(physical.metadata.num_row_groups)
        )
        rows += physical.metadata.num_rows
        if rows > limits.rows or expanded > _EXPANDED_BYTES:
            raise ValueError("Canonical expanded work limit exceeded")


def _check_roots(roots: object) -> list[dict[str, str]]:
    """Require typed, sorted and distinct selected roots; return them."""
    if (
        type(roots) is not list
        or any(
            type(r) is not dict or set(r) != {"kind", "id"} or r["kind"] not in KINDS
            for r in roots
        )
        or roots != sorted(roots, key=lambda r: (r["kind"], r["id"]))
        or len({r["id"] for r in roots}) != len(roots)
    ):
        raise ValueError("Invalid selected roots")
    return roots


class Reader(_Documents):
    """The checked, immutable documents of a Bundle, with resolver reads and queries.

    Opening checks the manifest, the file hashes and the limits, rebuilds each
    document from its canonical tables and checks its required references. It
    never executes a Specification. Native Geometry checks are explicit; see
    ``verify_geometry``.

    ``providers`` maps a Geometry pin's ``(provider, format, format_version)``
    to the provider that checks its files. ``limits`` bounds what the reader
    reads, and ``index`` sets how it checks the derived record and reference
    index.
    """

    def __init__(
        self,
        root: Path,
        *,
        providers: Mapping[ProviderKey, GeometryProvider] = _NO_PROVIDERS,
        limits: ReadLimits = _LIMITS,
        index: IndexCheck = IndexCheck.FULL,
    ) -> None:
        folder = Path(root).resolve(strict=True)
        self._open(
            folder, _read_manifest(folder), limits=limits, index=index, published=True
        )
        self.providers = dict(providers)

    @classmethod
    def _unpublished(
        cls,
        root: Path,
        manifest: dict[str, Any],
        *,
        providers: Mapping[ProviderKey, GeometryProvider],
    ) -> "Reader":
        """Open a Bundle that ``write`` has written but not yet published."""
        reader = cls.__new__(cls)
        reader._open(
            root.resolve(strict=True),
            manifest,
            limits=_LIMITS,
            index=IndexCheck.FULL,
            published=False,
        )
        reader.providers = dict(providers)
        return reader

    def _open(
        self,
        root: Path,
        manifest: dict[str, Any],
        *,
        limits: ReadLimits,
        index: IndexCheck,
        published: bool,
    ) -> None:
        """Check the manifest and the files, then rebuild and check each document."""
        if not isinstance(index, IndexCheck):
            raise TypeError("index must be an IndexCheck")
        self.root, self.manifest = root, manifest
        _check_format(manifest, limits)
        names = _check_inventory(
            root, manifest["files"], limits=limits, published=published
        )
        _check_canonical(root, manifest["files"], limits)
        self._primary = UUID(manifest["model"]["id"])
        # Each document is validated once, when it is rebuilt.
        super().__init__(self._rebuild(names, index))
        self._check_closure(limits)

    def _rebuild(self, names: list[str], index: IndexCheck) -> list[Document]:
        """Rebuild each document and require the exact files and Geometry paths."""
        m = self.manifest
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
            document, files = self._rebuild_document(descriptor, names, index)
            documents.append(document)
            expected_files.update(files)
            pin = _pin(document)
            if pin:
                path = "geometry" if m["geometry"] == pin else "assets/" + digest(pin)
                expected_geometry[str(document.id)] = path
                expected_files.update(self._geometry_files(pin, path))
        if set(names) != expected_files or m["geometry_paths"] != expected_geometry:
            raise ValueError("Unexpected Bundle files or Geometry paths")
        return documents

    def _rebuild_document(
        self,
        descriptor: dict[str, Any],
        names: list[str],
        index: IndexCheck,
    ) -> tuple[Document, set[str]]:
        """Rebuild one document from its tables; return it and its table files."""
        if set(descriptor) != _DESCRIPTOR_KEYS or descriptor["kind"] not in KINDS:
            raise ValueError("Invalid document descriptor")
        identifier = UUID(descriptor["id"])
        if str(identifier) != descriptor["id"]:
            raise ValueError("Noncanonical document identity")
        prefix = self._prefix(identifier)
        document = _DocumentReader(self.root, descriptor, prefix, names)._reconstruct(
            index
        )
        if _descriptor(document) != {
            k: v for k, v in descriptor.items() if k not in ("tables", "geometry")
        }:
            raise ValueError("Canonical document identity mismatch")
        if _pin(document) != descriptor["geometry"]:
            raise ValueError("Manifest Geometry pin differs from its Model")
        files = {t["path"] for t in descriptor["tables"]}
        files.update((f"{prefix}/records.parquet", f"{prefix}/references.parquet"))
        return document, files

    def _geometry_files(self, pin: Mapping[str, Any], path: str) -> list[str]:
        """Require that the manifest lists each file of a pin under path."""
        declared = [
            dict(entry, path=path + "/" + entry["path"]) for entry in pin["files"]
        ]
        if any(entry not in self.manifest["files"] for entry in declared):
            raise ValueError("Geometry inventory differs from its Model")
        return [entry["path"] for entry in declared]

    def _check_closure(self, limits: ReadLimits) -> None:
        """Require that the documents are the closure of the roots, and the identity."""
        roots = _check_roots(self.manifest["roots"])
        selected = [self._load(UUID(r["id"]), KINDS[r["kind"]]) for r in roots]
        if any(d.id == self._primary for d in selected):
            raise ValueError("Primary Model is already selected")
        closed = _collect(self.model(), selected, self, limits.documents)
        if set(closed._documents) != set(self._documents):
            raise ValueError("Unselected document outside dependency closure")
        found = identity(self.model(), documents=self.documents(), roots=roots)
        if found != self.manifest["id"]:
            raise ValueError("Canonical Bundle identity mismatch")

    def _prefix(self, identifier: UUID) -> str:
        return _prefix(identifier, self._primary)

    def model(self, id: UUID | None = None) -> Model:
        """Return the main Model, or the retained Model with the given UUID."""
        return self.load_model(self._primary if id is None else id)

    def geometry_path(self, id: UUID | None = None) -> Path | None:
        """Return the Geometry directory of a Model, or None if it has no Geometry.

        Without ``id``, return the directory of the main Model.
        """
        model = self.model(id)
        if model.geometry is None:
            return None
        return self.root / self.manifest["geometry_paths"][str(model.id)]

    def verify_geometry(self) -> None:
        """Check the files of each distinct Geometry pin with its provider.

        The provider is the one in ``providers`` for the pin, else the one
        registered under the pin's provider name.
        """
        checked = set()
        for document in self.documents():
            if not isinstance(document, Model) or document.geometry is None:
                continue
            pin = document.geometry.pin.to_data()
            if digest(pin) in checked:
                continue
            path = self.root / self.manifest["geometry_paths"][str(document.id)]
            _provider(pin, self.providers).validate(path, document.geometry)
            checked.add(digest(pin))

    def copy_to(self, store: RecordStore) -> tuple[dict[str, str], ...]:
        """Copy into an append-only store; retain IDs and reject conflicts first.

        Runs are published after their dependencies. This is idempotent, not a
        multi-document transaction: an IO failure can leave complete records.
        No workspace acceptance or investigation execution is implied. Return
        the kind and UUID of each document.
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
        document: UUID | None = None,
        kind: str | None = None,
        canonical_id: str | None = None,
        path: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return one page of the record index of a document, in record path order.

        Without ``document``, read the main Model. ``kind``, ``canonical_id`` and
        ``path`` filter the rows; ``path`` is a canonical record path, not a
        filesystem path. The result has the ``items`` of the page and the
        ``next_offset``, or None after the last page. No caller SQL is run.
        """
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
            raise MissingReferenceError(document, kind="document", where="Bundle")
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
