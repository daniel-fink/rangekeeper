# Architecture

Rangekeeper is a standalone modelling library. Its public APIs define canonical
records, identity, provenance, validation, calculations, execution and optional IO
and local display. Applications use these APIs to compose their own services and
interfaces.

## Package responsibilities

| Package | Responsibility |
| --- | --- |
| `model` | Immutable Model records, Geometry pins, provenance, equations and graph operations. |
| `specification` | Investigation choices over exact document revisions. |
| `run` | Finalized execution evidence, storage and numerical execution. |
| `calculations` | Known-data financial and time-series calculations. |
| `io` | Native serialization, stores, Polars conversion, canonical Speckle envelopes and optional Bundle IO. |
| `visualisation` | Local charts, tables, PyVis graphs and retained geometry display. |
| `shared` | Shared record, identity, unit and table support. |

LinkML YAML in `schema/` owns persistent fields. Python, C# and JSON Schema
definitions are generated from it. Handwritten behaviour preserves identity,
missingness, immutable revisions and complete provenance. See the
[record reference](../reference/records.md) and
[schema guide](../contributing/schema.md).

## Application boundary

Source acquisition, interpretation workflows, authentication, access policy,
service transports and application navigation belong to callers. They are not
required to import or use RK. A caller creates Models through public RK APIs and
retains the source context needed to explain its decisions. See
[source interpretation](source-workflows.md).

Domain imports do not load database engines, plotting libraries, source clients
or solver backends. Optional dependencies load at their capability boundary.
Use [installation extras](../guides/installation.md#choose-capabilities) to select
the required capabilities.

## Local display

The notebook Geometry viewer is built in `tools/geometry` and packaged as static
assets. Python installation does not run Node. It renders retained source content
without a live source account. See its [build guide](../../tools/geometry/README.md).
Application browsers and interactive layout services are outside the RK library.

## Native authoring

The portable C# Model library and generic Grasshopper components live in
`src/grasshopper`. The Model project needs neither Rhino nor a source SDK.
Component host loading and connector acceptance require their own checks; a
portable build cannot establish them. See [Grasshopper](../guides/grasshopper.md).

## Bundle implementation boundary

The [Bundle candidate](../reference/bundle.md) contains a main Model, selected
Models, Specifications and finalized Runs, with their exact interpretation
dependencies. Each spatial Model owns its Geometry pin and Entity mappings.
Equal pins can share retained native bytes. Changed Model content creates a new
Model; changed delivery selection creates a new Bundle.

RK owns canonical Bundle validation, the lossless schema-derived Parquet mapping
and its reader/writer. Arrow and DuckDB remain optional IO dependencies. Provider
decoding, acquisition, registration, access policy and rendering are application
responsibilities. Reading a complete retained Bundle needs no chat, ingestion
workspace or source-server connection. The
[format decision](../decisions/008-sqlite-model-package.md) retains the acceptance
criteria; the development candidate is not a stable-format release.

See [upgrading](../guides/upgrading.md) for removed APIs and explicit migrations.
