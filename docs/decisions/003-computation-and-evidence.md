# ADR-003: Separate calculations, declarations and acceptance

Status: implemented. Recorded: 2026-10-08 from the accepted source records below.

## Problem and choice

A calculation over known data, a declared equation and proof that a solver result
is acceptable are different operations. Keep known-data arithmetic in
`calculations`, passive equation authoring in `model.formulation`, and numerical
execution and independent acceptance in `run.execution`.

Source workflows interpret observations and retain Claims, source locations and
review decisions. Their transient Evidence objects convert explicitly to Model
provenance. They do not establish numerical feasibility. Policies enforce causal
availability and produce outcomes; saved Run validation checks that evidence
against pinned documents without rerunning the solver.

## Alternatives and consequences

One universal validation or evidence mechanism would conceal different failure
rules. Reusing solver success as acceptance would lose an independent check of
the declared equations. Use shared arithmetic and preparation only where contracts
match, while keeping the independent acceptance and publication decisions.

Execution, scenario and workflow implementations retain distinct fingerprint
contracts. A shared digest primitive does not make their identities interchangeable.
Optional adapters and solvers load at their capability boundaries. Local checks do
not establish acceptance of external hosts or services.

## Sources and related decisions

- [Execution](../reference/execution.md), [calculations](../reference/calculations.md),
  [source workflows](../concepts/source-workflows.md) and [Evidence](../reference/evidence.md).
- [RF integration contracts](../history/plans/REFACTORING_PLAN.md#agreed-integration-decisions).
- [RF-032 acceptance ownership](../history/plans/REFACTORING_FOLLOWUP_PLAN.md#rf-032-execution-acceptance-ownership).
- [ADR-001: document roots](001-document-roots.md).

Supersedes: no earlier ADR identifier was assigned. Superseded by: none.
