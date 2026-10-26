# ADR-014: Market paths and path generators

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-26.

## Problem

Today a `ScenarioPlan` is a recipe for random market histories: a method name,
a seed, periods and parameters. Using it takes several steps:

1. `sample` draws inputs and writes them into a new revision of the project Model.
2. `realize` calculates market Flows and writes them into another revision.
3. `generate` repeats this for each scenario key.
4. The result is one project Model revision for each future.
5. A `Market` view reads the result through fixed, domain-specific property names.

This causes five problems:
- The name "plan" conflicts with the walkthrough's "base plan".
- Random generation is not a fact about the project.
- Many futures make many copies of the project Model.
- Nothing records that two strategies used the same futures.
- The design does not use the batch cases and assignments that Specifications
  already have.

## Choice

Market futures are inputs to an investigation.

### Terms

| Term | Meaning | Class |
| --- | --- | --- |
| Path | One possible history of external conditions: named Flows, and the date each value becomes known | `MarketPath` |
| Market paths | A captured, replayable set of paths | `MarketPaths` |
| Path generator | A registered method that makes market paths | `PathGenerator` (protocol); `MarketDynamics` (built-in) |

The class names avoid a clash with `pathlib.Path` and `typing.Generator`.

### Generators

`PathGenerator` lives in `finance` ([ADR-010](010-layers-and-packages.md)). It
has three members:
- declared parameters: constants or distributions;
- `generate(periods, *, seed, count) -> MarketPaths`;
- a fingerprint.

Generators use the registry pattern in [ADR-013](013-execution-and-extensions.md).
There are two built-ins:
- `MarketDynamics`, with trend, volatility, cycle, noise and shock components;
- an independent-paths generator.

Output names, such as space-market price factors, belong to the generator and
not to the core library.

### The MarketPaths document

`MarketPaths` is a new stored, immutable document kind. It has metadata and
validation. It contains:

- its members: a key, named Flows and availability dates;
- a capture record: the generator name and fingerprint, the parameters, the
  seed, the random stream identities and the library versions.

Replay uses the captured values and draws no random numbers. Stores and Bundles
handle the document. Specifications and Runs pin it by UUID. This amends
ADR-001: there are three investigation roots and one kind of captured input
document.

### Investigation across paths

- **The project Model declares each external driver once,** for example a rent
  index Flow with its shape and units. Its equations use the driver. The Model
  does not store generated paths.
- **`Specification.across(paths, assign={...})`** makes a batch Specification
  with one case for each path. Each case fixes the driver Flows from its path.
  Each case carries the availability dates that policies use.
- **To compare strategies,** run each strategy's Specification across the same
  pinned `MarketPaths`. The Runs show that the strategies used the same futures.
- **For known-data analysis of one path,** use `flow` and `finance` operations
  on the Flows of a `MarketPath`.

### Removal

- **Removed:** `ScenarioPlan`, `ScenarioRealization`, `sample`, `capture`,
  `realize`, `generate`, `Market` and the `model.scenario` package.
- **Kept:** Distribution records, which generator parameters use.
- **Dropped at the 1.0.0 format reset:** existing captured realisations.
  Regenerate them from their recorded seed and parameters.

## Alternatives and consequences

- **Keep captures in Model provenance, with simpler names.** This option keeps
  one Model revision for each future, so it was rejected.
- **Store paths as a file referenced by digest.** This keeps three roots, but
  stores and Bundles would need support for files outside the document model.
- **Embed paths in each Specification.** This makes Specifications large, and
  strategies that share futures would duplicate the data.

The sequential-decision design for walkthrough lessons 05 and 06 must confirm
two details:
- how availability dates attach to case assignments;
- how a case refers to a path member.

The [scenario reference](../reference/scenarios-and-policies.md) changes when
the implementation lands.

## Sources and related decisions

- [ADR-001: document roots](001-document-roots.md), amended by this record.
- [ADR-013: execution and extension points](013-execution-and-extensions.md).
- [ADR-019: walkthrough direction](019-walkthrough-direction.md).

Supersedes: none. Amends: ADR-001. Superseded by: none.
