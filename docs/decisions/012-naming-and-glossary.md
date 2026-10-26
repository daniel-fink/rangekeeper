# ADR-012: Naming convention, glossary and the rename pass

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-26.

## Problem

About fifteen words have more than one meaning in the current code. Examples:

- two public `Aggregation` classes;
- three meanings each for "projection", "selection", "measure" and "align";
- five functions named `sum`, with four return types;
- four meanings of "target".

`units` is sometimes a `UnitSystem` and sometimes a unit string. Time ranges
use `start`/`end`, `start_inclusive`/`end_exclusive` or a span. Boolean
flags have opposite polarity. Several module names shadow Python builtins.

## Choice

### Convention

- **Lookups:** `model.<kind>(id_or_code)` returns one object and raises when it
  is missing. `find_*` searches and can return an empty result. `select_*`
  makes selectors.
- **Transforms** return the same type as their input, for example `trim`,
  `resample`, `convert` and `scale`.
- **Results:** rollups and aggregations return a `*Result` object with a typed
  `.value` and `.coverage`.
- **Identifiers:** `id` is an object's own UUID. `<x>_id` and `<x>_ids` are
  references. Do not use `identity`, `uid` or `token` for these.
- **Units:** `units` is always a unit string. `unit_system` is always a
  `UnitSystem`.
- **Time:** use a span, or a half-open `start` and `end` (the end is excluded).
- **Options:** every API uses `method=` for its option enum.
- **Booleans** are positive `include_*` flags with a default of false.
- **Text identifiers:**
  - `key` is local to an owner;
  - `code` is a catalogue code;
  - `name` is human-readable text;
  - `label` means only Classification labels.
- **Builtins:** no public module-level names shadow builtins such as `sum`,
  `compile` or `id`.
- **One word for each concept.** The [glossary](../concepts/glossary.md) owns
  the words and their meanings.

### Agreed renames

| Current | 1.0 |
| --- | --- |
| `Specification.lock` and `unlock` | `fix` and `free` |
| Period and Span `start_inclusive` and `end_exclusive` | `start` and `end` (half-open) |
| `calculations` | `finance` ([ADR-010](010-layers-and-packages.md)) |
| `ScenarioPlan`, `sample`, `capture`, `realize`, `generate` and `Market` | Path generators and MarketPaths ([ADR-014](014-market-paths.md)) |

### Initial rename map

The rename pass finalises these names. The table records the agreed direction.

| Current | Proposed 1.0 name |
| --- | --- |
| `calculations.series.Aggregation` | `FlowAggregate` |
| `model.system.reduction.Aggregation` | `RollupResult` |
| `Reduction` (scalar and Flow modes) | `QuantityRollup` and `FlowRollup` with one `Reducer` enum |
| `calculations.projection` (growth and distribution) | `profile`, with `Flow.from_profile` (amended by #201, decision D12) |
| `model.system.projection` (table export) | `model.system.table` |
| `duration.measure` (counts calendar steps) | `count_steps` |
| `duration.align` (finds the containing Period) | `containing_period` |
| Stream `labels` (line names) | `names` |
| `findings`, `issues` and `diagnostics` | `diagnostics` |
| Persisted `MissingHandling` and runtime `MissingValueHandling` | One persisted enum and one runtime enum with a distinct name |
| Shim modules `model.measure`, `model.distribution` and `model.characteristics` | Removed; re-exports move to the package `__init__` |

### The rename pass

All renames and module moves happen in one scripted codemod pass at milestone
1.0.0a2. The pass happens inside the 1.0.0 format reset
([ADR-017](017-api-and-formats.md)). It does these things:

- moves modules to the layers in [ADR-010](010-layers-and-packages.md);
- applies the glossary names;
- moves the tests to mirror the packages ([ADR-018](018-release-and-engineering.md));
- regenerates the computation fingerprints ([ADR-013](013-execution-and-extensions.md)).

New 1.0 work after the pass uses the new names.

Release 1.0.0a2 publishes two things:
- a **rename map** of old and new public names, in the upgrade guide;
- a **consumer codemod script** that applies the map to downstream code.

## Alternatives and consequences

- **Rename each part as its epic touches it.** This gives smaller pull requests,
  but it causes many identity changes and a long period of mixed names.
- **Rename after the API freeze.** New code would then use old names first.

One rename event causes one fingerprint change and one migration step for
consumers.

## Sources and related decisions

- [Glossary](../concepts/glossary.md).
- [ADR-010](010-layers-and-packages.md), [ADR-014](014-market-paths.md) and
  [ADR-017](017-api-and-formats.md).

Supersedes: none. Superseded by: none.
