# Architecture

Rangekeeper is a standalone modelling library. It has three jobs:
- declare a property project as an explicit, immutable set of facts and equations;
- investigate the project with forward and inverse questions, market paths and policies;
- keep exact evidence of each result.

Applications use the public APIs to build their own services and interfaces.

This page has three parts:
- the **principles** that apply now;
- the **1.0 layers**, which the 1.0.0a2 rename pass puts in place;
- the **package map**, with the moves that are not complete.

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

## 1.0 layers

Status: accepted on 2026-10-26. The scripted rename pass at milestone 1.0.0a2
moved the packages into these layers
([ADR-012](../decisions/012-naming-and-glossary.md)). The
[package map](#package-map) lists the moves that are not complete.

### Layers

A module imports only from its own layer or a lower layer. Import-linter
contracts enforce the rule.

| Order | Package | Contains |
| --- | --- | --- |
| 1 | `shared` (internal) | Errors and diagnostics, resolver and store protocols, the extension registry, fingerprints |
| 2 | `schema` (internal) | Data-only generated records, enums and JSON; the record runtime; the kind registry; structural validation |
| — | `quantity` | `Quantity` (also at the root) and `UnitSystem`, with the curated unit registry |
| 3 | `duration` | Frequency, Period, Span and calendar rules |
| 4 | `flow` | Movement, Flow, Stream, their options and table display, and the private engine |
| 5 | `finance` | Calculations on known values: PV, NPV, IRR, payments, growth, accounts, and path generators |
| 6 | `model` | The Model document, definitions, the system graph and rollups, equations, provenance and geometry |
| 7 | `specification` | The Specification document, composition, roles and policy declarations |
| 8 | `run` | The Run document and evidence validation |
| 9 | `execution` | Case resolution, role binding, problem building, backends, verification, policy evaluation and publication |
| 10 | `io` | JSON and YAML codecs, stores, Bundle and Polars export |

`quantity` sits beside `shared`, below `duration`. Users import from `rangekeeper`,
`quantity`, `duration`, `flow`, `finance`, `model`, `specification`, `execution`,
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

## Package map

The packages of `src/rangekeeper` follow the [1.0 layers](#10-layers). Some
contents are not yet in their 1.0 owner:

| Package | Contents now | Moves that follow |
| --- | --- | --- |
| `shared` | Errors, diagnostics, validation helpers, encoding, references, tables and fingerprints | The store and resolver protocols arrive from `io` ([#98](https://github.com/daniel-fink/rangekeeper/issues/98)) |
| `schema` | Generated records, enums, the record runtime, structural validation and record behaviours | The Flow and Movement behaviours move to `flow` ([#106](https://github.com/daniel-fink/rangekeeper/issues/106)) |
| `quantity` | `Quantity`, `UnitSystem` and the curated unit registry | — |
| `duration` | Frequency, Period, Span and calendar rules | — |
| `flow` | Stream, the Flow re-exports, their options, table display and the private engine | — |
| `finance` | Financial valuation, projection, accounts and deterministic dynamics | Path generators arrive from `model.scenario` ([#137](https://github.com/daniel-fink/rangekeeper/issues/137)) |
| `model` | The Model document, definitions, the system graph and rollups, equations, provenance, geometry and captured scenarios | `model.scenario` moves to `finance` and the MarketPaths document ([#137](https://github.com/daniel-fink/rangekeeper/issues/137)) |
| `specification` | The Specification document, composition, roles, and policy declarations and evaluation | Policy evaluation moves to `execution` ([#102](https://github.com/daniel-fink/rangekeeper/issues/102)) |
| `run` | The Run document, its report and outputs, and evidence validation | — |
| `execution` | Preparation, compilation, backends, acceptance and publication | Policy evaluation arrives from `specification` ([#102](https://github.com/daniel-fink/rangekeeper/issues/102)) |
| `io` | JSON and YAML codecs, stores, Bundle and Polars export | The store protocol moves to `shared` ([#98](https://github.com/daniel-fink/rangekeeper/issues/98)) |

Import-linter contracts that enforce the layer order follow in [#97](https://github.com/daniel-fink/rangekeeper/issues/97).

These folders are outside the package and its wheel:

| Folder | Responsibility |
| --- | --- |
| [`examples/walkthrough/helpers`](../../examples/walkthrough/helpers/README.md) | Charts, graph display, local display, the canonical Speckle envelope and the geometry viewer, for the lessons |
| [`examples/grasshopper`](../../examples/grasshopper/README.md) | The unsupported C# Model library and Grasshopper components |
| [`examples/rangekeeper_examples`](../guides/examples.md) | Shared design and investment builders for examples and tests |

LinkML YAML in `schema/` owns persistent fields. Python, C# and JSON Schema
definitions are generated from it. See the [record reference](../reference/records.md)
and the [schema guide](../contributing/schema.md).

Domain imports do not load database engines, plotting libraries, source clients
or solver backends. Optional dependencies load at their capability boundary. Use
[installation extras](../guides/installation.md#choose-capabilities) to select
the necessary capabilities.

### Local display

Charts, graph display, the canonical Speckle envelope and the geometry viewer
are [walkthrough helpers](../../examples/walkthrough/helpers/README.md), not library
modules ([ADR-010](../decisions/010-layers-and-packages.md)). The core keeps Flow,
Stream and pivot table display. The viewer is built in
`examples/walkthrough/viewer` and copied to the helpers as static assets; see its
[build guide](../../examples/walkthrough/viewer/README.md).

### Native authoring

The portable C# Model library and generic Grasshopper components are an
unsupported example in `examples/grasshopper`. The Model project needs neither
Rhino nor a source SDK. CI generates its C# records, builds it and round-trips the
cross-language fixtures, so it cannot drift from the schema. See the
[Grasshopper example](../../examples/grasshopper/README.md).

### Bundle implementation boundary

The [Bundle](../reference/bundle.md) contains a main Model and selected Models,
Specifications and finalized Runs, with their exact interpretation dependencies.
Each spatial Model owns its Geometry pin and Entity mappings. Rangekeeper owns
canonical Bundle validation, the lossless schema-derived Parquet mapping and its
reader and writer. Arrow and DuckDB stay optional IO dependencies. The current
format is not yet stable. Format 1 becomes stable at milestone 1.0.0b1
([ADR-017](../decisions/017-api-and-formats.md)).

See [upgrading](../guides/upgrading.md) for removed APIs and explicit migrations.
