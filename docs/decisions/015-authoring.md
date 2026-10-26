# ADR-015: Authoring with builders, equations and identities

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-26.

## Problem

Small tasks take 30 to 45 lines, five to nine imports and a new UUID for every
record. The examples below come from a usability test and from walkthrough
lesson 03:

- To revise a Model, a caller rebuilds the nested records down to the change.
- One equation is written as `equal(left=..., right=add(left=..., right=...))`.
- A Specification needs a hand-written Metadata record and a hand-typed format
  version.
- Unit strings and quantities need full constructors in each call.

## Choice

### Builders on documents

- `Model.build(*, namespace=None)` and `model.edit()` return a builder.
- The builder adds measures, classifications, entities, assemblies,
  relationships, values and equations. It refers to objects by handle or by code.
- `commit()` validates once and returns a new revision.
- Where possible, the builder's collection `add_*` methods are generated from
  the LinkML collections, so the builder stays in step with the schema.
- Builder errors point at the builder call.

Specification authoring uses the same style. A caller fixes and frees roles by
key: `fix(target, quantity)` and `free(target)` ([ADR-012](012-naming-and-glossary.md)).
`across(...)` makes a batch over market paths ([ADR-014](014-market-paths.md)).
The builder fills in the metadata and the format version.

Records stay public. They are for reading results and for full control.

### Equations

There are two ways to write an equation. Both are first-class: each is fully
supported, documented and tested, and both produce the same expression records.

- **Python operators on value handles,** for example
  `builder.equation(v.value == v.noi / v.cap_rate)`.
- **A string parser,** for example `builder.equation("value = noi / cap_rate")`.
  It resolves names against value keys.

The walkthrough teaches the string form. It shows the operator form once, in an
Under the hood aside ([ADR-020](020-walkthrough-plan-v2.md)).

### Identities and deterministic builds

Every record gets a new UUID by default. The builder fills in Metadata and the
format version.

A builder with a `namespace` derives UUIDs from the namespace and the code path
of each object (UUID version 5). **This is a tested contract:** the same inputs
and namespace give the same Model ID and the same record IDs. A golden test in
`tests/contracts` checks the contract. Pipelines that need reproducible IDs use
this mode.

### Quantities

`Quantity(magnitude, units)` stays the canonical form. `Quantity.parse("1e6 AUD/year")`
and a short `q(1e6, "AUD/year")` helper make notebook code shorter. APIs keep
typed Quantity parameters.

### Scope

This record fixes the direction. The walkthrough ideal-cells pass
([ADR-019](019-walkthrough-direction.md)) settles the exact builder methods.

## Alternatives and consequences

- **Records only, with less ceremony.** Defaults would make records smaller,
  but edits still rebuild nested records.
- **Declarative files first.** This option was deferred. Builders cover the
  Python route, and the codecs already read files.
- **Operators only, or strings only.** Operators give type checks and IDE
  support. Strings are easier for notebooks and files. Both routes produce the
  same records.

A builder is a second API surface. Generated `add_*` methods and a documented
mapping from builder calls to records reduce its maintenance cost.

## Sources and related decisions

- [ADR-011: records and validation](011-records-and-validation.md).
- [ADR-012: naming](012-naming-and-glossary.md).
- [ADR-019: walkthrough direction](019-walkthrough-direction.md).
- [ADR-020: walkthrough plan v2](020-walkthrough-plan-v2.md), which sets the
  equation style that the book teaches.

Supersedes: none. Superseded by: none.
