# ADR-010: Layers, packages and public namespaces

Status: accepted for 1.0; library boundary implemented in 1.0.0a1 (#87–#92), layers and namespaces pending. Recorded: 2026-10-26.

## Problem

The current package map does not show one owner for each concept:

- Value types (time, Quantity, Flow, Stream) sit inside `model`, beside the Model document.
- `calculations` and `model` import each other.
- `run` and `io` import each other.
- Generated record behaviours import upward into `model`.
- The same Flow operation exists in up to four places. Examples are `trim`, `resample` and `aggregate`, in `schema/behaviors`, `model.flux`, `calculations.series` and `calculations._batch`.
- The execution engine sits inside the evidence package `run`.
- Policy evaluation sits beside policy declarations in `specification`.
- Product adapters ship in the core package.
- No rule separates the packages that users import from internal packages.

## Choice

### Library boundary

The core library owns the data model, validation, calculation, execution and
native IO. It does not own product adapters, source ingestion, services,
authentication or user interfaces.

- The Speckle envelope, the geometry viewer, charts and graph display move to
  the walkthrough helpers.
- The C# Grasshopper solution moves to `examples/grasshopper`. It is an
  unsupported example. CI generates its C# records and builds it, so it cannot
  drift from the schema.
- Flow and Stream table display stays in the core, in `flow`.

### Layers

A module imports only from its own layer or from a lower layer. Import-linter
contracts in the test suite enforce this rule.

| Order | Package | Responsibility |
| --- | --- | --- |
| 1 | `shared` (internal) | Units policy support, errors and diagnostics, resolver and store protocols, the extension registry, fingerprints |
| 2 | `schema` (internal) | Data-only generated records, enums and JSON resources; the record runtime; the kind registry; structural validation |
| 3 | `duration` | Frequency, Period, Span and calendar rules |
| 4 | `profile` | Profiles: how an amount develops over Periods. Growth profiles (constant, linear, compounding) start from an initial amount; distribution profiles (uniform, S-curve) divide a total |
| 5 | `flow` | Movement, Flow, Stream, their options, `Flow.from_profile`, table display and the private calculation engine |
| 6 | `finance` | Calculations on known data: present value, NPV, IRR, payments, interest and path generators ([ADR-014](014-market-paths.md)). An account balance is a cumulative sum of Flows, not a `finance` class (#201, decision D2) |
| 7 | `model` | The Model document, definitions, the system graph and rollups, equations, provenance and geometry |
| 8 | `specification` | The Specification document, composition, roles and policy declarations |
| 9 | `run` | The Run document and the validation of its evidence |
| 10 | `execution` | The solve pipeline, backends, independent verification, policy evaluation and publication ([ADR-013](013-execution-and-extensions.md)) |
| 11 | `io` | JSON and YAML codecs, stores, Bundle and Polars export |

`Quantity` and `UnitSystem` live in the public `quantity` namespace, below
`duration`. `errors` is a public namespace for the exception hierarchy
([ADR-016](016-safety-defaults.md)).

### Ownership rules

- Flow and Stream methods are the only API for generic series operations.
  Examples are align, trim, resample, aggregate and scale. `calculations.series`
  is removed.
- `finance` replaces `calculations`. It keeps the financial operations. Path
  generators move into it from `model.scenario`.
- Growth and distribution are series shapes, not finance. They move from
  `calculations.projection` to `profile`, and `Flow.from_profile` applies them.
  The word "projection" is not used ([ADR-012](012-naming-and-glossary.md)).
  Amended 2026-10-26 by the walkthrough proposed cells (#201, decision D12).
- `Quantity` is at the root beside the three documents, because every layer uses
  it. Its namespace is `quantity`, not `units`, so "units" means only a unit string
  ([ADR-012](012-naming-and-glossary.md)). Amended 2026-10-26 (#201, decision D13).
- Policy declarations stay in `specification`. Policy evaluation moves to `execution`.
- The store and resolver protocols move to `shared`. This removes the `run` and
  `io` cycle.
- Schema behaviours do not import from higher layers.

### Public namespaces

Users import from `rangekeeper` (Model, Specification, Run and Quantity), `duration`, `profile`, `flow`,
`finance`, `model`, `specification`, `execution`, `io`, `errors` and `quantity`.
`schema` and `shared` are internal. Each owner re-exports the records that its
users need. For example, `flow` exports Flow, `model` exports Entity and
`specification` exports Assignment. [ADR-017](017-api-and-formats.md) defines
the stability promise for these names.

### Move map

| Current location | 1.0 location |
| --- | --- |
| `model.duration` | `duration` |
| `model.flux`, `model._flow_mapping`, `schema/behaviors/flow.py`, `calculations.series`, `calculations._batch` | `flow` |
| `model.measure` (Quantity), `shared.units` | `quantity`; `Quantity` is also at the root |
| `calculations` (financial, account, dynamics) | `finance` |
| `calculations.projection` (growth and distribution) | `profile`, and `Flow.from_profile` in `flow` |
| `model.scenario` | `finance` generators and the MarketPaths document ([ADR-014](014-market-paths.md)) |
| `run.execution`, policy evaluation in `specification.policy` | `execution` |
| `io.store` protocol | `shared` |
| `visualisation` (except table display), `io.speckle` | Walkthrough helpers |
| `src/grasshopper` | `examples/grasshopper` |

## Alternatives and consequences

- **Keep value types inside `model`.** This option has fewer moves, but the
  `model` and `calculations` cycle remains.
- **One `flow` package with a time sub-package.** This option was rejected for
  two packages, `duration` and `flow`.
- **Keep `calculations.series` as a functional mirror of the methods.** This
  option keeps two ways to do each operation, so it was rejected.
- **Keep the engine in `run.execution`.** This option keeps the engine inside
  the evidence package, so it was rejected.

The moves happen in one scripted rename pass at milestone 1.0.0a2
([ADR-012](012-naming-and-glossary.md)). The pass changes computation
fingerprints once ([ADR-013](013-execution-and-extensions.md)). Consumers get a
rename map and a codemod script. The current [architecture](../concepts/architecture.md)
keeps the present package map until the pass lands.

## Sources and related decisions

- [ADR-003: computation and evidence](003-computation-and-evidence.md) and
  [ADR-004: package and project ownership](004-package-and-project-ownership.md),
  amended by this record.
- [ADR-007: library boundary](007-library-boundary-and-api-retirement.md), amended by this
  record for adapters and native authoring.
- [Architecture](../concepts/architecture.md) and [glossary](../concepts/glossary.md).

Supersedes: none. Amends: ADR-003, ADR-004 and ADR-007. Superseded by: none.
