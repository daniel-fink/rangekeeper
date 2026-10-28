# Rangekeeper Bundle

The Bundle format is not yet stable. [ADR-008](../decisions/008-rangekeeper-bundle-contract.md)
holds the full acceptance matrix. [ADR-017](../decisions/017-api-and-formats.md)
makes format 1 stable at milestone 1.0.0b1. Provider, query and host acceptance
remain separate from the implemented canonical reader and writer.

## Canonical Geometry

The Model, Specification and Run formats are `1.0.0` ([ADR-017](../decisions/017-api-and-formats.md)). A Model has an optional `Geometry`.
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

Changing Geometry, mappings or canonical content requires a new Model.
DirectoryStore rejects changed content under an existing UUID. The reader does not
read 0.x documents; see [upgrading](../guides/upgrading.md).

## Investigation contents and dependency closure

A Bundle has one main Model and may select additional Models, Specifications and
finalized Runs. The reader retains the exact input Models, included/case
Specifications, child Runs, outputs and scoped report documents needed to interpret
those selections. Historical predecessors are not followed automatically. A root
may select earlier history explicitly. Unrelated extra records are rejected.

The main Model is the initial inspection target, not an acceptance decision.
A Model-only Bundle remains valid. Saved partial Specifications and failed Runs can
be retained; their inclusion does not claim numerical validity or execution support.
Resolved Run validation checks retained references and evidence. Reading never
executes a Specification. The consumer application owns live operations, workspace state and acceptance.

## Directory format and identity

```text
<bundle>/
  manifest.json
  model/<schema class>.parquet
  model/records.parquet
  model/references.parquet
  documents/<UUID>/<schema class>.parquet
  documents/<UUID>/records.parquet
  documents/<UUID>/references.parquet
  geometry/<native files>             # main Model's pin, if present
  assets/<pin digest>/<native files>  # other distinct pins
```

The writer uses the format identifier `rangekeeper.bundle/2-proposal` with the mapping
identifier `rangekeeper.parquet/1-proposal`. ADR-017 replaces them with
`rangekeeper.bundle/1` and `rangekeeper.parquet/1`.
The table mapping is unchanged and now applied to all three canonical root kinds.
The main Model descriptor is `model`, with its `tables` and `geometry` fields.
`documents` contains descriptors, table inventories and Geometry pins for the other
roots. `roots` lists the explicitly selected typed UUIDs beyond the main Model.
`geometry_paths` maps spatial Model UUIDs to their dataset directory. Equal complete
Geometry pins share bytes; each Model keeps its own canonical pin and mappings.

Bundle identity hashes format, mapping, main Model UUID, selected roots and the
sorted complete set of typed document UUIDs/canonical digests. Canonical record
identity and Bundle identity are distinct. Adding a Run changes the Bundle ID;
unchanged Models/Specifications keep their identities. Parquet repacking preserves
logical identity. Byte changes to Geometry require new canonical pins. The manifest
records every retained file's size and SHA-256; it does not hash itself.

Schema-derived columns retain absent/null/present states, typed unions, exact
integers, floating representations, collection order and opaque schema content.
A currency amount is the `Amount` option of the magnitude union: a `string`
field with its canonical text ([currency amounts](units.md#currency-amounts)).
A reader casts it to `DECIMAL(38, s)` or `DOUBLE` for analysis.
Record/reference indexes are checked against reconstruction. No canonical root is
stored as an opaque JSON fallback.

## Public optional IO

Install `rangekeeper[bundle]`. Domain imports still require neither Arrow nor DuckDB.
Use the explicit `rangekeeper.io.bundle` module:

```python
from rangekeeper.io.bundle import write, Reader

manifest = write(
    new_directory,
    result_model,
    documents=[run, next_specification],
    resolver=record_store,
)
reader = Reader(new_directory)
result = reader.model()  # main Model
inputs = reader.load_model(input_uuid)  # exact retained Model
spec = reader.load_specification(spec_uuid)
run = reader.load_run(run_uuid)
records = reader.documents()  # immutable roots, UUID order
reader.copy_to(new_record_store)  # no execution or acceptance
```

`documents=` selects root facades. `resolver=` supplies dependencies through the
public typed resolver. Missing/wrong-kind/wrong-identity records and Specification
dependency cycles fail. Run validation uses the complete retained resolver.
The writer checks round trips and publishes the manifest last. Existing destinations
are never overwritten; a failed write can leave an unpublished directory.

For the main Model, `geometry=` and `provider=` remain convenient single-source
arguments. `geometries={model_uuid: directory}` supplies native directories;
`providers={(provider, format, format_version): adapter}` supplies trusted decoders.
When neither argument supplies an adapter for a pin, the writer and
`verify_geometry()` use the provider registered under the pin's provider name in
`rangekeeper.io.geometry_providers` ([extension points](extensions.md)).
A source for one Model can serve another with the same complete pin. Unknown or
undeclared sources fail. `geometry_path(model_uuid)` locates its retained dataset.
`verify_geometry()` checks every distinct pin, including supporting Models when the
main Model has no Geometry. Ordinary canonical reads do not decode Geometry blobs.

`records(document=uuid, kind=None, canonical_id=None, path=None, offset=0, limit=100)` projects
one exact root; omission selects the main Model. Rows are ordered by their local
record path, compared segment by segment: array indices compare as numbers and
before names, so `/system/entities/2` precedes `/system/entities/10` and a record
precedes its children. Optional `path` is an exact canonical record path, never a filesystem path.
The query reads the verified Parquet index through parameterised DuckDB with
predicate/limit pushdown and 128 MB working memory; no full Arrow index copy precedes
the query. Opening still reconstructs and verifies all retained documents. It
validates each document once; caller-owned documents given to `write` are
validated again as detached snapshots.
`Reader(path, check_index=False)` skips comparing the derived record and
reference index with the reconstructed documents; it still checks their schemas
and file hashes. Use it only for a Bundle whose index a full open already
verified, with files unchanged since.
Offsets are scoped to that root and query. Limits are 1–1,000 rows.
The reader limits the Bundle to 1,000 documents, 10,000 files, 4 GiB retained bytes,
256 MiB compressed canonical tables, 512 MiB declared expanded table bytes and one
million physical canonical/index rows by default. These are proof bounds, not
validated production capacity or a hard native-call deadline.

`copy_to(store)` preflights identity conflicts and publication order, then publishes
complete records before dependent Runs. A cyclic Run publication dependency fails
before writes. This is idempotent but not a multi-document transaction; storage IO
failure can leave complete records. Further work explicitly creates revised
Specifications and new Runs/Models. The original Bundle remains unchanged.

## Earlier Bundle versions

The reader rejects the earlier `rangekeeper.bundle/1-proposal` version. To move its
records, use the matching earlier reader and an explicit reviewed export. No
in-place or automatic conversion is supplied. The Bundle expansion did not change
the Model, Specification or Run schema versions.

## Remaining acceptance

Full scalar, presence and union adversarial coverage, all source evidence and
change cases, large-scale hostile-file handling, provider queries, rendering
conversions and real-host consistency remain in P1–P8. Canonical Parquet checks
do not establish native provider, application service or browser acceptance.
Preserve these gates before broader adoption or stable-format release.
