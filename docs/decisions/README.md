# Decisions and implementation records

Use the [current guides](../README.md) for instructions. These records explain why
contracts and ownership boundaries exist. An implemented decision can remain
current after its execution plan moves to history.

| Decision | Status | Scope |
| --- | --- | --- |
| [ADR-001: document roots](001-document-roots.md) | Implemented | Model, Specification and finalized Run responsibilities |
| [ADR-002: records and identity](002-records-and-identity.md) | Implemented | Schema authority, immutable content and exact revision references |
| [ADR-003: computation and evidence](003-computation-and-evidence.md) | Implemented | Known-data calculations, passive formulations, source evidence and independent acceptance |
| [ADR-004: package and project ownership](004-package-and-project-ownership.md) | Implemented | Domain packages, `src/grasshopper`, examples, tools, docs and local verification |

The first three records summarize decisions already supported by the linked
implementation history. They do not invent an earlier approval date. ADR-004 also
records the source-project placement selected during this documentation pass.
Relationships are explicit links; a decision can affect several owners.

## Implementation history

- [RF-001–RF-023](../history/plans/REFACTORING_PLAN.md): coordinated domain refactor,
  implemented at `5a111b0` with its recorded local acceptance and scope limits.
- [RF-024–RF-034](../history/plans/REFACTORING_FOLLOWUP_PLAN.md): ownership and
  consolidation, implemented at `08aac85` with its recorded local acceptance.
- [Documentation and repository organization](../history/plans/DOCUMENTATION_PLAN.md):
  current pass, including the accepted Grasshopper location and verification record.

## Work that remains explicit

- [Windows/Rhino/connector acceptance](../contributing/windows-acceptance.md) remains
  open. Follow [legacy retirement](../contributing/legacy-retirement.md) before
  deleting any held predecessor code or tests.
- [Verification](../contributing/verification.md) is run explicitly by developers
  and agents. The GitHub workflows are removed; platform and service acceptance
  still require their own recorded results.
- Building a walkthrough does not publish it. Follow the
  [walkthrough procedure](../guides/walkthroughs.md) for the local build boundary.

Apply the [documentation lifecycle](../contributing/documentation.md) when a plan
is implemented or superseded. Transfer unfinished work, retain identifiers and
rationale, and update both navigation and successor links in the same change.
