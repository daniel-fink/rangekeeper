# Architecture

Rangekeeper is a standalone modelling library. It has three jobs:
- declare a property project as an explicit, immutable set of facts and equations;
- investigate the project with forward and inverse questions, market paths and rules;
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
| P1 | Three investigation roots: the **Model** (what the project is), the **Specification** (what we ask of it) and the **Run** (what happened). A **MarketPaths** document holds captured market paths (1.0 target, [#298](https://github.com/daniel-fink/rangekeeper/issues/298)). | [ADR-001](../decisions/001-document-roots.md), [ADR-014](../decisions/014-market-paths.md) |
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
| — | `money` | Currency amounts: the ISO 4217 catalogue, boundary conversions and rounding |
| — | `quantity` | `Quantity` (also at the root) and `UnitSystem`, with the curated unit registry |
| 3 | `duration` | Frequency, Period, Periods, Span, `NEVER` and calendar rules |
| 4 | `profile` | Growth and distribution profiles: how an amount develops over Periods |
| 5 | `flow` | Movement, Flow, Stream, their options and table display, and the private engine |
| 6 | `market` | Path generators (`Dynamics`) and the market paths document (`Paths`) |
| 7 | `finance` | Calculations on known values: PV, NPV, IRR, payments and interest |
| 8 | `model` | The Model document, definitions, the system graph and rollups, equations, provenance and geometry |
| 9 | `specification` | The Specification document, composition, roles and rule declarations |
| 10 | `run` | The Run document and evidence validation, with the rule trace check |
| 11 | `execution` | Case resolution, role binding, problem building, backends, verification, rule evaluation and publication |
| 12 | `io` | JSON and YAML codecs, stores, Bundle and Polars export |

`quantity` and `money` sit between `schema` and `duration`; `money` is below
`quantity`. Users import from `rangekeeper` and from the namespaces in
`rangekeeper.__all__`: `quantity`, `money`, `duration`, `profile`, `flow`,
`finance`, `model`, `specification`, `run`, `execution`, `io` and `errors`.
`schema` and `shared` are internal. `market` is internal now; it becomes public
with its 1.0.0b1 API
([#298](https://github.com/daniel-fink/rangekeeper/issues/298),
[#299](https://github.com/daniel-fink/rangekeeper/issues/299)). Owners re-export
the records that their users need. See [ADR-010](../decisions/010-layers-and-packages.md)
and [ADR-017](../decisions/017-api-and-formats.md).

### Kinds of classes

- **Documents** are validated, indexed facades: Model, Specification and Run.
  MarketPaths joins them in 1.0
  ([#298](https://github.com/daniel-fink/rangekeeper/issues/298)).
- **Value types** are immutable records with behaviour: Quantity, Period, Span,
  Movement, Flow and Stream. They keep their own invariants.
- **All other records** are plain data, read through their document.

Validation runs at commit points ([ADR-011](../decisions/011-records-and-validation.md)).

### How the parts connect

The flows below have two parts. **Now** is the 1.0.0a2 API. **1.0 target** is
the accepted design: the API does not exist yet. The linked gap issues track
each missing part, and the
[proposed walkthrough cells](../../examples/walkthrough/proposed/README.md)
show the target API in use.

**Author a Model** ([ADR-015](../decisions/015-authoring.md))
- Now:
  1. `rk.Model(name=)` makes an empty Model; `model.edit()` returns a `ModelDraft`.
  2. The draft adds Measures, Classifications, entities, assemblies and
     relationships. `draft.add_entity(code=, classification=)` returns an entity
     handle, which declares values, Flows and dates with `value(key=, units=)`,
     `flow(key=, units=, periods=)` and `date(key=)`. `equations(...)` takes
     Expression records from `rangekeeper.model.expression.authoring`, including
     date literals, `NEVER` and date arithmetic.
  3. `commit()` validates the revision once and returns it.
  4. Put the revision into an append-only store.

  `Model.create(...)` and `Model.from_data(...)` still take complete records,
  and `model.revise(Update(...))` replaces complete sections. See the
  [Model reference](../reference/model.md).
- 1.0 target: equations in text and in `rx`, with `NEVER`, Formulation handles,
  equation keys and edits of existing declarations.

  Gap issues: [#142](https://github.com/daniel-fink/rangekeeper/issues/142),
  [#145](https://github.com/daniel-fink/rangekeeper/issues/145),
  [#146](https://github.com/daniel-fink/rangekeeper/issues/146),
  [#280](https://github.com/daniel-fink/rangekeeper/issues/280),
  [#283](https://github.com/daniel-fink/rangekeeper/issues/283),
  [#284](https://github.com/daniel-fink/rangekeeper/issues/284),
  [#305](https://github.com/daniel-fink/rangekeeper/issues/305),
  [#309](https://github.com/daniel-fink/rangekeeper/issues/309).

**Calculate with known data**
1. Make Flows and Streams from dates, periods and amounts.
2. Use Flow and Stream methods and the `finance` operations `pv`, `npv`, `irr`
   and `payment`. The older `finance.financial` functions (`calculate_pv`,
   `calculate_xnpv`, `calculate_irr`) remain until their uses move
   ([#167](https://github.com/daniel-fink/rangekeeper/issues/167)).
3. Read the resulting Flows or Quantities. No Model is necessary.

**Investigate a Model** ([ADR-013](../decisions/013-execution-and-extensions.md))
- Now: `model.specify(name=)` makes a Specification that pins one Model
  revision; `fix(key=value)` and `free("key")` each return a new
  Specification. `fix` takes a Quantity, Quantity text or a number for a ratio.
  A value that is not fixed is free, and `roles` lists the role of each value.
  `on(model=)` moves the Specification to another Model revision. Records add
  bounds and rules. `rangekeeper.execution.solve(specification=)`
  runs the typed stages: it resolves the cases, validates each composition, binds
  roles, builds the affine problem, solves it in a separate process, makes a
  candidate, verifies it independently and assembles an `Outcome`, and writes
  nothing. `execute(specification, store)` also publishes the output Models and
  then the Runs. Each stage is a public function that writes to no store. Read
  a solved value by key, `outcome["land_cost"]`, and the result from
  `outcome.status`; `outcome.raise_for_status()` raises when the solve found no
  determined result. See the
  [execution reference](../reference/execution.md#stages).
- 1.0 target:
  1. Write a Specification that pins one Model revision. Fix and free values,
     and add bounds or rules.
  2. `solve` resolves cases and validates the composition.
  3. It binds roles and builds an `AffineProblem`.
  4. The backend solves the problem.
  5. The candidate is verified independently.
  6. `execute` also publishes the Run and the output Model to a store.
  7. Read solved values from the `Outcome`.

  Gap issues: [#292](https://github.com/daniel-fink/rangekeeper/issues/292),
  [#296](https://github.com/daniel-fink/rangekeeper/issues/296),
  [#297](https://github.com/daniel-fink/rangekeeper/issues/297).

**Work with market paths** ([ADR-014](../decisions/014-market-paths.md))
- Now: the internal `market` package has the deterministic kernels
  (`market.dynamics`), the scenario plan, path generation, captured paths,
  `Market` access and replay. See
  [market paths and rules](../reference/market-paths-and-rules.md).
- 1.0 target:
  1. Choose a path generator (`rk.market.Dynamics`) and its parameters.
  2. Generate market paths (`rk.market.Paths`) with a seed.
  3. Use `Specification.across(paths=)` to make one case for each path. Path
     series fix the Model values with the same key; `series=` maps any others.
  4. Execute the batch. To compare strategies, run each Specification across the
     same pinned paths.

  Gap issues: [#298](https://github.com/daniel-fink/rangekeeper/issues/298),
  [#299](https://github.com/daniel-fink/rangekeeper/issues/299),
  [#306](https://github.com/daniel-fink/rangekeeper/issues/306).

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
| `shared` | Errors, diagnostics, validation helpers, encoding, the resolver and store protocols, tables and fingerprints | — |
| `schema` | Data-only generated records, enums, the record runtime, the kind registry and structural validation | — |
| `money` | The ISO 4217 catalogue and minor units, `to_number`, `to_amount` and `round` | — |
| `quantity` | `Quantity`, `UnitSystem` and the curated unit registry | — |
| `duration` | Frequency, Period, Span and calendar rules | — |
| `profile` | Growth profiles (`Constant`, `Linear`, `Compounding`), distribution profiles (`Uniform`, `SCurve`), the `Profile` Protocol and the `profiles` registry; the Distribution owner (public as `rangekeeper.model.Distribution`). `Flow.from_profile` in `flow` makes the Flow | — |
| `flow` | Flow, Movement and Stream, their options, table display and the private engine | — |
| `market` | Deterministic kernels (`market.dynamics`), path generation, captured paths, `Market` access and replay | `Dynamics`, `generate` and `Paths` replace the scenario plan ([#298](https://github.com/daniel-fink/rangekeeper/issues/298), [#299](https://github.com/daniel-fink/rangekeeper/issues/299)). Generation, `Market` and replay still import `model`, above `market` |
| `finance` | Financial valuation: `pv`, `npv`, `irr` and `payment`; the older `financial` module with PV, XNPV, IRR and day counts | `pv`, `npv` and `irr` replace `financial.calculate_*` ([#167](https://github.com/daniel-fink/rangekeeper/issues/167)) |
| `model` | The Model document, definitions, the system graph and rollups, equations, provenance and geometry | — |
| `specification` | The Specification document, composition, roles, and rule declarations and their validation | Rule queries over a `Window` replace the rule records ([#300](https://github.com/daniel-fink/rangekeeper/issues/300), [#215](https://github.com/daniel-fink/rangekeeper/issues/215)) |
| `run` | The Run document, its report and outputs, and evidence validation. The internal `run._rule` has the rule trace check, with the exact condition truth and the availability rule that rule evaluation also uses | — |
| `execution` | The typed stages (case resolution, validation, role binding, problem building, candidates, verification and assembly), backends, the executor and rule evaluation (`execution.rule`) | Sequential rule evaluation replaces `execution.rule.evaluate` ([#215](https://github.com/daniel-fink/rangekeeper/issues/215)) |
| `io` | JSON and YAML codecs, stores, Bundle and Polars export. It re-exports the `RecordStore` protocol from `shared` | — |

The import-linter contract in [`pyproject.toml`](../../pyproject.toml) enforces the
layer order. The `layers` CI job and a pre-commit hook run it; see
[layer rules](../contributing/README.md#layer-rules).

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
