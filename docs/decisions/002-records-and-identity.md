# ADR-002: Generate immutable records and pin exact revisions

Status: implemented. Recorded: 2026-10-08 from the accepted source records below.

## Problem and choice

Python, C# and stored documents need one field contract. Handwritten copies can
lose field presence, alter ordering or disagree about references. Use LinkML as
the authority for persistent fields, enums and structural constraints. Generate
language records and schema resources; keep semantic behavior in its domain owner.

Use immutable records and exact revision UUID references. Stores are append-only.
A domain declaration's identity can survive a content change while its enclosing
Model receives a new revision identity. Missing, null, empty, zero and false remain
distinct where allowed by the schema. Mathematical sequences retain their order.

## Alternatives and consequences

Handwritten field models would duplicate the schema. Mutable revisions or implicit
latest-version resolution would change the meaning of saved evidence. Instead,
callers revise complete documents explicitly and pass a resolver where external
references must be checked. Generated source changes go through the generators.

Exact content preservation and schema-equivalent comparison serve different
operations. Neither Python dictionary equality nor unordered comparison is a
universal substitute. C# local authoring checks do not reproduce all Python
semantic validation.

## Sources and related decisions

- [Record contract](../reference/records.md) and [identity contract](../reference/identity.md).
- [Schema tooling evaluation](../history/SCHEMA_TOOLING_EVALUATION.md).
- [RF-020 comparison rules](../history/plans/REFACTORING_PLAN.md#rf-020-integrate-record-equivalence-and-simplify-revision-comparison).
- [RF-025 record construction](../history/plans/REFACTORING_FOLLOWUP_PLAN.md#rf-025-record-construction).
- [ADR-001: document roots](001-document-roots.md).

Supersedes: no earlier ADR identifier was assigned. Superseded by: none.
