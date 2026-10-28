# ADR-011: Records, behaviour and validation

Status: accepted for 1.0; implemented in 1.0.0a2 (#106–#116, #111). Recorded: 2026-10-26.

## Problem

- **Behaviour attaches from below.** Generated record classes get mixins from
  `schema/behaviors`. A behaviour that needs Flow or Stream must import from a
  higher layer.
- **Every change is a full rebuild.** Each construction and each `replace`
  copies the subtree, runs jsonschema over all of it, normalises it again and
  freezes it.
  - A `replace` on a Flow with 120 movements takes about 2 ms.
  - jsonschema takes most of the time to build a Model.
  - One execution validates the same content between three and eight times.
- **The runtime reads metadata on every access.** It reads slot metadata from
  `slots.json` each time it reads or encodes a field.
- **Validity is uneven.** A Flow can be unordered or contain duplicate IDs
  until a caller runs `.check()`.
- **Some field lists are hand-written,** which breaks LinkML's role as the only
  field authority. Examples are the Polars columns, the facade sections, a
  special case in Bundle and an accepted version literal.

## Choice

### Behaviour and classes

- Generated records in `schema` contain data only.
- An owner adds behaviour by subclassing its record, for example
  `class Flow(records.Flow)` in `flow`. The owner registers the class in a
  kind registry. `from_data`, the codecs and traversal use the registry, so
  decoding returns the rich class.
- **Documents** are validated, indexed facades. The documents are Model,
  Specification, Run and MarketPaths ([ADR-014](014-market-paths.md)).
- **Value types** are immutable records with behaviour. The value types are
  Quantity, Period, Span, Movement, Flow and Stream.
- **All other records are plain data.** A caller reads them through their
  document.

### Record runtime

The record semantics stay the same:
- missing, null and empty are different;
- numbers stay exact;
- children are frozen;
- wire order is kept.

The mechanism changes:

- The generator emits per-class slots, per-field encode and decode functions
  and typed constructors. The runtime does not interpret `slots.json` while it runs.
- Decoded children are cached.
- `replace` checks only the fields that change. An `OMIT` value removes an
  optional field.
- `repr` gives a short summary, not the full tree.
- The generator is split into small functions. It checks for slot names that
  collide with keywords or methods. It checks that each slot has one record type.
- Each hand-written field list is derived from the schema or from LinkML
  annotations.

### When validation runs

| Tier | When | What |
| --- | --- | --- |
| Local invariants | Construction of a value type | A Flow is ordered, has unique Movement IDs and has one unit. A Period starts before it ends. |
| Structural | Untrusted input only: `from_data`, `loads`, `read` and store reads | jsonschema conformance |
| Semantic | Commit points: `create`, `revise`, builder `commit()`, `put` of untrusted data, and before execution | Document rules, references, units and dimensions ([ADR-016](016-safety-defaults.md)) |
| Verification | After a solve | Independent verification of the candidate ([ADR-013](013-execution-and-extensions.md)) |

Validated objects pass forward as trusted types. Stores and codecs accept a
validated document of the exact facade type without validating it again. Data
input is always validated.

### Validation API

Each document has two methods:

- `validate(*, resolver=None) -> ValidationReport`. It does not raise for
  content problems.
- `check(*, resolver=None) -> Self`. It raises a `RangekeeperError` subclass
  that carries the report.

Internal helpers use one verb family.

## Alternatives and consequences

- **Keep mixins and forbid upward imports.** This is a smaller change, but Flow
  stays split between `schema` and `flow`.
- **Keep objects valid at every construction.** This is the simplest mental
  model, but it has the highest cost.
- **Use msgspec or pydantic.** These options cannot express every presence and
  union rule without extra code. The generated runtime keeps the exact semantics.

This record changes how ADR-002 is implemented, not its contract. The
[record reference](../reference/records.md) changes when the implementation lands.

## Sources and related decisions

- [ADR-002: records and identity](002-records-and-identity.md), amended by this record.
- [ADR-010: layers and packages](010-layers-and-packages.md).
- [Schema development](../contributing/schema.md).

Supersedes: none. Amends: ADR-002. Superseded by: none.
