# ADR-005: Flux and Stream implementation

Status: implemented. Recorded: 2026-10-08.

## Problem

The legacy Stream let a caller collect flows, choose a common frequency, inspect
the line items and calculate a combined Flow. The replacement API required callers
to write their own resampling loops, alignment, aggregation and dataframe joins.
Simple notebooks were harder to read, and larger models repeated work.

Equation builders named one participant `result`. That name suggested a fixed
solve direction, but a Specification can fix any participant and solve another.

## Choice

Restore Stream as the main interface to coordinate, display, resample and combine
flows. The public module is `rangekeeper.model.flux`; it exports Flow, Movement and
Stream.

- Flow and Movement records stay the one authoritative representation of Model
  content. Stream can hold a private Polars state that it derives from its inputs.
  That state is not an editable copy of Model content. Each operation returns a
  new Stream or result and does not change its inputs.
- Polars does the bulk alignment, resampling, aggregation and coverage
  calculations. Span and Period own named extents and the calendar operations.
- Reductions aggregate scalar and Flow Values through an explicit hierarchy.
- Equation builders use explicit keyword parameters for each mathematical role,
  for example `flow.sum(summands=..., total=...)`. A name identifies a quantity in
  a relationship. It does not make that quantity fixed or unknown.
- Collection operations have two explicit routes. The calculation route reads
  known amounts and returns results. The formulation route relates Movement
  references in passive equations and reads no amounts. The library does not
  switch from one route to the other because an amount is unresolved.

## Alternatives and consequences

An earlier proposal kept Stream as a thin collection around the existing
calculation functions. It did not remove the repeated alignment and join code, so
it was not chosen. Replacing Flow storage with a dataframe is a separate redesign.
Consider it only if measurements show that record construction or storage is the
dominant cost.

The renamed builder parameters and the `model.flux` module are breaking changes
for earlier callers. The [expressions reference](../reference/expressions.md#passive-flow-and-hierarchy-builders)
lists the current parameter names.
The same equations now solve forward and backward. The
[codebase acceptance record](../research/flux-stream-2026-10-08/README.md) contains
the tests, timings, memory costs and external limits.

## Sources and related decisions

- [Implementation plan](../history/plans/005-flux-and-stream-implementation.md):
  design detail, naming inventory, implementation sequence and acceptance criteria.
- [Calculations](../reference/calculations.md), [expressions](../reference/expressions.md),
  [system reductions](../reference/system.md) and [tables](../reference/tables.md).
- [ADR-003: computation and evidence](003-computation-and-evidence.md) and
  [ADR-004: package ownership](004-package-and-project-ownership.md).
- [First notebook acceptance](../research/basic-dcf-2026-10-08/README.md).

Supersedes: none. Superseded by: none.
