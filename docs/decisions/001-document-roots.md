# ADR-001: Separate Model, Specification and Run

Status: implemented. Recorded: 2026-10-08 from the accepted design and implementation
records below. This date records the summary; it does not replace their chronology.

## Problem and choice

One project must support several investigations without changing its declared
equations. A saved result must retain the exact inputs and requirements that gave
it meaning. Use three document roots: Model for project declarations,
Specification for an investigation, and Run for finalized execution evidence.

A recorded quantity does not permanently fix a solve target. A Specification
selects assignments and unknowns over an exact Model revision. A Run pins that
Specification and records accepted output revisions. Each root has a distinct
validation and publication contract.

## Alternatives and consequences

Combining requirements or solver state with Model declarations would couple the
project's equations to one investigation. Treating a Run as a mutable Model would
lose the finalized attempt boundary. The separate roots retain explicit revision
references and let the same equations support forward and inverse questions.
They require explicit composition, resolution and acceptance steps.

This decision does not promise that every expression represented by the schema
can be solved by the current executor. Source workflow configuration also remains
separate from a mathematical Specification.

## Sources and related decisions

- [Framework concepts](../concepts/model-specification-run.md).
- [Domain migration record](../history/DOMAIN_MIGRATION_PLAN.md).
- [RF-001–RF-023 implementation](../history/plans/REFACTORING_PLAN.md#combined-implementation-record).
- [ADR-002: records and identity](002-records-and-identity.md).
- [ADR-003: computation and evidence](003-computation-and-evidence.md).

Supersedes: no earlier ADR identifier was assigned. Superseded by: none.
