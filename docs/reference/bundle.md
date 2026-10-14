# Rangekeeper Bundle candidate

This is an implemented review candidate in RK `0.10.0.dev1`, not a stable public
interchange release. [ADR-008](../decisions/008-sqlite-model-package.md) retains the
full acceptance matrix. The [T1 record](../research/bundle-t1-2026-10-14/README.md)
separates this implementation from remaining provider, query and host work.

## Canonical Geometry

Model schema `0.8.0` adds optional `Geometry`; Specification and Run remain `0.7.0`.
The authority is [geometry.yaml](../../schema/geometry.yaml), imported by
[model.yaml](../../schema/model.yaml). Python/C#/JSON Schema and slot metadata are
generated from that authority. Geometry contains one exact pin and zero or more
mappings. The pin records provider, native format/version, immutable specification
identifier/digest, file inventory/content digest and optional source address/version.
Mappings join an Entity or Assembly UUID to an explicit typed source element.
They do not change membership, place an Entity or replace provenance.

`GeometryElement` has namespace, object/group kind, key, optional scope and ordered
placement path. RK checks canonical endpoint kinds, duplicate declared pairs and
inventory consistency. Provider adapters check native selector resolution,
ambiguous identities, structural groups, representations and required assets.
RK contains no Speckle SDK or provider catalogue. Other providers require an
explicit, independently tested adapter.

Reading an existing Model with schema 0.7.0 preserves it. Such a Model cannot
contain Geometry. `rangekeeper.io.migration.model_07_to_08(model, id=...)` explicitly
creates a new Model UUID, retains `previous`, and changes the schema version. It
does not modify the old artifact. Changing Geometry, mappings or canonical content
requires a new Model. DirectoryStore rejects changed content under an existing UUID.

## Directory format and identity

```text
<bundle>/
  manifest.json
  model/<schema class>.parquet
  model/records.parquet
  model/references.parquet
  geometry/<native files>        # absent for a Model-only Bundle
```

The format identifiers are `rangekeeper.bundle/1-proposal` and
`rangekeeper.parquet/1-proposal`. The manifest pins Model UUID/schema/digest,
slot-schema digest, table inventory and every file's relative path, byte size and
SHA-256. Its Geometry declaration must exactly match the canonical Model pin.

Bundle identity is SHA-256 of canonical JSON containing format, mapping and the
canonical Model digest. The Model digest uses RK schema-aware comparison data.
Unordered record collections are normalized for identity; ordered mathematical
collections retain order. Repacking RK Parquet compression or row groups preserves
logical identity. Geometry's exact byte inventory is already Model content, so
changing native bytes changes the logical content. The manifest does not hash itself.

A table is derived for each encountered schema class. Field state is absent,
explicit null or present. Typed tagged columns retain scalar and record union
branches; integers use exact decimal text and floats remain binary64. Lists and
keyed collections retain presence, order and empty containers. Embedded records
are linked by ownership paths. `records.parquet` and `references.parquet` are
validated derived indexes, not a second canonical authority. Opaque Claim Content
is inert JSON because the RK schema declares it opaque; the Model is never a
single JSON fallback file.

## Optional IO

Install `rangekeeper[bundle]` or `pip install '.[bundle]'` from this checkout.
The extra pins PyArrow 23.0.1 and DuckDB 1.4.3. Model imports require neither.
Use the explicit public module:

```python
from rangekeeper.io.bundle import write, Reader

manifest = write(new_directory, model)  # Model-only
restored = Reader(new_directory).model()
assert restored.to_data() == model.to_data()
```

For Geometry, pass its exact native directory and a provider implementing
`validate(root, geometry)` to `write`. No provider is selected from source text.
The writer validates the complete reconstruction and native bytes before publishing
the manifest. Existing destinations are never overwritten. Failed writes can leave
an unpublished directory for diagnosis. Core separately owns registered storage,
access control, catalogue updates and workspace acceptance.

`Reader(root, provider=...)` checks the manifest, supported pins, closed inventory,
file paths, Model file hashes, typed table shape, reconstruction and derived indexes.
`verify_geometry()` checks native bytes/semantics through the explicit provider.
Ordinary RK record queries do not read Geometry blobs. A reader for a changed or
untrusted delivery must verify Geometry before accepting native content.

`records(kind=None, offset=0, limit=100)` returns stable path-ordered summaries and
an optional `next_offset`. Limits are 1–1,000 returned rows. The reader rejects more
than 10,000 files, 4 GiB total retained bytes, 256 MiB compressed Model data,
512 MiB expanded Model table data or one million Model rows by default. These are
proof bounds, not validated production capacity. The reference reader reconstructs
at mount and registers Arrow data with a bounded DuckDB connection for projections.
It does not provide the full proposed evidence/graph/asset catalogue.

## Remaining acceptance

The current native adapter in Core covers a pinned subset of Speckle spec 1.4.1:
unquantized SGEO v1 meshes and lines, explicit object/group mappings and nested
instance transform chains. A tested subset is not all native formats or general
BRep support. Full scalar/presence/union adversarial coverage, all source evidence
and change cases, large-scale hostile-file handling, complete query projections,
render conversions and real-host consistency remain in P1–P8. Preserve the
concrete format review before project adoption.
