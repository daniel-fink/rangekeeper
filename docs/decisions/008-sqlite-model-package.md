# ADR-008: Model and Speckle Package contract

Status: Package contract agreed on 13 October 2026; implementation pending. The
SQLite development experiment is retained as earlier evidence. It does not
implement this contract. No installed API or public Model schema changes here.

## Intention

Support source files → informed user decisions → a reproducible RK Model →
inspection. Keep the Speckle source package beside the Model, with explicit,
verifiable links between them. The same Package must support independent browser,
ChatGPT and future native interfaces without making a renderer part of RK semantics.

## Contract and terms

**One Speckle-backed Package contains exactly one immutable Model, pinned to
exactly one Speckle bundle. The Model owns the bundle pin and the mappings.**

| Term | Meaning |
| --- | --- |
| Model | The canonical RK Model, including its source bundle pin and mappings under the future schema. Use “new Model” when this content changes; no separate “RK revision” object is introduced. |
| Speckle bundle | The retained native source package: objects, properties, relations, geometry and required assets. It is not reduced to a mesh collection or flattened into RK entities. |
| Package | The immutable delivery unit that identifies and contains that Model and its exact bundle. A manifest records their identities and integrity information. |

This is a **Speckle-backed Package profile**. Ordinary RK Models without geometry
or a Speckle source remain valid. They do not require an empty fabricated bundle.
The schema extension, migration and concrete field names remain implementation work.

The Model's pin must identify exact bundle content by a digest and retain its
Speckle project/model/version address when available. A mutable alias such as
`latest` is not a pin. A different pinned source version creates a new Model even
when its bundle bytes happen to match. Record an unavailable source version as
unavailable; do not invent one or use a URL as an integrity check.

Mappings belong to the Model. They identify their RK target and the source bundle,
object, property, relation or geometry representation they address. Source key
spaces and scopes must be explicit: object IDs, relation node IDs, geometry IDs,
application IDs and instance paths are not interchangeable. Allow many-to-many
associations and valid RK objects with no source association. Do not assume one
Speckle object equals one RK Entity. Mappings can also concern Values and Relationships.

### Change rules

| Change | Model | Speckle bundle | Package |
| --- | --- | --- | --- |
| RK domain content changes | New Model | Same bundle may be reused | New Package |
| Source bundle content changes | New Model, because its pin changes | New bundle content | New Package |
| Pinned Speckle source version changes | New Model, even if source bytes match | Retain exact content and new version address | New Package |
| Mapping or canonical association changes | New Model | Same bundle may be reused | New Package |
| Model pin or other canonical Package content changes | New Model if Model content changes | Exact content remains pinned | New Package |
| Camera, selection, renderer conversion or render cache changes outside canonical contents | Same Model | Same bundle | Same Package |
| Copy, archive compression or derived SQLite index changes, with identical canonical contents | Same Model | Same bundle | Same Package; delivery file hash may differ |

Stable Entity and Value UUIDs can persist across Models. The Model identity must
change when its canonical content changes. Reject any attempt to publish one
Model identity with a different bundle pin or mappings. Never silently update the
bundle under an existing Package. Retaining an unchanged bundle in several Packages
is valid; each Package must still resolve its exact content independently.

This rule applies when a Package is built or published. Editing can use a mutable
workspace before publication; it does not mutate an already published Package.

### Integrity and physical storage

Keep the native Speckle bundle adjacent to the RK data. Logical separation does
not require separate downloads: a portable container could contain a manifest,
an RK SQLite database and the original Speckle files. This supersedes the earlier
“one Model = one physical SQLite file” proposal. SQLite remains a candidate RK
store; the archive format, database layout and canonical digest algorithm are not
adopted by this decision. Native bundle bytes must survive packaging unchanged.

Separate logical Model/Package identity from a delivery file's byte hash. The
bundle digest must cover a defined, complete source file inventory. The Package
manifest must bind the Model and bundle and their required format/schema versions.
There must be no circular hash: the Model pins the source bundle; the outer Package
identifies the Model and bundle. The Model must not contain its enclosing Package
digest. Derived database indexes and rendering caches cannot become new authorities
for mappings or source content.

Validate the pin, contents, source selectors, RK targets and required asset closure
before accepting a Package. A valid package does not prove that a user's source
interpretation is correct. Source acceptance remains an explicit ingestion step.
There is no automatic bidirectional synchronisation between the two models.

## Ownership and geometry boundary

| Owner | Responsibility |
| --- | --- |
| Rangekeeper | Canonical Model schema, source binding and representation contract, Model identity, serialisation and semantic validation |
| Speckle specification and source adapter | Native bundle format and source semantics; format-specific decoding and source integrity checks |
| Whirlwind MCP | Source acquisition, user decisions, builds, Package assembly/publication and authorised service access |
| Whirlwind Viewer | Bounded projections, component queries, geometry conversion, rendering and host adapters |
| Hosting application | Package/Model catalogue, users, permissions and session state |

Specification and Run retain their separate meanings. Preserve provenance without
requiring every original source-workspace file to be a Package asset. The chosen
source profile must declare what it contains and what is required for offline use.

Define a general source binding/representation contract before deciding whether to
add a geometry Value kind or store a geometry binding in characteristics. Do not
copy Speckle's geometry schema into RK or force its entire graph into RK's schema.
Keep source properties and relations available for inspection even when they have
no RK counterpart. EAV means entity–attribute–value; a source property table using
that layout does not make the source graph equivalent to the RK domain model.

Preserve source units, coordinate systems, transform chains, nested instances and
placement identity. RK Assembly membership does not define spatial placement.
Source geometry roles such as DISPLAY, SOLID and CENTERLINE have distinct meanings;
source containment and hosting relations must not automatically become RK membership.
Keep authored geometry and source appearance in the retained bundle. An interface
owns triangulation, level of detail, display-only overrides, camera and caches.
A different web or native renderer can display the same Package differently without
changing it. An edit to retained source geometry or placement creates a new Package.

Use format-specific adapters for native bundles and legacy Speckle object graphs.
Do not require legacy root objects, detached references or `__closure` fields in
the native bundle contract. The existing capture and viewer loader prove only the
legacy path. Pin the actual bundle specification commit, schema version and decoder
versions when implementing the native path; following `main` is not a compatibility test.

Primary source specifications: [Speckle bundle specification](https://github.com/specklesystems/speckle-bundle-spec),
[relations](https://docs.speckle.systems/next/developers/object-model/relations) and
[viewer bundle loading](https://docs.speckle.systems/next/developers/viewer/loading-bundles).
These define source formats and adapter options, not local implementation acceptance.

## Earlier SQLite experiment — not Package conformance

The [prototype](../../tools/sqlite_spike/package.py) derives record tables and
columns from the generated `src/rangekeeper/schema/slots.json` contract. That
contract comes from the authoritative LinkML schema. There is no second handwritten
list of domain fields and no dependency on Payload's physical database structure.

| Storage | Rule |
| --- | --- |
| `rk_<RecordKind>` | One row per embedded record, located by its original JSON pointer. Fields use exact JSON text. SQL NULL means absent; text `null` means present null. |
| `children` | Links embedded records to their containing slot and array position or mapping key. Empty containers, order and multiplicity remain intact. |
| `records` | Canonical UUID, record kind and nearest identified owner. Anonymous records have paths, not invented domain IDs. Opaque Claim content is not traversed. |
| `refs` | Schema-declared local UUID references. `Metadata.previous` remains an external revision reference in its original field; no predecessor is required. |
| `geometry` | Original UTF-8 object records, independently compressed, with SHA-256 checksums. Speckle IDs remain opaque transport IDs. |
| `geometry_refs` | Direct detached references only. Original closure declarations are retained and checked, but their transitive edges are not duplicated in this index. |
| `associations` | Validated legacy Model identity and Entity/Assembly association with a retained geometry record. |
| `documents` | Exact original Model JSON and the slot contract. These are comparison evidence; reconstruction reads generated record tables. |
| `package` | Format version, Model identity, checksums and geometry descriptor. |

This deliberately preserves values in JSON cells rather than choosing a SQL type
for every union. It proves lossless, schema-driven storage; it does not establish
the final numeric indexing or query design. Python Model validation remains the
semantic boundary. SQL constraints do not replace it.

The initial geometry codec is `speckle-object-transport/1`, tested with the retained
SpecklePy 3.0.7 capture. It checks root presence, detached references, closure IDs,
reachability and canonical associations. It rejects detected external file/blob
references. Other Speckle formats, external textures and general source-format
completeness need their own codec and conformance fixtures. Unknown source
semantics cannot be certified by a recursive JSON scan.

The complete source object graph is retained, including source BReps and existing
display meshes. Keeping a source display mesh does not require an interface to use
that mesh. The spike's alternate conversion is a planar quad test; it is not a
general BRep tessellator or a native iOS implementation.

### Experimental identity and publication

| Identifier | Meaning in this experiment |
| --- | --- |
| Model UUID | The unchanged public Model 0.7.0 identity; its current contract excludes geometry |
| Model digest | SHA-256 of validated Model JSON with sorted object keys, exact scalar types and retained array order |
| Package content digest | Model digest, geometry format/descriptor, exact geometry-record hashes and associations |
| Database file hash | Exact SQLite bytes, including physical layout and indexes |

Experimental consumers must pin the package content digest as well as the Model
UUID. Geometry can still change under the same legacy Model UUID because public
geometry fields and revision enforcement are deliberately not implemented yet.
Adoption must close that gap; a package digest is not a substitute for the future
Model identity rule. The digest is also not RK schema equivalence: array order and
original geometry encoding affect it. A storage/index change alone can leave the
content digest unchanged while changing the database file hash.

The builder validates input, writes a private database in one transaction, closes
it, verifies reconstruction and assets, then publishes with a no-overwrite file
link. It uses rollback-journal mode so the finished artifact has no required WAL
sidecar. This is local atomic publication, not a distributed publication protocol
or a cross-file identity registry. Power-loss durability and platform-specific
publication behaviour need separate acceptance before production use.

### Experimental queries and checks

The experiment provides bounded object-ID pages and direct Assembly membership
pages, canonical record lookup, geometry-object retrieval, Model reconstruction
and a full verification scan. Query tests deny access to the geometry and retained
document tables while object and membership reads run. Reconstruction is checked
against the retained document; derived lookup tables and geometry indexes are also
checked, so a missing index row cannot silently change a query result.

Object lookup reconstructs the selected record's full embedded content. It is not
yet a bounded value/evidence API. Opening loads the geometry-hash manifest but no
geometry blobs. Full validation intentionally reads all content and must precede
trusting a received artifact. The reader is an experiment for trusted local files,
not a hostile-file parser or an externally exposed SQL service.

See [the local evidence](../research/sqlite-model-2026-10-13/README.md) and
[repeatable commands](../../tools/sqlite_spike/README.md).

### Generator and host assessment

Stock LinkML 1.11.1 SQL generation was run against `schema/model.yaml`, with
SQLAlchemy 2.0.54. Both tested mappings emitted `Expression.Call_id` and
`Expression.call_id`; SQLite rejected the duplicate column name. The captured
DDL and errors are retained with the evidence. This result applies to those
versions and that input. It does not rule out fixing or configuring the upstream
generator. Production mapping needs explicit decisions about unions, field
presence, ordered collections, inheritance and local/external reference scope.

Payload generates its physical schema from collection configuration. An RK-owned
database does not automatically supply native Payload collection APIs or drawers.
The shared read-adapter step must compare a read-service adapter, a Payload projection and
the cost of retaining the native UI. Do not allow Payload development schema push
or host migrations to modify a published RK package.

The [Payload v4 migration guide](https://payloadcms.com/docs/beta/migration-guide/v4)
was checked during this work. This experiment imports no Payload API and changes no
Payload configuration. It establishes an independent boundary, not a v4 integration
pass. Repeat the Viewer v4 procedure when implementing its adapter.

Primary references: [SQLite application files](https://www.sqlite.org/appfileformat.html),
[LinkML SQL generation](https://linkml.io/linkml/generators/sqltable.html),
[Payload SQLite](https://payloadcms.com/docs/database/sqlite), and
[Speckle object encoding](https://docs.speckle.systems/developers/sdks/python/concepts/objects).

## Spike steps, turn bundles and review

The published [Viewer spike plan](https://github.com/daniel-fink/whirlwind-viewer/blob/98e92ccd2bc2cc572628439ed072696e66710f7f/docs/decisions/001-viewer-plan.md)
owns host sequencing and links its browsing, tree, ChatGPT and Payload v4 checks.
This ADR owns the canonical Package contract and P1–P8 criteria.

The Package contract is agreed. Do not ask for another approval of its one-to-one
pin rule. Implement the following steps in dependency order; the earlier SQLite
proof remains input evidence, not completion of step A.

| Step | Work and concrete result | Acceptance and user review |
| --- | --- | --- |
| A: Schema and Package lifecycle | Specify the Model-owned pin/mappings, identity rules and migration; pin the native Speckle spec; build a native fixture, Package validator and offline reopen proof. Compare the RK storage mapping and preserve the legacy reader boundary. | Pass P1–P5 below. Review the concrete schema, manifest, mappings, change cases and reopened artifact before adopting the public format and wiring hosts to it. |
| B: Shared reads and host adapter | Define bounded object/value/evidence/graph/source/geometry reads for one exact Package; connect shared Viewer components; compare a read service with native Payload projections. | Pass P6–P7 and the full-browser portion of P8. Keep Payload's application database separate from the immutable Package. Repeat v4 host checks. |
| C: Navigation and inspector | Trial the tree library; finish occurrence, browse/inspect and restore rules; compose the same inspector and tree in the full browser and independent shell. | Use Viewer's browsing matrix. Review the actual tree, selection and inspector behaviour after automated and browser checks. |
| D: Focused resources and workflow | Connect MCP Package access and component dispatch; verify real ChatGPT tree/inspector then graph/3D, standalone deep links, and build/reopen workflow. | Pass P8 in actual hosts. Review focused UI beside the full browser; test full-browser embedding separately if claimed. |

Each step can include implementation, fixtures, checks and a reviewable result in
one turn. B and C can share a turn. D can share a later turn with workflow checks
when access and dependencies are ready. The entire spike is not one unattended
turn: schema/artifact review after A and product review after B/C remain deliberate
checkpoints. User interpretation review belongs inside the ingestion workflow.
Routine reversible fixes and verification do not need separate permission stops.

### Package acceptance criteria

| ID | Required evidence |
| --- | --- |
| P1: Cardinality and identity | A valid Speckle-backed Package contains one Model and one pinned bundle. Reject missing/extra bundles, mismatched pins, and reuse of a Model identity with changed canonical content. Geometry-free Models remain valid outside this profile. |
| P2: Change matrix | RK-only, bundle-only, source-version-only and mapping-only changes each produce a new Model and Package. Bundle-only changes cannot retain the old Model identity. Stable Entity/Value UUIDs and reuse of an unchanged bundle work. |
| P3: Integrity and reopening | Reopen a copied Package offline without the source server or original capture. Reject tampered/missing source files, wrong digests/versions and invalid mappings before publication. Preserve native bundle bytes; verify all declared required assets. |
| P4: Source semantics | Test many-to-many and absent associations, non-geometry properties/relations, scoped selectors, units, nested instances and transforms. Preserve geometry roles and placement without inferring placement from RK Assembly membership. |
| P5: Schema and storage | Reconstruct the Model under the new schema; preserve field presence, scalar types, order and provenance. Verify migrations and explicit handling of unsupported formats. Distinguish logical content identity from storage-byte hashes and exclude circular digests. |
| P6: Bounded reads | Object/value/evidence/membership/graph queries are bounded and do not load geometry blobs. Geometry requests resolve exact source selectors from the same Package. Declare scale and large-object limits from measured fixtures. |
| P7: Interface independence | Two supported render conversions leave Model, bundle and Package unchanged. Camera/selection/cache changes stay outside canonical contents. Host schema push and migrations cannot modify published Packages. A quad conversion alone does not establish general BRep or native-app support. |
| P8: Host consistency | Full browser, focused resources and deep links carry the exact Package and Model identity plus canonical selection/scope. Reject stale cross-Package requests. Verify the same mappings/evidence in each claimed host, actual ChatGPT tool/UI exchanges, and the separate Payload v4 procedure. |

The existing test `test_content_digest_separates_geometry_from_legacy_model_id`
records a legacy identity gap. It must not count as P2 acceptance. The existing
SQLite proof, planar quad, local browser and older v4 results establish only their
recorded scope. They do not accept the new schema, native bundle codec, ChatGPT,
native iOS, general BRep conversion or production service.

Before production adoption, also establish publication durability, migration and
codec support policy, access isolation, hostile-file handling and declared scale
limits. Cross-Package search belongs to a separate catalogue/index. Core ingestion
must remain usable without a viewer.
