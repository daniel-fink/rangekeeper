"""Experimental RK SQLite package. This module is not an installed RK API.

The published Model schema is unchanged. Geometry is an experimental package
extension, pinned by the package content digest until its domain contract is reviewed.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, closing
import gzip
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zlib

from rangekeeper.io import json as codec
from rangekeeper.io.speckle import validate_associations
from rangekeeper.model import Model


FORMAT = "rk.sqlite-experiment/1"
GEOMETRY_FORMAT = "speckle-object-transport/1"
APPLICATION_ID = 0x524B5350  # RKSP; experimental, not a registered file format.
SCHEMA_BYTES = files("rangekeeper.schema").joinpath("slots.json").read_bytes()
SLOTS = json.loads(SCHEMA_BYTES)


def encoded(value):
    """Preserve JSON scalar types and array order; ignore object-key order only."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def sha(data):
    return hashlib.sha256(data).hexdigest()


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def pointer(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def schema_sql():
    """Generate one table per RK record kind from its generated slot contract.

    SQL NULL denotes an absent field. JSON text 'null' denotes a present null.
    Embedded records have separate rows; child links replace placeholder nulls.
    JSON cells retain exact numbers and unions until a typed SQL mapping is reviewed.
    """
    sql = [
        "CREATE TABLE package (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE documents (name TEXT PRIMARY KEY, data BLOB NOT NULL)",
        "CREATE TABLE records (path TEXT PRIMARY KEY, kind TEXT NOT NULL, "
        "canonical_id TEXT UNIQUE, owner_id TEXT)",
        "CREATE INDEX records_kind ON records(kind, canonical_id)",
        "CREATE INDEX records_owner ON records(owner_id)",
        "CREATE TABLE children (parent TEXT NOT NULL REFERENCES records(path), "
        "slot TEXT NOT NULL, locator TEXT NOT NULL, "
        "child TEXT NOT NULL UNIQUE REFERENCES records(path), "
        "PRIMARY KEY(parent,slot,locator))",
        "CREATE TABLE refs (parent TEXT NOT NULL REFERENCES records(path), "
        "slot TEXT NOT NULL, position INTEGER NOT NULL, "
        "target TEXT NOT NULL REFERENCES records(canonical_id), "
        "PRIMARY KEY(parent,slot,position))",
        "CREATE INDEX refs_target ON refs(target)",
        "CREATE TABLE geometry (id TEXT PRIMARY KEY, digest TEXT NOT NULL, "
        "raw_bytes INTEGER NOT NULL, data BLOB NOT NULL)",
        "CREATE TABLE geometry_refs (source TEXT REFERENCES geometry(id), "
        "target TEXT REFERENCES geometry(id), PRIMARY KEY(source,target))",
        "CREATE TABLE associations (position INTEGER PRIMARY KEY, "
        "domain_id TEXT NOT NULL REFERENCES records(canonical_id), "
        "geometry_id TEXT NOT NULL REFERENCES geometry(id), data TEXT NOT NULL)",
    ]
    for kind, fields in sorted(SLOTS.items()):
        columns = ["path TEXT PRIMARY KEY REFERENCES records(path)"]
        columns += [
            f"{quoted(name)} TEXT CHECK ({quoted(name)} IS NULL OR json_valid({quoted(name)}))"
            for name in fields
        ]
        sql.append(f"CREATE TABLE {quoted('rk_' + kind)} ({', '.join(columns)})")
    return ";\n".join(sql) + ";\n"


def insert_model(db, model):
    """Shred only schema-declared records; opaque evidence stays opaque."""

    def visit(kind, data, path="", owner=None):
        fields = SLOTS[kind]
        identity = data.get("id") if "id" in fields else None
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?)", (path, kind, identity, owner)
        )
        cells = dict(data)
        for name, value in data.items():
            meta = fields[name]
            record_kinds = [
                o["kind"]
                for o in meta["options"]
                if o["category"] in ("record", "keyed")
            ]
            if value is None:
                continue
            entries = (
                list(value.items())
                if meta["mapping"]
                else list(enumerate(value)) if meta["many"] else [(None, value)]
            )
            if record_kinds:
                # A reviewed mapping is required if a slot gains two record alternatives.
                if len(record_kinds) != 1:
                    raise ValueError(f"unsupported record union: {kind}.{name}")
                replacement = (
                    dict(value)
                    if meta["mapping"]
                    else list(value) if meta["many"] else value
                )
                for index, item in entries:
                    if not isinstance(item, dict):
                        continue
                    child = path + "/" + pointer(name)
                    if index is not None:
                        child += "/" + pointer(index)
                    visit(record_kinds[0], item, child, identity or owner)
                    db.execute(
                        "INSERT INTO children VALUES (?,?,?,?)",
                        (path, name, encoded(index), child),
                    )
                    if index is None:
                        replacement = None
                    else:
                        replacement[index] = None
                cells[name] = replacement
            local_ref = any(
                o["category"] == "uuid" and o["kind"] != "UUID" for o in meta["options"]
            )
            # Previous is an external revision link; a complete Model does not
            # require the predecessor. Its exact value remains in rk_Metadata.
            if local_ref and (kind, name) != ("Metadata", "previous"):
                for position, (_, item) in enumerate(entries):
                    if isinstance(item, str):
                        db.execute(
                            "INSERT INTO refs VALUES (?,?,?,?)",
                            (path, name, position, item),
                        )
        columns = ["path", *cells]
        db.execute(
            f"INSERT INTO {quoted('rk_' + kind)} ({','.join(map(quoted, columns))}) "
            f"VALUES ({','.join('?' for _ in columns)})",
            [path, *[encoded(v) for v in cells.values()]],
        )

    visit("Model", model.to_data())


def geometry_dependencies(value, *, include_closure=True):
    """Find detached references and closure declarations in the pinned old format."""
    result = set()
    if isinstance(value, dict):
        # The experiment retains object records, not external files. Do not claim
        # a complete package when a source asks a consumer to fetch another asset.
        for name in ("url", "filePath", "fileUrl", "textureUrl"):
            if value.get(name):
                raise ValueError(f"unsupported external geometry asset: {name}")
        if "blob" in str(value.get("speckle_type", "")).lower():
            raise ValueError("external Speckle blob requires a separate asset mapping")
        if value.get("speckle_type") == "reference":
            target = value.get("referencedId")
            if not isinstance(target, str) or not target:
                raise ValueError("invalid detached geometry reference")
            result.add(target)
        closure = value.get("__closure", {})
        if not isinstance(closure, dict):
            raise ValueError("invalid geometry closure")
        if include_closure:
            result.update(closure)
        for child in value.values():
            result.update(geometry_dependencies(child, include_closure=include_closure))
    elif isinstance(value, list):
        for child in value:
            result.update(geometry_dependencies(child, include_closure=include_closure))
    return result


def check_geometry(model, transport, associations, descriptor):
    if descriptor is None:
        if transport or associations:
            raise ValueError("geometry data requires a format descriptor")
        return [], {}
    if descriptor.get("format") != GEOMETRY_FORMAT:
        raise ValueError("unsupported geometry format")
    if descriptor.get("root_id") not in transport:
        raise ValueError("missing geometry root")
    associations = validate_associations(model, associations)
    for item in associations:
        if item.get("content_id") not in transport:
            raise ValueError(f"missing associated geometry: {item.get('content_id')}")
    dependencies = {}
    for identity, text in transport.items():
        obj = codec._parse(text)
        if not isinstance(obj, dict) or obj.get("id") != identity:
            raise ValueError(f"geometry identity mismatch: {identity}")
        dependencies[identity] = geometry_dependencies(obj, include_closure=False)
        missing = geometry_dependencies(obj) - transport.keys()
        if missing:
            raise ValueError(f"missing geometry dependencies: {sorted(missing)[:3]}")
    reached, pending = set(), [
        descriptor["root_id"],
        *[a["content_id"] for a in associations],
    ]
    while pending:
        current = pending.pop()
        if current not in reached:
            reached.add(current)
            pending.extend(dependencies[current])
    if reached != set(transport):
        raise ValueError("unreachable geometry records")
    return associations, dependencies


def build(destination, model_text, transport=None, associations=(), descriptor=None):
    """Validate and publish a new complete file. Existing destinations are preserved."""
    destination = Path(destination)
    transport = {} if transport is None else transport
    model = codec.loads(model_text, kind=Model)
    associations, dependencies = check_geometry(
        model, transport, associations, descriptor
    )
    model_digest = sha(encoded(model.to_data()).encode())
    geometry_digests = {
        key: sha(value.encode()) for key, value in sorted(transport.items())
    }
    manifest = {
        "format": FORMAT,
        "model_id": str(model.id),
        "model_schema_version": model.metadata.schema_version,
        "model_digest": model_digest,
        "geometry": descriptor,
        "geometry_digests": geometry_digests,
        "associations": associations,
    }
    metadata = {
        "format": FORMAT,
        "model_id": str(model.id),
        "model_digest": model_digest,
        "content_digest": sha(encoded(manifest).encode()),
        "source_digest": sha(model_text.encode()),
        "slots_digest": sha(SCHEMA_BYTES),
        "manifest": manifest,
    }
    descriptor_fd, temporary = tempfile.mkstemp(
        prefix=".rk-sqlite-", dir=destination.parent
    )
    os.close(descriptor_fd)
    temporary = Path(temporary)
    try:
        with closing(sqlite3.connect(temporary)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            db.execute("PRAGMA user_version=1")
            db.executescript(schema_sql())
            db.execute("BEGIN")
            db.execute("PRAGMA defer_foreign_keys=ON")
            db.executemany(
                "INSERT INTO package VALUES (?,?)",
                [(k, encoded(v)) for k, v in metadata.items()],
            )
            db.executemany(
                "INSERT INTO documents VALUES (?,?)",
                [("model.json", model_text.encode()), ("slots.json", SCHEMA_BYTES)],
            )
            insert_model(db, model)
            for identity, text in sorted(transport.items()):
                raw = text.encode()
                db.execute(
                    "INSERT INTO geometry VALUES (?,?,?,?)",
                    (identity, sha(raw), len(raw), zlib.compress(raw)),
                )
            db.executemany(
                "INSERT INTO geometry_refs VALUES (?,?)",
                [
                    (key, target)
                    for key, refs in dependencies.items()
                    for target in sorted(refs)
                ],
            )
            db.executemany(
                "INSERT INTO associations VALUES (?,?,?,?)",
                [
                    (i, a["domain_id"], a["content_id"], encoded(a))
                    for i, a in enumerate(associations)
                ],
            )
            db.commit()
        with Reader(temporary) as reader:
            reader.verify()
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(
            temporary, destination
        )  # Atomic create; never overwrite an accepted file.
    finally:
        temporary.unlink(missing_ok=True)
    return metadata


class Reader(AbstractContextManager):
    """Read-only experimental queries. Opening reads metadata, never geometry blobs."""

    def __init__(self, path):
        self.db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA query_only=ON")
            self.db.execute("PRAGMA trusted_schema=OFF")
            if self.db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                raise ValueError("not an RK experiment file")
            if self.db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("unsupported storage version")
            self.metadata = {
                r["key"]: json.loads(r["value"])
                for r in self.db.execute("SELECT * FROM package")
            }
            if self.metadata["format"] != FORMAT or self.metadata[
                "slots_digest"
            ] != sha(SCHEMA_BYTES):
                raise ValueError("unsupported package or RK slot contract")
        except BaseException:
            self.db.close()
            raise

    def __exit__(self, *args):
        self.db.close()

    def record_at(self, path):
        row = self.db.execute(
            "SELECT kind FROM records WHERE path=?", (path,)
        ).fetchone()
        if row is None:
            raise KeyError(path)
        kind = row[0]
        if kind not in SLOTS:
            raise ValueError(f"unknown record kind: {kind}")
        cells = self.db.execute(
            f"SELECT * FROM {quoted('rk_' + kind)} WHERE path=?", (path,)
        ).fetchone()
        if cells is None:
            raise ValueError(f"missing record row: {path}")
        value = {k: json.loads(cells[k]) for k in SLOTS[kind] if cells[k] is not None}
        for child in self.db.execute(
            "SELECT * FROM children WHERE parent=?", (path,)
        ).fetchall():
            locator = json.loads(child["locator"])
            # Only forward, schema-shaped paths can be reconstructed.
            expected = path + "/" + pointer(child["slot"])
            if locator is not None:
                expected += "/" + pointer(locator)
            if child["child"] != expected:
                raise ValueError("invalid embedded record path")
            item = self.record_at(child["child"])
            if locator is None:
                value[child["slot"]] = item
            else:
                value[child["slot"]][locator] = item
        return value

    def model(self):
        """Reconstruct from generated tables, independently of the retained document."""
        return Model.from_data(self.record_at(""))

    def object(self, identity):
        row = self.db.execute(
            "SELECT path FROM records WHERE canonical_id=?", (str(identity),)
        ).fetchone()
        if row is None:
            raise KeyError(str(identity))
        return self.record_at(row[0])

    @staticmethod
    def _page(limit, offset):
        if (
            type(limit) is not int
            or not 1 <= limit <= 200
            or type(offset) is not int
            or offset < 0
        ):
            raise ValueError("limit must be 1..200; offset must be nonnegative")

    def objects(self, *, limit=50, offset=0):
        self._page(limit, offset)
        rows = self.db.execute(
            "SELECT canonical_id,kind FROM records WHERE kind IN ('Entity','Assembly','Relationship') "
            "ORDER BY canonical_id LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(row) for row in rows]

    def members(self, assembly_id, *, limit=50, offset=0):
        self._page(limit, offset)
        parent = self.db.execute(
            "SELECT path,kind FROM records WHERE canonical_id=?", (str(assembly_id),)
        ).fetchone()
        if parent is None or parent["kind"] != "Assembly":
            raise ValueError("membership requires an Assembly")
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT slot,position,target FROM refs WHERE parent=? AND slot IN ('entities','relationships') "
                "ORDER BY slot,position LIMIT ? OFFSET ?",
                (parent["path"], limit, offset),
            )
        ]

    def geometry_object(self, identity):
        row = self.db.execute(
            "SELECT * FROM geometry WHERE id=?", (identity,)
        ).fetchone()
        if row is None:
            raise KeyError(identity)
        try:
            raw = zlib.decompress(row["data"])
        except zlib.error as error:
            raise ValueError(f"invalid compressed geometry: {identity}") from error
        expected = self.metadata["manifest"]["geometry_digests"].get(identity)
        if (
            len(raw) != row["raw_bytes"]
            or sha(raw) != row["digest"]
            or sha(raw) != expected
        ):
            raise ValueError(f"geometry checksum mismatch: {identity}")
        return raw.decode()

    def verify(self):
        """Full acceptance scan. This deliberately reads geometry; normal queries do not."""
        if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        if self.db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("dangling SQLite reference")
        model = self.model()
        original = self.db.execute(
            "SELECT data FROM documents WHERE name='model.json'"
        ).fetchone()[0]
        original_model = codec.loads(original.decode(), kind=Model)
        if sha(original) != self.metadata["source_digest"]:
            raise ValueError("source document checksum mismatch")
        actual = sha(encoded(model.to_data()).encode())
        if actual != self.metadata["model_digest"] or encoded(
            model.to_data()
        ) != encoded(original_model.to_data()):
            raise ValueError("Model reconstruction mismatch")
        manifest = self.metadata["manifest"]
        if str(model.id) != self.metadata["model_id"] or manifest["model_id"] != str(
            model.id
        ):
            raise ValueError("Model revision mismatch")
        if (
            manifest["model_digest"] != actual
            or sha(encoded(manifest).encode()) != self.metadata["content_digest"]
        ):
            raise ValueError("package content checksum mismatch")
        slots = self.db.execute(
            "SELECT data FROM documents WHERE name='slots.json'"
        ).fetchone()[0]
        if slots != SCHEMA_BYTES:
            raise ValueError("retained schema checksum mismatch")
        # Check derived lookup rows as well as reconstruction. A deleted ref must
        # not pass merely because its original field still exists in a record row.
        with closing(sqlite3.connect(":memory:")) as expected:
            expected.executescript(schema_sql())
            insert_model(expected, original_model)
            for table in ("records", "children", "refs", *["rk_" + k for k in SLOTS]):
                sql = f"SELECT * FROM {quoted(table)} ORDER BY 1"
                if sorted(map(tuple, self.db.execute(sql)), key=repr) != sorted(
                    expected.execute(sql).fetchall(), key=repr
                ):
                    raise ValueError(f"derived record mismatch: {table}")
        ids = [r[0] for r in self.db.execute("SELECT id FROM geometry ORDER BY id")]
        if set(ids) != set(manifest["geometry_digests"]):
            raise ValueError("geometry inventory mismatch")
        transport = {identity: self.geometry_object(identity) for identity in ids}
        associations = [
            json.loads(r[0])
            for r in self.db.execute("SELECT data FROM associations ORDER BY position")
        ]
        if associations != manifest["associations"]:
            raise ValueError("geometry association mismatch")
        _, dependencies = check_geometry(
            model, transport, associations, manifest["geometry"]
        )
        expected_refs = {
            (key, target) for key, targets in dependencies.items() for target in targets
        }
        if (
            set(map(tuple, self.db.execute("SELECT source,target FROM geometry_refs")))
            != expected_refs
        ):
            raise ValueError("geometry dependency index mismatch")
        expected_associations = [
            (i, a["domain_id"], a["content_id"], encoded(a))
            for i, a in enumerate(associations)
        ]
        if (
            list(
                map(
                    tuple,
                    self.db.execute("SELECT * FROM associations ORDER BY position"),
                )
            )
            != expected_associations
        ):
            raise ValueError("geometry association index mismatch")
        return {
            "model_id": str(model.id),
            "records": self.db.execute("SELECT count(*) FROM records").fetchone()[0],
            "geometry_records": len(ids),
            "associations": len(associations),
            "content_digest": self.metadata["content_digest"],
        }


def capture_inputs(source):
    """Read the existing pinned walkthrough capture; never contact a source service."""
    source = Path(source)
    manifest = json.loads((source / "manifest.json").read_text())
    contents = {}
    for name in ("model.json", "transport.json.gz", "associations.json"):
        contents[name] = (source / name).read_bytes()
        if sha(contents[name]) != manifest["files"][name]["sha256"]:
            raise ValueError(f"capture checksum mismatch: {name}")
    return (
        contents["model.json"].decode(),
        json.loads(gzip.decompress(contents["transport.json.gz"])),
        json.loads(contents["associations.json"]),
        {
            "format": GEOMETRY_FORMAT,
            "root_id": manifest["requested_object_id"],
            "source_manifest": manifest,
            "placement": "preserved in retained geometry",
            "units": "preserved per source object",
        },
    )
