# Architecture after the 0.9 ownership split

The coordinated target adds Core-owned persistent modelling work and general
Workflows. An ingestion Workflow is one application composition; RK Specification
and Run remain distinct canonical contracts. Projects retains authored work in
the existing `whirlwind-projects` repository. See the
[Core refactor plan](https://github.com/daniel-fink/whirlwind-core/blob/main/docs/decisions/004-core-lifecycle-refactor.md).
Broader Core lifecycle and native Rangekeeper Bundle implementation are pending.

## Engine, Core and Interface

The three repositories have distinct roles:

| Section | Role | Repository |
| --- | --- | --- |
| Engine | Modelling engine | `rangekeeper` |
| Core | Application core | `whirlwind-core` |
| Interface | User interface | `whirlwind-interface` |

Core owns Whirlwind application APIs. Rangekeeper retains its public modelling
APIs and canonical readers. MCP is a transport adapter within Core. Interface
covers browsing and inspection now, with editing and authoring anticipated.
Future user edits go through Core application operations and Rangekeeper rules;
published Bundles remain immutable. The rename does not add editing capability.

## Ownership

Rangekeeper owns immutable canonical Model, Specification and Run contracts, identity,
provenance, validation, units, calculations and execution. `io` owns native serialization,
stores, Polars conversion and the canonical Speckle envelope. `visualisation` owns simple
local chart, table, PyVis graph and retained geometry display. Importing RK core does not
load an ingestion engine, source reader, browser or service client.

Whirlwind Core owns acquisition, source interpretation, transient Evidence, recipes,
workspace decisions, ingestion builds and optional Rhino source extraction. It
also owns the local Bundle application proof and thin HTTP/MCP adapters as each
is implemented. The full access contract remains open. Whirlwind
Interface owns advanced browsers and graph layout. RK owns and builds its notebook
Geometry viewer in `tools/geometry`; it has no build or runtime dependency on
Whirlwind. RK imports neither Whirlwind Python package.

The portable C# Model library and generic Grasshopper authoring components stay in RK.
Generated canonical record and envelope definitions have one authority in RK. The
source-specific Grasshopper component is in Core and consumes the pinned RK assemblies.

See [the decision](../decisions/007-three-repository-refactor.md),
[upgrade paths](../guides/upgrading.md), and [Grasshopper](../guides/grasshopper.md).

The agreed [Model and Geometry Bundle contract](../decisions/008-sqlite-model-package.md)
contains a main Model plus selected Models, Specifications and finalized Runs,
with their interpretation dependencies. Each spatial Model owns its exact Geometry
pin and Entity-to-source-element mappings. Equal pins share retained native bytes.
Model changes create a new Model; changing the delivered selection creates a new
Bundle without changing unchanged record identities. Geometry is provider-neutral; its first planned format is Speckle's
2026.9 object-model/bundle schema, with an exact specification pin. Source data stays
adjacent to schema-derived RK Parquet tables. One Bundle access layer contains
DuckDB and provider adapters and supplies queries, provenance, geometry and assets
under shared identity and access rules. Entity
associations support navigation and selection; property and relation evidence use
the separate RK provenance structure. Rendering belongs to the interface. The greenfield Interface uses React/TypeScript/
Vite, Mantine Tree, AG Grid Community, Cytoscape and Speckle; Payload/Next are excluded.
RK owns the lossless RK Parquet mapping/reader, with storage dependencies in optional
IO modules. Whirlwind composes it with provider interfaces and access policy. Direct
Python, HTTP and MCP share application semantics; reading a complete retained
Bundle requires neither ingestion state, a chat nor source-server access.
The earlier SQLite experiment remains historical evidence. The development
candidate described below adds schema and IO support; stable format acceptance
remains open.

## Bundle implementation boundary

The [Bundle candidate](../reference/bundle.md) adds `model.geometry` and optional
`io.bundle`/`io.migration`. Schema YAML remains authoritative; Python/C#/JSON and
slot metadata are generated. Provider decoding, acquisition, registration and
access policy belong to Core. No engine domain import loads Arrow or DuckDB.
