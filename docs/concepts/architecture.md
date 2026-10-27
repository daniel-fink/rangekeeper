# Architecture

Rangekeeper is a standalone modelling library. It has three jobs:
- declare a property project as an explicit, immutable set of facts and equations;
- investigate the project with forward and inverse questions, market paths and policies;
- keep exact evidence of each result.

Applications use the public APIs to build their own services and interfaces.

This page has three parts:
- the **principles** that apply now;
- the **accepted 1.0 target**, which is not implemented yet;
- the **current package map**, which applies until the 1.0.0a2 rename pass.

The [glossary](glossary.md) defines the terms.

## Principles

| # | Principle | Decision |
| --- | --- | --- |
| P1 | Three investigation roots: the **Model** (what the project is), the **Specification** (what we ask of it) and the **Run** (what happened). A **MarketPaths** document holds captured market paths. | [ADR-001](../decisions/001-document-roots.md), [ADR-014](../decisions/014-market-paths.md) |
| P2 | Equations state relationships only. A Specification decides which values are fixed and which are free. The same Model answers forward and inverse questions. | [ADR-001](../decisions/001-document-roots.md) |
| P3 | LinkML is the only authority for fields. Records are generated from it. Behaviour is written by the owner of the concept. | [ADR-002](../decisions/002-records-and-identity.md), [ADR-011](../decisions/011-records-and-validation.md) |
| P4 | Revisions are immutable and referenced by exact UUID. Stores are append-only. Nothing resolves to "the latest" without being asked. | [ADR-002](../decisions/002-records-and-identity.md) |
| P5 | Presence is exact: missing, null, empty, zero and false are all different. Every quantity has units. | [ADR-002](../decisions/002-records-and-identity.md) |
| P6 | Three kinds of mathematics stay separate: calculations on known data, declared equations, and solved results with independent verification before publication. | [ADR-003](../decisions/003-computation-and-evidence.md), [ADR-013](../decisions/013-execution-and-extensions.md) |
| P7 | Evidence is part of the model: claims, sources, captured market paths and implementation fingerprints. A Run is final. | [ADR-001](../decisions/001-document-roots.md), [ADR-003](../decisions/003-computation-and-evidence.md) |
| P8 | Optional capabilities load at their boundary. Core imports stay light. | [ADR-010](../decisions/010-layers-and-packages.md) |
| P9 | The core contains the data model, validation, calculation, execution and native IO. Product adapters, source ingestion, services and user interfaces are outside it. | [ADR-010](../decisions/010-layers-and-packages.md) |

## Application boundary

The callers own these things:
- source acquisition and interpretation workflows;
- authentication and access policy;
- service transports and application navigation.

They are not required to import or use Rangekeeper. A caller creates Models
through the public APIs. It keeps the source context that explains its decisions.
See [source interpretation](source-workflows.md).

## Accepted 1.0 target

Status: accepted on 2026-10-26; implementation pending. The scripted rename
pass at milestone 1.0.0a2 makes this the package map
([ADR-012](../decisions/012-naming-and-glossary.md)).

### Layers

A module imports only from its own layer or a lower layer. Import-linter
contracts enforce the rule.

| Order | Package | Contains |
| --- | --- | --- |
| 1 | `shared` (internal) | Errors and diagnostics, resolver and store protocols, the extension registry, fingerprints |
| 2 | `schema` (internal) | Data-only generated records, enums and JSON; the record runtime; the kind registry; structural validation |
| — | `quantity` | `Quantity` (also at the root) and `UnitSystem`, with the curated unit registry |
| 3 | `duration` | Frequency, Period, Span and calendar rules |
| 4 | `profile` | Growth and distribution profiles: how an amount develops over Periods |
| 5 | `flow` | Movement, Flow, Stream, their options and table display, and the private engine |
| 6 | `finance` | Calculations on known values: PV, NPV, IRR, payments, interest, and path generators |
| 7 | `model` | The Model document, definitions, the system graph and rollups, equations, provenance and geometry |
| 8 | `specification` | The Specification document, composition, roles and policy declarations |
| 9 | `run` | The Run document and evidence validation |
| 10 | `execution` | Case resolution, role binding, problem building, backends, verification, policy evaluation and publication |
| 11 | `io` | JSON and YAML codecs, stores, Bundle and Polars export |

`quantity` sits beside `shared`, below `duration`. Users import from `rangekeeper`,
`quantity`, `duration`, `profile`, `flow`, `finance`, `model`, `specification`, `execution`,
`io` and `errors`. `schema` and `shared` are internal. Owners re-export the
records that their users need. See [ADR-010](../decisions/010-layers-and-packages.md)
and [ADR-017](../decisions/017-api-and-formats.md).

### Kinds of classes

- **Documents** are validated, indexed facades: Model, Specification, Run and
  MarketPaths.
- **Value types** are immutable records with behaviour: Quantity, Period, Span,
  Movement, Flow and Stream. They keep their own invariants.
- **All other records** are plain data, read through their document.

Validation runs at commit points ([ADR-011](../decisions/011-records-and-validation.md)).

### How the parts connect

**Author a Model** ([ADR-015](../decisions/015-authoring.md))
1. Start a builder with `Model.build()`, or with `model.edit()` for a change.
2. Add definitions, entities, relationships, values and equations.
3. Call `commit()`. It validates once and returns a new immutable revision.
4. Put the revision into an append-only store.

**Calculate with known data**
1. Make Flows and Streams from dates, periods and amounts.
2. Use Flow and Stream methods and `finance` operations.
3. Read the resulting Flows or Quantities. No Model is necessary.

**Investigate a Model** ([ADR-013](../decisions/013-execution-and-extensions.md))
1. Write a Specification that pins one Model revision. Fix and free values,
   and add bounds or policies.
2. `solve` resolves cases and validates the composition.
3. It binds roles and builds an `AffineProblem`.
4. The backend solves the problem.
5. The candidate is verified independently.
6. `execute` also publishes the Run and the output Model to a store.
7. Read solved values from the `Outcome`.

**Work with market paths** ([ADR-014](../decisions/014-market-paths.md))
1. Choose a path generator and its parameters.
2. Generate `MarketPaths` with a seed.
3. Use `Specification.across(paths, assign=...)` to make one case for each path.
4. Execute the batch. To compare strategies, run each Specification across the
   same pinned paths.

**Analyse structure**
1. Select a View of a Model.
2. Build a Hierarchy from relationships or memberships.
3. Roll up, pivot or filter values.
4. Read the result, or export a detached table.

**Exchange data**
- Strict codecs read and write JSON and YAML with an explicit kind.
- Stores are append-only by UUID.
- A Bundle delivers a set of documents with their exact dependencies.
- Polars tables are detached from the evidence.

## Current package map

This map applies until the 1.0.0a2 rename pass.

| Package | Responsibility |
| --- | --- |
| `model` | Immutable Model records, Geometry pins, provenance, equations, graph operations, Flow and Stream with their table display, calendar rules and captured scenarios. |
| `specification` | Investigation choices over exact document revisions, and policy declarations and evaluation. |
| `run` | Finalized execution evidence, storage and numerical execution. |
| `calculations` | Known-data financial and time-series calculations. |
| `io` | Native serialization, stores, Polars conversion, canonical Speckle envelopes and optional Bundle IO. |
| `visualisation` | Local charts, PyVis graphs and retained geometry display. |
| `shared` | Shared record, identity, unit and table support. |
| `schema` | Generated records, enums, the record runtime and structural validation. |

LinkML YAML in `schema/` owns persistent fields. Python, C# and JSON Schema
definitions are generated from it. See the [record reference](../reference/records.md)
and the [schema guide](../contributing/schema.md).

Domain imports do not load database engines, plotting libraries, source clients
or solver backends. Optional dependencies load at their capability boundary. Use
[installation extras](../guides/installation.md#choose-capabilities) to select
the necessary capabilities.

### Local display

The notebook geometry viewer is built in `tools/geometry` and packaged as static
assets. Python installation does not run Node. The viewer shows retained source
content without a live source account. See its [build guide](../../tools/geometry/README.md).
Under the 1.0 target, the viewer moves to the walkthrough helpers.

### Native authoring

The portable C# Model library and generic Grasshopper components live in
`src/grasshopper`. The Model project needs neither Rhino nor a source SDK. See
[Grasshopper](../guides/grasshopper.md). Under the 1.0 target, the solution
moves to `examples/grasshopper`.

### Bundle implementation boundary

The [Bundle](../reference/bundle.md) contains a main Model and selected Models,
Specifications and finalized Runs, with their exact interpretation dependencies.
Each spatial Model owns its Geometry pin and Entity mappings. Rangekeeper owns
canonical Bundle validation, the lossless schema-derived Parquet mapping and its
reader and writer. Arrow and DuckDB stay optional IO dependencies. The current
format is not yet stable. Format 1 becomes stable at milestone 1.0.0b1
([ADR-017](../decisions/017-api-and-formats.md)).

See [upgrading](../guides/upgrading.md) for removed APIs and explicit migrations.
